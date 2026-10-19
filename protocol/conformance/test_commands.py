"""Commands, manual control and telemetry (SPEC §4, §5, §8)."""

from __future__ import annotations

import time

import pytest

from .conftest import plan_id


def test_lights(client):
    names = client.hello["capabilities"]["lights"]
    for name in names:
        assert client.ok("light.set", name=name, level=0.5)["level"] == 0.5
    assert all(client.ok("light.get")["lights"][n] == 0.5 for n in names)
    client.err("light.set", "invalid_param", name="no_such_light", level=1)
    client.err("light.set", "invalid_param", name=names[0], level=1.5)
    client.err("light.set", "invalid_param", name=names[0], level="bright")
    for name in names:
        client.ok("light.set", name=name, level=0)


def test_status_led(client):
    name = client.hello["capabilities"]["status_leds"][0]
    assert client.ok("status.set", name=name, pattern="blink")["pattern"] == "blink"
    client.err("status.set", "invalid_param", name=name, pattern="disco")
    client.ok("status.set", name=name, pattern="on")


def test_colour_status_led(client):
    caps = client.hello["capabilities"]
    colour = caps.get("color_leds", [])
    if not colour:
        pytest.skip("this bot has no colour LED")
    name = colour[0]
    assert set(colour) <= set(caps["status_leds"])
    res = client.ok("status.set", name=name, pattern="blink", color=[255, 120, 0])
    assert res["color"] == [255, 120, 0]
    assert client.ok("status.set", name=name, pattern="on")["color"] == [255, 120, 0]  # kept
    client.err("status.set", "invalid_param", name=name, pattern="on", color=[256, 0, 0])
    client.err("status.set", "invalid_param", name=name, pattern="on", color="red")
    plain = [n for n in caps["status_leds"] if n not in colour]
    if plain:
        client.err("status.set", "invalid_param", name=plain[0], pattern="on", color=[0, 0, 255])
    # as a plan step
    pid = plan_id()
    step = {"seq": 1, "op": "status", "name": name, "pattern": "on", "color": [0, 255, 0]}
    client.ok("plan.load", plan_id=pid, steps=[step], autostart=True, end=True)
    client.wait_for("evt", "plan.done", plan_id=pid)
    client.ok("status.set", name=name, pattern="off")


def test_speed_limits_are_clamped(client):
    limits = client.hello["limits"]
    res = client.ok("speed.set", linear=limits["max_linear"] * 10)
    assert res["linear"] == limits["max_linear"]
    client.err("speed.set", "invalid_param", linear=-1)
    client.err("speed.set", "invalid_param")
    client.ok("speed.set", linear=0.2, angular=1.5)
    current = client.ok("speed.get")
    assert (current["linear"], current["angular"]) == (0.2, 1.5)


def test_odometry_and_encoders(client):
    client.ok("odom.reset")
    odom = client.ok("odom.get")
    assert (odom["x"], odom["y"], odom["yaw"]) == (0, 0, 0)
    enc = client.ok("encoder.get")
    assert isinstance(enc["left"]["ticks"], int) and isinstance(enc["right"]["ticks"], int)


def test_motor_write_range(client):
    client.err("motor.write", "invalid_param", left=1.5, right=0)
    client.ok("motor.write", left=0.2, right=0.2)
    client.ok("stop")


def test_velocity_command_expires(client):
    """The motor watchdog: an un-refreshed command stops by itself."""
    client.ok("odom.reset")
    client.ok("drive.velocity", v=0.1, w=0)
    client.wait_for("evt", "motion.stopped", timeout=3, reason="command_timeout")
    time.sleep(0.3)  # let the wheels spin down
    assert client.ok("odom.get")["x"] > 0
    assert abs(client.ok("odom.get")["v"]) < 0.01


def test_manual_control_stops_when_its_connection_closes(client, connect_client):
    other = connect_client()
    other.ok("drive.velocity", v=0.1, w=0)
    other.close()
    client.wait_for("evt", "motion.stopped", timeout=3, reason="disconnect")


def test_wifi_status(client):
    status = client.ok("wifi.status")
    assert status["mode"] in ("ap", "sta", "ap+sta")
    assert status["hostname"].startswith("movebot-")
    assert status["ap"] is not None or status["sta"] is not None  # never unreachable
    saved = status["saved"]
    assert saved["mode"] in ("ap", "sta", "ap+sta")
    assert "password" not in saved and "ap_password" not in saved  # SPEC §12.2
    assert "password" not in str(status).replace("has_password", "")


def test_wifi_scan_and_test_do_not_change_anything(client):
    before = client.ok("wifi.status")
    networks = client.ok("wifi.scan")["networks"]
    assert [n["rssi"] for n in networks] == sorted((n["rssi"] for n in networks), reverse=True)
    assert len({n["ssid"] for n in networks}) == len(networks)
    assert all(n["security"] in ("open", "wpa", "wpa2", "wpa3", "enterprise") for n in networks)
    result = client.ok("wifi.test", ssid="no-such-network-4f2a", password="x" * 8, timeout_ms=3000)
    assert result["joined"] is False and result["reason"] in ("not_found", "timeout")
    after = client.ok("wifi.status")
    assert after["saved"] == before["saved"] and after["mode"] == before["mode"]


def test_wifi_set_refuses_bad_settings_and_keeps_the_old_ones(client):
    before = client.ok("wifi.status")["saved"]
    client.err("wifi.set", "invalid_param", mode="mesh")
    client.err("wifi.set", "invalid_param", mode="sta")  # no network given
    client.err("wifi.set", "invalid_param", mode="ap", ap_password="short")
    client.err("wifi.set", "invalid_param", mode="sta", ssid="Lab", ip="192.168.1.20")  # half
    client.err("device.set", "invalid_param", name="Robot/One!")
    client.err("system.restart", "invalid_param", delay_ms=60000)
    assert client.ok("wifi.status")["saved"] == before


def test_telemetry_subscription(client):
    res = client.ok("sub", topics=["odom", "power"], rate_hz=20)
    assert set(res["topics"]) >= {"odom", "power"}
    odom = client.wait_for("tlm", "odom", timeout=2)
    assert {"x", "y", "yaw", "v", "w"} <= odom.keys()
    client.wait_for("tlm", "power", timeout=2)
    client.ok("unsub", topics=["odom", "power"])
    client.err("sub", "invalid_param", topics=["gps"])
