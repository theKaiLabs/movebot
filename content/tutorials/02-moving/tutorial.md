# Moving: distances, turns and speed

The robot measures distances in **metres** and angles in **degrees**. Every move waits until
it is finished, so the robot always does them in the order you wrote them.

## Straight lines

```python
--8<-- "moves.py:straight"
```

`bot.speed` is a speed **limit** in percent: 100 is as fast as the robot can go. Slower moves
are more precise.

## Turning on the spot

```python
--8<-- "moves.py:turns"
```

- `left()` and `right()` turn by an amount (90° if you do not say).
- `turn(degrees)` does both: positive numbers turn left, negative ones right. This is the
  mathematician's way: angles grow counter-clockwise.
- `turn_to(heading)` turns until the robot *faces* a direction, wherever it faces now.
  `0` is the direction it faced at the start (or at the last `reset_odometry()`).

## Curves

```python
--8<-- "moves.py:curves"
```

`arc(radius, degrees)` drives along a circle. The bigger the radius, the wider the curve.

## Where am I?

```python
--8<-- "moves.py:pose"
```

The robot counts how far each wheel turns (with *encoders*) and works out where it must be.
This is called **odometry**. It is good, but not perfect: wheels slip a little, so after many
moves the robot is not exactly where it thinks it is.

!!! note "Try it"
    Run `moves.py`. In theory the robot ends up back at the start, facing the same way.
    How close does it get? Run it twice: is the error the same each time?

## Things to try

- Make the robot drive a circle with `arc`. What radius fits in your arena?
- Use `turn_to` to make the robot face 0°, 90°, 180° and -90° in turn.
- Set `bot.speed = 20` and then `100`. Does speed change how precise the moves are?
