"""Obstacle avoider: explore the room without bumping into anything.

The distance sensor looks ahead. When something is too close, the robot turns until the
way is clear, then drives on. The map shows where it went and what it saw.
"""

import math
import random
import time

from movebot import Bot
from movebot.ui import App

bot = Bot()
app = App("Obstacle avoider", bot=bot)

sensors = bot.modules.of_type("distance")
if not sensors:
    raise SystemExit("This app needs a distance sensor (the simulator has one).")
sensor = sensors[0]

with app.row():
    with app.column():
        view = app.map("Where it went (red: what the sensor saw)", robot=lambda: bot.pose)
        readings = app.plot("Distance ahead", window=20, min=0, max=2, unit="m")
    with app.column():
        with app.card("Explore"):
            explore = app.toggle("Explore the room")
            speed = app.slider("Speed", 0.05, 0.3, 0.15, step=0.01, unit="m/s")
            safe = app.slider("Turn away when closer than", 0.15, 0.6, 0.3, step=0.05, unit="m")
            state = app.text("Doing", "waiting")
            distance_meter = app.meter("Distance ahead", min=0, max=2, unit="m")
        app.video("What the robot sees", bot.camera)

app.start()

# --8<-- [start:loop]
seen = []  # spots where the sensor found something
turning = None  # None while driving, else +1 (left) or -1 (right)
moving = False
loops = 0
while True:
    distance = sensor.distance  # metres, or None if nothing is within 2 m
    distance_meter.value = distance
    readings.add(distance)

    loops += 1
    if distance is not None and loops % 10 == 0:  # twice a second: add to the map
        pose = bot.pose
        seen.append(
            (pose.x + distance * math.cos(pose.yaw), pose.y + distance * math.sin(pose.yaw))
        )
        view.dots("seen", seen[-300:], color="#dc2626", size=2.5)

    if not explore.value:
        if moving:
            bot.stop()
            moving, turning = False, None
            bot.rgb_led.off()
        state.value = "waiting"
        time.sleep(0.1)
        continue

    too_close = distance is not None and distance < safe.value
    clear = distance is None or distance > safe.value * 1.5
    if turning is None and too_close:
        turning = random.choice([1, -1])  # pick a side and turn until the way is clear
    elif turning is not None and clear:
        turning = None

    if turning is None:
        bot.drive(speed.value)
        bot.rgb_led.on("green")
        state.value = "driving"
    else:
        bot.drive(0, 90 * turning)
        bot.rgb_led.on("red")
        state.value = "turning " + ("left" if turning > 0 else "right")
    moving = True
    time.sleep(0.05)
# --8<-- [end:loop]
