# Drive with buttons

Your first MoveBot app: a few buttons that move the robot, a slider for its speed, and a
live read-out of where it is.

The trick: **every function becomes a button**. Writing `@app.button("Forward 20 cm")`
above a function puts a button on the screen, and clicking it runs the function.

```python
@app.button("Draw a square")
def square():
    for _ in range(4):
        bot.forward(0.3)   # metres
        bot.left()         # 90 degrees
```

`@app.slider` works the same way, except the function gets the slider's value, and
`@app.output` shows whatever the function returns, updated a few times per second.

## Things to try

- Add a button that draws a triangle. (How many degrees must each turn be?)
- Add a "Spin" button using `bot.spin()`.
- Draw a square with a route instead: `bot.route().forward(0.3).left()...run()` – and print
  the result to see how far off the robot ended up.
- Press the space bar while the robot is driving. What happens?

!!! note "Works on"
    Every computer, with the simulator or a MoveBot. No extra packages needed.
