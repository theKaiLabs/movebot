"""Drive forward and stop 20 cm before whatever is ahead (a wall, a box, a ball)."""

import time

from movebot import Bot

bot = Bot()

# --8<-- [start:find]
sensors = bot.modules.of_type("distance")
if not sensors:
    raise SystemExit("This robot has no distance sensor plugged in.")
sensor = sensors[0]
# --8<-- [end:find]

# --8<-- [start:loop]
bot.rgb_led.on("green")
bot.drive(0.15)  # start driving; we decide when to stop
while True:
    distance = sensor.distance  # metres, or None if nothing is in range
    print("distance:", distance)
    if distance is not None and distance < 0.20:
        break
    time.sleep(0.05)
bot.stop()
bot.rgb_led.on("red")
print(f"Stopped {sensor.distance * 100:.0f} cm from it")
# --8<-- [end:loop]
