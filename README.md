# MoveBot

MoveBot is a small learning robot for high-school students and their teachers: two wheels
with encoders, a camera (ESP32-S3), lights, status LEDs and add-on modules, programmed in
Python from a laptop, PC or Raspberry Pi.

This is the **open** part of the project: the wire protocol, the `movebot` Python library,
the examples and lessons, and (soon) the ROS 2 bridge. Students and teachers use it through
the MoveBot app, which adds the code editor, the simulator and the UI kit (see
[ADR 0006](docs/adr/0006-simulator-and-ui-kit-ship-with-the-app.md)). The plan is in
[docs/software-plan.md](docs/software-plan.md).

## Programming a robot

```python
from movebot import Bot

bot = Bot()                                   # finds the robot (or Bot("192.168.4.1"))
bot.forward(0.5)                              # metres
bot.left()                                    # 90 degrees
bot.route().forward(0.3).left().forward(0.3).run()
print(bot.pose)
bot.camera.save("view.jpg")
```

In the MoveBot app, `Bot("sim")` gives a simulated robot and `from movebot.ui import App`
gives your program its own screen ([docs/ui.md](docs/ui.md)). With a real robot,
`movebot relay 192.168.4.1` lets several programs share it. See
[packages/movebot](packages/movebot/README.md) for the library.

## Repository layout

| Path | What |
|---|---|
| [`protocol/SPEC.md`](protocol/SPEC.md) | The wire protocol (v0.1 draft). The contract between bot, library, app and ROS node. |
| [`protocol/schema/`](protocol/schema/) | JSON Schema for every message. |
| [`protocol/vectors/`](protocol/vectors/) | Example messages, valid and invalid. |
| [`protocol/modules/`](protocol/modules/) | One descriptor per add-on module type, and how to add a new one. |
| [`protocol/conformance/`](protocol/conformance/) | Tests any bot must pass: `pytest protocol/conformance --target ws://<bot>/ws`. |
| [`packages/movebot/`](packages/movebot/) | The Python library and the `movebot` command. |
| [`content/`](content/) | Example packs: a program, its screen and its lesson. |
| [`docs/`](docs/) | The UI kit reference, ADRs and the plan. |

## Development

```bash
uv sync                          # creates .venv with the library and dev tools
uv run pytest                    # library tests (simulator tests skip without the app)
uv run ruff check . && uv run ruff format --check .
```

The full suite (simulator, UI kit, examples, conformance through the relay) runs from a
checkout of the private `movebot-studio` repository, which contains this one as a submodule.
Testing real firmware works from here: `uv run pytest protocol/conformance --target
ws://192.168.4.1/ws` (tests marked `sim_only` are skipped).

Decisions that shape the code are written down as ADRs in [`docs/adr/`](docs/adr/); please
add one when you change something fundamental, especially the protocol.
