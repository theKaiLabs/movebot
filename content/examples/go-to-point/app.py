"""Go to a point: click on the map and the robot steers there with feedback control.

Every 50 ms the robot compares where it is with where it should go, and corrects its
speed and steering. Compare it with a route, which plans the whole trip in advance.
"""

import math
import time

from movebot import Bot
from movebot.ui import App

bot = Bot()
app = App("Go to a point", bot=bot)
goal = {"x": None, "y": None}


def set_goal(x, y):
    goal.update(x=x, y=y)
    view.dots("goal", [(x, y)], color="#16a34a", size=7)
    status.value = f"going to x={x:.2f}, y={y:.2f}"


with app.row():
    with app.column():
        view = app.map("Click to choose where to go", robot=lambda: bot.pose, on_click=set_goal)
        errors = app.plot("Distance left (m) and heading error (°/100)", window=20)
    with app.column():
        with app.card("Feedback control"):
            # --8<-- [start:gains]
            steer_gain = app.slider("Steering strength", 0.5, 6.0, 2.5, step=0.5)
            top_speed = app.slider("Top speed", 0.05, 0.3, 0.2, step=0.01, unit="m/s")
            # --8<-- [end:gains]
            status = app.text("Status", "click on the map")

            @app.button("Stop", style="secondary")
            def stop():
                goal.update(x=None, y=None)
                bot.stop()
                status.value = "stopped"

        with app.card("Compare: a planned route"):
            # --8<-- [start:route]
            @app.button("Go there with a route instead", style="secondary")
            def by_route():
                if goal["x"] is None:
                    status.value = "click on the map first"
                    return
                x, y = goal["x"], goal["y"]
                goal.update(x=None, y=None)  # the feedback loop leaves it alone
                status.value = "driving the route"
                bot.route().go_to(x, y).run()  # turn once, then drive straight: no corrections
                status.value = (
                    f"route done, {math.dist((x, y), (bot.pose.x, bot.pose.y)) * 100:.1f} cm away"
                )

            # --8<-- [end:route]

app.start()


# --8<-- [start:control]
def wrap(angle):
    """An angle between -pi and pi (turning 350° left = turning 10° right)."""
    return (angle + math.pi) % (2 * math.pi) - math.pi


while True:
    time.sleep(0.05)
    if goal["x"] is None:
        continue
    pose = bot.pose
    dx, dy = goal["x"] - pose.x, goal["y"] - pose.y
    distance = math.hypot(dx, dy)
    heading_error = wrap(math.atan2(dy, dx) - pose.yaw)  # how far we must turn, radians
    errors.add({"distance": distance, "heading": math.degrees(heading_error) / 100})

    if distance < 0.03:  # close enough: arrived
        bot.stop()
        goal.update(x=None, y=None)
        status.value = f"arrived, {distance * 100:.1f} cm from the goal"
        continue

    turn = steer_gain.value * heading_error  # turn harder when facing further away
    speed = min(top_speed.value, distance) * max(0.0, math.cos(heading_error))  # slow when off
    bot.drive(speed, math.degrees(turn))
# --8<-- [end:control]
