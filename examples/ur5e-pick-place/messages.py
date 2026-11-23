"""Shared message definitions between sim_plugin.py and viewer_plugin.py."""

import dataclasses
from mujoco.studio import messages


@dataclasses.dataclass(frozen=True)
class RoutineConfig(messages.Snapshot):
  """UI -> sim: routine settings."""

  speed: float = 0.35  # Tool speed along each leg, in m/s.
  loop: bool = True  # Start again a few seconds after finishing.


@dataclasses.dataclass(frozen=True)
class RestartEvent(messages.Event):
  """UI -> sim: put the cubes back and start the routine again."""


@dataclasses.dataclass(frozen=True)
class Telemetry(messages.Snapshot):
  """sim -> UI: latest-wins summary of the routine."""

  sim_time: float = 0.0
  stage: str = ''
  placed: tuple[str, ...] = ()
  runs: int = 0
