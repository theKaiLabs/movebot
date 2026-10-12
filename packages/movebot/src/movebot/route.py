"""Routes: a list of moves built up front and handed to the bot in one go.

A route is plain data. Building one sends nothing; ``run()`` uploads it as a plan,
the bot drives it on its own, and the library resumes it if Wi-Fi drops::

    route = bot.route()
    route.forward(0.5).left().forward(0.5)
    route.preview()          # where the bot should end up after each move
    result = route.run()     # planned vs. actual pose for every move
"""

from __future__ import annotations

import json
import math
import shlex
from dataclasses import dataclass
from typing import Any

from .models import Pose
from .protocol import wrap_angle

# Used for compiling when no bot is attached (e.g. previewing a route offline).
_DEFAULT_LIMITS = {"max_linear": 0.4, "max_angular": 4.0}
_DEFAULT_LIGHTS = ["light_left", "light_right"]


@dataclass(frozen=True)
class CompiledStep:
    step: dict[str, Any]  # wire step without "seq"
    expected: Pose  # where the bot should be after this step
    label: str


class Route:
    """A sequence of moves. Every method returns the route, so calls can be chained."""

    def __init__(self, bot: Any = None) -> None:
        self._bot = bot
        self._ops: list[dict[str, Any]] = []

    # -- moves ---------------------------------------------------------------------------

    def forward(self, distance: float, *, speed: float | None = None) -> Route:
        """Drive ``distance`` metres forward (negative = backward). ``speed`` in m/s."""
        return self._add("forward", distance=float(distance), speed=speed)

    def back(self, distance: float, *, speed: float | None = None) -> Route:
        """Drive ``distance`` metres backward."""
        return self._add("forward", distance=-float(distance), speed=speed)

    def turn(self, degrees: float, *, speed: float | None = None) -> Route:
        """Turn on the spot; positive = left (counter-clockwise). ``speed`` in degrees/s."""
        return self._add("turn", degrees=float(degrees), speed=speed)

    def left(self, degrees: float = 90, *, speed: float | None = None) -> Route:
        """Turn left on the spot (90 degrees unless you say otherwise)."""
        return self.turn(abs(degrees), speed=speed)

    def right(self, degrees: float = 90, *, speed: float | None = None) -> Route:
        """Turn right on the spot (90 degrees unless you say otherwise)."""
        return self.turn(-abs(degrees), speed=speed)

    def u_turn(self) -> Route:
        """Turn around (180 degrees)."""
        return self.turn(180)

    def spin(self, degrees: float = 360) -> Route:
        """Spin on the spot, a full turn unless you say otherwise."""
        return self.turn(degrees)

    def turn_to(self, heading: float) -> Route:
        """Turn to face ``heading`` degrees (0 = the direction the bot faced at the start)."""
        return self._add("turn_to", heading=float(heading))

    def arc(self, radius: float, degrees: float, *, speed: float | None = None) -> Route:
        """Drive forward along a circle of ``radius`` metres for ``degrees`` (+ left, - right)."""
        return self._add("arc", radius=float(radius), degrees=float(degrees), speed=speed)

    def drive(self, speed: float, turn_rate: float = 0.0, *, seconds: float) -> Route:
        """Drive at ``speed`` m/s while turning at ``turn_rate`` degrees/s for ``seconds``."""
        return self._add(
            "drive", speed=float(speed), turn_rate=float(turn_rate), seconds=float(seconds)
        )

    def go_to(self, x: float, y: float, *, speed: float | None = None) -> Route:
        """Turn towards the point (x, y) in metres and drive to it."""
        return self._add("go_to", x=float(x), y=float(y), speed=speed)

    def wait(self, seconds: float) -> Route:
        """Wait before the next move."""
        return self._add("wait", seconds=float(seconds))

    # -- other things the bot can do on the way ------------------------------------------

    def lights_on(self) -> Route:
        """Switch every light on."""
        return self._add("lights", level=1.0)

    def lights_off(self) -> Route:
        """Switch every light off."""
        return self._add("lights", level=0.0)

    def light(self, name: str, level: float) -> Route:
        """Set one light's brightness, 0 (off) to 1 (full)."""
        return self._add("light", name=name, level=float(level))

    def status_led(self, pattern: str, *, name: str = "status") -> Route:
        """Show a status LED pattern: ``off``, ``on``, ``blink``, ``blink_fast``, ``pulse``."""
        return self._add("status_led", pattern=pattern, name=name)

    def speed(self, percent: float) -> Route:
        """Change the speed limit for the rest of the route (percent of the bot's maximum)."""
        return self._add("speed", percent=float(percent))

    def marker(self, label: str) -> Route:
        """Ask the bot to report ``label`` when it gets here (see ``bot.on("marker", ...)``)."""
        return self._add("marker", label=str(label))

    def _add(self, op: str, **args: Any) -> Route:
        self._ops.append({"op": op, **{k: v for k, v in args.items() if v is not None}})
        return self

    # -- using the route -----------------------------------------------------------------

    def __len__(self) -> int:
        return len(self._ops)

    def __repr__(self) -> str:
        return f"Route({self.to_text()!r})"

    def run(self, bot: Any = None, *, wait: bool = True, on_disconnect: str = "continue") -> Any:
        """Send the route to the bot. With ``wait=True`` returns a ``RouteResult``."""
        target = bot or self._bot
        if target is None:
            raise ValueError("This route has no bot. Use bot.route() or route.run(bot).")
        return target.run_route(self, wait=wait, on_disconnect=on_disconnect)

    def preview(self, start: Pose | None = None) -> list[Pose]:
        """Where the bot should be after each move (no bot needed)."""
        return [c.expected for c in self.compile(start or Pose())]

    def compile(self, start: Pose, hello: dict[str, Any] | None = None) -> list[CompiledStep]:
        """Turn the moves into wire steps, tracking the expected pose as we go."""
        hello = hello or {}
        limits = {**_DEFAULT_LIMITS, **hello.get("limits", {})}
        lights = hello.get("capabilities", {}).get("lights", _DEFAULT_LIGHTS)
        pose = start
        out: list[CompiledStep] = []

        def emit(step: dict[str, Any], label: str) -> None:
            out.append(CompiledStep(step, pose, label))

        for op in self._ops:
            kind = op["op"]
            if kind == "forward":
                pose = _advance(pose, op["distance"], 0.0)
                step = {"op": "drive", "dist": op["distance"]}
                _maybe(step, "speed", op.get("speed"))
                emit(step, f"forward {op['distance']:g} m")
            elif kind == "turn":
                yaw = math.radians(op["degrees"])
                pose = Pose(pose.x, pose.y, wrap_angle(pose.yaw + yaw))
                step = {"op": "turn", "yaw": yaw}
                _maybe(step, "speed", op.get("speed"), math.radians)
                emit(step, f"turn {op['degrees']:g}°")
            elif kind == "turn_to":
                yaw = math.radians(op["heading"])
                pose = Pose(pose.x, pose.y, wrap_angle(yaw))
                emit({"op": "turn_to", "yaw": yaw}, f"turn to {op['heading']:g}°")
            elif kind == "arc":
                angle = math.radians(op["degrees"])
                pose = _advance(pose, op["radius"] * abs(angle), angle)
                step = {"op": "arc", "radius": op["radius"], "angle": angle}
                _maybe(step, "speed", op.get("speed"))
                emit(step, f"arc r={op['radius']:g} m {op['degrees']:g}°")
            elif kind == "drive":
                w = math.radians(op["turn_rate"])
                pose = _advance(pose, op["speed"] * op["seconds"], w * op["seconds"])
                step = {
                    "op": "drive_for",
                    "v": op["speed"],
                    "w": w,
                    "ms": round(op["seconds"] * 1000),
                }
                emit(step, f"drive {op['speed']:g} m/s for {op['seconds']:g} s")
            elif kind == "go_to":
                dx, dy = op["x"] - pose.x, op["y"] - pose.y
                distance = math.hypot(dx, dy)
                target = f"go to ({op['x']:g}, {op['y']:g})"
                if distance < 0.001:
                    continue
                turn = wrap_angle(math.atan2(dy, dx) - pose.yaw)
                if abs(turn) > math.radians(0.5):
                    pose = Pose(pose.x, pose.y, wrap_angle(pose.yaw + turn))
                    emit({"op": "turn", "yaw": turn}, f"{target}: turn")
                pose = Pose(op["x"], op["y"], pose.yaw)
                step = {"op": "drive", "dist": distance}
                _maybe(step, "speed", op.get("speed"))
                emit(step, f"{target}: drive")
            elif kind == "wait":
                emit({"op": "wait", "ms": round(op["seconds"] * 1000)}, f"wait {op['seconds']:g} s")
            elif kind == "lights":
                for name in lights:
                    emit(
                        {"op": "light", "name": name, "level": op["level"]},
                        f"{name} {op['level']:g}",
                    )
            elif kind == "light":
                emit(
                    {"op": "light", "name": op["name"], "level": op["level"]},
                    f"{op['name']} {op['level']:g}",
                )
            elif kind == "status_led":
                emit(
                    {"op": "status", "name": op["name"], "pattern": op["pattern"]},
                    f"status {op['pattern']}",
                )
            elif kind == "speed":
                fraction = max(0.0, min(op["percent"], 100.0)) / 100
                step = {
                    "op": "speed",
                    "linear": max(fraction * limits["max_linear"], 0.01),
                    "angular": max(fraction * limits["max_angular"], 0.05),
                }
                emit(step, f"speed {op['percent']:g}%")
            elif kind == "marker":
                emit({"op": "marker", "label": op["label"]}, f"marker {op['label']}")
            else:  # pragma: no cover - guarded by _add / parse
                raise ValueError(f"unknown route op {kind!r}")
        return out

    # -- saving and loading --------------------------------------------------------------

    def to_json(self) -> str:
        """The route as JSON text, to save it in a file."""
        return json.dumps({"movebot_route": 1, "moves": self._ops}, indent=2)

    @classmethod
    def from_json(cls, text: str, bot: Any = None) -> Route:
        """A route from JSON text made by ``to_json()``."""
        data = json.loads(text)
        if data.get("movebot_route") != 1:
            raise ValueError("not a MoveBot route file")
        route = cls(bot)
        for op in data["moves"]:
            if op.get("op") not in _OPS_FROM_JSON:
                raise ValueError(f"unknown move {op.get('op')!r}")
            route._ops.append(dict(op))
        return route

    def to_text(self) -> str:
        """The route in the little language ``Route.parse`` reads (per-move speeds are omitted)."""
        return "; ".join(_op_to_text(op) for op in self._ops)

    @classmethod
    def parse(cls, text: str, bot: Any = None) -> Route:
        """Read a route written as text, one move per line or separated by ``;``.

        Example: ``"forward 0.5; left; wait 1; lights on; go_to 1 0.5"``.
        Lines starting with ``#`` are comments.
        """
        route = cls(bot)
        lines = [ln.split("#", 1)[0] for ln in text.replace(";", "\n").splitlines()]
        for number, line in enumerate(lines, start=1):
            words = shlex.split(line)
            if not words:
                continue
            name, args = words[0].lower(), words[1:]
            try:
                _parse_one(route, name, args)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"route line {number} ({line.strip()!r}): {exc}") from None
        return route


def _advance(pose: Pose, distance: float, dyaw: float) -> Pose:
    """Pose after moving ``distance`` along an arc that turns by ``dyaw``."""
    if abs(dyaw) < 1e-9:
        return Pose(
            pose.x + distance * math.cos(pose.yaw), pose.y + distance * math.sin(pose.yaw), pose.yaw
        )
    r = distance / dyaw
    x = pose.x + r * (math.sin(pose.yaw + dyaw) - math.sin(pose.yaw))
    y = pose.y - r * (math.cos(pose.yaw + dyaw) - math.cos(pose.yaw))
    return Pose(x, y, wrap_angle(pose.yaw + dyaw))


def _maybe(step: dict[str, Any], key: str, value: float | None, convert: Any = None) -> None:
    if value is not None:
        step[key] = convert(value) if convert else value


_OPS_FROM_JSON = {
    "forward", "turn", "turn_to", "arc", "drive", "go_to", "wait",
    "lights", "light", "status_led", "speed", "marker",
}  # fmt: skip


def _op_to_text(op: dict[str, Any]) -> str:
    kind = op["op"]
    if kind == "forward":
        d = op["distance"]
        return f"forward {d:g}" if d >= 0 else f"back {-d:g}"
    if kind == "turn":
        return f"turn {op['degrees']:g}"
    if kind == "turn_to":
        return f"turn_to {op['heading']:g}"
    if kind == "arc":
        return f"arc {op['radius']:g} {op['degrees']:g}"
    if kind == "drive":
        return f"drive {op['speed']:g} {op['turn_rate']:g} {op['seconds']:g}"
    if kind == "go_to":
        return f"go_to {op['x']:g} {op['y']:g}"
    if kind == "wait":
        return f"wait {op['seconds']:g}"
    if kind == "lights":
        return "lights on" if op["level"] > 0 else "lights off"
    if kind == "light":
        return f"light {op['name']} {op['level']:g}"
    if kind == "status_led":
        return f"led {op['pattern']}"
    if kind == "speed":
        return f"speed {op['percent']:g}"
    if kind == "marker":
        return f"marker {op['label']}"
    raise ValueError(f"unknown route op {kind!r}")


def _parse_one(route: Route, name: str, args: list[str]) -> None:
    def nums(low: int, high: int) -> list[float]:
        if not low <= len(args) <= high:
            want = str(low) if low == high else f"{low}-{high}"
            raise ValueError(f"'{name}' takes {want} number(s)")
        return [float(a) for a in args]

    if name in ("forward", "fd"):
        route.forward(*nums(1, 1))
    elif name in ("back", "bk", "backward"):
        route.back(*nums(1, 1))
    elif name in ("left", "lt"):
        route.left(*nums(0, 1))
    elif name in ("right", "rt"):
        route.right(*nums(0, 1))
    elif name == "turn":
        route.turn(*nums(1, 1))
    elif name == "turn_to":
        route.turn_to(*nums(1, 1))
    elif name in ("u_turn", "uturn"):
        nums(0, 0)
        route.u_turn()
    elif name == "spin":
        route.spin(*nums(0, 1))
    elif name == "arc":
        route.arc(*nums(2, 2))
    elif name == "drive":
        speed, turn_rate, seconds = nums(3, 3)
        route.drive(speed, turn_rate, seconds=seconds)
    elif name in ("go_to", "goto"):
        route.go_to(*nums(2, 2))
    elif name == "wait":
        route.wait(*nums(1, 1))
    elif name == "speed":
        route.speed(*nums(1, 1))
    elif name == "lights":
        if args == ["on"]:
            route.lights_on()
        elif args == ["off"]:
            route.lights_off()
        else:
            raise ValueError("use 'lights on' or 'lights off'")
    elif name == "light":
        if len(args) != 2:
            raise ValueError("use 'light <name> <level 0-1>'")
        route.light(args[0], float(args[1]))
    elif name == "led":
        if len(args) != 1:
            raise ValueError("use 'led <off|on|blink|blink_fast|pulse>'")
        route.status_led(args[0])
    elif name == "marker":
        if not args:
            raise ValueError("use 'marker <label>'")
        route.marker(" ".join(args))
    else:
        raise ValueError(f"unknown move '{name}'")
