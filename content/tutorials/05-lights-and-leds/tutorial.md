# Lights and LEDs

The robot has three kinds of lights:

| | In code | What it is for |
|---|---|---|
| Two **headlights** | `bot.lights` | Lighting the way (and the camera picture) |
| The **status LED** | `bot.status_led` | The controller board's own LED, one colour |
| The **RGB LED** | `bot.rgb_led` | Any colour you like: show what your program is doing |

!!! tip "Seeing them in the simulator"
    A real camera cannot see the robot's own LEDs, but in the simulator they are shown in the
    bottom-left corner of the camera picture (**L R ESP RGB**), and the headlights light up
    the floor. Open the **Robot camera** tab at the bottom of the app to watch them while
    `lights.py` runs.

Open `lights.py` and run it, then read on.

## Headlights

```python
--8<-- "lights.py:headlights"
```

`bot.lights` controls both lights; `bot.lights.left` and `bot.lights.right` control one each.
`level` is the brightness: 0 is off, 1 is full, and anything in between dims them.

## The status LED

```python
--8<-- "lights.py:status"
```

Patterns: `on()`, `off()`, `blink()`, `blink(fast=True)` and `pulse()`. The robot runs the
pattern by itself, so your program can carry on.

## The RGB LED

```python
--8<-- "lights.py:rgb"
```

Screens and LEDs make every colour by mixing **red, green and blue** light. `(255, 0, 0)` is
full red, `(255, 255, 0)` is red plus green, which looks yellow, and `(255, 255, 255)` is
white. You can also use a name (red, orange, yellow, green, cyan, blue, purple, magenta,
pink, white) or a colour code like `"#ff00aa"`.

## Lights as signals

```python
--8<-- "lights.py:signal"
```

Robots use lights to tell people what they are doing. A blinking yellow light that means
"moving" and a green one that means "done" are easy to see from across the room.

## Things to try

- Make a traffic light: green for 3 seconds, yellow for 1, red for 3, again and again.
- Pick a colour for each direction (forward, left, right) and light it before every move.
- What colour is `(255, 120, 0)`? Guess first, then try it.
