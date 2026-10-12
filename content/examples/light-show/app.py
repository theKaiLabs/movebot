"""Light show: routes that dance with the headlights and the RGB LED.

Each show is a route: the robot keeps the timing itself, so the show stays smooth even if
the Wi-Fi is slow.
"""

from movebot import Bot
from movebot.ui import App

bot = Bot()
app = App("Light show", bot=bot)


# --8<-- [start:police]
def police_car():
    route = bot.route()
    for _ in range(6):
        route.rgb_led("on", "red").light("light_left", 1).light("light_right", 0).wait(0.25)
        route.rgb_led("on", "blue").light("light_left", 0).light("light_right", 1).wait(0.25)
    return route.lights_off().rgb_led("off")


# --8<-- [end:police]


# --8<-- [start:disco]
def disco():
    route = bot.route()
    colours = ["red", "orange", "yellow", "green", "cyan", "blue", "purple", "magenta"]
    for colour in colours:
        route.rgb_led("on", colour).turn(45)  # light and move together
    route.lights_on().spin(360).lights_off()
    return route.rgb_led("pulse", "white")


# --8<-- [end:disco]


def lighthouse():
    route = bot.route().lights_on()
    for _ in range(2):
        route.spin(360)
    return route.lights_off()


def traffic_light():
    route = bot.route()
    route.rgb_led("on", "green").wait(2)
    route.rgb_led("on", "yellow").wait(1)
    route.rgb_led("on", "red").wait(2)
    route.rgb_led("on", "green").forward(0.2).back(0.2)  # green: go!
    return route.rgb_led("off")


SHOWS = {
    "Police car": police_car,
    "Disco": disco,
    "Lighthouse": lighthouse,
    "Traffic light": traffic_light,
}

with app.row():
    app.video("What the robot sees", bot.camera)
    with app.column():
        with app.card("Shows"):
            # --8<-- [start:buttons]
            for name, make in SHOWS.items():
                app.button(name, lambda make=make: make().run())
            # --8<-- [end:buttons]
        with app.card("Do it yourself"):

            @app.slider("Headlights", 0, 100, 0, unit="%")
            def headlights(percent):
                bot.lights.level = percent / 100

            pattern = app.select("RGB pattern", ["on", "blink", "blink_fast", "pulse", "off"])

            # --8<-- [start:colour]
            @app.select(
                "RGB colour", ["red", "orange", "yellow", "green", "blue", "purple", "white"]
            )
            def colour(name):
                bot.rgb_led.set(pattern.value, name)

            # --8<-- [end:colour]

app.run()
