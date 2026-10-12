"""Teach by showing: the robot learns what to do from pictures you label.

Point the camera at something (use the arrows), tell the robot what it means, and repeat.
Then switch on "Obey": for each new picture the robot finds the most similar pictures it was
shown, and does what they meant. This is machine learning, with a method called k-nearest
neighbours.
"""

import time

import numpy as np
from movebot import Bot
from movebot.ui import App

bot = Bot()
app = App("Teach by showing", bot=bot)

ACTIONS = {"forward": "green", "left": "blue", "right": "purple", "stop": "red"}
examples = []  # (features, action) pairs: what the robot has been shown


# --8<-- [start:features]
def features(image):
    """Describe a picture with 48 numbers: the average colour of a 4 x 4 grid of patches."""
    height, width = image.shape[:2]
    patches = image[: height // 4 * 4, : width // 4 * 4].reshape(4, height // 4, 4, width // 4, 3)
    return patches.mean(axis=(1, 3)).ravel() / 255  # 4 * 4 patches * 3 colours, each 0-1


# --8<-- [end:features]


# --8<-- [start:predict]
def predict(feature, k=3):
    """The action most of the k most similar examples had, and how sure we are (0-1)."""
    if not examples:
        return None, 0.0
    distances = [np.linalg.norm(feature - known) for known, _ in examples]
    nearest = np.argsort(distances)[:k]  # positions of the k smallest distances
    votes = [examples[i][1] for i in nearest]
    best = max(set(votes), key=votes.count)
    return best, votes.count(best) / len(votes)


# --8<-- [end:predict]

with app.row():
    with app.column():
        view = app.video("What the robot sees")

        @app.dpad("Aim the camera (hold an arrow)")
        def aim(direction):
            if direction == "left":
                bot.drive(0, 45)
            elif direction == "right":
                bot.drive(0, -45)
            elif direction == "up":
                bot.drive(0.1)
            elif direction == "down":
                bot.drive(-0.1)
            else:
                bot.stop()

    with app.column():
        with app.card("1. Teach: this picture means…"):
            # --8<-- [start:teach]
            def teach(action):
                examples.append((features(bot.camera.frame()), action))
                counts.value = ", ".join(
                    f"{name}: {sum(1 for _, a in examples if a == name)}" for name in ACTIONS
                )

            for action in ACTIONS:
                app.button(action, lambda action=action: teach(action), style="secondary")
            # --8<-- [end:teach]
            counts = app.text("Examples so far", "none")

            @app.button("Forget everything", style="danger")
            def forget():
                examples.clear()
                counts.value = "none"

        with app.card("2. Let it decide"):
            obey = app.toggle("Obey")
            guess = app.text("The robot thinks")
            sure = app.meter("How sure", 0, min=0, max=100, unit="%")

app.start()

# --8<-- [start:loop]
obeying, shown = False, None
for image in bot.camera.frames():
    view.show(image)
    action, confidence = predict(features(image))
    guess.value = action or "nothing yet: teach me first"
    sure.value = round(confidence * 100)
    if action and action != shown:  # the LED shows what it thinks
        bot.rgb_led.on(ACTIONS[action])
        shown = action
    if not obey.value or action is None:
        if obeying:  # "Obey" was just switched off
            bot.stop()
            obeying = False
        continue
    obeying = True
    if action == "forward":
        bot.drive(0.12)
    elif action == "left":
        bot.drive(0, 40)
    elif action == "right":
        bot.drive(0, -40)
    else:
        bot.stop()
    time.sleep(0.05)
# --8<-- [end:loop]
