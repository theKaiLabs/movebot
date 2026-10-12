# Light show

A route is not only moves: it can switch lights, change the RGB LED and wait. The robot then
does all of it by itself, with perfect timing.

!!! tip "Try it first"
    Run the app and press **Police car**. In the simulator the headlights and LEDs are shown
    in the bottom-left corner of the camera picture, and the headlights light up the floor.

## A police car

```python
--8<-- "app.py:police"
```

Each pass of the loop adds four steps: red with the left light, wait, blue with the right
light, wait. Six passes make a three-second show. Nothing is sent until `run()`.

**Why a route?** If your program switched the lights itself, every change would travel over
Wi-Fi, and a slow moment would make the blinking stutter. The robot keeps a route's timing on
its own.

## Moving and lighting together

```python
--8<-- "app.py:disco"
```

Steps run one after another: the LED changes colour, then the robot turns 45°, eight times
round. `spin(360)` with the lights on makes a lighthouse.

## One button per show

```python
--8<-- "app.py:buttons"
```

A loop can make buttons too. (`lambda make=make:` keeps each button's own show; without
`make=make` every button would run the last one.)

## Your own colours

```python
--8<-- "app.py:colour"
```

## Things to try

- Make a birthday show: the RGB LED counts through your age in blinks.
- Add an ambulance: blue only, blinking fast, and the robot drives slowly forward.
- Write a show as text: `Route.parse("rgb on red; wait 0.5; rgb on #00ff00; spin 360")`.

!!! note "Works on"
    Every computer, with the simulator or a MoveBot.
