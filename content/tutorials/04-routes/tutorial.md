# Routes: give the robot a whole plan

So far your program told the robot one move at a time, and waited after each. A **route** is
a list of moves that you build first and then hand to the robot in one go. The robot keeps
driving it even if the Wi-Fi drops for a moment, and your program is free to do other things.

## Building a route

```python
--8<-- "delivery.py:build"
```

Building a route sends nothing to the robot yet. Each line adds moves; they can be chained
with dots. Besides the moves you know, a route can:

- `go_to(x, y)` drive to a spot (it works out the turn and the distance for you),
- `marker("name")` report when the robot gets there,
- `lights_on()`, `rgb_led("blink", "red")`, `wait(1)`, `speed(50)`.

## Checking the plan

```python
--8<-- "delivery.py:preview"
```

`preview()` works out where the robot *should* be after each move, without moving. Handy for
checking your maths before you drive.

## Driving it

```python
--8<-- "delivery.py:markers"
```

```python
--8<-- "delivery.py:background"
```

`run()` sends the route. With `wait=False` your program carries on straight away; the
**handle** tells you how far the robot got. Without it, `run()` waits until the end.

## Plan versus reality

```python
--8<-- "delivery.py:result"
```

The result compares where each move *should* have ended with where the robot measured it
ended. That difference is **drift**.

!!! tip "Write a route as text"
    `Route.parse("forward 0.5; left; forward 0.3; marker shop")` builds the same thing from
    text, so a route can come from a file, or from a text box in your own app.

## Things to try

- Add a fourth stop, the "library", and a marker for it.
- Make the robot blink its RGB LED green at every stop: `.rgb_led("blink", "green")`.
- While the route runs, press **Esc**. What does `result.ok` say now, and why?
