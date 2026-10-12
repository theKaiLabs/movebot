"""Add-on modules: descriptors, reading, actions, telemetry, hot-plug (SPEC §8)."""

from __future__ import annotations

import json

import pytest

from .conftest import MODULES_DIR


def descriptor(module_type: str) -> dict:
    path = MODULES_DIR / f"{module_type}.json"
    assert path.exists(), f"module type {module_type!r} has no descriptor in protocol/modules/"
    return json.loads(path.read_text(encoding="utf-8"))


TYPE_CHECKS = {
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "null": lambda v: v is None,
    "string": lambda v: isinstance(v, str),
    "array": lambda v: isinstance(v, list),
    "object": lambda v: isinstance(v, dict),
}


def matches_type(value, declared) -> bool:
    kinds = declared if isinstance(declared, list) else [declared]
    return any(TYPE_CHECKS[k](value) for k in kinds)


@pytest.fixture
def modules(client):
    found = client.hello["modules"]
    if not found:
        pytest.skip("no modules attached to this bot")
    return found


def test_attached_modules_follow_their_descriptors(modules):
    ids = [m["id"] for m in modules]
    assert len(ids) == len(set(ids)), "module ids must be unique"
    for module in modules:
        spec = descriptor(module["type"])
        assert module["version"] <= spec["version"]
        assert sorted(module["values"]) == sorted(spec["values"])
        assert sorted(module["actions"]) == sorted(spec["actions"])


def test_module_list_matches_hello(client, modules):
    assert client.ok("module.list")["modules"] == modules


def test_read_returns_the_described_values(client, modules):
    for module in modules:
        res = client.ok("module.read", module_id=module["id"])
        assert res["module_id"] == module["id"] and res["module_type"] == module["type"]
        spec = descriptor(module["type"])["values"]
        assert sorted(res["values"]) == sorted(spec)
        for name, value in res["values"].items():
            assert matches_type(value, spec[name]["type"]), f"{module['id']}.{name} = {value!r}"


def test_unknown_module_and_action(client, modules):
    client.err("module.read", "unknown_module", module_id="no_such_module")
    client.err("module.call", "invalid_param", module_id=modules[0]["id"], action="explode")


def test_actions_from_the_descriptor_work(client, modules):
    for module in modules:
        for action, spec in descriptor(module["type"])["actions"].items():
            args = {name: field.get("maximum", 1) for name, field in spec.get("args", {}).items()}
            res = client.ok("module.call", module_id=module["id"], action=action, args=args)
            assert res["action"] == action and isinstance(res["result"], dict)


def test_module_telemetry(client, modules):
    topic = f"module.{modules[0]['id']}"
    client.ok("sub", topics=[topic], rate_hz=20)
    message = client.wait_for("tlm", topic, timeout=2)
    assert message["module_id"] == modules[0]["id"]
    client.ok("unsub", topics=[topic])
    client.err("sub", "invalid_param", topics=["module.no_such_module"])


@pytest.mark.sim_only
def test_hot_plug(client):
    added = client.ok("sim.attach", module="distance:rear_distance")["module"]
    event = client.wait_for("evt", "module.added")
    assert event["module"] == added
    assert any(m["id"] == "rear_distance" for m in client.ok("module.list")["modules"])
    client.ok("sim.detach", module_id="rear_distance")
    assert client.wait_for("evt", "module.removed")["module_id"] == "rear_distance"
    client.err("module.read", "unknown_module", module_id="rear_distance")
