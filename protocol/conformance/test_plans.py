"""Plans: numbering, queueing, execution, arbitration and disconnect policies (SPEC §6)."""

from __future__ import annotations

import math
import time

import pytest

from .conftest import plan_id


def waits(*ms: int, start: int = 1) -> list[dict]:
    return [{"seq": start + i, "op": "wait", "ms": m} for i, m in enumerate(ms)]


def test_a_plan_runs_to_completion_with_events_in_order(client):
    pid = plan_id()
    client.ok("odom.reset")
    steps = [
        {"seq": 1, "op": "drive", "dist": 0.05},
        {"seq": 2, "op": "turn", "yaw": math.pi / 2},
        {"seq": 3, "op": "marker", "label": "corner"},
        {"seq": 4, "op": "light", "name": client.hello["capabilities"]["lights"][0], "level": 1},
        {"seq": 5, "op": "wait", "ms": 50},
    ]
    res = client.ok("plan.load", plan_id=pid, steps=steps, autostart=True, end=True)
    assert res["next_seq"] == 6

    done = client.wait_for("evt", "plan.done", plan_id=pid, timeout=10)
    assert done["done_seq"] == 5
    finished = [m["seq"] for m in client.inbox if m.get("evt") == "plan.step_done"]
    assert finished == [1, 2, 3, 4, 5]
    marker = next(m for m in client.inbox if m.get("evt") == "plan.marker")
    assert marker["label"] == "corner" and marker["seq"] == 3

    results = client.ok("plan.results", plan_id=pid)["results"]
    assert [r["seq"] for r in results] == [1, 2, 3, 4, 5]
    assert all(r["result"] == "ok" for r in results)
    assert results[0]["pose"]["x"] == pytest.approx(0.05, abs=0.01)
    assert results[1]["pose"]["yaw"] == pytest.approx(math.pi / 2, abs=0.05)
    client.ok("light.set", name=steps[3]["name"], level=0)


def test_duplicates_are_ignored_and_gaps_rejected(client):
    pid = plan_id()
    assert client.ok("plan.load", plan_id=pid, steps=waits(10, 10, 10))["next_seq"] == 4
    # 2 and 3 are duplicates, 4 is new
    assert client.ok("plan.append", plan_id=pid, steps=waits(10, 10, 10, start=2))["next_seq"] == 5
    gap = client.err("plan.append", "gap", plan_id=pid, steps=waits(10, start=7))
    assert gap["error"]["next_seq"] == 5
    # retrying the original load is harmless
    assert client.ok("plan.load", plan_id=pid, steps=waits(10, 10, 10))["next_seq"] == 5
    status = client.ok("plan.status", plan_id=pid)
    assert status["state"] == "loaded" and status["done_seq"] == 0


def test_partial_acceptance_after_a_gap(client):
    pid = plan_id()
    client.ok("plan.load", plan_id=pid, steps=waits(10))
    res = client.ok("plan.append", plan_id=pid, steps=[*waits(10, start=2), *waits(10, start=9)])
    assert res["next_seq"] == 3


def test_queue_limit_and_end_flag(client):
    pid = plan_id()
    size = client.hello["limits"]["plan_queue"]
    res = client.ok("plan.load", plan_id=pid, steps=waits(*[10] * (size + 3)), end=True)
    assert res["next_seq"] == size + 1
    assert res["queue_free"] == 0
    assert res["end"] is False, "end only counts when every step was accepted"


def test_invalid_steps_reject_the_whole_request(client):
    pid = plan_id()
    client.err(
        "plan.load", "invalid_param", plan_id=pid, steps=[*waits(10), {"seq": 2, "op": "fly"}]
    )
    client.err("plan.status", "unknown_plan", plan_id=pid)
    client.err("plan.load", "invalid_param", plan_id=pid, steps=[{"seq": 1, "op": "drive"}])
    client.err("plan.load", "invalid_param", plan_id=pid, steps=waits(10), on_disconnect="panic")


def test_only_one_active_plan(client):
    first, second = plan_id(), plan_id()
    client.ok("plan.load", plan_id=first, steps=waits(10))
    client.err("plan.load", "busy", plan_id=second, steps=waits(10))
    res = client.ok("plan.load", plan_id=second, steps=waits(10), replace=True)
    assert res["plan_id"] == second
    assert client.wait_for("evt", "plan.cancelled", plan_id=first)
    client.err("plan.status", "unknown_plan", plan_id=first)


def test_manual_control_is_refused_while_a_plan_moves(client):
    pid = plan_id()
    client.ok("plan.load", plan_id=pid, steps=waits(2000), autostart=True, end=True)
    client.err("drive.velocity", "busy", v=0.1, w=0)
    client.err("motor.write", "busy", left=0.1, right=0.1)
    client.wait_for("evt", "plan.done", plan_id=pid, timeout=10)
    client.ok("drive.velocity", v=0.0, w=0)


def test_an_open_plan_waits_for_more_steps(client):
    pid = plan_id()
    client.ok("plan.load", plan_id=pid, steps=waits(10), autostart=True)
    client.wait_for("evt", "plan.step_done", plan_id=pid, seq=1)
    assert client.ok("plan.status", plan_id=pid)["state"] == "running"
    client.ok("drive.velocity", v=0.0, w=0)  # an idle plan does not block manual control
    client.ok("plan.append", plan_id=pid, steps=waits(10, start=2), end=True)
    assert client.wait_for("evt", "plan.done", plan_id=pid)["done_seq"] == 2


def test_pause_takes_effect_between_steps(client):
    pid = plan_id()
    client.ok("plan.load", plan_id=pid, steps=waits(2000, 2000), autostart=True, end=True)
    client.wait_for("evt", "plan.step_started", plan_id=pid, seq=1)
    client.ok("plan.pause", plan_id=pid)
    paused = client.wait_for("evt", "plan.paused", plan_id=pid, timeout=10)
    assert paused["done_seq"] >= 1
    assert client.ok("plan.status", plan_id=pid)["state"] == "paused"
    client.ok("plan.resume", plan_id=pid)
    assert client.wait_for("evt", "plan.done", plan_id=pid, timeout=10)["done_seq"] == 2


def test_cancel_and_stop(client):
    pid = plan_id()
    client.ok("plan.load", plan_id=pid, steps=waits(5000, 10), autostart=True, end=True)
    client.wait_for("evt", "plan.step_started", plan_id=pid, seq=1)
    client.ok("plan.cancel", plan_id=pid)
    cancelled = client.wait_for("evt", "plan.cancelled", plan_id=pid)
    assert cancelled["seq"] == 1
    result = client.ok("plan.results", plan_id=pid)["results"]
    assert [(r["seq"], r["result"]) for r in result] == [(1, "cancelled")]
    client.err("plan.append", "invalid_state", plan_id=pid, steps=waits(10, start=3))
    assert client.ok("plan.cancel", plan_id=pid)["state"] == "cancelled"  # idempotent

    pid = plan_id()
    client.ok("plan.load", plan_id=pid, steps=waits(5000), autostart=True, end=True)
    client.wait_for("evt", "plan.step_started", plan_id=pid, seq=1)
    client.ok("stop")
    assert client.wait_for("evt", "plan.cancelled", plan_id=pid)["reason"] == "stop"


def test_status_without_plan_id(client):
    status = client.ok("plan.status")
    assert status["state"] in ("none", "loaded", "running", "paused", "done", "failed", "cancelled")
    assert status["boot_id"] == client.hello["boot_id"]


@pytest.mark.parametrize(
    ("policy", "expected_state", "expected_done"),
    [("continue", "done", 2), ("finish_step", "cancelled", 1), ("stop", "cancelled", 1)],
)
def test_disconnect_policies(connect_client, policy, expected_state, expected_done):
    owner = connect_client()
    owner.ok("stop")
    pid = plan_id()
    owner.ok("plan.load", plan_id=pid, steps=waits(4000, 4000), autostart=True, end=True,
             on_disconnect=policy)  # fmt: skip
    owner.wait_for("evt", "plan.step_started", plan_id=pid, seq=1)
    owner.close()  # the link drops while step 1 is running

    later = connect_client()
    status = later.wait_state(pid, {"done", "cancelled"}, timeout=15)
    assert status["state"] == expected_state
    assert status["done_seq"] == expected_done
    results = later.ok("plan.results", plan_id=pid)["results"]
    if policy == "stop":
        assert results[0]["result"] == "cancelled"
    else:
        assert results[0]["result"] == "ok"


def test_an_idle_open_plan_of_a_client_that_left_does_not_block(connect_client):
    owner = connect_client()
    owner.ok("stop")
    pid = plan_id()
    # no `end`: the owner could still add moves (this is what bot.forward() etc. do)
    owner.ok("plan.load", plan_id=pid, steps=waits(50), autostart=True)
    owner.wait_for("evt", "plan.step_done", plan_id=pid, seq=1)
    owner.close()  # e.g. the program was ended

    other = connect_client()
    new = plan_id()
    deadline = time.monotonic() + 5
    while True:  # the bot may take a moment to notice the closed connection
        res = other.req("plan.load", plan_id=new, steps=waits(10), autostart=True, end=True)
        if res["ok"] or time.monotonic() > deadline:
            break
        assert res["error"]["code"] == "busy"
        time.sleep(0.1)
    assert res["ok"], f"the old plan still blocks: {res.get('error')}"
    other.wait_for("evt", "plan.done", plan_id=new)
