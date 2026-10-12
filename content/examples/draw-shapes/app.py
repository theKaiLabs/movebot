"""Draw shapes: plan a shape on the map, then let the robot drive it.

The dashed line is the plan; the grey trail is where the robot really went.
"""

from movebot import Bot
from movebot.ui import App

bot = Bot()
app = App("Draw shapes", bot=bot)


# --8<-- [start:route]
def shape_route(sides, size):
    """A route that drives a regular shape: `sides` sides of `size` metres."""
    route = bot.route()
    for _ in range(sides):
        route.forward(size)
        route.left(360 / sides)
    return route


# --8<-- [end:route]


# --8<-- [start:plan]
def show_plan(*_):
    route = shape_route(sides.value, size.value)
    start = bot.pose
    corners = [start, *route.preview(start)]  # where the robot should be after each move
    view.line("plan", corners, color="#2563eb", dashed=True)
    return route


# --8<-- [end:plan]

with app.row():
    view = app.map("Seen from above", robot=lambda: bot.pose)
    with app.column():
        with app.card("Shape"):
            sides = app.slider("Sides", 3, 10, 4, on_change=show_plan)
            size = app.slider("Side length", 0.1, 0.4, 0.3, step=0.05, unit="m",
                              on_change=show_plan)  # fmt: skip

            # --8<-- [start:drive]
            @app.button("Drive it")
            def drive():
                route = show_plan()
                bot.rgb_led.blink("yellow")
                result = route.run()  # the robot drives the whole shape by itself
                bot.rgb_led.on("green" if result.ok else "red")
                report.value = f"ended {result.drift * 100:.1f} cm from the plan"

            # --8<-- [end:drive]

            report = app.text("Result", "not driven yet")

        with app.card("Map"):

            @app.button("Clear the trail", style="secondary")
            def clear():
                view.clear()
                show_plan()

            @app.button("Back to the start", style="secondary")
            def home():
                bot.route().go_to(0, 0).turn_to(0).run()
                show_plan()


app.start()
show_plan()
app.run()
