"""Make a screen for your robot program: buttons, sliders, live values, video.

The UI kit comes with the MoveBot app; in the app's Python this just works::

    from movebot.ui import App
    app = App("My robot", bot=bot)
    app.button("Forward", lambda: bot.forward(0.2))
    app.run()

Every component is documented in docs/ui.md, and the examples in content/examples use it.
"""

from __future__ import annotations

from ._studio import load

_ui = load("ui", "The UI kit (movebot.ui)")

App = _ui.App
Click = _ui.Click
KeyEvent = _ui.KeyEvent
control_panel = _ui.control_panel

__all__ = ["App", "Click", "KeyEvent", "control_panel"]
