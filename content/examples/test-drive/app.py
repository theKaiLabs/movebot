"""Test drive: try the robot out before you write any code.

Hold an arrow (or an arrow key, or W A S D) to drive, and let go to stop.

Run it from the MoveBot app, or with a robot (or `movebot sim`) and the app's Python.
"""

from movebot import Bot
from movebot.ui import App

bot = Bot()
app = App("Test drive", bot=bot)

with app.row():
    app.video("What the robot sees", bot.camera)

    with app.column():
        with app.card("Drive"):
            speed = app.slider("Speed", 0.05, 0.4, 0.15, step=0.01, unit="m/s")
            turning = app.slider("Turning speed", 20, 180, 90, step=5, unit="°/s")

            # --8<-- [start:drive]
            @app.dpad("Hold an arrow to drive")
            def drive(direction):
                if direction == "up":
                    bot.drive(speed.value)  # keeps driving until told otherwise
                elif direction == "down":
                    bot.drive(-speed.value)
                elif direction == "left":
                    bot.drive(0, turning.value)  # turn on the spot, + is left
                elif direction == "right":
                    bot.drive(0, -turning.value)
                else:  # the arrow was let go
                    bot.stop()

            # --8<-- [end:drive]

        with app.card("Robot"):
            app.text("Position", lambda: bot.pose)
            app.meter("Battery", lambda: bot.battery, unit="%")
            with app.row():
                app.button("Lights on/off", bot.lights.toggle, style="secondary")
                app.button("Reset position", bot.reset_odometry, style="secondary")

app.run()
