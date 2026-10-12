# Looking through the camera

To a computer, a picture is just a big grid of numbers. Once you see it that way, you can
measure it, change it, and teach the robot to react to what it sees.

## A picture is an array

```python
--8<-- "pixels.py:frame"
```

`bot.camera.frame()` gives the newest picture as a **numpy array**: a grid with one row per
line of the picture and one column per pixel. Each pixel has **3 numbers**, for **blue,
green and red** (in that order: that is how OpenCV, the most used vision library, stores
them). Each number goes from 0 (none) to 255 (full).

## One pixel

```python
--8<-- "pixels.py:pixel"
```

`image[row, column]` picks one pixel. Row 0 is the top of the picture, column 0 the left.

## Many pixels at once

```python
--8<-- "pixels.py:brightness"
```

numpy can work on the whole picture in one go: `image.mean()` is the average of every number
in it. `image[: height // 2]` is the top half (all rows before the middle).

!!! tip "Try it"
    Run `pixels.py` while the robot faces the open floor, then again facing a wall. How do the
    top and bottom halves change?

## Saving a picture

```python
--8<-- "pixels.py:save"
```

The file appears in the same folder as your program.

## Filters

`filters.py` changes every picture as it arrives and shows both on a screen:

```python
--8<-- "filters.py:filters"
```

```python
--8<-- "filters.py:loop"
```

`bot.camera.frames()` gives a new picture every time round the loop, always the newest one.

## Things to try

- Add a filter that swaps red and blue: `image[:, :, ::-1]`.
- Make a "black and white" filter: every pixel brighter than 128 becomes 255, the rest 0.
  (Hint: `(grey > 128) * 255`.)
- Turn the headlights on and off while `pixels.py` measures the bottom half. What changes?
