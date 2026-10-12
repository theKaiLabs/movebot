"""Follow the blue ball.

The camera looks for the ball by its colour. When "Follow the ball" is on, the robot
turns towards the ball and drives up to it.

Run it with a robot, or first start the simulator in another terminal: movebot sim
"""

import cv2
import numpy as np
from movebot import Bot
from movebot.ui import App

bot = Bot()
app = App("Follow the ball", bot=bot)


# --8<-- [start:find-ball]
def find_ball(image, low, high):
    """Find the biggest blob whose colour is between low and high (HSV).

    Returns ((x, y, radius) or None, mask).
    """
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)  # hue tells colours apart, even in shade
    mask = cv2.inRange(hsv, low, high)  # white where the colour matches
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None, mask
    biggest = max(contours, key=cv2.contourArea)
    (x, y), radius = cv2.minEnclosingCircle(biggest)
    if radius < 3:  # a few stray pixels are not a ball
        return None, mask
    return (x, y, radius), mask


# --8<-- [end:find-ball]


# --8<-- [start:pick-colour]
def pick_colour(click):
    """Click on the ball in the picture to teach the robot its colour."""
    hue, saturation, value = click.hsv
    hue_from.value = max(0, hue - 12)
    hue_to.value = min(179, hue + 12)
    min_saturation.value = max(40, saturation - 80)
    min_brightness.value = max(40, value - 80)


# --8<-- [end:pick-colour]


# --8<-- [start:screen]
with app.row():
    with app.column():
        camera_view = app.video(
            "What the robot sees (click the ball to pick its colour)", on_click=pick_colour
        )
        mask_view = app.video("Pixels that match the colour")
    with app.column():
        with app.card("Robot"):
            follow = app.toggle("Follow the ball")
            speed = app.slider("Speed", 0.05, 0.3, 0.12, step=0.01, unit="m/s")
            steering = app.slider("Steering strength", 10, 120, 60, unit="°/s")
            status = app.text("Ball")
        with app.card("Colour of the ball (HSV)"):
            hue_from = app.slider("Hue from", 0, 179, 100)
            hue_to = app.slider("Hue to", 0, 179, 130)
            min_saturation = app.slider("Saturation at least", 0, 255, 120)
            min_brightness = app.slider("Brightness at least", 0, 255, 70)
# --8<-- [end:screen]

app.start()
driving = False

# --8<-- [start:loop]
for image in bot.camera.frames():
    low = np.array([hue_from.value, min_saturation.value, min_brightness.value])
    high = np.array([hue_to.value, 255, 255])
    ball, mask = find_ball(image, low, high)

    width = image.shape[1]
    if ball is None:
        status.value = "not seen"
    else:
        x, y, radius = ball
        cv2.circle(image, (int(x), int(y)), int(radius), (0, 255, 255), 2)
        cv2.line(image, (width // 2, 0), (width // 2, image.shape[0]), (255, 255, 255), 1)
        status.value = f"seen at x={x:.0f} px, {2 * radius:.0f} px wide"
    camera_view.show(image)
    mask_view.show(mask)

    if not follow.value:
        if driving:
            bot.stop()
            driving = False
        continue

    driving = True
    if ball is None:
        bot.drive(0, 30)  # look around: turn left slowly
    elif radius > width * 0.15:
        bot.drive(0, 0)  # close enough: wait here
        status.value = "found it!"
    else:
        error = (x - width / 2) / (width / 2)  # -1 = far left, +1 = far right
        bot.drive(speed.value, -steering.value * error)  # turn towards the ball
# --8<-- [end:loop]
