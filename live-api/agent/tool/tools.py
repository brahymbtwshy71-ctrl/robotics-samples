"""Tool declarations for Proactive Agent.

All tools are declared as plain Python dicts matching the Gemini API JSON
format. No protobuf dependencies.

Tool sets return raw dicts matching the Gemini API.

Typical usage:

    from tool import tools

    my_tools = tools.robot_tools()
"""

from typing import Any


# ---------------------------------------------------------------------------
# Individual tool declarations
# ---------------------------------------------------------------------------


def _tool(
    name: str,
    description: str,
    parameters: dict[str, Any],
    behavior: str | None = None,
) -> dict[str, Any]:
  """Helper to build a single FunctionDeclaration dict."""
  d: dict[str, Any] = {
      "name": name,
      "description": description,
      "parameters": parameters,
  }
  if behavior is not None:
    d["behavior"] = behavior
  return d


def run_instruction_tool() -> dict[str, Any]:
  """Tool to send a natural language instruction to the robot."""
  return _tool(
      name="run_instruction",
      description=(
          "When you call this tool, the robot will start executing the"
          " instruction. The robot continues executing until you call"
          " `run_instruction` again with a new instruction. Observe the scene"
          " visually to determine if the current step is complete."
      ),
      parameters={
          "type": "OBJECT",
          "properties": {
              "instruction": {
                  "type": "STRING",
                  "description": (
                      "A specific, unambiguous, atomic (involving single"
                      " action) natural language instruction for the robot"
                      " (e.g. 'bring the cup to the table', 'put the dice in"
                      " the green tray'). This instruction should be specific"
                      " enough to describe the exact object, e.g. 'the white"
                      " cup on the center of the table'. Always use 'pick and"
                      " place' instead of just 'pick'. Always give concrete"
                      " from and to locations. It probably should not contain"
                      " the word 'and' except in 'pick and place'."
                  ),
              },
          },
          "required": ["instruction"],
      },
      behavior="BLOCKING",
  )


def draw_points_tool() -> dict[str, Any]:
  """Tool to draw labeled point overlays on the camera image."""
  return _tool(
      name="draw_points",
      description=(
          "Draw one or more labeled blue point overlays on the camera image"
          " to highlight points or objects in the scene. Coordinates are"
          " integers 0-1000 where (0,0) is top-left and (1000,1000) is"
          " bottom-right."
      ),
      parameters={
          "type": "OBJECT",
          "properties": {
              "points": {
                  "type": "ARRAY",
                  "description": "List of points to draw.",
                  "items": {
                      "type": "OBJECT",
                      "properties": {
                          "x": {
                              "type": "NUMBER",
                              "description": (
                                  "Horizontal position, 0-1000"
                                  " (0=left, 1000=right)."
                              ),
                          },
                          "y": {
                              "type": "NUMBER",
                              "description": (
                                  "Vertical position, 0-1000"
                                  " (0=top, 1000=bottom)."
                              ),
                          },
                          "label": {
                              "type": "STRING",
                              "description": (
                                  "Text label displayed next to the point."
                              ),
                          },
                      },
                      "required": ["x", "y"],
                  },
              },
          },
          "required": ["points"],
      },
      behavior="NON_BLOCKING",
  )


def stop_tool() -> dict[str, Any]:
  """Tool to stop all robot motion immediately."""
  return _tool(
      name="stop",
      description="Stop all robot motion immediately.",
      parameters={"type": "OBJECT", "properties": {}},
  )


def ack_tool() -> dict[str, Any]:
  """Tool to acknowledge the heartbeat without taking action."""
  return _tool(
      name="ack",
      description=(
          "Call this tool to acknowledge the regular heartbeat and indicate"
          " that no new intervention is needed. This is the default action when"
          " no other specific action is required."
      ),
      parameters={"type": "OBJECT", "properties": {}},
      behavior="BLOCKING",
  )


def make_gesture_tool() -> dict[str, Any]:
  """Tool to make the robot perform a gesture."""
  return _tool(
      name="make_gesture",
      description="Make the robot perform a gesture.",
      parameters={
          "type": "OBJECT",
          "properties": {
              "gesture": {
                  "type": "STRING",
                  "description": (
                      "The name of the gesture to perform. Valid gestures"
                      " are: 'wave', 'thinking_pose', 'dance_move',"
                      " 'alive', 'left_hand_wave', 'right_hand_wave',"
                      " 'idle_nod', 'idle_hands', 'greeting_crowd',"
                      " 'look_right', 'addresses_audience',"
                      " 'addressing_audience_on_the_left',"
                      " 'addressing_the_audience_on_the_right',"
                      " 'agrees_with_someone', 'arms_wide_open',"
                      " 'both_arms_in_one_direction',"
                      " 'bringing_hands_together',"
                      " 'calming_audience_on_the_left',"
                      " 'calming_down_audience',"
                      " 'came_up_with_an_idea', 'celebrates',"
                      " 'comes_up_with_an_idea', 'disappointed',"
                      " 'greets_with_both_hands', 'hands_up',"
                      " 'has_a_question', 'is_afraid_of_something',"
                      " 'is_demanding_sth', 'looks_around',"
                      " 'looks_around_starts_by_turning_its_head_left',"
                      " 'looks_down', 'looks_up_raises_hands',"
                      " 'makes_a_point', 'open_arm_welcoming',"
                      " 'opens_its_arms_looking_at_the_scene_in_front_of_it',"
                      " 'pointing_to_the_left_and_explaining_sth',"
                      " 'points_at_something',"
                      " 'points_somewhere_and_agrees',"
                      " 'raises_hand_and_agrees', 'goodbye',"
                      " 'hello', 'hello_1', 'no',"
                      " 'showing_scary_move', 'thinks_about_sth',"
                      " 'thinks_how_to_solve_a_problem',"
                      " 'thumbs_up',"
                      " 'turns_its_head_right_and_notices_sth',"
                      " 'turns_left_and_then_pays_attention_to_sth_in_center',"
                      " 'victory_sign',"
                      " 'want_audience_to_calm_down',"
                      " 'wants_audience_to_calm_down'."
                  ),
              },
          },
          "required": ["gesture"],
      },
      behavior="NON_BLOCKING",
  )


def send_message_tool(
    enable_send_message_to_user: bool = False,
) -> dict[str, Any]:
  """Tool to send a message to another robot agent (or the user)."""
  if enable_send_message_to_user:
    desc = (
        "Send a text message to the user or another robot agent in the fleet."
        " Use this to delegate tasks or coordinate with other robots or to"
        " talk to the user."
    )
    target_desc = (
        "The target robot agent name (e.g. 'duo', 'apollo', 'user')."
    )
  else:
    desc = (
        "Send a text message to another robot agent in the fleet."
        " Use this to delegate tasks or coordinate with other robots."
    )
    target_desc = "The target robot agent name (e.g. 'duo', 'apollo')."

  return _tool(
      name="send_message",
      description=desc,
      parameters={
          "type": "OBJECT",
          "properties": {
              "target": {
                  "type": "STRING",
                  "description": target_desc,
              },
              "message": {
                  "type": "STRING",
                  "description": (
                      "The message to send. Can be a task instruction, "
                      "status update, or coordination signal. Do not send "
                      "emojis in the message."
                  ),
              },
          },
          "required": ["target", "message"],
      },
      behavior="NON_BLOCKING",
  )


def get_calendar_tool() -> dict[str, Any]:
  """Tool to retrieve upcoming events from the shared calendar."""
  return _tool(
      name="get_calendar",
      description=(
          "Retrieve upcoming events from the shared family calendar. Use this"
          " to check for planned activities."
      ),
      parameters={"type": "OBJECT", "properties": {}},
      behavior="BLOCKING",
  )


def turn_head_to_uv_tool() -> dict[str, Any]:
  """Tool to turn the robot head to a normalized pixel coordinate."""
  return _tool(
      name="turn_head_to_uv",
      description=(
          "Turn the robot head to look at a specific point in the current"
          " camera view. Takes two arguments: `u` (horizontal, 0=left, 1=right)"
          " and `v` (vertical, 0=top, 1=bottom). Both are normalized pixel"
          " coordinates between 0 and 1."
      ),
      parameters={
          "type": "OBJECT",
          "properties": {
              "u": {
                  "type": "NUMBER",
                  "description": (
                      "Horizontal pixel coordinate, normalized between 0 and"
                      " 1. 0 is the left edge, 1 is the right edge."
                  ),
              },
              "v": {
                  "type": "NUMBER",
                  "description": (
                      "Vertical pixel coordinate, normalized between 0 and"
                      " 1. 0 is the top edge, 1 is the bottom edge."
                  ),
              },
          },
          "required": ["u", "v"],
      },
      behavior="NON_BLOCKING",
  )


# ---------------------------------------------------------------------------
# Tool sets — return lists of dicts wrapped in {"functionDeclarations": [...]}
# ---------------------------------------------------------------------------

def _wrap(decls: list[dict[str, Any]]) -> list[dict[str, Any]]:
  """Wrap a list of function declarations in the Gemini API format."""
  return [{"functionDeclarations": decls}]


def robot_tools() -> list[dict[str, Any]]:
  """Motion control tools: run_instruction, stop, ack."""
  return _wrap([run_instruction_tool(), stop_tool(), ack_tool()])


def human_tools() -> list[dict[str, Any]]:
  """Human/local mode tools: run_instruction, stop, ack."""
  return _wrap([
      run_instruction_tool(),
      stop_tool(),
      ack_tool(),
      send_message_tool(enable_send_message_to_user=True),
  ])


def all_tools() -> list[dict[str, Any]]:
  """All available tools (robot + UI + gesture + ack)."""
  return _wrap([
      run_instruction_tool(),
      draw_points_tool(),
      stop_tool(),
      ack_tool(),
      make_gesture_tool(),
  ])


def collab_tools() -> list[dict[str, Any]]:
  """Robot + collaboration tools for multi-agent coordination."""
  return _wrap([
      run_instruction_tool(),
      stop_tool(),
      ack_tool(),
      send_message_tool(),
  ])


def navigate_tool() -> dict[str, Any]:
  """Tool to navigate to a named waypoint."""
  return _tool(
      name="navigate",
      description=(
          "Navigate the robot to a named waypoint using GraphNav. The robot"
          " will walk to the specified waypoint and report when it arrives."
          " Call only after get_waypoints returns navigation_ready=true, use"
          " an exact name from that result, and call stow before navigating."
      ),
      parameters={
          "type": "OBJECT",
          "properties": {
              "waypoint": {
                  "type": "STRING",
                  "description": (
                      "Exact waypoint name from the latest successful"
                      " get_waypoints result. Never invent, normalize, or reuse"
                      " a name from an earlier session."
                  ),
              },
          },
          "required": ["waypoint"],
      },
      behavior="BLOCKING",
  )


def drive_tool() -> dict[str, Any]:
  """Tool for short body-relative movement without GraphNav waypoints."""
  return _tool(
      name="drive",
      description=(
          "Drive Spot without a waypoint for a short, bounded interval using"
          " body-frame velocities. Positive v_x moves forward, positive v_y"
          " moves left, and positive v_rot turns counterclockwise. The robot"
          " powers on and stands automatically. The current camera-arm joint"
          " pose is held relative to the body, so the gripper camera moves"
          " with Spot. Use small commands near people, furniture, stairs, or"
          " other obstacles."
      ),
      parameters={
          "type": "OBJECT",
          "properties": {
              "v_x": {
                  "type": "NUMBER",
                  "minimum": -0.8,
                  "maximum": 0.8,
                  "description": (
                      "Forward velocity in meters per second, from -0.8"
                      " backward to 0.8 forward."
                  ),
              },
              "v_y": {
                  "type": "NUMBER",
                  "minimum": -0.5,
                  "maximum": 0.5,
                  "description": (
                      "Sideways velocity in meters per second, from -0.5"
                      " right to 0.5 left."
                  ),
              },
              "v_rot": {
                  "type": "NUMBER",
                  "minimum": -1.0,
                  "maximum": 1.0,
                  "description": (
                      "Yaw velocity in radians per second, from -1.0"
                      " clockwise to 1.0 counterclockwise."
                  ),
              },
              "duration": {
                  "type": "NUMBER",
                  "minimum": 0.1,
                  "maximum": 2.0,
                  "description": "How long to drive, in seconds (0.1 to 2.0).",
              },
          },
          "required": ["v_x", "v_y", "v_rot", "duration"],
      },
      behavior="BLOCKING",
  )


def stop_spot_tool() -> dict[str, Any]:
  """Tool to immediately stop Spot motion and freeze the arm."""
  return _tool(
      name="stop",
      description=(
          "Immediately cancel base motion and navigation and freeze the arm."
          " Call this whenever motion is unsafe or the user asks Spot to stop."
      ),
      parameters={"type": "OBJECT", "properties": {}},
      behavior="BLOCKING",
  )


def look_tool() -> dict[str, Any]:
  """Tool to aim the gripper camera by rotating only the arm."""
  return _tool(
      name="look",
      description=(
          "Aim Spot's gripper-mounted camera by rotating only the arm; the"
          " robot body and feet remain stationary. Use small steps and"
          " inspect the fresh camera frame returned after each move."
      ),
      parameters={
          "type": "OBJECT",
          "properties": {
              "direction": {
                  "type": "STRING",
                  "enum": ["up", "down", "left", "right"],
                  "description": "Direction to aim the camera view.",
              },
              "angle_rad": {
                  "type": "NUMBER",
                  "minimum": 0.05,
                  "maximum": 0.35,
                  "description": (
                      "Positive angular step in radians. Use 0.15 for a"
                      " small adjustment and 0.3 for a larger adjustment."
                  ),
              },
          },
          "required": ["direction"],
      },
      behavior="BLOCKING",
  )


def detect_tool() -> dict[str, Any]:
  """Detect an object or placement location and store a one-time target."""
  return _tool(
      name="detect",
      description=(
          "Use the Spot backend's Gemini Robotics detector to locate exactly"
          " one language-specified object or placement location in the stable"
          " hand-camera image."
          " When the user asks to pick up an object, assume it is in the"
          " current view and call this tool instead of claiming it is not"
          " visible without attempting detection."
          " The backend returns and stores the grasp location and the UI"
          " overlays it. Call only after the camera view has remained stable"
          " for at least three seconds. After a correct detection, call pick"
          " or place with no arguments before any camera or robot movement."
      ),
      parameters={
          "type": "OBJECT",
          "properties": {
              "instruction": {
                  "type": "STRING",
                  "description": (
                      "A concise description identifying exactly one visible"
                      ' object, such as "the red cube on the floor".'
                  ),
              },
          },
          "required": ["instruction"],
      },
      behavior="BLOCKING",
  )


def pick_tool() -> dict[str, Any]:
  """Grasp the target stored by the latest detect call."""
  return _tool(
      name="pick",
      description=(
          "Grasp the one-time location stored by the most recent successful"
          " detect call. This tool accepts no pixel coordinates. Call it only"
          " after confirming the detection overlay is on the requested object"
          " and before any robot or camera motion. The target is consumed"
          " after one attempt. A completed call still requires visual success"
          " verification. The backend reduces the gripper hold torque after"
          " the native Spot grasp succeeds."
      ),
      parameters={"type": "OBJECT", "properties": {}},
      behavior="BLOCKING",
  )


def deploy_arm_tool() -> dict[str, Any]:
  """Deploy arm."""
  return _tool(
      name="deploy_arm",
      description=(
          "Deploy the robot arm from its stowed position. Must be called"
          " before any arm or gripper operations."
      ),
      parameters={"type": "OBJECT", "properties": {}},
      behavior="BLOCKING",
  )


def stow_arm_tool() -> dict[str, Any]:
  """Stow arm."""
  return _tool(
      name="stow_arm",
      description=(
          "Stow the robot arm back into its carry position. Call this before"
          " navigating to avoid collisions."
      ),
      parameters={"type": "OBJECT", "properties": {}},
      behavior="BLOCKING",
  )


def open_gripper_tool() -> dict[str, Any]:
  """Open gripper."""
  return _tool(
      name="open_gripper",
      description=(
          "Open the robot gripper. Optionally specify the fraction to open to."
      ),
      parameters={
          "type": "OBJECT",
          "properties": {
              "fraction": {
                  "type": "NUMBER",
                  "description": (
                      "How far to open (0=closed, 1=fully open). Default is"
                      " 1.0."
                  ),
              },
          },
      },
      behavior="NON_BLOCKING",
  )


def close_gripper_tool() -> dict[str, Any]:
  """Close gripper."""
  return _tool(
      name="close_gripper",
      description="Close the robot gripper to grasp an object.",
      parameters={"type": "OBJECT", "properties": {}},
      behavior="NON_BLOCKING",
  )


def stand_tool() -> dict[str, Any]:
  """Stand up."""
  return _tool(
      name="stand",
      description=(
          "Power on the robot and stand up. Call this to wake the robot from"
          " sitting."
      ),
      parameters={"type": "OBJECT", "properties": {}},
      behavior="BLOCKING",
  )


def sit_tool() -> dict[str, Any]:
  """Sit down."""
  return _tool(
      name="sit",
      description=(
          "Sit the robot down and power off its motors. Call this only when"
          " the user's current instruction explicitly asks Spot to sit; never"
          " sit automatically when a task ends or Spot becomes idle."
      ),
      parameters={"type": "OBJECT", "properties": {}},
      behavior="BLOCKING",
  )


def get_battery_tool() -> dict[str, Any]:
  """Get battery."""
  return _tool(
      name="get_battery",
      description="Check the robot battery level and power state.",
      parameters={"type": "OBJECT", "properties": {}},
      behavior="BLOCKING",
  )


def get_waypoints_tool() -> dict[str, Any]:
  """Get waypoints."""
  return _tool(
      name="get_waypoints",
      description=(
          "List registered navigation destinations and report GraphNav"
          " readiness. Use only when the user asks for destinations or"
          " requests waypoint navigation; do not call at startup or for"
          " manipulation, camera, status, or local-drive tasks. If the user"
          " only asks for names, return them without discussing localization."
          " For navigation, use a returned name only when navigation_ready is"
          " true. If false, explain that GraphNav must be loaded and localized."
          " If null or absent, say readiness could not be verified; do not"
          " assume localization is missing and do not call navigate."
      ),
      parameters={"type": "OBJECT", "properties": {}},
      behavior="BLOCKING",
  )


def health_check_tool() -> dict[str, Any]:
  """Tool to check the robot connection status, lease holder state, and battery levels."""
  return _tool(
      name="health_check",
      description=(
          "Check robot connection, lease holder, and battery state. Use when"
          " the user asks for status, before physical motion when control"
          " state is unknown, or after evidence of a connection, lease, or"
          " battery problem. Do not call automatically at startup or while"
          " idle."
      ),
      parameters={"type": "OBJECT", "properties": {}},
      behavior="BLOCKING",
  )


def place_tool() -> dict[str, Any]:
  """Place the held object at the target stored by detect."""
  return _tool(
      name="place",
      description=(
          "Place the currently held object at the one-time location stored by"
          " the most recent successful detect call. This tool accepts no"
          " coordinates. Call it immediately after detecting the intended"
          " placement surface, before any robot or camera movement. The"
          " backend moves the hand to the projected 3D target and releases"
          " only after arm arrival is confirmed; a failed approach leaves the"
          " gripper closed."
      ),
      parameters={"type": "OBJECT", "properties": {}},
      behavior="BLOCKING",
  )


def wait_for_pick_up_tool() -> dict[str, Any]:
  """Wait for a recipient to lift and take the held object."""
  return _tool(
      name="wait_for_pick_up",
      description=(
          "Wait for a person to pick up the object currently held by Spot."
          " Call from carry pose after reaching the recipient. The tool"
          " monitors upward hand motion; when the hand rises by the threshold,"
          " it opens the gripper, waits briefly, closes the gripper, and stows"
          " the arm. A timeout leaves the object held."
      ),
      parameters={
          "type": "OBJECT",
          "properties": {
              "monitor_sec": {
                  "type": "NUMBER",
                  "minimum": 1.0,
                  "maximum": 120.0,
                  "description": "Maximum seconds to wait for pickup.",
              },
              "upward_threshold_m": {
                  "type": "NUMBER",
                  "minimum": 0.005,
                  "maximum": 0.2,
                  "description": "Upward hand displacement that triggers release; default 0.02 m.",
              },
              "open_duration_sec": {
                  "type": "NUMBER",
                  "minimum": 0.1,
                  "maximum": 10.0,
                  "description": "Seconds to keep the gripper open; default 3 seconds.",
              },
          },
      },
      behavior="BLOCKING",
  )


def stow_tool() -> dict[str, Any]:
  """Tool to stow the arm safely, choosing carry pose if holding an object."""
  return _tool(
      name="stow",
      description=(
          "Stow the arm safely. If the robot is holding an object, it will"
          " move the arm to a stable carry pose to prevent collision. If it"
          " is not holding anything, it will stow the arm completely."
      ),
      parameters={"type": "OBJECT", "properties": {}},
      behavior="BLOCKING",
  )


def spot_tools() -> list[dict[str, Any]]:
  """Spot navigation + manipulation tools."""
  return _wrap([
      health_check_tool(),
      get_waypoints_tool(),
      navigate_tool(),
      drive_tool(),
      stop_spot_tool(),
      look_tool(),
      detect_tool(),
      pick_tool(),
      place_tool(),
      wait_for_pick_up_tool(),
      stand_tool(),
      sit_tool(),
      stow_tool(),
      ack_tool(),
      send_message_tool(enable_send_message_to_user=True),
  ])


def tinybot_make_gesture_tool() -> dict[str, Any]:
  """Tool to make the tinybot perform a gesture."""
  return _tool(
      name="make_gesture",
      description="Make the tinybot perform a gesture.",
      parameters={
          "type": "OBJECT",
          "properties": {
              "gesture": {
                  "type": "STRING",
                  "description": (
                      "The name of the gesture to perform. Valid gestures"
                      " are: 'nod', 'no', 'home', 'home_pose'."
                  ),
              },
              "speed": {
                  "type": "INTEGER",
                  "description": "Speed of gesture (default: 150).",
              },
          },
          "required": ["gesture"],
      },
      behavior="NON_BLOCKING",
  )


def move_absolute_tool() -> dict[str, Any]:
  """Tool to move tinybot joints to absolute angles."""
  return _tool(
      name="move_absolute",
      description="Move tinybot joints to absolute angles in degrees.",
      parameters={
          "type": "OBJECT",
          "properties": {
              "angles": {
                  "type": "ARRAY",
                  "items": {"type": "NUMBER"},
                  "description": "Target joint angles in degrees.",
              },
              "speeds": {
                  "type": "ARRAY",
                  "items": {"type": "INTEGER"},
                  "description": "Movement speeds for each joint.",
              },
              "blocking": {
                  "type": "BOOLEAN",
                  "description": (
                      "Whether to block until movement is complete (default:"
                      " true)."
                  ),
              },
          },
          "required": ["angles", "speeds"],
      },
      behavior="BLOCKING",
  )


def move_relative_tool() -> dict[str, Any]:
  """Tool to move tinybot joints by relative angles."""
  return _tool(
      name="move_relative",
      description="Move tinybot joints by relative angles in degrees.",
      parameters={
          "type": "OBJECT",
          "properties": {
              "relative_angles": {
                  "type": "ARRAY",
                  "items": {"type": "NUMBER"},
                  "description": "Relative angles in degrees.",
              },
              "speeds": {
                  "type": "ARRAY",
                  "items": {"type": "INTEGER"},
                  "description": "Movement speeds for each joint.",
              },
              "blocking": {
                  "type": "BOOLEAN",
                  "description": (
                      "Whether to block until movement is complete (default:"
                      " true)."
                  ),
              },
          },
          "required": ["relative_angles", "speeds"],
      },
      behavior="BLOCKING",
  )


def clear_overlay_tool() -> dict[str, Any]:
  """Tool to clear point overlays on the camera image."""
  return _tool(
      name="clear_overlay",
      description="Clear all drawn point overlays from the camera image.",
      parameters={"type": "OBJECT", "properties": {}},
      behavior="NON_BLOCKING",
  )


def tinybot_tools() -> list[dict[str, Any]]:
  """Tinybot motion + drawing tools."""
  return _wrap([
      turn_head_to_uv_tool(),
      tinybot_make_gesture_tool(),
      move_absolute_tool(),
      move_relative_tool(),
      draw_points_tool(),
      clear_overlay_tool(),
      stop_tool(),
      ack_tool(),
      send_message_tool(enable_send_message_to_user=True),
  ])

