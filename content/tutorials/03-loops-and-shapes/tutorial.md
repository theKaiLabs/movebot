# Loops and shapes

A square is "forward, turn" four times. Instead of writing the same two lines four times,
let Python repeat them.

## A loop

```python
--8<-- "square.py"
```

`for side in range(4):` runs the indented lines four times. Each time `side` holds the next
number: 0, 1, 2 and 3 (Python counts from 0).

## Any shape: a function

Why 90° for a square? The robot turns a little at every corner, and by the time it is back
at the start it has turned **once all the way round**: 360°. A square has 4 corners, so each
turn is 360 ÷ 4 = 90°. A triangle needs 360 ÷ 3 = 120°.

That rule works for every regular shape, so we can write it once as a **function**:

```python
--8<-- "polygons.py:polygon"
```

`sides` and `length` are **parameters**: blanks that get filled in when you use the function.

```python
--8<-- "polygons.py:use"
```

## Things to try

- Draw a pentagon, an octagon and a 12-sided shape. When does it start to look like a circle?
- Add a third parameter, `turn_right=False`, and make the shape go the other way when it is
  `True`.
- A star: drive forward and turn **144°**, five times. Why 144? (Hint: this time the robot
  turns round *twice* before it is back.)
- Change `bot.left(turn)` to `bot.left(turn + 5)`. What happens after many sides?
