"""A delivery round: a route the robot drives on its own."""

import time

from movebot import Bot

bot = Bot()
bot.reset_odometry()

# --8<-- [start:build]
route = bot.route()
route.forward(0.5).marker("shop")
route.left().forward(0.3).marker("school")
route.left().forward(0.5).marker("park")
route.go_to(0, 0).turn_to(0)  # home again, facing the way we started
# --8<-- [end:build]

# --8<-- [start:preview]
for pose in route.preview():
    print("planned:", pose)
# --8<-- [end:preview]

# --8<-- [start:markers]
bot.on("marker", lambda event: print("Arrived at the", event["label"]))
# --8<-- [end:markers]

# --8<-- [start:background]
handle = route.run(wait=False)  # start it, and carry on with this program
while not handle.done:
    done, total = handle.progress
    print(f"{done} of {total} moves done")
    time.sleep(1)
result = handle.wait()
# --8<-- [end:background]

# --8<-- [start:result]
print("Every move went well:", result.ok)
print(f"Planned end vs. measured end: {result.drift * 100:.1f} cm apart")
# --8<-- [end:result]
