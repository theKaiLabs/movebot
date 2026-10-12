# Camera explorer

A camera is a trade-off: bigger pictures show more detail, but they take longer to send, so
fewer arrive each second and each one is older by the time your program sees it. This app
measures all of that live.

!!! tip "Try it first"
    Run the app and switch the **Preset** between *fast*, *balanced* and *detail*. Watch the
    picture size, the pictures per second and the age of each picture.

## Presets

```python
--8<-- "app.py:preset"
```

| Preset | Size | Pictures per second (at most) | Good for |
|---|---|---|---|
| fast | 320 x 240 | 25 | Steering, following things |
| balanced | 640 x 480 | 15 | Most projects |
| detail | 1280 x 720 | 8 | Reading signs, taking photos |

## Measuring

```python
--8<-- "app.py:loop"
```

- `bot.camera.latest()` gives the newest picture **with details**: `frame.image` is the numpy
  array, `frame.age` how many seconds ago it arrived, and `frame.seq` its number. If the
  number is the same as last time, no new picture has arrived yet.
- `image.reshape(-1, 3)` turns the grid of pixels into one long list of `[blue, green, red]`,
  and `.mean(axis=0)` averages each column: the average colour of the whole picture.
- Counting pictures for one second gives the **frame rate**.

```python
--8<-- "app.py:plot"
```

`colours.add({...})` adds one point to each line of the plot.

## Things to try

- Turn on the **Headlights**. Which line in the plot changes most? Why?
- Drive up to the red ball (Test drive helps). What happens to the red line?
- Which preset would you choose for following a ball? For reading a sign? Explain why.
- Snapshots are saved in the `snapshots` folder next to `app.py`. Open one.

!!! note "Works on"
    Every computer, with the simulator or a MoveBot with a camera.
