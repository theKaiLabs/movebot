"""Headlights, the status LED and the RGB LED."""

import time

from movebot import Bot

bot = Bot()

# --8<-- [start:headlights]
bot.lights.on()  # both headlights
time.sleep(1)
bot.lights.left.off()  # just one
time.sleep(1)
bot.lights.level = 0.3  # dimmed: 0 is off, 1 is full brightness
time.sleep(1)
bot.lights.off()
# --8<-- [end:headlights]

# --8<-- [start:status]
bot.status_led.blink()  # the controller board's own LED
time.sleep(2)
bot.status_led.on()
# --8<-- [end:status]

# --8<-- [start:rgb]
for colour in ["red", "orange", "yellow", "green", "blue", "purple"]:
    bot.rgb_led.on(colour)
    time.sleep(0.5)
bot.rgb_led.on((0, 255, 180))  # mix your own: (red, green, blue), each 0-255
time.sleep(1)
bot.rgb_led.pulse("#ff00aa")  # or a colour code, like on a web page
time.sleep(2)
# --8<-- [end:rgb]

# --8<-- [start:signal]
bot.rgb_led.blink("yellow")  # "careful, I am moving"
bot.forward(0.3)
bot.rgb_led.on("green")  # "done"
# --8<-- [end:signal]

time.sleep(1)
bot.rgb_led.off()
