# Room scanner

A distance sensor only measures one number: how far away the nearest thing straight ahead is.
Turn around while measuring, and you get the shape of the room. This is how robot vacuum
cleaners and self-driving cars build maps (with faster spinning sensors called *lidar*).

!!! tip "Try it first"
    Run the app and press **Scan here**. Red dots appear where the sensor hit something.
    Drive to another spot with the arrows and scan again: more of the room appears.

## From a distance to a dot on the map

```python
--8<-- "app.py:to_map"
```

The sensor points the way the robot faces (its heading). Something `distance` metres away in
that direction is at:

```text
x = robot x + distance · cos(heading)
y = robot y + distance · sin(heading)
```

`cos` and `sin` split a distance in a direction into "how far along x" and "how far along y".
The sensor sits at the front of the robot, so `MOUNT` is added first.

## Scanning

```python
--8<-- "app.py:scan"
```

The robot turns slowly and measures about 30 times a second. Counting how far it has turned
is a little tricky: the heading jumps from 180° to -180°, so each step is wrapped into
-180°…180° before adding it up.

## Things to try

- Scan in three different places. Do the walls from different scans line up? If not, why?
  (Hint: the map uses the robot's *own idea* of where it is: odometry.)
- Turn faster (change 40 to 120). What happens to the map?
- Draw lines instead of dots: `view.line("walls", points)`. When does that look right, and
  when wrong?
- Find the closest thing in a scan and drive towards it.

!!! note "Works on"
    Every computer, with the simulator (which has a distance sensor) or a MoveBot with a
    distance sensor module.
