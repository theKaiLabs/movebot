"""The beginner Bot API against the in-process simulator."""

from __future__ import annotations

import math
import threading
import time

import pytest

pytest.importorskip("movebot_studio.sim", reason="the simulator comes with the MoveBot app")
from movebot import Bot, BotBusy, BotNotFound, MoveCancelled, MoveFailed, PlanLost, Route


@pytest.fixture
def bot():
    b = Bot.simulated(time_scale=20)
    yield b
    b.close()


def test_connects_and_describes_itself(bot):
    assert bot.connected
    assert bot.name.startswith("MoveBot-")
    assert bot.info["protocol"] == "0.1"
    assert bot.sim is not None


def test_forward_and_turns(bot):
    result = bot.forward(0.3)
    assert result.ok and result.op == "drive"
    assert result.pose.x == pytest.approx(0.3, abs=0.005)
    bot.left()
    assert bot.pose.heading == pytest.approx(90, abs=1.5)
    bot.right(45)
    assert bot.pose.heading == pytest.approx(45, abs=2)
    bot.turn_to(0)
    assert bot.pose.heading == pytest.approx(0, abs=1.5)
    bot.back(0.1)
    assert bot.pose.x == pytest.approx(0.2, abs=0.01)


def test_odometry_matches_the_simulated_truth_without_noise(bot):
    bot.forward(0.4)
    bot.left()
    bot.forward(0.2)
    truth, pose = bot.sim.truth, bot.pose
    assert pose.distance_to(truth) < 0.01


def test_moves_started_without_waiting_run_in_order(bot):
    first = bot.forward(0.2, wait=False)
    second = bot.left(wait=False)
    third = bot.forward(0.2, wait=False)
    assert not third.done
    r3 = third.wait(timeout=10)
    r1, r2 = first.wait(), second.wait()
    assert (r1.seq, r2.seq, r3.seq) == (1, 2, 3)
    assert r1.t_end <= r2.t_start + 1 and r2.t_end <= r3.t_start + 1
    assert r3.pose.x == pytest.approx(0.2, abs=0.01)
    assert r3.pose.y == pytest.approx(0.2, abs=0.01)


def test_route_runs_and_reports_planned_vs_actual(bot):
    route = bot.route()
    for _ in range(4):
        route.forward(0.3).left()
    result = route.run()
    assert result.ok
    assert len(result.steps) == 8
    assert result.drift < 0.02
    assert "drift at the end" in str(result)


def test_route_without_waiting(bot):
    handle = bot.route().forward(0.2).wait(0.5).forward(0.2).run(wait=False)
    assert handle.progress[1] == 3
    result = handle.wait(timeout=10)
    assert handle.done and result.ok


def test_long_route_is_streamed_through_the_bots_queue(bot):
    queue = bot.info["limits"]["plan_queue"]
    route = Route()
    for _ in range(queue + 10):
        route.wait(0.01)
    result = bot.run_route(route)
    assert result.ok and len(result.steps) == queue + 10


def test_route_survives_a_wifi_drop(bot):
    route = bot.route()
    for _ in range(6):
        route.forward(0.1).wait(0.2)
    handle = route.run(wait=False)
    time.sleep(0.15)
    bot.sim.drop_connection()
    result = handle.wait(timeout=20)
    assert result.ok
    assert [s.seq for s in result.steps] == list(range(1, 13)), "every move exactly once"
    assert bot.pose.x == pytest.approx(0.6, abs=0.02)


def test_single_moves_survive_a_wifi_drop(bot):
    pending = bot.forward(0.3, wait=False)
    time.sleep(0.05)
    bot.sim.drop_connection()
    assert pending.wait(timeout=10).ok
    assert bot.forward(0.1).ok  # the library is connected again


def test_reboot_is_reported_as_plan_lost(bot):
    handle = bot.route().wait(5).forward(0.1).run(wait=False)
    time.sleep(0.05)
    bot.sim.reboot()
    bot.sim.drop_connection()  # a real reboot also drops the link
    with pytest.raises(PlanLost):
        handle.wait(timeout=10)


def test_blocked_wheels_raise_move_failed(bot):
    bot.sim.block_wheels()
    with pytest.raises(MoveFailed) as info:
        bot.forward(0.3)
    assert info.value.reason == "stalled"
    assert "blocking" in str(info.value)
    bot.sim.block_wheels(False)
    assert bot.forward(0.1).ok  # a new move works afterwards


def test_a_move_right_after_a_failure_starts_fresh(bot):
    """Regression: the next move must not join the plan that just failed."""
    for _ in range(5):
        bot.sim.block_wheels()
        with pytest.raises(MoveFailed):
            bot.forward(0.3)
        bot.sim.block_wheels(False)
        assert bot.forward(0.02).ok


def test_route_failure_carries_the_partial_result(bot):
    bot.sim.block_wheels()
    with pytest.raises(MoveFailed) as info:
        bot.route().wait(0.1).forward(0.3).forward(0.3).run()
    result = info.value.route_result
    assert [s.result for s in result.steps] == ["ok", "failed"]
    bot.sim.block_wheels(False)


def test_stop_cancels_queued_moves(bot):
    a = bot.forward(1.0, wait=False)
    b = bot.forward(1.0, wait=False)
    time.sleep(0.05)
    bot.stop()
    with pytest.raises(MoveCancelled):
        a.wait(timeout=5)
    with pytest.raises(MoveCancelled):
        b.wait(timeout=5)
    assert bot.forward(0.05).ok


def test_drive_is_held_until_stopped(bot):
    bot.drive(0.1)
    time.sleep(1.0)  # longer than the bot's command timeout: the library keeps it alive
    moving = bot.pose
    assert moving.x > 0.5
    bot.stop()
    time.sleep(0.2)
    stopped = bot.pose.x
    time.sleep(0.3)
    assert bot.pose.x == pytest.approx(stopped, abs=0.002)


def test_drive_during_a_move_is_refused_nicely(bot):
    bot.forward(1.0, wait=False)
    time.sleep(0.02)
    with pytest.raises(BotBusy, match="still doing a move"):
        bot.drive(0.1)
    bot.stop()


def test_drive_for_seconds(bot):
    result = bot.drive(0.1, seconds=2)
    assert result.ok
    assert result.pose.x == pytest.approx(0.2, abs=0.02)


def test_lights_status_and_speed(bot):
    bot.lights.on()
    assert bot.lights.level == 1 and bot.lights.left.level == 1
    bot.lights.right.off()
    assert bot.lights.right.level == 0
    bot.lights.toggle()
    assert bot.lights.level == 0
    bot.status_led.blink()
    bot.speed = 50
    assert bot.speed == pytest.approx(50)


def test_markers_reach_callbacks(bot):
    seen: list[str] = []
    done = threading.Event()

    def on_marker(event):
        seen.append(event["label"])
        if len(seen) == 2:
            done.set()

    bot.on("marker", on_marker)
    bot.route().marker("start").forward(0.1).marker("end").run()
    assert done.wait(5)
    assert seen == ["start", "end"]


def test_arc_and_spin(bot):
    bot.arc(0.2, 90)
    pose = bot.pose
    assert (pose.x, pose.y) == (pytest.approx(0.2, abs=0.02), pytest.approx(0.2, abs=0.02))
    assert pose.heading == pytest.approx(90, abs=2)
    bot.spin()
    assert math.remainder(bot.pose.yaw - pose.yaw, 2 * math.pi) == pytest.approx(0, abs=0.05)


def test_unreachable_address_gives_a_friendly_error():
    with pytest.raises(BotNotFound, match="Could not reach MoveBot"):
        Bot("127.0.0.1:9", timeout=1)


def test_env_var_selects_the_bot(monkeypatch):
    from movebot_studio.sim import SimulatorThread

    with SimulatorThread() as sim:
        monkeypatch.setenv("MOVEBOT_URL", sim.url)
        with Bot() as b:
            assert b.info["boot_id"] == sim.bot.boot_id
