# Follow the blue ball

The robot looks through its camera, finds a blue ball and drives towards it. No
distance sensor, no map: only colours in a picture, and a rule for steering.

**You will learn:** how a camera picture is stored, why robots like the HSV colour space,
how a *mask* picks out one colour, and how *proportional steering* turns "the ball is a bit
to the left" into "turn a bit left".

!!! tip "Try it first"
    Run the app (in the simulator or with the robot). Click on the blue ball in the top
    picture, then switch on **Follow the ball**.

## 1. The screen and the code behind it

Every part of the screen is one line of code. In the MoveBot app, press **</> Code** above
the app and click any part to jump to its line.

```python
--8<-- "app.py:screen"
```

- `app.video(...)` makes the two picture boxes. The first one also has `on_click=pick_colour`:
  clicking it runs the `pick_colour` function.
- `app.toggle(...)` and `app.slider(...)` give you values you can read at any time with
  `.value`, for example `follow.value` is `True` while the switch is on.
- `app.text("Ball")` is a line of text the program changes with `status.value = ...`.

## 2. Finding the ball

A camera picture is a grid of pixels; each pixel has three numbers for blue, green and red.
Shadows change all three, so "blue" is hard to describe in BGR. In **HSV** the *hue* says
which colour it is (blue ≈ 120), *saturation* how strong, and *value* how bright. A blue
ball in shade still has a hue around 120.

```python
--8<-- "app.py:find-ball"
```

1. `cv2.cvtColor` converts the picture to HSV.
2. `cv2.inRange` makes the **mask**: white where the colour is between `low` and `high`.
   That is the second picture on the screen.
3. `cv2.findContours` finds the white blobs, and we keep the biggest one.
4. `cv2.minEnclosingCircle` gives its centre `(x, y)` and `radius` in pixels.

## 3. Teaching the robot a colour

Instead of guessing numbers, click the ball:

```python
--8<-- "app.py:pick-colour"
```

`click.hsv` is the colour under the mouse. We set the sliders to a range around it.

## 4. Steering towards it

```python
--8<-- "app.py:loop"
```

The loop runs once per camera picture. The key line is:

```python
error = (x - width / 2) / (width / 2)   # -1 = far left, +1 = far right
bot.drive(speed.value, -steering.value * error)
```

If the ball is right of the middle, `error` is positive, so the turn rate is negative: the
robot turns right. The further off-centre, the harder it turns. This is called
**proportional control**, and it is how a lot of robots steer.

## Things to try

- Make **Steering strength** very high. What happens, and why? (Hint: the camera picture is
  always a little old by the time the robot reacts.)
- Use the red ball instead: what hue does it have? Why is red tricky in HSV?
- Stop when the ball is close, then back away and turn around.
- Print `bot.camera.latest().t` and the time now: how old is each picture?

!!! note "Works on"
    Windows, macOS, Linux and Raspberry Pi, with the simulator or a MoveBot with a camera.
    Needs OpenCV (`pip install movebot[vision]`; the MoveBot app includes it).
