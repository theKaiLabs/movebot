"""Drive with buttons: your first MoveBot app.

Each function below becomes a button. Change them, add your own, and run again!

Run it with a robot, or first start the simulator in another terminal: movebot sim
"""

from movebot import Bot
from movebot.ui import App

bot = Bot()
app = App("Drive with buttons", bot=bot)

with app.row():
    with app.card("Move"):

        @app.button("Forward 20 cm")
        def forward():
            bot.forward(0.2)

        @app.button("Back 20 cm", style="secondary")
        def back():
            bot.back(0.2)

        @app.button("Turn left", style="secondary")
        def left():
            bot.left()

        @app.button("Turn right", style="secondary")
        def right():
            bot.right()

    with app.card("Shapes"):

        @app.button("Draw a square")
        def square():
            for _ in range(4):
                bot.forward(0.3)
                bot.left()

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
