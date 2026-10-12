# Obstacle avoider

Robot vacuum cleaners do this: drive until something is in the way, turn away, carry on. The
robot uses its **distance sensor**, which measures how far away the nearest thing straight
ahead is.

!!! tip "Try it first"
    Run the app and switch on **Explore the room**. The grey trail on the map shows where the
    robot went; the red dots are what the sensor saw. After a minute, the dots draw the walls
    and boxes.

## The loop

```python
--8<-- "app.py:loop"
```

Every 50 milliseconds the robot goes round the loop: **sense** (read the distance),
**decide** (too close?), **act** (drive or turn).

### Two states

The robot is either **driving** (`turning is None`) or **turning** (`turning` is +1 or -1).
Keeping track of which state it is in is what makes it behave sensibly:

- while driving, it only starts turning when something is **too close**;
- while turning, it only drives again when the way is **clearly free**: 1.5 times further than
  the turning distance.

Why two different distances? With one, the robot would flicker between "turn" and "drive"
right at the border, wobbling instead of turning. Leaving a gap between the two is called
**hysteresis**; thermostats use the same trick.

### Mapping what it saw

The sensor looks straight ahead, so the thing it measured is `distance` metres along the
robot's heading:

```text
x = pose.x + distance · cos(heading)
y = pose.y + distance · sin(heading)
```

## Things to try

- Make the robot always turn the same way. What happens in a corner?
- Set **Turn away when closer than** to 0.15 and the speed to the maximum. Does it still stop
  in time? (Look at the plot.)
- Remove the hysteresis (use `safe.value` for both). What does the robot do now?
- Make the robot slow down as it gets closer: `speed = distance / 4`.

!!! note "Works on"
    Every computer, with the simulator (which has a distance sensor) or a MoveBot with a
    distance sensor module.
