# Examples and lessons

Each folder in [`examples/`](examples/) is an **example pack**: a working program with its
own screen (built with `movebot.ui`) and a lesson that explains it. The MoveBot app copies
these into the workspace, shows the screen in *Apps* mode and the lesson in *Learn* mode.

```
examples/follow-the-ball/
  example.toml   # title, level, minutes, concepts, needs, platforms, licence, ...
  app.py         # the program, with its screen
  lesson.md      # the lesson; shows parts of app.py (see below)
```

A lesson shows a part of `app.py` with a snippet inside a code fence:

````markdown
```python
--8<-- "app.py:find-ball"
```
````

and the part is marked in `app.py` with comments:

```python
# --8<-- [start:find-ball]
def find_ball(image, low, high):
    ...
# --8<-- [end:find-ball]
```

| Example | Level | What it teaches |
|---|---|---|
| [drive-with-buttons](examples/drive-with-buttons/) | 0 | functions become buttons; moves in metres and degrees |
| [follow-the-ball](examples/follow-the-ball/) | 3 | camera images, HSV colour, masks, proportional steering |

In the MoveBot app, open the *Apps* gallery. From a checkout with the app's Python,
run one against the simulator:

```bash
uv run movebot sim                                   # in one terminal
uv run python content/examples/follow-the-ball/app.py   # in another
```

Every pack is checked in CI: `example.toml` has the required fields, every snippet a lesson
uses exists in `app.py`, and the app starts against the simulator (the tests live in the
MoveBot app's repository, which includes this one).
