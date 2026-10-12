# Your own screen

With the UI kit, a few lines of Python give your program a screen with buttons, sliders and
live values. No HTML needed. Run `remote.py` to see the result: the screen opens right next to
the code.

## The app

```python
--8<-- "remote.py:app"
```

`App` is the screen. Giving it `bot=bot` means: when the app closes, or you press the space
bar, the robot stops.

```python
--8<-- "remote.py:run"
```

`app.run()` shows the screen and keeps the program running until you stop it.

## Parts of the screen

Every `app.something(...)` adds one part, in order, from the top. `with app.row():` puts parts
side by side, `with app.column():` stacks them, and `with app.card("Title"):` draws a box.

**Camera:**

```python
--8<-- "remote.py:camera"
```

**A slider** gives a value you read with `.value` whenever you need it:

```python
--8<-- "remote.py:slider"
```

## Functions become buttons

Put `@app.button(...)` above a function and the function *becomes* a button: clicking it runs
the function. This `@` line is called a **decorator**.

```python
--8<-- "remote.py:button"
```

The same trick works for other parts. The function gets what happened as a parameter:

```python
--8<-- "remote.py:dpad"
```

```python
--8<-- "remote.py:select"
```

And `@app.output` shows whatever the function **returns**, updated a few times a second:

```python
--8<-- "remote.py:output"
```

## Which code made what?

Press **</> Show code** above the screen, then click any part of it: the app jumps to the line
that made it. Lessons use the same trick to explain the example apps.

!!! note "Everything the UI kit can do"
    The full list (toggles, text boxes, joysticks, keyboards, plots, maps, logs, ...) is in
    **Docs → UI kit: App**.

## Things to try

- Add a "Square" button that drives a square.
- Add an `@app.output("Battery")` that returns `bot.battery`.
- Add a toggle: `@app.toggle("Headlights")` gets `True` or `False`.
