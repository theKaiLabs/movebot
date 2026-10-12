"""What is a picture, to a computer?"""

from movebot import Bot

bot = Bot()

# --8<-- [start:frame]
image = bot.camera.frame()  # the newest picture
height, width, channels = image.shape
print(f"The picture is {width} x {height} pixels, with {channels} numbers per pixel")
# --8<-- [end:frame]

# --8<-- [start:pixel]
blue, green, red = image[height // 2, width // 2]  # the pixel in the middle: [row, column]
print(f"Middle pixel: red={red}, green={green}, blue={blue}")
# --8<-- [end:pixel]

# --8<-- [start:brightness]
print("Average brightness (0-255):", round(float(image.mean()), 1))
top, bottom = image[: height // 2], image[height // 2 :]
print("Top half:", round(float(top.mean())), " bottom half:", round(float(bottom.mean())))
# --8<-- [end:brightness]

# --8<-- [start:save]
path = bot.camera.save("what_i_see.jpg")
print("Saved", path)
# --8<-- [end:save]
