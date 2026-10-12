"""Change the camera picture with numpy and show it on a screen."""

import numpy as np
from movebot import Bot
from movebot.ui import App

bot = Bot()
app = App("Picture filters", bot=bot)

with app.row():
    original = app.video("What the camera sees")
    changed = app.video("After the filter")
    with app.card("Filter"):
        choice = app.select("Filter", ["grey", "negative", "only red", "brighter"])


# --8<-- [start:filters]
def apply(image, name):
    if name == "grey":
        grey = image.mean(axis=2)  # average of blue, green and red, for every pixel
        return grey.astype(np.uint8)
    if name == "negative":
        return 255 - image  # dark becomes light and light becomes dark
    if name == "only red":
        result = image.copy()
        result[:, :, 0] = 0  # no blue
        result[:, :, 1] = 0  # no green
        return result
    if name == "brighter":
        return np.clip(image.astype(int) + 60, 0, 255).astype(np.uint8)
    return image


# --8<-- [end:filters]

app.start()  # show the screen, then run our own loop
# --8<-- [start:loop]
for image in bot.camera.frames():
    original.show(image)
    changed.show(apply(image, choice.value))
# --8<-- [end:loop]
