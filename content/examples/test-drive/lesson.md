# Test drive

Before writing any code, get to know the robot: drive it around, look through its camera, and
watch its position change.

!!! tip "Try it first"
    Press **▶ Run**. Hold the up arrow to drive forward and let go to stop. The arrow keys
    and W A S D work too. Press **Esc** (or the space bar) at any time to stop the robot.

## Holding an arrow

```python
--8<-- "app.py:drive"
```

`bot.drive(speed, turn_rate)` starts the wheels and **keeps them going**: speed in metres per
second, turning in degrees per second (positive turns left). The robot only stops when
something tells it to, here `bot.stop()` when you let go of the arrow.

Compare this with *Drive with buttons*, where every click is one complete move such as
`bot.forward(0.2)`.

## Where am I?

The robot counts how far each wheel turns and works out where it is: `x` and `y` in metres
from where it started, and which way it faces (`heading`, in degrees). **Reset position**
makes the current spot the new start.

## Things to try

- Drive one metre forward by eye, then look at the position. How close were you?
- Drive in a circle and come back to the start. Is the position back at 0, 0? Why not
  exactly?
- Open the code and make the robot slower when it drives backwards.

!!! note "Works on"
    Every computer, with the simulator or a MoveBot. No extra packages needed.
