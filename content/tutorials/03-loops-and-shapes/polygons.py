"""Any regular polygon, with one function."""

from movebot import Bot

bot = Bot()


# --8<-- [start:polygon]
def polygon(sides, length):
    """Drive a shape with `sides` equal sides, each `length` metres long."""
    turn = 360 / sides  # all the turns together make one full turn
    for _ in range(sides):
        bot.forward(length)
        bot.left(turn)


# --8<-- [end:polygon]

# --8<-- [start:use]
polygon(3, 0.3)  # a triangle
polygon(6, 0.15)  # a hexagon
# --8<-- [end:use]

print("Done at", bot.pose)
