# The UI kit: `movebot.ui`

Give your robot program its own screen, with buttons, sliders, live values and video,
without writing any HTML. The UI kit comes with the MoveBot app: run your program from the
app (or with the app's Python) and `from movebot.ui import App` just works. The examples in
[`content/examples`](../content/examples/) all use it.

```python
from movebot import Bot
from movebot.ui import App

bot = Bot()
app = App("Drive me", bot=bot)
app.video("Camera", bot.camera)
app.joystick("Drive", lambda x, y: bot.drive(0.2 * y, -90 * x))
app.button("Lights", bot.lights.toggle)
app.text("Position", lambda: bot.pose)        # a function = a value that keeps updating
app.run()
```

## Two ways to write it

**Pass a function** to a component, as above. **Or use it as a decorator**: the function
right below becomes the button, slider or output.

```python
@app.button("Draw a square")
def square():
    for _ in range(4):
        bot.forward(0.3)
        bot.left()

@app.slider("Speed", 10, 100, 50, unit="%")
def set_speed(percent):
    bot.speed = percent

@app.output("Position")
def position():
    return bot.pose
```

## The app

| | |
|---|---|
| `App(title, bot=None, refresh=0.2)` | `bot=` adds a red **STOP** button; the **space bar** stops the bot too, and closing the app stops it. `refresh` is how often live values update (seconds). |
| `app.run()` | Open the screen and wait until you press Ctrl+C. |
| `app.start()` | Open the screen and carry on with your own code (for example a camera loop). Returns the address. |
| `app.stop()` | Close the screen (and stop the bot). |

Your functions run in the background, one at a time per component: clicking a button again
while its code is still running does nothing, and a slider that moves while its function runs
calls it once more with the latest value. If your code raises an error, the screen shows it
with the line number, and the app keeps running.

## Layout

```python
with app.row():              # side by side (wraps on narrow screens)
    with app.column():       # on top of each other
        ...
    with app.card("Robot"):  # a box with a title
        ...
```

## Components

Every component returns an object; keep it in a variable to read or change it later.

| Component | What it does | Read / change it |
|---|---|---|
| `button(label, on_click, style="primary")` | Runs `on_click()`. Styles: `primary`, `secondary`, `danger`. | `.update(label=...)` |
| `toggle(label, on_change, value=False)` | On/off switch; `on_change(True/False)`. | `.value` |
| `slider(label, min, max, value, step=None, unit=None, on_change=None)` | `on_change(number)`. Whole numbers if min and max are. | `.value` |
| `select(label, options, value=None, on_change=None)` | Drop-down list; `on_change(choice)`. | `.value` |
| `input(label, on_submit, placeholder=None)` | Text box; Enter runs `on_submit(text)`. | `.value` |
| `joystick(label, on_move)` | `on_move(x, y)`, both -1..1 (up is +y, right is +x); back to (0, 0) when released. | `.x`, `.y` |
| `keyboard(on_key, keys=None)` | `on_key(event)` with `event.key` and `event.pressed`. | `.pressed` (keys held now) |
| `text(label, value=None, unit=None)` | A labelled value. Give a function to keep it updated. | `.value` |
| `output(label)` | Decorator form of a live `text`. | |
| `meter(label, value, min=0, max=100, unit=None)` | A bar between `min` and `max` (value or function). | `.value` |
| `plot(label, source=None, window=30)` | Live chart of the last `window` seconds. `source` returns a number or a dict of numbers (one line each). | `.add(value)` |
| `video(label, source=None, fps=15, on_click=None)` | Pictures from `bot.camera`, from a function returning an image, or from `.show(image)`. `on_click(click)` gets `click.x`, `click.y`, `click.color` (B, G, R) and `click.hsv` (OpenCV scale). | `.show(image)` |
| `log(label, lines=200, capture_print=False)` | Lines of text; `capture_print=True` also shows everything you `print`. | `.write(...)`, `.clear()` |
| `markdown(text)` | Plain text with **bold**, `code`, headings and lists. | |

Images can be colour (BGR, like OpenCV), grayscale, or a True/False mask.

Every component also has `.visible` (show or hide it) and `.update(...)`.

## Seeing which code made what

The **</> Code** button at the top of the screen marks every part with the file and line that
created it; click a part to see (or, in the MoveBot app, jump to) that line. Lessons use the
same information to explain how the screen is connected to the code.

## A ready-made control panel

`movebot panel` (or `control_panel(bot).run()`) opens a screen with the camera, a joystick,
arrow-key driving, the speed limit, lights, battery and sensor readings.
