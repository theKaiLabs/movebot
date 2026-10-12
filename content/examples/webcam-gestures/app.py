"""Webcam gestures: steer the robot with your hands, in front of your computer's webcam.

Record a few pictures of each gesture (a hand up for forward, a hand left, a hand right,
two hands for stop... your choice), then switch on "Drive with gestures". The robot learns
your gestures with k-nearest neighbours, the same method as "Teach by showing".
"""

import time

import cv2
import numpy as np
from movebot import Bot
from movebot.ui import App

bot = Bot()
app = App("Webcam gestures", bot=bot)

GESTURES = ["forward", "left", "right", "stop"]
examples = []  # (features, gesture)
recording = {"gesture": None, "left": 0}  # what the loop is recording right now
webcam = {"capture": None}


# --8<-- [start:features]
def features(picture):
    """A tiny grey version of the picture (24 x 18), scaled so lighting matters less."""
    grey = cv2.cvtColor(picture, cv2.COLOR_BGR2GRAY)
    small = cv2.resize(grey, (24, 18), interpolation=cv2.INTER_AREA).astype(float).ravel()
    return (small - small.mean()) / (small.std() + 1e-6)


# --8<-- [end:features]


def predict(feature, k=5):
    if len(examples) < 2:
        return None, 0.0
    distances = [np.linalg.norm(feature - known) for known, _ in examples]
    votes = [examples[i][1] for i in np.argsort(distances)[:k]]
    best = max(set(votes), key=votes.count)
    return best, votes.count(best) / len(votes)


def message(text):
    """A dark picture with a message, for when there is no webcam picture."""
    picture = np.full((240, 320, 3), 30, np.uint8)
    cv2.putText(picture, text, (12, 125), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (220, 220, 220), 1)
    return picture


with app.row():
    with app.column():
        view = app.video("Your webcam (mirrored)")
        app.video("What the robot sees", bot.camera)
    with app.column():
        with app.card("1. Webcam"):
            # --8<-- [start:webcam]
            @app.toggle("Use my webcam")
            def use_webcam(on):
                if on:
                    capture = cv2.VideoCapture(0)  # 0 = the first webcam of this computer
                    if not capture.isOpened():
                        status.value = "no webcam found on this computer"
                        return
                    webcam["capture"] = capture
                    status.value = "on"
                else:
                    capture, webcam["capture"] = webcam["capture"], None
                    if capture is not None:
                        capture.release()
                    status.value = "off"

            # --8<-- [end:webcam]
            status = app.text("Webcam", "off (your webcam is only used when you switch it on)")
        with app.card("2. Record each gesture"):
            for gesture in GESTURES:
                app.button(
                    f"Record “{gesture}”",
                    lambda gesture=gesture: recording.update(gesture=gesture, left=15),
                    style="secondary",
                )
            counts = app.text("Pictures recorded", "none")
        with app.card("3. Drive"):
            drive = app.toggle("Drive with gestures")
            guess = app.text("Gesture")
            sure = app.meter("How sure", 0, min=0, max=100, unit="%")

app.start()
view.show(message("Switch on 'Use my webcam'"))

# --8<-- [start:loop]
driving = False
while True:
    capture = webcam["capture"]
    if capture is None:
        if driving:
            bot.stop()
            driving = False
        time.sleep(0.1)
        continue
    ok, picture = capture.read()
    if not ok:
        time.sleep(0.05)
        continue
    picture = cv2.flip(picture, 1)  # like a mirror: your left is on the left
    feature = features(picture)

    if recording["left"] > 0:  # recording: store this picture as an example
        examples.append((feature, recording["gesture"]))
        recording["left"] -= 1
        counts.value = ", ".join(f"{g}: {sum(1 for _, x in examples if x == g)}" for g in GESTURES)
        cv2.putText(picture, f"recording {recording['gesture']}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)  # fmt: skip
        view.show(picture)
        time.sleep(0.1)
        continue

    gesture, confidence = predict(feature)
    guess.value = gesture or "record some gestures first"
    sure.value = round(confidence * 100)
    view.show(picture)

    if drive.value and gesture and confidence >= 0.6:
        driving = True
        if gesture == "forward":
            bot.drive(0.12)
        elif gesture == "left":
            bot.drive(0, 45)
        elif gesture == "right":
            bot.drive(0, -45)
        else:
            bot.stop()
    elif driving:
        bot.stop()
        driving = False
# --8<-- [end:loop]
