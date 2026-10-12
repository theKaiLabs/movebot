# Colour detective

Click on anything in the camera picture. The app tells you its colour in two ways, lights the
robot's RGB LED in that colour, and shows every pixel that has a similar colour.

!!! tip "Try it first"
    Run the app and click the blue ball, then the red one, then the floor. Move the
    **How similar** slider and watch the second picture.

## Picking a colour

```python
--8<-- "app.py:pick"
```

`click.color` is the pixel's colour as **blue, green, red** numbers from 0 to 255.
`(red, green, blue)` is also how the RGB LED is told which colour to show.

The same colour as **hue, saturation, value** (HSV):

- **hue**: which colour it is, as a position on a colour wheel (OpenCV uses 0-179:
  red ≈ 0, yellow ≈ 30, green ≈ 60, blue ≈ 120),
- **saturation**: how strong the colour is (grey = 0),
- **value**: how bright it is.

Shadows change all three RGB numbers, but hardly change the hue. That is why robots look for
colours by **hue**.

## Finding similar pixels

```python
--8<-- "app.py:mask"
```

This works on the whole picture at once. `hue_gap` is how far each pixel's hue is from the
picked one. Hue goes round in a circle, so 178 and 2 are only 4 apart. A pixel counts when its
hue is close enough **and** it is colourful (grey floors have random hues).

## The share of the picture

```python
--8<-- "app.py:loop"
```

The mask is a grid of `True`/`False`. Python counts `True` as 1, so the **mean** of the mask
is the share of pixels that match.

## Things to try

- Pick the floor. Why does almost nothing match? (Look at its saturation.)
- Drive closer to the blue ball. How does the share change? Could the robot use that to
  guess the distance?
- Light the LED in the *opposite* colour: hue + 90 (in OpenCV units).

!!! note "Works on"
    Windows, macOS, Linux and Raspberry Pi, with the simulator or a MoveBot with a camera.
    Needs OpenCV (`pip install movebot[vision]`; the MoveBot app includes it).
