"""Add-on modules (sensors and more): ``bot.modules.front_distance.distance``.

Every module works without any code here: values can be read as attributes and actions
called as methods, using the names the bot reports. A *driver* class adds a friendlier
API (units students expect, docstrings) for a module type::

    @register("distance")
    class DistanceSensor(Module):
        @property
        def distance(self) -> float | None:
            return self.read()["distance"]

Adding a new kind of module therefore needs: a firmware driver, a descriptor file in
``protocol/modules/``, and optionally a driver class like the ones below.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterator
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .bot import Bot

_DRIVERS: dict[str, type[Module]] = {}


def register(type_name: str) -> Callable[[type[Module]], type[Module]]:
    """Class decorator: use this driver for modules of ``type_name``."""

    def wrap(cls: type[Module]) -> type[Module]:
        _DRIVERS[type_name] = cls
        return cls

    return wrap


class Module:
    """Any module. Values are attributes, actions are methods (names come from the bot)."""

    def __init__(self, bot: Bot, descriptor: dict[str, Any]) -> None:
        self._bot = bot
        self.id: str = descriptor["id"]
        self.type: str = descriptor.get("type", "")
        self.version: int = int(descriptor.get("version", 1))
        self.info: dict[str, Any] = dict(descriptor.get("info", {}))
        self.value_names: list[str] = list(descriptor.get("values", []))
        self.actions: list[str] = list(descriptor.get("actions", []))

    def read(self) -> dict[str, Any]:
        """Ask the module for fresh values (one request to the bot)."""
        return self._bot._run(self._bot._abot.read_module(self.id))

    def call(self, action: str, **args: Any) -> dict[str, Any]:
        """Run an action on the module, e.g. ``module.call("calibrate")``."""
        return self._bot._run(self._bot._abot.call_module(self.id, action, **args))

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        if name in self.value_names:
            return self.read()[name]
        if name in self.actions:
            return lambda **args: self.call(name, **args)
        values = ", ".join(self.value_names) or "-"
        actions = ", ".join(self.actions) or "-"
        raise AttributeError(
            f"module {self.id!r} ({self.type}) has no value or action {name!r}. "
            f"Values: {values}; actions: {actions}"
        )

    def __dir__(self) -> list[str]:
        return sorted({*super().__dir__(), *self.value_names, *self.actions})

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} {self.id!r} type={self.type!r}>"


@register("distance")
class DistanceSensor(Module):
    """Measures the distance to whatever is in front of it."""

    @property
    def distance(self) -> float | None:
        """Distance in metres, or None if nothing is in range."""
        values = self.read()
        return values["distance"] if values.get("valid") else None

    @property
    def distance_cm(self) -> float | None:
        """The same distance in centimetres."""
        d = self.distance
        return None if d is None else d * 100

    def set_range(self, max_range: float) -> None:
        """Ignore things further away than ``max_range`` metres."""
        self.call("set_range", max=max_range)


@register("imu")
class Imu(Module):
    """Inertial measurement unit: which way the bot faces and how fast it turns."""

    @property
    def heading(self) -> float:
        """Heading in degrees since the last calibrate() (+ = turned left)."""
        return math.degrees(self.read()["heading"])

    @property
    def turn_rate(self) -> float:
        """How fast the bot turns, in degrees per second (+ = left)."""
        return math.degrees(self.read()["gyro_z"])

    @property
    def acceleration(self) -> tuple[float, float]:
        """(forward, sideways) acceleration in m/s²."""
        values = self.read()
        return values["accel_x"], values["accel_y"]

    def calibrate(self) -> None:
        """Make the current direction heading 0."""
        self.call("calibrate")


class Modules:
    """The modules plugged into the bot right now: ``bot.modules.<id>`` or ``bot.modules["id"]``."""

    def __init__(self, bot: Bot) -> None:
        self._bot = bot
        self._cache: dict[str, Module] = {}

    def _get(self, module_id: str) -> Module | None:
        descriptor = self._bot._abot.module_descriptors.get(module_id)
        if descriptor is None:
            return None
        cached = self._cache.get(module_id)
        if cached is None or cached.type != descriptor.get("type"):
            cls = _DRIVERS.get(descriptor.get("type", ""), Module)
            cached = self._cache[module_id] = cls(self._bot, descriptor)
        return cached

    def __getattr__(self, module_id: str) -> Module:
        if module_id.startswith("_"):
            raise AttributeError(module_id)
        module = self._get(module_id)
        if module is None:
            present = ", ".join(self.ids()) or "none"
            raise AttributeError(f"no module {module_id!r} on this MoveBot (plugged in: {present})")
        return module

    def __getitem__(self, module_id: str) -> Module:
        module = self._get(module_id)
        if module is None:
            raise KeyError(module_id)
        return module

    def __contains__(self, module_id: object) -> bool:
        return isinstance(module_id, str) and module_id in self._bot._abot.module_descriptors

    def __iter__(self) -> Iterator[Module]:
        return iter([self[i] for i in self.ids()])

    def __len__(self) -> int:
        return len(self._bot._abot.module_descriptors)

    def __dir__(self) -> list[str]:
        return sorted({*super().__dir__(), *self.ids()})

    def ids(self) -> list[str]:
        return list(self._bot._abot.module_descriptors)

    def of_type(self, type_name: str) -> list[Module]:
        return [m for m in self if m.type == type_name]

    def __repr__(self) -> str:
        inner = ", ".join(f"{m.id} ({m.type})" for m in self) or "none"
        return f"<Modules: {inner}>"
