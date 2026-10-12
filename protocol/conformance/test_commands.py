"""Commands, manual control and telemetry (SPEC §4, §5, §8)."""

from __future__ import annotations

import time


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
    assert status["mode"] in ("ap", "sta")


def test_telemetry_subscription(client):
    res = client.ok("sub", topics=["odom", "power"], rate_hz=20)
    assert set(res["topics"]) >= {"odom", "power"}
    odom = client.wait_for("tlm", "odom", timeout=2)
    assert {"x", "y", "yaw", "v", "w"} <= odom.keys()
    client.wait_for("tlm", "power", timeout=2)
    client.ok("unsub", topics=["odom", "power"])
    client.err("sub", "invalid_param", topics=["gps"])
