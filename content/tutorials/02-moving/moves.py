"""A tour of the ways the robot can move. It ends where it started."""

from movebot import Bot, Pose

bot = Bot()
bot.reset_odometry()  # where we are now becomes x=0, y=0, heading 0

# --8<-- [start:straight]
bot.speed = 60  # percent of the robot's top speed
bot.forward(0.4)  # metres
bot.back(0.1)
# --8<-- [end:straight]

# --8<-- [start:turns]
bot.left(90)  # degrees, on the spot
bot.right(45)
bot.turn(-45)  # + turns left, - turns right
bot.turn_to(0)  # face the way we faced at the start
# --8<-- [end:turns]

# --8<-- [start:curves]
bot.arc(0.15, 360)  # a full circle with a radius of 15 cm, to the left
bot.back(0.3)  # back to the start
# --8<-- [end:curves]

# --8<-- [start:pose]
pose = bot.pose
print(f"x = {pose.x:.3f} m, y = {pose.y:.3f} m, facing {pose.heading:.1f}°")
print(f"{pose.distance_to(Pose()) * 100:.1f} cm away from the start")
# --8<-- [end:pose]
