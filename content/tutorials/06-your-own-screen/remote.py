"""My robot remote: a screen made from Python."""

from movebot import Bot
from movebot.ui import App

bot = Bot()
# --8<-- [start:app]
app = App("My robot remote", bot=bot)
# --8<-- [end:app]

with app.row():
    # --8<-- [start:camera]
    app.video("Camera", bot.camera)
    # --8<-- [end:camera]

    with app.column():
        with app.card("Drive"):
            # --8<-- [start:slider]
            speed = app.slider("Speed", 0.05, 0.3, 0.15, step=0.01, unit="m/s")
            # --8<-- [end:slider]

            # --8<-- [start:dpad]
            @app.dpad("Hold an arrow")
            def drive(direction):
                if direction == "up":
                    bot.drive(speed.value)
                elif direction == "down":
                    bot.drive(-speed.value)
                elif direction == "left":
                    bot.drive(0, 90)
                elif direction == "right":
                    bot.drive(0, -90)
                else:
                    bot.stop()

            # --8<-- [end:dpad]

        with app.card("Robot"):
            # --8<-- [start:button]
            @app.button("Lights on/off")
            def lights():
                bot.lights.toggle()

            # --8<-- [end:button]

            # --8<-- [start:output]
            @app.output("Position")
            def position():
                return bot.pose

            # --8<-- [end:output]

            # --8<-- [start:select]
            @app.select("RGB LED", ["off", "red", "green", "blue"])
            def led(colour):
                if colour == "off":
                    bot.rgb_led.off()
                else:
                    bot.rgb_led.on(colour)

            # --8<-- [end:select]

# --8<-- [start:run]
app.run()
# --8<-- [end:run]
