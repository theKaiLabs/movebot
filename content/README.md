# Tutorials, examples and lessons

The MoveBot app copies this folder into the student's workspace. **Tutorials** are step-by-step
lessons with small programs, in order; **examples** are working apps with their own screen
(built with `movebot.ui`) and a lesson each. Both appear in the app's *Learn* mode (tutorials
also under *Docs*), and examples in the *Apps* gallery.

```
tutorials/03-loops-and-shapes/
  tutorial.toml   # id, title, summary, order, minutes, concepts, needs, platforms, licence
  tutorial.md     # the tutorial; shows parts of the programs next to it
  square.py       # programs the tutorial explains (the app offers to open them)
  polygons.py

examples/follow-the-ball/
  example.toml    # title, level, icon, minutes, concepts, needs, platforms, licence, ...
  app.py          # the program, with its screen
  lesson.md       # the lesson; shows parts of app.py (see below)
```

A lesson shows a part of a program with a snippet inside a code fence:

````markdown
```python
--8<-- "app.py:find-ball"
```
````

and the part is marked in the program with comments (indented code is shown from column 0):

```python
# --8<-- [start:find-ball]
def find_ball(image, low, high):
    ...
# --8<-- [end:find-ball]
```

`--8<-- "square.py"` (no part name) shows a whole file.

## Tutorials

| # | Tutorial | What it teaches |
|---|---|---|
| 1 | [Your first program](tutorials/01-first-program/) | running a program, the bot object, stopping, the Python shell |
| 2 | [Moving](tutorials/02-moving/) | metres and degrees, turns, arcs, speed, odometry |
| 3 | [Loops and shapes](tutorials/03-loops-and-shapes/) | for loops, functions, parameters, polygon angles |
| 4 | [Routes](tutorials/04-routes/) | plans, previewing, markers, drift, running in the background |
| 5 | [Lights and LEDs](tutorials/05-lights-and-leds/) | headlights, status LED, RGB colours, signalling |
| 6 | [Your own screen](tutorials/06-your-own-screen/) | the UI kit: buttons, sliders, arrows, live values |
| 7 | [Looking through the camera](tutorials/07-camera/) | images as numpy arrays, pixels, filters |
| 8 | [Sensors and add-ons](tutorials/08-sensors/) | modules, distance sensor, sense-decide-act |

## Examples (two per level)

| Example | Level | What it teaches |
|---|---|---|
| [drive-with-buttons](examples/drive-with-buttons/) | 0 Meet | functions become buttons; arrows; the camera |
| [test-drive](examples/test-drive/) | 0 Meet | driving at a speed, stopping, position from the wheels |
| [draw-shapes](examples/draw-shapes/) | 1 Move | routes, polygon angles, plan versus reality, the map |
| [light-show](examples/light-show/) | 1 Move | routes with lights, RGB colours, timing |
| [camera-explorer](examples/camera-explorer/) | 2 See | resolution, frame rate, latency, average colour |
| [colour-detective](examples/colour-detective/) | 2 See | RGB and HSV, hue, masks |
| [follow-the-ball](examples/follow-the-ball/) | 3 React | camera images, HSV colour, masks, proportional steering |
| [obstacle-avoider](examples/obstacle-avoider/) | 3 React | sense-decide-act, thresholds, hysteresis, states |
| [teach-by-showing](examples/teach-by-showing/) | 4 Learn | machine learning, features, k-nearest neighbours |
| [webcam-gestures](examples/webcam-gestures/) | 4 Learn | training data, normalising, confidence thresholds |
| [go-to-point](examples/go-to-point/) | 5 Robotics | feedback control, atan2, open versus closed loop |
| [room-scanner](examples/room-scanner/) | 5 Robotics | mapping, coordinate frames, odometry drift |

In the MoveBot app, open the *Apps* gallery. From a checkout with the app's Python,
run one against the simulator:

```bash
uv run movebot sim                                   # in one terminal
uv run python content/examples/follow-the-ball/app.py   # in another
```

Teachers can add their own tutorials and examples in the app's workspace: any folder with a
`tutorial.toml` + `tutorial.md`, or an `example.toml` + `app.py` (+ `lesson.md`), appears in
the app.

Everything is checked in CI (the tests live in the MoveBot app's repository, which includes
this one): the `.toml` files have the required fields, every snippet a lesson uses exists,
every example app starts against the simulator, every tutorial program runs, and there are
two examples per level.
