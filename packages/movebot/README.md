# movebot

Program the **MoveBot** learning robot from Python. In the MoveBot app you also get a
simulator (`Bot("sim")`), so you can start without a robot, and the UI kit (`movebot.ui`).

```python
from movebot import Bot

bot = Bot("sim")      # a simulated bot; Bot() finds the real one
bot.forward(0.5)      # metres
bot.left()            # 90 degrees
bot.lights.on()
print(bot.pose)       # x, y and heading measured by the wheel encoders
```

## Routes

Build a whole route and let the bot drive it on its own. If the Wi-Fi drops, it keeps
going and the library catches up when it reconnects:

```python
route = bot.route().forward(0.5).left().forward(0.5).wait(1).u_turn()
print(route.preview())    # where the bot should be after each move
result = route.run()
print(result)             # planned vs. actual position for every move
```

## Camera

Pictures are numpy arrays in BGR order, ready for OpenCV:

```python
image = bot.camera.frame()             # the newest picture
for image in bot.camera.frames():      # a fresh picture every time round the loop
    ...                                # e.g. find the blue ball, then bot.drive(0.1, turn_rate)
bot.camera.configure("balanced")       # presets: fast (320x240), balanced (640x480), detail (1280x720)
bot.camera.save("snapshot.jpg")
```

## Modules

Add-on sensors appear under `bot.modules`, named by the bot:

```python
print(bot.modules)                           # <Modules: front_distance (distance), imu (imu)>
print(bot.modules.front_distance.distance)   # metres, or None if nothing is in range
bot.modules.imu.calibrate()
print(bot.modules.imu.heading)               # degrees
```

Try them in the simulator: `Bot.simulated(modules=["distance:front_distance", "imu"])`.

## Your own app screen

`movebot.ui` (comes with the MoveBot app; reference: `docs/ui.md`) makes a control screen
in the browser: no HTML needed. Functions become
buttons, functions that return something become live values:

```python
from movebot.ui import App

app = App("My robot", bot=bot)         # bot=... adds a STOP button (and the space bar)
app.video("Camera", bot.camera)
app.joystick("Drive", lambda x, y: bot.drive(0.2 * y, -90 * x))

@app.button("Draw a square")
def square():
    for _ in range(4):
        bot.forward(0.3)
        bot.left()

@app.output("Position")
def position():
    return bot.pose

app.run()                              # opens the browser; Ctrl+C to stop
```

Also: `toggle`, `slider`, `select`, `input`, `keyboard`, `text`, `meter`, `plot`, `log`,
`markdown`, and `row` / `column` / `card` for layout. `app.start()` instead of `app.run()`
keeps your own loop running next to the screen (see the follow-the-ball example). The
**</> Code** button on the page shows which line made each part.

## Command line

```
movebot sim                      # run a simulated bot on this computer (MoveBot app)
movebot sim --module imu         # ... with a simulated IMU
movebot panel                    # ready-made control panel (MoveBot app)
movebot relay 192.168.4.1        # share one real bot with several programs
movebot shell                    # Python prompt with a connected `bot`
movebot route "forward 0.5; left; forward 0.5"
movebot info
```

Units: metres, seconds and degrees in this API. The wire protocol uses metres and
radians (see `protocol/SPEC.md` in the repository).
