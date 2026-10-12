# Webcam gestures

Steer the robot with your hands. The computer's webcam watches you, and the program learns
which picture means which command from examples you record yourself.

!!! tip "Try it first"
    1. Switch on **Use my webcam** (it is only used while this is on).
    2. Make a gesture, for example one hand up for *forward*, and press **Record “forward”**.
       Keep the gesture still while it records 15 pictures. Do the same for left, right and
       stop.
    3. Switch on **Drive with gestures**.

## Using the webcam

```python
--8<-- "app.py:webcam"
```

OpenCV's `VideoCapture(0)` opens the computer's first webcam; `capture.read()` gives the next
picture. Webcams are private: the program only opens it when you ask, and closes it again.

## Features: making pictures comparable

```python
--8<-- "app.py:features"
```

The picture is turned grey and shrunk to 24 x 18 pixels: only the rough shape of your gesture
is left, which is exactly what matters. Then every number has the average subtracted and is
divided by the spread (the *standard deviation*). This **normalising** means a darker or
brighter room does not change the features much.

## Learning and deciding

```python
--8<-- "app.py:loop"
```

Recording stores the features of 15 pictures with the gesture's name. Afterwards every new
picture is compared with all of them, and the 5 most similar ones vote (k-nearest neighbours).
The robot only obeys when at least 60% of the votes agree: a **confidence threshold**, so it
stops instead of guessing when it is unsure.

## Things to try

- Record the same gestures standing further away. Does it still work? Why do more varied
  examples help?
- Ask a friend to use your recordings. Does it work for them? What does that tell you about
  training data?
- Lower the threshold to 0.4 and raise it to 0.9. What changes?
- Add a fifth gesture, "spin", that makes the robot spin.

!!! note "Works on"
    Windows, macOS and Linux computers with a webcam, with the simulator or a MoveBot. Needs
    OpenCV (`pip install movebot[vision]`; the MoveBot app includes it).
