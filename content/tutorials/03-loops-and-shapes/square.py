"""A square, written with a loop."""

from movebot import Bot

bot = Bot()

for side in range(4):  # side is 0, 1, 2, 3
    print("Side", side + 1)
    bot.forward(0.3)
    bot.left(90)

print("Back where I started?", bot.pose)
