# Teach by showing

Instead of writing rules ("if the picture is blue, go forward"), you **show** the robot
examples and let it work out the rule itself. That is **machine learning**.

!!! tip "Try it first"
    1. Aim the camera at the blue ball (hold the arrows) and press **forward** a few times.
    2. Turn towards the red ball and press **left** a few times; aim at the green ball and
       press **right**; aim at an empty wall and press **stop**.
    3. Switch on **Obey** and watch: the robot now reacts to what it sees.

## Turning a picture into numbers

A picture has tens of thousands of numbers. Comparing whole pictures would be slow and easily
confused by small changes, so we describe each picture with a few numbers: its **features**.

```python
--8<-- "app.py:features"
```

The picture is cut into a 4 x 4 grid, and each patch is replaced by its average colour: 16
patches x 3 colours = **48 numbers**, each between 0 and 1.

## Learning = remembering examples

```python
--8<-- "app.py:teach"
```

Teaching just stores the features of the current picture together with the answer you gave.
These are the **training examples**.

## Deciding: k-nearest neighbours

```python
--8<-- "app.py:predict"
```

For a new picture, the robot measures how *different* it is from every example
(`np.linalg.norm` is the distance between two lists of numbers, like the distance between two
points, but in 48 dimensions). It takes the **k = 3 most similar** examples and lets them vote.
If all three agree, it is sure; if they disagree, it is less sure.

```python
--8<-- "app.py:loop"
```

## Things to try

- Teach only one example per action. Is the robot as good as with five each?
- Teach "forward" for the blue ball, then drive much further away from it. Does the robot
  still recognise it from far away? Why, or why not?
- Change `k` to 1, then to 7. What changes?
- Can you teach it to drive towards the blue ball and stop when it is close? (Hint: a close
  ball looks different from a far one: teach both.)

!!! note "Works on"
    Every computer, with the simulator or a MoveBot with a camera. Only numpy is needed.
