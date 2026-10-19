"""Behaviour that needs fault injection (reboot, blocked wheels): simulator only."""

from __future__ import annotations

import time

import pytest

from .conftest import plan_id

pytestmark = pytest.mark.sim_only


def test_reboot_changes_boot_id_and_forgets_plans(target, client, connect_client):
    pid = plan_id()
    client.ok(
        "plan.load", plan_id=pid, steps=[{"seq": 1, "op": "wait", "ms": 5000}], autostart=True
    )
    old_boot = client.hello["boot_id"]
    new_boot = client.ok("sim.reboot")["boot_id"]
    assert new_boot != old_boot
    later = connect_client()
    assert later.hello["boot_id"] == new_boot
    later.err("plan.status", "unknown_plan", plan_id=pid)
    target.hello = later.hello  # keep the session fixture's view current


def _restart(client, connect_client, target):
    old_boot = client.hello["boot_id"]
    assert client.ok("system.restart", delay_ms=100)["restarting"] is True
    deadline = time.monotonic() + 15
    while True:  # the bot (or the relay in front of it) takes a moment to come back
        time.sleep(0.3)
        try:
            later = connect_client()
        except Exception:
            if time.monotonic() > deadline:
                raise
            continue
        if later.hello["boot_id"] != old_boot:
            target.hello = later.hello
            return later
        later.close()
        if time.monotonic() > deadline:
            raise AssertionError("the bot did not restart")


def test_wifi_settings_name_and_restart(target, client, connect_client):
    """The whole set-up flow (SPEC §12), on the simulator's made-up networks."""
    old_name = client.hello["name"]
    test = client.ok("wifi.test", ssid="Classroom", password="robots123")
    assert test["joined"] is True and test["ip"].startswith("192.168.1.")
    assert (
        client.ok("wifi.test", ssid="Classroom", password="wrong-one")["reason"] == "wrong_password"
    )
    saved = client.ok("wifi.set", mode="ap+sta", ssid="Classroom", password="robots123")["saved"]
    assert saved["mode"] == "ap+sta" and saved["has_password"] and "password" not in saved
    assert client.ok("device.set", name="Rover 7")["applied_on_reboot"] is True
    assert client.ok("wifi.status")["pending_restart"] is True
    try:
        later = _restart(client, connect_client, target)
        assert later.hello["name"] == "Rover 7"
        status = later.ok("wifi.status")
        assert status["mode"] == "ap+sta" and status["pending_restart"] is False
        assert status["sta"]["state"] == "connected" and status["ip"] == test["ip"]
        assert status["ap"]["ssid"] == "Rover 7"  # the bot's own network is named after it
        # a network it cannot join: it falls back to its own network (SPEC §12.1)
        later.ok("wifi.set", mode="sta", ssid="Classroom", password="not-the-password")
        later = _restart(later, connect_client, target)
        status = later.ok("wifi.status")
        assert status["sta"]["state"] == "failed" and status["sta"]["reason"] == "wrong_password"
        assert status["ap"] is not None and status["mode"] == "ap+sta"
    finally:
        last = connect_client()
        last.ok("wifi.reset_ap")
        last.ok("device.set", name=old_name)
        last = _restart(last, connect_client, target)
        assert last.ok("wifi.status")["mode"] == "ap" and last.hello["name"] == old_name


def test_blocked_wheels_fail_the_step_as_stalled(client):
    client.ok("sim.fault", blocked=True)
    try:
        pid = plan_id()
        client.ok("plan.load", plan_id=pid, steps=[
            {"seq": 1, "op": "drive", "dist": 0.3},
            {"seq": 2, "op": "wait", "ms": 10},
        ], autostart=True, end=True)  # fmt: skip
        failed = client.wait_for("evt", "plan.failed", plan_id=pid, timeout=10)
        assert failed["seq"] == 1 and failed["reason"] == "stalled"
        status = client.ok("plan.status", plan_id=pid)
        assert status["state"] == "failed" and status["done_seq"] == 1
        results = client.ok("plan.results", plan_id=pid)["results"]
        assert [(r["seq"], r["result"], r.get("reason")) for r in results] == [
            (1, "failed", "stalled")
        ]
    finally:
        client.ok("sim.fault", blocked=False)


def test_step_timeout(client):
    pid = plan_id()
    client.ok("sim.fault", blocked=True)
    try:
        # Blocked wheels would stall first, so use a timeout shorter than the stall window.
        client.ok("plan.load", plan_id=pid, steps=[
            {"seq": 1, "op": "drive", "dist": 0.3, "timeout_ms": 100},
        ], autostart=True, end=True)  # fmt: skip
        failed = client.wait_for("evt", "plan.failed", plan_id=pid, timeout=10)
        assert failed["reason"] == "timeout"
    finally:
        client.ok("sim.fault", blocked=False)
