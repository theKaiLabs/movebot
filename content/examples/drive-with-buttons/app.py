"""Drive with buttons: your first MoveBot app.

Click an arrow to move one step. Every function below with @app.... above it becomes part
of the screen: change them, add your own, and run again!

Run it from the MoveBot app, or with a robot (or `movebot sim`) and the app's Python.
"""

from movebot import Bot
from movebot.ui import App

bot = Bot()
app = App("Drive with buttons", bot=bot)

with app.row():
    # --8<-- [start:camera]
    app.video("What the robot sees", bot.camera)
    # --8<-- [end:camera]

    with app.column():
        with app.card("Move one step"):
            # --8<-- [start:dpad]
            @app.dpad("Click an arrow")
            def step(direction):
                if direction == "up":
                    bot.forward(0.2)  # metres
                elif direction == "down":
                    bot.back(0.2)
                elif direction == "left":
                    bot.left()  # 90 degrees
                elif direction == "right":
                    bot.right()
                # when the arrow is let go, direction is None: nothing to do

            # --8<-- [end:dpad]

        with app.card("Shapes"):
            # --8<-- [start:square]
            @app.button("Draw a square")
            def square():
                for _ in range(4):
                    bot.forward(0.3)
                    bot.left()

            # --8<-- [end:square]

            @app.slider("Speed", 10, 100, 50, unit="%")
            def set_speed(percent):
                bot.speed = percent

        with app.card("Where am I"):

            @app.output("Position")
            def position():
                return bot.pose

            @app.button("Lights on/off", style="secondary")
            def lights():
                bot.lights.toggle()


app.run()
