"""Room scanner: spin around, measure distances, and draw a map of the room.

Each measurement is a dot where the distance sensor hit something. Scan in a few places
(drive with the arrows in between) and the walls and boxes appear on the map.
"""

import math
import time

from movebot import Bot
from movebot.ui import App

bot = Bot()
app = App("Room scanner", bot=bot)

sensors = bot.modules.of_type("distance")
if not sensors:
    raise SystemExit("This app needs a distance sensor (the simulator has one).")
sensor = sensors[0]
MOUNT = 0.06  # m from the middle of the robot to the sensor
points = []  # every spot where the sensor hit something


# --8<-- [start:to_map]
def hit_point(pose, distance):
    """Where the sensor's beam hit something, in map coordinates (metres)."""
    reach = MOUNT + distance  # from the middle of the robot
    return pose.x + reach * math.cos(pose.yaw), pose.y + reach * math.sin(pose.yaw)


# --8<-- [end:to_map]


# --8<-- [start:scan]
def scan():
    """Turn once around on the spot, measuring all the way."""
    status.value = "scanning…"
    bot.rgb_led.pulse("cyan")
    start = bot.pose.heading
    turned, last = 0.0, start
    bot.drive(0, 40)  # turn left slowly, 40 degrees per second
    while turned < 360:
        distance = sensor.distance
        pose = bot.pose
        if distance is not None:
            points.append(hit_point(pose, distance))
            if len(points) % 15 == 0:  # show the map growing while we scan
                view.dots("walls", points, color="#dc2626", size=2.5)
        step = (pose.heading - last + 180) % 360 - 180  # how far we turned since last time
        turned += abs(step)
        last = pose.heading
        time.sleep(0.03)
    bot.stop()
    view.dots("walls", points, color="#dc2626", size=2.5)
    bot.rgb_led.on("green")
    status.value = f"{len(points)} points measured"


# --8<-- [end:scan]

with app.row():
    view = app.map("The room, as the robot measured it", robot=lambda: bot.pose)
    with app.column():
        with app.card("Scan"):
            app.button("Scan here", scan)
            status = app.text("Status", "press Scan here")

            @app.button("Clear the map", style="secondary")
            def clear():
                points.clear()
                view.clear()
                status.value = "map cleared"

        with app.card("Move somewhere else"):

            @app.dpad("Hold an arrow")
            def move(direction):
                if direction == "up":
                    bot.drive(0.15)
                elif direction == "down":
                    bot.drive(-0.15)
                elif direction == "left":
                    bot.drive(0, 60)
                elif direction == "right":
                    bot.drive(0, -60)
                else:
                    bot.stop()

            app.text("Distance ahead", lambda: sensor.distance, unit="m")

app.run()
