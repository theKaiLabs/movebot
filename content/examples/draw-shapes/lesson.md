# Draw shapes

Choose a shape, check the plan on the map, and let the robot drive it. Then compare: did the
robot end up where the plan said?

!!! tip "Try it first"
    Run the app. Move the **Sides** slider and watch the dashed plan change. Press
    **Drive it**: the grey trail shows where the robot really went.

## A shape is a route

```python
--8<-- "app.py:route"
```

A regular shape is "forward, turn" again and again. All the turns add up to one full turn,
so each turn is `360 / sides` degrees. The function does not drive anything: it builds a
**route**, a plan the robot can drive later.

## Checking the plan before driving

```python
--8<-- "app.py:plan"
```

`route.preview(start)` works out where the robot should be after every move, starting from
where it is now. `view.line(...)` draws those corners on the map as a dashed line. The sliders
call `show_plan` whenever they move, so the plan always matches them.

## Driving it

```python
--8<-- "app.py:drive"
```

`route.run()` sends the whole plan to the robot and waits until it is done. The result says
whether every move went well and how far the end (as the wheels measured it) **drifted** from
the plan.

## Things to try

- Which shape drifts most: a triangle or a 10-sided shape? Why might that be?
- Add a "Star" button: five times forward and turn **144°**.
- Draw two shapes in a row without going home in between. Does the drift add up?
- Change the route so the robot blinks its RGB LED at every corner:
  `route.rgb_led("blink", "blue")`.

!!! note "Works on"
    Every computer, with the simulator or a MoveBot.
