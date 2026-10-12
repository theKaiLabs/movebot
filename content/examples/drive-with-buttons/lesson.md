# Drive with buttons

Your first MoveBot app: the robot's camera, arrows that move it one step at a time, a button
that draws a square, a slider for its speed, and a live read-out of where it is.

!!! tip "Try it first"
    Press **▶ Run**. Click the arrows (or use the arrow keys) and watch the camera picture
    change. Then press **Draw a square**.

## Every function becomes part of the screen

Writing `@app.button("Draw a square")` above a function puts a button on the screen, and
clicking it runs the function:

```python
--8<-- "app.py:square"
```

`@app.slider` works the same way, except the function gets the slider's value, and
`@app.output` shows whatever the function returns, updated a few times per second.

## The arrows

`@app.dpad` makes four arrow buttons. When you press one, the function gets the direction:
`"up"`, `"down"`, `"left"` or `"right"`. When you let go it gets `None`.

```python
--8<-- "app.py:dpad"
```

Each press is one move: 20 cm forward or back, or a 90° turn. Want to *hold* an arrow to keep
driving instead? Open the **Test drive** app and see how it uses `bot.drive(...)` and
`bot.stop()`.

## The camera

One line shows what the robot sees:

```python
--8<-- "app.py:camera"
```

## Things to try

- Make the arrows move 10 cm instead of 20 cm. Make left and right turn 45°.
- Add a button that draws a triangle. (How many degrees must each turn be?)
- Add a "Spin" button using `bot.spin()`.
- Draw a square with a route instead: `bot.route().forward(0.3).left()...run()`, and print
  the result to see how far off the robot ended up.
- Press the space bar while the robot is driving. What happens?

!!! note "Works on"
    Every computer, with the simulator or a MoveBot. No extra packages needed.
