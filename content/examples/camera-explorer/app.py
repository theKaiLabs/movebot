"""Camera explorer: picture sizes, speed, colours and brightness, measured live."""

import pathlib
import time

import numpy as np
from movebot import Bot
from movebot.ui import App

bot = Bot()
app = App("Camera explorer", bot=bot)
SNAPSHOTS = pathlib.Path(__file__).with_name("snapshots")

with app.row():
    with app.column():
        view = app.video("What the robot sees")
        # --8<-- [start:plot]
        colours = app.plot("Average colour (0-255)", window=20, min=0, max=255)
        # --8<-- [end:plot]
    with app.column():
        with app.card("Camera settings"):
            # --8<-- [start:preset]
            @app.select("Preset", ["fast", "balanced", "detail"])
            def preset(name):
                bot.camera.configure(name)

            # --8<-- [end:preset]
            size = app.text("Picture size")
            fps = app.text("Pictures per second")
            age = app.text("Age of the picture", unit="ms")
        with app.card("Try"):

            @app.toggle("Headlights")
            def headlights(on):
                bot.lights.level = 1.0 if on else 0.0

            @app.button("Save a snapshot", style="secondary")
            def snapshot():
                SNAPSHOTS.mkdir(exist_ok=True)
                path = bot.camera.save(str(SNAPSHOTS / time.strftime("%H-%M-%S.jpg")))
                saved.value = pathlib.Path(path).name

            saved = app.text("Last snapshot", "none yet")

app.start()

# --8<-- [start:loop]
count, started, last = 0, time.monotonic(), None
while True:
    frame = bot.camera.latest()  # the picture plus when it was taken
    if frame.seq == last:  # the same picture as last time: wait for a new one
        time.sleep(0.01)
        continue
    last = frame.seq
    image = frame.image
    view.show(image)

    height, width = image.shape[:2]
    size.value = f"{width} x {height} pixels"
    age.value = round(frame.age * 1000)

    blue, green, red = image.reshape(-1, 3).mean(axis=0)  # average of every pixel
    colours.add({"red": red, "green": green, "blue": blue, "bright": float(np.mean(image))})

    count += 1
    if time.monotonic() - started >= 1:
        fps.value = round(count / (time.monotonic() - started), 1)
        count, started = 0, time.monotonic()
# --8<-- [end:loop]
