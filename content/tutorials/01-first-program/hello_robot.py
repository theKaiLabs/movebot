"""Hello, robot! Drive forward, turn, and say where we are."""

from movebot import Bot

bot = Bot()  # connect to the robot (in the MoveBot app: the one at the top)
print("Connected to", bot.name)

bot.forward(0.3)  # 30 cm forward
bot.left()  # turn left 90 degrees
bot.forward(0.2)

print("I am at", bot.pose)
