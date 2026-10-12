"""The relay: one connection to the bot, shared by several local programs."""

from __future__ import annotations

import json
import time

import pytest

pytest.importorskip("movebot_studio.sim", reason="the simulator comes with the MoveBot app")

from movebot import Bot, BotInUse
from movebot.relay import RelayThread
from movebot_studio.sim import Limits, SimOptions, SimulatorThread
from websockets.sync.client import connect


def eventually(condition, timeout: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout
    while not condition():
        if time.monotonic() > deadline:
            return False
        time.sleep(0.02)
    return True


@pytest.fixture
def sim():
    # A long command timeout, so a stop caused by the relay is distinguishable from the
    # bot's own watchdog.
    options = SimOptions(time_scale=5, limits=Limits(command_timeout_ms=3000))
    with SimulatorThread(options) as s:
        yield s


@pytest.fixture
def relay(sim):
    with RelayThread(sim.url, max_clients=3) as r:
        yield r


def test_programs_share_one_bot_connection(sim, relay):
    with Bot(relay.url) as a, Bot(relay.url) as b:
        assert len(sim.server._clients) == 1
        assert a.info["relay"]["upstream"] == sim.url
        assert a.info["boot_id"] == sim.bot.boot_id
        a.forward(0.2)
        assert b.pose.x == pytest.approx(0.2, abs=0.01)


def test_events_reach_every_program(relay):
    with Bot(relay.url) as a, Bot(relay.url) as b:
        seen: list[str] = []
        b.on("marker", lambda e: seen.append(e["label"]))
        a.route().marker("hello").forward(0.05).run()
        assert eventually(lambda: seen == ["hello"])


def test_a_crashed_driver_stops_the_bot(sim, relay):
    with Bot(relay.url) as watcher:
        raw = connect(relay.url).__enter__()
        json.loads(raw.recv(timeout=5))  # hello
        raw.send(
            json.dumps({"type": "req", "id": "x-1", "cmd": "drive.velocity", "v": 0.1, "w": 0})
        )
        json.loads(raw.recv(timeout=5))
        assert eventually(lambda: sim.bot.drive.speed_left > 0.05)
        raw.__exit__(None, None, None)  # the program is gone, without saying stop
        started = time.monotonic()
        assert eventually(lambda: sim.bot.manual is None or sim.bot.manual.a == 0, timeout=2)
        assert time.monotonic() - started < 1.0  # well before the bot's 3 s watchdog
        assert watcher.connected


def test_plans_follow_their_policy_when_the_owner_disappears(sim, relay):
    raw = connect(relay.url).__enter__()
    json.loads(raw.recv(timeout=5))
    load = {
        "type": "req", "id": "p-1", "cmd": "plan.load", "plan_id": "relaystop",
        "steps": [{"seq": 1, "op": "wait", "ms": 60000}],
        "autostart": True, "end": True, "on_disconnect": "stop",
    }  # fmt: skip
    raw.send(json.dumps(load))
    while json.loads(raw.recv(timeout=5)).get("id") != "p-1":
        pass
    raw.__exit__(None, None, None)
    assert eventually(lambda: sim.bot.plans.plan.state == "cancelled")


def test_camera_is_shared_through_one_stream(sim, relay):
    with Bot(relay.url) as a, Bot(relay.url) as b:
        assert a.camera.frame().shape == (240, 320, 3)
        assert b.camera.frame().shape == (240, 320, 3)
        assert sim.server._mjpeg.clients == 1
        a.camera.stop()
        b.camera.stop()
        assert eventually(lambda: sim.bot.camera_streaming is False)


def test_programs_keep_working_when_the_bot_link_drops(sim, relay):
    with Bot(relay.url) as a:
        reconnects: list[bool] = []
        a.on("reconnected", lambda e: reconnects.append(True))
        sim.drop_connections()  # the relay's link to the bot drops, ours to the relay does not
        assert a.forward(0.1).ok
        assert reconnects == []


def test_a_bot_restart_reaches_the_programs(sim, relay):
    with Bot(relay.url) as a:
        old_boot = a.info["boot_id"]
        restarted: list[bool] = []
        a.on("rebooted", lambda e: restarted.append(True))
        sim.call(sim.bot.reboot)
        sim.drop_connections()
        assert eventually(lambda: restarted == [True])
        assert a.info["boot_id"] == sim.bot.boot_id != old_boot


def test_relay_connection_limit(relay):
    bots = [Bot(relay.url) for _ in range(3)]
    try:
        with pytest.raises(BotInUse):
            Bot(relay.url)
    finally:
        for b in bots:
            b.close()
