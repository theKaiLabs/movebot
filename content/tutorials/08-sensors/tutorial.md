# Sensors and add-ons

The robot can carry **add-on modules**: a distance sensor, a motion sensor (IMU), and more
later. Your program can ask which ones are plugged in and read them like any other value.

!!! note "In the simulator"
    The app's simulated robot has a distance sensor at the front (`front_distance`) and an
    IMU (`imu`). A real MoveBot only has the modules you plug in.

## What is plugged in?

```python
--8<-- "what_is_plugged_in.py:list"
```

Every module has an `id` (its name on this robot), a `type` (what kind of module it is), and
values you can read. You can also reach one by its id: `bot.modules.front_distance.distance`.

## Finding a distance sensor

```python
--8<-- "stop_in_time.py:find"
```

Asking for a *type* instead of an id makes your program work on any robot with that kind of
sensor, whatever it is called.

## Reacting: a loop with a decision

```python
--8<-- "stop_in_time.py:loop"
```

This is the heart of most robot programs:

1. **Sense**: read the sensor.
2. **Decide**: is it closer than 20 cm?
3. **Act**: keep going, or stop.

…and do it again, many times a second. `bot.drive(speed)` starts the wheels and keeps them
turning, so the loop can check the sensor while the robot moves.

!!! warning "Why not exactly 20 cm?"
    The robot keeps moving for a moment while the program reads, decides and sends `stop`.
    Faster driving means stopping later. Try different speeds and measure.

In the simulator the robot starts facing a blue ball, so that is what it stops in front of.
Turn it towards a wall first (`bot.left()` before the loop) to stop at the wall instead.

## Things to try

- Stop at 10 cm, then 50 cm. How accurate is it at each speed?
- Instead of stopping, turn left until the way is clear and carry on driving.
- Show the distance on the RGB LED: green when far, yellow when close, red when very close.
