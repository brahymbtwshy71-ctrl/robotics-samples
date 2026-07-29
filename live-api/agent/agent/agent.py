"""Agent configuration for Proactive Agent.

An Agent is a named composition of system instruction (SI), developer
instruction (DI), and tool declarations.  It is embodiment-agnostic —
the same Agent can be used with any embodiment.

Typical usage:

    agent = Agent.from_name("human")
    print(agent.system_instruction)
    print(agent.tools)
"""

import dataclasses
from typing import Any

from prompt import si_builder
from tool import tools as tools_lib


@dataclasses.dataclass
class Agent:
  """A named composition of prompt (system instruction) and tools."""

  name: str
  system_instruction: str
  developer_instruction: str
  tools: list[dict[str, Any]]

  # ---------------------------------------------------------------------------
  # Pre-built presets
  # ---------------------------------------------------------------------------

  @classmethod
  def human(cls) -> "Agent":
    """Local/browser mode with webcam."""
    builder = si_builder.SIBuilder()
    builder.load_instruction_file("human_di.md")
    return cls(
        name="human",
        system_instruction="",
        developer_instruction=builder.build(),
        tools=tools_lib.human_tools(),
    )

  @classmethod
  def spot(cls) -> "Agent":
    """Boston Dynamics Spot robot agent."""
    builder = si_builder.SIBuilder()
    builder.load_instruction_file("spot_di.md")
    return cls(
        name="spot",
        system_instruction="",
        developer_instruction=builder.build(),
        tools=tools_lib.spot_tools(),
    )

  @classmethod
  def tinybot(cls) -> "Agent":
    """Tinybot robot agent."""
    builder = si_builder.SIBuilder()
    builder.load_instruction_file("tinybot_di.md")
    return cls(
        name="tinybot",
        system_instruction="",
        developer_instruction=builder.build(),
        tools=tools_lib.tinybot_tools(),
    )

  # ---------------------------------------------------------------------------
  # Name-based lookup
  # ---------------------------------------------------------------------------

  @classmethod
  def from_name(cls, name: str) -> "Agent":
    """Returns an Agent for the specified name string.

    Args:
      name: "human", "spot", or "tinybot" is supported for Lite.

    Returns:
      An Agent instance.

    Raises:
      ValueError: If the name is unknown.
    """
    presets = {
        "human": cls.human,
        "spot": cls.spot,
        "tinybot": cls.tinybot,
    }
    if name not in presets:
      raise ValueError(
          f"Unknown agent name: {name}. Available: {list(presets.keys())}"
      )
    return presets[name]()
