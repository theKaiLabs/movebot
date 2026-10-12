# Your first program

In this tutorial you write a program that drives the robot, run it, and stop it safely.

!!! tip "Simulator or robot?"
    Every tutorial works with the **simulator** (a robot inside the app) and with a real
    MoveBot. Choose one at the top of the app. Start with the simulator: it cannot fall off
    a table. To see what the robot sees while your program runs, open the **Robot camera**
    tab at the bottom of the app.

## The program

```python
--8<-- "hello_robot.py"
```

Press **Open hello_robot.py** above, then **▶ Run** (or F5). Watch the output at the bottom:

```
Connected to MoveBot-1A2B
I am at x=0.300 m, y=0.200 m, heading=90.0°
```

Line by line:

- `from movebot import Bot` loads the MoveBot library.
- `bot = Bot()` connects to the robot. From now on, `bot` *is* your robot.
- `bot.forward(0.3)` drives 0.3 metres (30 cm). The program waits until the move is
  finished before going to the next line.
- `bot.left()` turns left by 90 degrees, on the spot.
- `bot.pose` is where the robot thinks it is: `x` forward and `y` to the left of where it
  started, in metres, and `heading`, which way it faces in degrees.

## Stopping

There are two different stop buttons:

| Button | What it does |
|---|---|
| **Stop robot** (top right, or **Esc**) | Stops the wheels *now*. Your program keeps running. |
| **Stop program** (next to Run) | Ends your program. The robot stops too. |

Press **Esc** whenever the robot does something you did not expect.

## Try it in the Python shell

The **Python shell** tab at the bottom runs one line at a time, with `bot` already
connected. Type these and press Enter after each:

```python
bot.forward(0.1)
bot.right(45)
bot.pose
```

The shell is great for trying things out; a program is for keeping what works.

## Things to try

- Make the robot drive a capital **L**: forward, turn, forward.
- What does `bot.right(180)` do? And `bot.back(0.2)`?
- Change `0.3` to `3`. What happens when the robot reaches a wall?
