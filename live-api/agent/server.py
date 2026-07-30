# /// script
# dependencies = [
#   "fastapi",
#   "uvicorn",
#   "websockets",
#   "websocket-client",
#   "httpx",
#   "numpy",
#   "pillow",
#   "protobuf",
#   "grpcio",
#   "google-ai-generativelanguage",
# ]
# ///

r"""Proactive Agent — FastAPI server.

This is the main entry point for the agent. It provides:
  - WebSocket /ws endpoint for bidirectional Gemini Live API sessions
  - Static UI serving
  - Minimal REST API for camera proxy and inter-agent messaging

No external frameworks, SSOT, or internal RPC infrastructure.
"""

import argparse
import asyncio
import base64
import dataclasses
import json
import logging
import os
import re
import signal
import tempfile
import time
import zipfile

import fastapi
from fastapi import responses as fastapi_responses
from fastapi import staticfiles as fastapi_staticfiles
from fastapi.middleware import cors as cors_middleware
import uvicorn

import session_config
import session_manager
from agent import agent as agent_lib
from embodiment import human as human_embodiment_lib
from embodiment.spot import robot_client as spot_robot_client_lib
from embodiment.spot import spot_embodiment as spot_embodiment_lib
from embodiment.tinybot import tinybot_embodiment as tinybot_embodiment_lib
from model import tts_client as tts_client_lib
from tool import tools as tools_lib


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Server configuration
# ---------------------------------------------------------------------------
@dataclasses.dataclass
class ServerConfig:
  """Server-level configuration from CLI flags."""

  model: str = "models/gemini-robotics-er-2-streaming-preview"
  robot_url: str = "http://localhost:8888"
  api_key: str | None = None
  tts_api_key: str | None = None
  use_tts: bool = True
  tts_voice: str = "en-US-Chirp3-HD-Puck"
  tts_language_code: str = "en-US"
  tts_audio_gain: float = 1.0
  response_modality: str = "AUDIO"
  dump_video_dir: str = ""
  heartbeat_interval_seconds: float = 2.0
  heartbeat_min_delay_seconds: float = 2.0
  heartbeat_enabled: bool = True
  use_event_driven_heartbeat: bool = True
  media_resolution: str = "low"
  enable_send_message_to_user: bool = True
  mock_robot: bool = False
  agent_peers: dict[str, str] = dataclasses.field(default_factory=dict)
  custom_si: dict[str, str] = dataclasses.field(default_factory=dict)
  custom_di: dict[str, str] = dataclasses.field(default_factory=dict)
  custom_heartbeat_text: dict[str, str] = dataclasses.field(
      default_factory=dict
  )
  port: int = 8000


# ---------------------------------------------------------------------------
# UI directory resolution (handles .par packaging)
# ---------------------------------------------------------------------------
def _resolve_ui_dir():
  """Find the ui/ directory."""
  this_dir = os.path.dirname(os.path.abspath(__file__))
  candidate = os.path.join(this_dir, "ui")
  if os.path.isdir(candidate):
    logger.info("Found UI directory: %s", candidate)
    return candidate
  return None

# ---------------------------------------------------------------------------
# Thinking level resolution
# ---------------------------------------------------------------------------
def resolve_thinking_level(
    model_name: str,
    session_override: str | None = None,
) -> str:
  """Resolve thinking level: session override > model default > global default."""
  if session_override is not None:
    return session_override
  normalized = model_name.removeprefix("models/")
  spec = session_config.KNOWN_MODELS.get(
      normalized, session_config.DEFAULT_MODEL_SPEC
  )
  return spec.thinking_level


# ---------------------------------------------------------------------------
# Type conversion utility for query parameter parsing
# ---------------------------------------------------------------------------
def _convert_type(value: str, type_hint) -> object:
  """Convert a string value to the expected type hint."""
  if type_hint is bool or type_hint == "bool":
    return value.lower() in ("true", "1", "yes")
  if type_hint is int or type_hint == "int":
    return int(value)
  if type_hint is float or type_hint == "float":
    return float(value)
  return value


# ---------------------------------------------------------------------------
# FastAPI app setup
# ---------------------------------------------------------------------------
router = fastapi.APIRouter()


@router.get("/")
async def root(request: fastapi.Request):
  ui_dir = request.app.state.ui_dir
  if not ui_dir:
    return fastapi_responses.PlainTextResponse("UI not found")
  return fastapi_responses.FileResponse(os.path.join(ui_dir, "index.html"))


@router.get("/api/camera")
async def api_camera(request: fastapi.Request):
  """Return the latest camera frame as MJPEG stream (robot camera proxy)."""
  poller = request.app.state.active_poller_ref
  if not poller:
    return fastapi.Response(status_code=204)

  async def _mjpeg_gen():
    async for frame in poller.get_stream():
      yield (
          b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
      )

  return fastapi.responses.StreamingResponse(
      _mjpeg_gen(),
      media_type="multipart/x-mixed-replace; boundary=frame",
      headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
  )


@router.post("/api/send")
async def api_send(request: fastapi.Request):
  """Inject text into the active session (inter-agent messaging)."""
  body = await request.json()
  text = body.get("text", "")
  active_session = request.app.state.active_session
  if not active_session or not text:
    return fastapi.responses.JSONResponse(
        status_code=400, content={"error": "No active session or empty text"}
    )
  await active_session.get_text_queue().put(text)
  return {"status": "ok"}


@router.get("/api/server_defaults")
async def api_server_defaults(request: fastapi.Request):
  """Return available models and server defaults for the UI."""
  config = request.app.state.config
  return {
      "models": list(session_config.KNOWN_MODELS.keys()),
      "default_model": config.model,
      "default_modality": config.response_modality,
      "use_tts": config.use_tts,
  }


def _validate_agent_name(name: object) -> str:
  if not isinstance(name, str) or not name.strip():
    raise fastapi.HTTPException(status_code=400, detail="agent_name is required")
  name = name.strip()
  try:
    agent_lib.Agent.from_name(name)
  except ValueError as exc:
    raise fastapi.HTTPException(status_code=400, detail=str(exc)) from exc
  return name


def _set_optional_override(
    overrides: dict[str, str],
    agent_name: str,
    value: object,
) -> None:
  if value is None or value == "":
    overrides.pop(agent_name, None)
    return
  if not isinstance(value, str):
    raise fastapi.HTTPException(status_code=400, detail="Instruction values must be strings")
  overrides[agent_name] = value


@router.post("/api/config/instructions")
async def update_instructions(request: fastapi.Request):
  """Update runtime instructions used when the next agent session starts."""
  body = await request.json()
  agent_name = _validate_agent_name(body.get("agent_name"))
  config = request.app.state.config

  _set_optional_override(
      config.custom_si, agent_name, body.get("system_instruction")
  )
  _set_optional_override(
      config.custom_di, agent_name, body.get("developer_instruction")
  )
  _set_optional_override(
      config.custom_heartbeat_text, agent_name, body.get("heartbeat_text")
  )

  for field in ("heartbeat_interval_seconds", "heartbeat_min_delay_seconds"):
    value = body.get(field)
    if value is None:
      continue
    try:
      value = float(value)
    except (TypeError, ValueError) as exc:
      raise fastapi.HTTPException(
          status_code=400, detail=f"{field} must be a number"
      ) from exc
    if value <= 0:
      raise fastapi.HTTPException(
          status_code=400, detail=f"{field} must be greater than zero"
      )
    setattr(config, field, value)

  if "use_event_driven_heartbeat" in body:
    value = body["use_event_driven_heartbeat"]
    if not isinstance(value, bool):
      raise fastapi.HTTPException(
          status_code=400,
          detail="use_event_driven_heartbeat must be a boolean",
      )
    config.use_event_driven_heartbeat = value

  return {
      "success": True,
      "agent_name": agent_name,
      "requires_reconnect": request.app.state.active_session is not None,
  }


@router.delete("/api/config/instructions")
async def reset_instructions(request: fastapi.Request, agent_name: str):
  """Reset one agent's overrides and heartbeat settings to startup values."""
  agent_name = _validate_agent_name(agent_name)
  config = request.app.state.config
  config.custom_si.pop(agent_name, None)
  config.custom_di.pop(agent_name, None)
  config.custom_heartbeat_text.pop(agent_name, None)

  defaults = request.app.state.instruction_defaults
  config.heartbeat_interval_seconds = defaults["heartbeat_interval_seconds"]
  config.heartbeat_min_delay_seconds = defaults["heartbeat_min_delay_seconds"]
  config.use_event_driven_heartbeat = defaults["use_event_driven_heartbeat"]
  return {
      "success": True,
      "agent_name": agent_name,
      "requires_reconnect": request.app.state.active_session is not None,
  }


@router.get("/api/agent_config/{name}")
async def api_agent_config(
    request: fastapi.Request,
    name: str,
    endpoint_type: str = "gemini_live_api",
    model: str | None = None,
):
  """Return the resolved agent configuration."""
  config = request.app.state.config
  try:
    agent = agent_lib.Agent.from_name(name)
    agent_si = config.custom_si.get(name, "")
    agent_di = config.custom_di.get(name, "")
    agent_hb = (
        config.custom_heartbeat_text.get(name, "")
        or session_manager.get_default_heartbeat_text()
    )
    if agent_si:
      agent.system_instruction = agent_si
    if agent_di:
      agent.developer_instruction = agent_di
  except ValueError:
    raise fastapi.HTTPException(
        status_code=400, detail=f"Unknown agent name: {name}"
    )

  resolved_tools = agent.tools


  decls = []
  for t in resolved_tools:
    if "functionDeclarations" in t:
      decls.extend(t["functionDeclarations"])
    else:
      decls.append(t)

  service_address = "generativelanguage.googleapis.com"

  return {
      "name": agent.name,
      "system_instruction": agent.system_instruction,
      "developer_instruction": agent.developer_instruction,
      "is_modified": bool(
          agent_si or agent_di or config.custom_heartbeat_text.get(name, "")
      ),
      "tools": decls,
      "model": config.model,
      "response_modality": config.response_modality,
      "use_tts": config.use_tts,
      "tts_voice": config.tts_voice,
      "tts_language_code": config.tts_language_code,
      "endpoint_type": endpoint_type,
      "service_address": service_address,
      "heartbeat_text": agent_hb,
      "heartbeat_interval_seconds": config.heartbeat_interval_seconds,
      "heartbeat_min_delay_seconds": config.heartbeat_min_delay_seconds,
      "use_event_driven_heartbeat": config.use_event_driven_heartbeat,
      "thinking_level": resolve_thinking_level(model or config.model),
  }


# ---------------------------------------------------------------------------
# WebSocket endpoint — the heart of the system
# ---------------------------------------------------------------------------
@router.websocket("/ws")
async def websocket_endpoint(
    websocket: fastapi.WebSocket,
    agent_name: str = "human",
    custom_si: str = "",
    enabled_tools: str = "",
    response_modality: str | None = None,
    model: str | None = None,
    use_tts: bool | None = None,
    thinking_level: str | None = None,
    endpoint_type: str = "gemini_live_api",
):
  """WebSocket: Proactive Agent session with Gemini Live API."""
  app = websocket.app
  config = app.state.config

  await websocket.accept()
  logger.info("WebSocket connected")

  async def ui_callback(event):
    await websocket.send_json(event)

  async with app.state.session_lock:
    if app.state.active_session is not None:
      await websocket.close(
          code=1008, reason="Only one active session allowed"
      )
      return

    if agent_name == "spot":
      current_embodiment = spot_embodiment_lib.SpotEmbodiment(
          robot_url=config.robot_url
      )
      await current_embodiment.initialize()
      app.state.active_poller_ref = current_embodiment.poller
    elif agent_name == "tinybot":
      current_embodiment = tinybot_embodiment_lib.TinybotEmbodiment(
          robot_url=config.robot_url
      )
      app.state.active_poller_ref = current_embodiment.poller
    else:
      # Default to human (local webcam/mic) embodiment
      current_embodiment = human_embodiment_lib.HumanEmbodiment()

    # Build SessionConfig from query params
    session_cfg = session_config.SessionConfig(
        agent_name=agent_name,
        custom_si=custom_si,
        enabled_tools=enabled_tools.split(",") if enabled_tools else [],
        response_modality=response_modality,
        model=model or config.model,
        use_tts=use_tts,
        thinking_level=thinking_level,
        endpoint_type=endpoint_type,
    )
    logger.info("[SERVER] Resolved session config: %s", session_cfg)

    # Resolve agent
    custom_si_override = session_cfg.custom_si or config.custom_si.get(
        session_cfg.agent_name, ""
    )
    custom_di_override = session_cfg.custom_di or config.custom_di.get(
        session_cfg.agent_name, ""
    )
    heartbeat_text_override = (
        session_cfg.heartbeat_text
        or config.custom_heartbeat_text.get(session_cfg.agent_name, "")
    )
    resolved_model = session_cfg.model or config.model
    assert resolved_model is not None

    resolved_thinking_level = resolve_thinking_level(
        resolved_model, session_cfg.thinking_level
    )
    agent = agent_lib.Agent.from_name(
        session_cfg.agent_name,
    )
    if custom_si_override:
      agent.system_instruction = custom_si_override
    if custom_di_override:
      agent.developer_instruction = custom_di_override

    # Determine tools (agent tools, optionally filtered)
    agent_tools = (
        current_embodiment.get_tools()
        if agent_name in ("spot", "tinybot")
        else agent.tools
    )
    if session_cfg.enabled_tools:
      enabled = set(session_cfg.enabled_tools)
      agent_tools = [
          {
              **group,
              "functionDeclarations": [
                  declaration
                  for declaration in group.get("functionDeclarations", [])
                  if declaration.get("name") in enabled
              ],
          }
          for group in agent_tools
          if group.get("functionDeclarations")
      ]
      agent_tools = [
          group for group in agent_tools if group["functionDeclarations"]
      ]

    modality = session_cfg.response_modality or config.response_modality
    resolved_use_tts = (
        session_cfg.use_tts
        if session_cfg.use_tts is not None
        else config.use_tts
    )

    logger.info(
        "Session: agent=%s, model=%s, modality=%s, tts=%s, thinking_level=%s",
        session_cfg.agent_name,
        resolved_model,
        modality,
        resolved_use_tts,
        resolved_thinking_level,
    )

    app.state.active_session = session_manager.SessionManager(
        model=resolved_model,
        embodiment_instance=current_embodiment,
        tools=agent_tools,
        system_instruction=agent.system_instruction,
        developer_instruction=agent.developer_instruction,
        response_modality=modality,
        dump_video_dir=config.dump_video_dir or None,
        api_key=config.api_key,
        heartbeat_interval_seconds=config.heartbeat_interval_seconds,
        heartbeat_enabled=config.heartbeat_enabled,
        heartbeat_min_delay_seconds=config.heartbeat_min_delay_seconds,
        agent_peers=config.agent_peers,
        peer_name=session_cfg.agent_name,
        use_event_driven_heartbeat=config.use_event_driven_heartbeat,
        media_resolution=config.media_resolution,
        heartbeat_text=heartbeat_text_override,
        enable_send_message_to_user=config.enable_send_message_to_user,
        endpoint_type=session_cfg.endpoint_type,
        thinking_level=resolved_thinking_level,
    )
    app.state.session_agent_name = session_cfg.agent_name

  try:

    async def audio_output(data):
      try:
        await websocket.send_bytes(data)
      except Exception:  # pylint: disable=broad-except
        logger.warning("Failed to send audio output to WebSocket")

    # TTS callback
    tts_client = None
    text_output_cb = None
    if resolved_use_tts:
      tts_client = tts_client_lib.Tts3pClient(
          voice_name=config.tts_voice,
          language_code=config.tts_language_code,
          api_key=config.tts_api_key,
          audio_gain=config.tts_audio_gain,
      )
      logger.info("TTS client initialized with voice: %s", config.tts_voice)

      async def text_output(text):
        filtered_text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
        if not filtered_text.strip():
          return

        start_sec = time.time()
        logger.info("Synthesizing TTS for: %.50s", filtered_text)
        total_bytes = 0
        first_chunk_sent = False
        t_start = 0.0
        try:
          async for chunk in tts_client.synthesize_stream(filtered_text):
            if not first_chunk_sent:
              t_start = time.time()
              first_chunk_sent = True
            if chunk:
              await audio_output(chunk)
              total_bytes += len(chunk)
        except Exception as e:
          logger.error("TTS streaming failed: %s", e)

        if total_bytes > 0 and t_start > 0.0:
          total_playback_secs = total_bytes / 48000.0
          elapsed_secs = time.time() - t_start
          remaining_secs = max(0.0, total_playback_secs - elapsed_secs)
          await asyncio.sleep(remaining_secs)

      text_output_cb = text_output

    async def receive_from_client():
      """Read audio/text/image from browser WebSocket."""
      try:
        while True:
          message = await websocket.receive()
          if message.get("type") == "websocket.disconnect":
            logger.info("WebSocket disconnect event received")
            break
          if message.get("bytes"):
            await current_embodiment.get_audio_queue().put(message["bytes"])
          elif message.get("text"):
            text = message["text"]
            try:
              payload = json.loads(text)
              if isinstance(payload, dict):
                if payload.get("type") == "image":
                  data = base64.b64decode(payload["data"])
                  await current_embodiment.get_video_queue().put(data)
                  continue
            except json.JSONDecodeError:
              pass
            await current_embodiment.get_text_queue().put(text)
      except fastapi.WebSocketDisconnect:
        logger.info("WebSocket disconnected")
      except asyncio.CancelledError:
        pass
      except Exception as e:  # pylint: disable=broad-except
        logger.error("Receive error: %s", e)

    async def run_session():
      try:
        assert app.state.active_session is not None
        async for event in app.state.active_session.start_session(
            audio_output_callback=audio_output,
            text_output_callback=text_output_cb,
        ):
          if event:
            success = True
            try:
              await websocket.send_json(event)
            except (fastapi.WebSocketDisconnect, RuntimeError):
              logger.info("WebSocket disconnected during send_json")
              success = False

            if not success:
              break
      except Exception as e:
        logger.error("Error in run_session: %s", e)

    receive_task = asyncio.create_task(receive_from_client())
    session_task = asyncio.create_task(run_session())

    done, pending = await asyncio.wait(
        [session_task, receive_task],
        return_when=asyncio.FIRST_COMPLETED,
    )
    for t in pending:
      t.cancel()
    if pending:
      await asyncio.gather(*pending, return_exceptions=True)

  except Exception as e:  # pylint: disable=broad-except
    import traceback
    traceback.print_exc()
    logger.error("Session error: %s", e, exc_info=True)
  finally:
    app.state.active_poller_ref = None
    try:
      await current_embodiment.close()
    except Exception as exc:  # pylint: disable=broad-except
      logger.warning("Failed to close embodiment: %s", exc)
    async with app.state.session_lock:
      app.state.active_session = None
    try:
      await websocket.close()
    except Exception:  # pylint: disable=broad-except
      pass


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------
def create_app(config: ServerConfig) -> fastapi.FastAPI:
  """Creates a FastAPI app instance with the given configuration."""
  ui_dir = _resolve_ui_dir()

  application = fastapi.FastAPI()
  
  @application.on_event("startup")
  def startup_event():
    # Force our package loggers to INFO and ensure they write to stdout
    loggers = [
        logging.getLogger(),
        logging.getLogger("__main__"),
    ]
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    ch.setFormatter(formatter)
    for l in loggers:
      l.setLevel(logging.INFO)
      l.addHandler(ch)
      l.propagate = False  # Avoid duplicate logs if root logger starts working

  application.state.config = config
  application.state.ui_dir = ui_dir
  application.state.active_poller_ref = None
  application.state.active_session = None
  application.state.session_agent_name = None
  application.state.session_lock = asyncio.Lock()
  application.state.instruction_defaults = {
      "heartbeat_interval_seconds": config.heartbeat_interval_seconds,
      "heartbeat_min_delay_seconds": config.heartbeat_min_delay_seconds,
      "use_event_driven_heartbeat": config.use_event_driven_heartbeat,
  }

  application.add_middleware(
      cors_middleware.CORSMiddleware,
      allow_origins=["*"],
      allow_credentials=True,
      allow_methods=["*"],
      allow_headers=["*"],
  )

  if ui_dir:
    application.mount(
        "/static",
        fastapi_staticfiles.StaticFiles(directory=ui_dir, follow_symlink=True),
        name="static",
    )
    logger.info("UI mounted from %s", ui_dir)
  else:
    logger.warning("UI directory not found.")

  application.include_router(router)
  return application


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------
def main():
  parser = argparse.ArgumentParser(description="Proactive Agent Server")
  parser.add_argument(
      "--model", default="models/gemini-robotics-er-2-streaming-preview", help="Model name."
  )
  parser.add_argument(
      "--robot_url", default="http://localhost:8888", help="Robot URL."
  )
  parser.add_argument(
      "--api_key",
      default=os.getenv("GEMINI_API_KEY"),
      help="Gemini API key (or set GEMINI_API_KEY env var).",
  )
  parser.add_argument(
      "--tts_api_key",
      default=os.getenv("TTS_API_KEY"),
      help="TTS API key (or set TTS_API_KEY env var).",
  )
  parser.add_argument(
      "--use_tts", action="store_true", default=True, help="Enable TTS."
  )
  parser.add_argument("--no_tts", dest="use_tts", action="store_false")
  parser.add_argument(
      "--tts_voice",
      default="en-US-Chirp3-HD-Puck",
      help="TTS voice name.",
  )
  parser.add_argument(
      "--tts_language_code", default="en-US", help="TTS language code."
  )
  parser.add_argument(
      "--tts_audio_gain", type=float, default=1.0, help="TTS audio gain."
  )
  parser.add_argument(
      "--response_modality", default="AUDIO", help="Response modality."
  )
  parser.add_argument("--dump_video_dir", default="", help="Dump video dir.")
  parser.add_argument("--port", type=int, default=8000, help="Server port.")
  parser.add_argument(
      "--heartbeat_interval_seconds",
      type=float,
      default=2.0,
      help="Heartbeat interval.",
  )
  parser.add_argument(
      "--heartbeat_min_delay_seconds",
      type=float,
      default=2.0,
      help="Min heartbeat delay.",
  )
  parser.add_argument(
      "--heartbeat_enabled", action="store_true", default=True
  )
  parser.add_argument(
      "--no_heartbeat", dest="heartbeat_enabled", action="store_false"
  )
  parser.add_argument(
      "--use_event_driven_heartbeat", action="store_true", default=True
  )
  parser.add_argument(
      "--media_resolution",
      default="low",
      choices=["low", "medium", "high", "ultra_high"],
  )
  parser.add_argument(
      "--enable_send_message_to_user", action="store_true", default=True
  )
  parser.add_argument(
      "--mock_robot", action="store_true", default=False, help="Mock robot."
  )
  parser.add_argument(
      "--agent_peers",
      default="",
      help="Comma-separated peers: name=url,name=url",
  )

  args = parser.parse_args()

  # Try to load API key from file if not provided
  api_key = args.api_key
  if not api_key:
    for p in [
        os.path.expanduser("~/.config/gemini/API_KEY"),
        os.path.expanduser("~/.config/safari_sdk/API_KEY"),
    ]:
      if os.path.isfile(p):
        with open(p, "r") as f:
          api_key = f.read().strip()
          logger.info("Loaded API key from %s", p)
          break

  # Parse agent peers
  agent_peers = {}
  if args.agent_peers:
    for pair in args.agent_peers.split(","):
      pair = pair.strip()
      if "=" in pair:
        name, url = pair.split("=", 1)
        agent_peers[name.strip()] = url.strip()

  config = ServerConfig(
      model=args.model,
      robot_url=args.robot_url,
      api_key=api_key,
      tts_api_key=args.tts_api_key,
      use_tts=args.use_tts,
      tts_voice=args.tts_voice,
      tts_language_code=args.tts_language_code,
      tts_audio_gain=args.tts_audio_gain,
      response_modality=args.response_modality,
      dump_video_dir=args.dump_video_dir,
      heartbeat_interval_seconds=args.heartbeat_interval_seconds,
      heartbeat_min_delay_seconds=args.heartbeat_min_delay_seconds,
      heartbeat_enabled=args.heartbeat_enabled,
      use_event_driven_heartbeat=args.use_event_driven_heartbeat,
      media_resolution=args.media_resolution,
      enable_send_message_to_user=args.enable_send_message_to_user,
      mock_robot=args.mock_robot,
      agent_peers=agent_peers,
      port=args.port,
  )

  logger.info("Server config: %s", config)
  app_instance = create_app(config)

  uvicorn_config = uvicorn.Config(
      app_instance, host="0.0.0.0", port=config.port, log_level="info"
  )
  server = uvicorn.Server(uvicorn_config)

  def _handle_shutdown(sig, frame):
    del sig, frame
    logger.info("Received shutdown signal, stopping server...")
    server.should_exit = True

  signal.signal(signal.SIGINT, _handle_shutdown)
  signal.signal(signal.SIGTERM, _handle_shutdown)

  server.run()


if __name__ == "__main__":
  main()
