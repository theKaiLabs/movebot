"""Behaviour that needs fault injection (reboot, blocked wheels): simulator only."""

from __future__ import annotations

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
