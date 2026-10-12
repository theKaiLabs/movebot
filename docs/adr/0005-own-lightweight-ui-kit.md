# 5. The UI kit runs on its own small web server, not on NiceGUI

Date: 2026-10-12 · Status: accepted (supersedes the "prototype on NiceGUI" idea in plan §2.4)

## Context

Every example needs a built-in GUI (buttons, sliders, live values, video) that students and
teachers can use directly, that runs in a normal browser tab and inside the MoveBot app, and
that can show which line of code made each part of the screen (for the lessons). The plan
suggested building it on NiceGUI behind our own API.

## Decision

`movebot.ui` is our own API **and** our own small implementation:

* A web server on the `websockets` library we already depend on, serving one static page
  (`ui/static/index.html`, `app.js`, `app.css`, no build step, no CDN) and one WebSocket for
  events, updates and video frames (binary, with acknowledgements so a slow page always
  gets the newest frame).
* Student callbacks run on a worker thread pool, never on the server's event loop, so
  blocking robot calls like `bot.forward(0.5)` are fine inside a button. Each component runs
  its code at most once at a time (buttons ignore extra clicks, sliders and joysticks keep
  only the latest value).
* Every component records the file and line that created it; the page's **Code** inspector
  shows it and tells the embedding app (`postMessage`), and `/api/components` lists it for
  tools (lesson screenshots with callouts).

## Why not NiceGUI

* **Size and dependencies.** NiceGUI brings FastAPI, uvicorn, python-socketio and more. The
  UI kit adds nothing beyond `websockets`, numpy and Pillow, which matters for school
  laptops, Raspberry Pis and the offline installer.
* **Threading model.** Beginner callbacks block. With NiceGUI they would need explicit
  `run.io_bound` wrapping; here the default is already right.
* **Control over what lessons need**: source mapping, embedding, video flow control,
  the STOP button and the space bar as an e-stop.

## Consequences

* We maintain about 900 lines of JS/CSS/Python for the page and the server. The component set is
  deliberately small: row, column, card, button, toggle, slider, select, input, joystick,
  keyboard, text, meter, plot, video, log, markdown.
* The API stays ours, so the implementation can still be swapped later without changing any
  lesson.
* The page is tested through its WebSocket in the unit tests (`tests/test_ui.py`), and every
  example app is started against the simulator in CI (`tests/test_examples.py`).
