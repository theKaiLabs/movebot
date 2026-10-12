"""Camera settings, presets, the MJPEG stream and the privacy indicator (SPEC §7)."""

from __future__ import annotations

import pytest

from .mjpeg_client import HttpStream, camera_base


@pytest.fixture
def camera(client):
    info = client.hello["capabilities"]["camera"]
    if not info:
        pytest.skip("this bot has no camera")
    client.ok("camera.set", preset="fast")
    yield info
    client.ok("camera.set", preset="fast")


def stream(target, camera, path="/stream") -> HttpStream:
    host, port = camera_base(target.url, camera)
    return HttpStream(host, port, path)


def test_required_presets_are_offered(camera):
    presets = camera["presets"]
    assert presets["fast"] == {
        "resolution": "320x240",
        "fps": 25,
        "quality": presets["fast"]["quality"],
    }
    assert presets["balanced"]["resolution"] == "640x480"
    assert presets["detail"]["resolution"] == "1280x720"
    for preset in presets.values():
        assert preset["resolution"] in camera["resolutions"]


def test_presets_and_custom_settings(client, camera):
    for name, preset in camera["presets"].items():
        res = client.ok("camera.set", preset=name)
        assert res["preset"] == name
        assert (res["resolution"], res["fps"]) == (preset["resolution"], preset["fps"])
    res = client.ok("camera.set", resolution=camera["resolutions"][0], fps=5, quality=50)
    assert res["preset"] is None
    assert (res["resolution"], res["fps"], res["quality"]) == (camera["resolutions"][0], 5, 50)
    assert client.ok("camera.get")["resolution"] == camera["resolutions"][0]


def test_invalid_camera_settings(client, camera):
    client.err("camera.set", "invalid_param", preset="ultra")
    client.err("camera.set", "invalid_param", resolution="123x45")
    client.err("camera.set", "invalid_param", fps=camera["max_fps"] + 1)
    client.err("camera.set", "invalid_param", quality=0)


def test_capture_returns_one_jpeg(target, camera):
    with stream(target, camera, camera.get("capture_path", "/capture")) as http:
        assert " 200 " in http.status
        assert http.headers["content-type"] == "image/jpeg"
        body = http.body()
    assert body[:2] == b"\xff\xd8"


def test_stream_parts_carry_timestamp_frame_and_pose(target, camera):
    with stream(target, camera) as http:
        assert " 200 " in http.status
        assert http.headers["content-type"].startswith("multipart/x-mixed-replace")
        parts = [http.next_part() for _ in range(4)]
    frames = [int(p.headers["x-frame"]) for p in parts]
    stamps = [int(p.headers["x-timestamp"]) for p in parts]
    assert frames == sorted(frames) and len(set(frames)) == 4
    assert stamps == sorted(stamps)
    for part in parts:
        assert part.headers["content-type"] == "image/jpeg"
        assert len(part.headers["x-pose"].split(",")) == 3
        assert part.size == (320, 240)


def test_resolution_change_reaches_the_stream(client, target, camera):
    with stream(target, camera) as http:
        http.next_part()
        client.ok("camera.set", preset="balanced")
        sizes = [http.next_part().size for _ in range(6)]
    assert sizes[-1] == (640, 480)


def test_privacy_indicator_follows_the_stream(client, target, camera):
    assert camera.get("privacy_indicator")
    with stream(target, camera) as http:
        http.next_part()
        client.wait_for("evt", "camera.streaming", active=True)
        assert client.ok("camera.get")["streaming"] is True
    client.wait_for("evt", "camera.streaming", active=False)
