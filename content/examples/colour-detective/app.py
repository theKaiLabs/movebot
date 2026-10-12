"""Colour detective: click anything in the picture to find out its colour.

The RGB LED copies the colour you picked, and the second picture shows every pixel with a
similar colour.
"""

import cv2
import numpy as np
from movebot import Bot
from movebot.ui import App

bot = Bot()
app = App("Colour detective", bot=bot)
picked = {"hsv": None}  # the colour we are looking for


# --8<-- [start:pick]
def pick(click):
    blue, green, red = click.color  # OpenCV order: blue, green, red
    hue, saturation, value = click.hsv
    picked["hsv"] = click.hsv
    rgb_text.value = f"red {red}, green {green}, blue {blue}  (#{red:02x}{green:02x}{blue:02x})"
    hsv_text.value = f"hue {hue}, saturation {saturation}, value {value}"
    bot.rgb_led.on((red, green, blue))  # show the colour on the robot


# --8<-- [end:pick]


# --8<-- [start:mask]
def similar(image, hsv, tolerance):
    """True for every pixel whose hue is close to the picked one (and colourful enough)."""
    hue, saturation, _ = hsv
    pixels = cv2.cvtColor(image, cv2.COLOR_BGR2HSV).astype(int)
    hue_gap = np.abs(pixels[:, :, 0] - hue)
    hue_gap = np.minimum(hue_gap, 180 - hue_gap)  # hue goes round in a circle
    colourful = pixels[:, :, 1] > max(40, saturation // 2)
    return (hue_gap <= tolerance) & colourful


# --8<-- [end:mask]

with app.row():
    with app.column():
        camera_view = app.video("Click on something", on_click=pick)
        mask_view = app.video("Pixels with a similar colour")
    with app.card("What colour is it?"):
        rgb_text = app.text("Red, green, blue", "click the picture")
        hsv_text = app.text("Hue, saturation, value")
        tolerance = app.slider("How similar (hue)", 2, 30, 10)
        share = app.meter("Share of the picture", 0, unit="%")

app.start()

# --8<-- [start:loop]
for image in bot.camera.frames():
    camera_view.show(image)
    if picked["hsv"] is None:
        continue
    mask = similar(image, picked["hsv"], tolerance.value)
    mask_view.show(mask)
    share.value = round(100 * mask.mean(), 1)  # True counts as 1, so the mean is a share
# --8<-- [end:loop]
