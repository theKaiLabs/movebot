"""Modules: descriptors, generic access, drivers, hot-plug and simulated sensors."""

from __future__ import annotations

import json
import pathlib
import time

import pytest
from jsonschema import Draft202012Validator
from movebot import Bot
from movebot.errors import NotSupported
from movebot.modules import _DRIVERS, DistanceSensor, Imu, Module

MODULES_DIR = pathlib.Path(__file__).resolve().parents[3] / "protocol" / "modules"
DESCRIPTOR_SCHEMA = json.loads((MODULES_DIR / "descriptor.schema.json").read_text("utf-8"))
DESCRIPTORS = {
    p.stem: json.loads(p.read_text("utf-8"))
    for p in MODULES_DIR.glob("*.json")
    if p.name != "descriptor.schema.json"
}


@pytest.mark.parametrize("name", sorted(DESCRIPTORS))
def test_descriptor_files_are_valid(name):
    Draft202012Validator(DESCRIPTOR_SCHEMA).validate(DESCRIPTORS[name])
    assert DESCRIPTORS[name]["type"] == name, "file name must equal the module type"


def test_simulated_modules_match_their_descriptor():
    sim_modules = pytest.importorskip("movebot_studio.sim.modules").SIM_MODULES
    for type_name, cls in sim_modules.items():
        spec = DESCRIPTORS[type_name]
        assert sorted(cls.value_names) == sorted(spec["values"]), type_name
        assert sorted(cls.actions) == sorted(spec["actions"]), type_name
        assert cls.version == spec["version"], type_name


def test_every_library_driver_has_a_descriptor():
    assert set(_DRIVERS) <= set(DESCRIPTORS)


@pytest.fixture
def bot():
    pytest.importorskip("movebot_studio.sim", reason="the simulator comes with the MoveBot app")
    b = Bot.simulated(time_scale=10, modules=["distance:front_distance", "imu"])
    yield b
    b.close()


def test_modules_are_listed_with_drivers(bot):
    assert bot.modules.ids() == ["front_distance", "imu"]
    assert isinstance(bot.modules.front_distance, DistanceSensor)
    assert isinstance(bot.modules["imu"], Imu)
    assert "imu" in bot.modules and len(bot.modules) == 2
    assert [m.type for m in bot.modules] == ["distance", "imu"]


def test_distance_sensor_sees_the_ball_getting_closer(bot):
    sensor = bot.modules.front_distance
    before = sensor.distance
    assert before == pytest.approx(1.0 - 0.033, abs=0.01)  # blue ball 1 m ahead
    bot.forward(0.5)
    assert sensor.distance == pytest.approx(before - 0.5, abs=0.02)
    assert sensor.distance_cm == pytest.approx(sensor.distance * 100)
    sensor.set_range(0.3)
    bot.back(0.4)
    assert sensor.distance is None  # now out of range


def test_imu_heading_in_degrees_and_calibrate(bot):
    imu = bot.modules.imu
    bot.left()
    assert imu.heading == pytest.approx(90, abs=2)
    imu.calibrate()
    assert imu.heading == pytest.approx(0, abs=0.5)
    bot.right(45)
    assert imu.heading == pytest.approx(-45, abs=2)


def test_generic_access_works_without_a_driver(bot):
    generic = Module(bot, bot._abot.module_descriptors["front_distance"])
    assert generic.valid is True
    assert generic.distance > 0
    assert generic.set_range(max=1.5) == {"max_range": 1.5}
    with pytest.raises(AttributeError, match="no value or action"):
        generic.colour  # noqa: B018


def test_unknown_modules_give_helpful_errors(bot):
    with pytest.raises(AttributeError, match="plugged in: front_distance, imu"):
        bot.modules.gripper  # noqa: B018
    with pytest.raises(NotSupported, match=r"Check bot.modules"):
        bot._run(bot._abot.read_module("gripper"))


def eventually(condition, timeout: float = 3.0) -> bool:
    deadline = time.monotonic() + timeout
    while not condition():
        if time.monotonic() > deadline:
            return False
        time.sleep(0.02)
    return True


def test_hot_plug_updates_bot_modules(bot):
    seen = []
    bot.on("module_added", lambda e: seen.append(e["module"]["id"]))
    bot.sim.attach("distance:rear_distance")
    assert eventually(lambda: "rear_distance" in bot.modules)
    assert isinstance(bot.modules.rear_distance, DistanceSensor)
    bot.sim.detach("rear_distance")
    assert eventually(lambda: "rear_distance" not in bot.modules)
    assert eventually(lambda: seen == ["rear_distance"])
