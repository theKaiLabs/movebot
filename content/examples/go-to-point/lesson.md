# Go to a point

Click anywhere on the map and the robot drives there. Not by planning the trip in advance, but
by **correcting itself many times a second**, like you do when you walk towards a door.
That is **feedback control**, and almost every robot uses it.

!!! tip "Try it first"
    Run the app and click on the map. Then click somewhere behind the robot. Watch the plot:
    the distance shrinks and the heading error goes to zero.

## The control loop

```python
--8<-- "app.py:control"
```

Every 50 ms:

1. **Where is the goal, seen from the robot?** `dx` and `dy` point from the robot to the
   goal. `math.atan2(dy, dx)` turns them into a direction, and subtracting the robot's own
   heading gives the **heading error**: how far it has to turn. `wrap` keeps it between
   -180° and 180°, so the robot turns the short way round.
2. **Steer in proportion to the error.** Facing far away from the goal: turn hard. Almost
   facing it: turn gently. This is **proportional control**.
3. **Drive in proportion to how well it is aimed.** `cos(heading_error)` is 1 when facing the
   goal and 0 at 90°, so the robot slows down while it turns, and never drives away from the
   goal. Near the goal, `min(top_speed, distance)` slows it down too.

## Tuning

```python
--8<-- "app.py:gains"
```

The **steering strength** (the *gain*) decides how hard the robot reacts. Too low and it
drives in wide, lazy curves. Too high and it overshoots and wobbles, because by the time it
reacts, it has already turned past the goal.

## Plan versus feedback

```python
--8<-- "app.py:route"
```

A route turns once and then drives straight, without looking again: **open loop**. The
feedback loop keeps checking: **closed loop**. In the simulator both work well; on a real
floor with slipping wheels, which one would you trust more?

## Things to try

- Find the highest steering strength that does not wobble.
- Make the robot also *face* a direction when it arrives (hint: a second phase that only
  turns).
- Click several spots quickly. The robot changes its mind: why is that easy with feedback,
  and hard with a route?

!!! note "Works on"
    Every computer, with the simulator or a MoveBot.
