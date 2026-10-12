"""Route building, compiling, previews and the text/JSON formats (no bot needed)."""

from __future__ import annotations

import math

import pytest
from movebot import Pose, Route


def close(a: Pose, b: Pose, tol: float = 1e-6) -> bool:
    return (
        abs(a.x - b.x) < tol
        and abs(a.y - b.y) < tol
        and abs(math.remainder(a.yaw - b.yaw, 2 * math.pi)) < tol
    )


def test_square_preview_returns_to_start():
    route = Route()
    for _ in range(4):
        route.forward(0.5).left()
    poses = route.preview()
    assert len(poses) == 8
    assert close(poses[0], Pose(0.5, 0, 0))
    assert close(poses[1], Pose(0.5, 0, math.pi / 2))
    assert close(poses[-1], Pose(0, 0, 0))


def test_right_and_back():
    poses = Route().right().back(0.2).preview()
    assert close(poses[0], Pose(0, 0, -math.pi / 2))
    assert close(poses[1], Pose(0, 0.2, -math.pi / 2))


def test_arc_quarter_circle():
    (left,) = Route().arc(0.5, 90).preview()
    assert close(left, Pose(0.5, 0.5, math.pi / 2))
    (right,) = Route().arc(0.5, -90).preview()
    assert close(right, Pose(0.5, -0.5, -math.pi / 2))


def test_drive_for_time_matches_arc():
    (pose,) = Route().drive(0.1, 18, seconds=5).preview()  # 0.5 m while turning 90°
    radius = 0.5 / (math.pi / 2)
    assert close(pose, Pose(radius, radius, math.pi / 2))


def test_go_to_compiles_to_turn_then_drive():
    compiled = Route().go_to(1.0, 1.0).compile(Pose())
    assert [c.step["op"] for c in compiled] == ["turn", "drive"]
    assert compiled[0].step["yaw"] == pytest.approx(math.pi / 4)
    assert compiled[1].step["dist"] == pytest.approx(math.sqrt(2))
    assert close(compiled[-1].expected, Pose(1.0, 1.0, math.pi / 4))


def test_go_to_uses_the_pose_reached_by_earlier_moves():
    compiled = Route().forward(1).go_to(1, 0.5).compile(Pose())
    assert [c.step["op"] for c in compiled] == ["drive", "turn", "drive"]
    assert compiled[2].step["dist"] == pytest.approx(0.5)


def test_go_to_straight_ahead_skips_the_turn():
    compiled = Route().go_to(2, 0).compile(Pose())
    assert [c.step["op"] for c in compiled] == ["drive"]


def test_wire_units_are_radians_and_ms():
    compiled = Route().turn(90, speed=45).wait(1.5).compile(Pose())
    assert compiled[0].step == {
        "op": "turn",
        "yaw": pytest.approx(math.pi / 2),
        "speed": pytest.approx(math.pi / 4),
    }
    assert compiled[1].step == {"op": "wait", "ms": 1500}


def test_lights_on_expands_to_every_light():
    hello = {"capabilities": {"lights": ["a", "b", "c"]}}
    steps = [c.step for c in Route().lights_on().compile(Pose(), hello)]
    assert steps == [{"op": "light", "name": n, "level": 1.0} for n in "abc"]


def test_speed_percent_uses_the_bots_limits():
    hello = {"limits": {"max_linear": 0.5, "max_angular": 2.0}}
    (c,) = Route().speed(50).compile(Pose(), hello)
    assert c.step == {"op": "speed", "linear": 0.25, "angular": 1.0}


def test_text_round_trip():
    text = (
        "forward 0.5; left; turn -30; back 0.2; arc 0.3 90; drive 0.1 10 2; wait 1; "
        "lights on; led blink; rgb pulse #00ff80; speed 50; marker corner one; go_to 1 2; "
        "turn_to 45"
    )
    route = Route.parse(text)
    assert Route.parse(route.to_text()).to_text() == route.to_text()
    assert len(route) == 14
    assert "rgb pulse #00ff80" in route.to_text()
    (step,) = [c.step for c in route.compile(Pose()) if c.step.get("name") == "rgb"]
    assert step == {"op": "status", "name": "rgb", "pattern": "pulse", "color": [0, 255, 128]}


def test_parse_comments_newlines_and_logo_aliases():
    route = Route.parse("""
        # a square
        fd 0.5
        lt
        fd 0.5 ; rt 45
    """)
    assert route.to_text() == "forward 0.5; turn 90; forward 0.5; turn -45"


@pytest.mark.parametrize(
    "bad", ["fly 3", "forward", "forward far", "arc 1", "lights dim", "led", "rgb on glitter"]
)
def test_parse_errors_name_the_line(bad):
    with pytest.raises(ValueError, match="route line 1"):
        Route.parse(bad)


def test_json_round_trip():
    route = Route().forward(0.5, speed=0.1).left(45).marker("here").go_to(1, 1)
    again = Route.from_json(route.to_json())
    assert again.to_json() == route.to_json()
    assert [c.step for c in again.compile(Pose())] == [c.step for c in route.compile(Pose())]


def test_from_json_rejects_unknown_moves():
    with pytest.raises(ValueError):
        Route.from_json('{"movebot_route": 1, "moves": [{"op": "teleport"}]}')


def test_run_without_a_bot_explains_itself():
    with pytest.raises(ValueError, match="no bot"):
        Route().forward(1).run()
