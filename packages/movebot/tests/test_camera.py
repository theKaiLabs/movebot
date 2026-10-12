"""Camera API against the simulator, including a small follow-the-ball control loop."""

from __future__ import annotations

import math
import time

import numpy as np
import pytest

pytest.importorskip("movebot_studio.sim", reason="the simulator comes with the MoveBot app")
from movebot import Bot
from movebot.mjpeg import jpeg_size


@pytest.fixture
def bot():
    b = Bot.simulated(time_scale=4)
    yield b
    b.close()


def blue_mask(image: np.ndarray) -> np.ndarray:
    b, g, r = image[:, :, 0].astype(int), image[:, :, 1].astype(int), image[:, :, 2].astype(int)
    return (b > 150) & (r < 100) & (g < 140)


def test_frame_is_an_opencv_style_image(bot):
    image = bot.camera.frame()
    assert image.shape == (240, 320, 3) and image.dtype == np.uint8
    latest = bot.camera.latest()
    assert latest.t is not None and latest.pose is not None and latest.size == (320, 240)
    assert np.array_equal(latest.rgb[:, :, 0], latest.image[:, :, 2])


def test_the_blue_ball_ahead_is_in_the_middle(bot):
    mask = blue_mask(bot.camera.frame())
    _, xs = np.nonzero(mask)
    assert len(xs) > 20, "the blue ball 1 m ahead should be visible"
    assert abs(xs.mean() - 160) < 10


def test_frames_are_always_new(bot):
    seen = []
    for i, _ in enumerate(bot.camera.frames()):
        seen.append(bot.camera.latest().seq)
        if i == 3:
            break
    assert seen == sorted(seen)


def test_configure_and_wait_for_the_new_size(bot):
    bot.camera.frame()
    settings = bot.camera.configure("detail")
    assert settings["resolution"] == "1280x720"
    assert bot.camera.frame().shape == (720, 1280, 3)
    custom = bot.camera.configure(resolution="640x480", fps=10, quality=60)
    assert custom["preset"] is None
    assert bot.camera.latest().size == (640, 480)
    assert bot.camera.settings["fps"] == 10


def test_save(bot, tmp_path):
    path = bot.camera.save(str(tmp_path / "view.jpg"))
    with open(path, "rb") as fh:
        assert jpeg_size(fh.read()) == (320, 240)


def test_privacy_events(bot):
    events = []
    bot.on("camera_streaming", lambda e: events.append(e["active"]))
    bot.camera.frame()
    bot.camera.stop()
    deadline = time.monotonic() + 3
    while events != [True, False] and time.monotonic() < deadline:
        time.sleep(0.05)
    assert events == [True, False]


def test_follow_the_blue_ball():
    """The flagship lesson in miniature: steer towards the blue ball using only the camera."""
    with Bot.simulated(time_scale=2) as bot:
        bot.sim.clear_balls()
        bot.sim.place_ball(1.0, 0.35, "blue")
        bot.turn(-20)  # start looking away from the ball
        for image in bot.camera.frames():
            _, xs = np.nonzero(blue_mask(image))
            if len(xs) == 0:
                bot.drive(0.0, 30)  # search: turn left
                continue
            if len(xs) > 0.08 * image.shape[0] * image.shape[1]:
                break  # the ball fills the view: we are there
            error = (xs.mean() - image.shape[1] / 2) / (image.shape[1] / 2)
            bot.drive(0.12, -60 * error)
        bot.stop()
        truth = bot.sim.truth
        assert math.hypot(1.0 - truth.x, 0.35 - truth.y) < 0.3
