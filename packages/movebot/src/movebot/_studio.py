"""Hooks into the MoveBot app (``movebot_studio``), which provides the simulator and UI kit.

The library talks to robots on its own. The simulator (``Bot("sim")``) and the UI kit
(``movebot.ui``) come with the MoveBot app; in the app's Python they are always there.
"""

from __future__ import annotations

import importlib
from types import ModuleType

from .errors import NeedsMoveBotApp


def load(module: str, feature: str) -> ModuleType:
    """Import ``movebot_studio.<module>``, or explain that ``feature`` needs the app."""
    try:
        return importlib.import_module(f"movebot_studio.{module}")
    except ImportError as exc:
        if exc.name is None or not exc.name.startswith("movebot_studio"):
            raise  # something else is missing; show the real problem
        raise NeedsMoveBotApp(
            f"{feature} comes with the MoveBot app. Run your program from the MoveBot app "
            "(or with its Python), or connect to a real robot with Bot() / Bot('192.168.4.1')."
        ) from None
