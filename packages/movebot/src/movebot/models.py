"""Small value types returned by the library."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Pose:
    """Where the bot thinks it is, relative to where it started (or last reset).

    ``x`` is forward and ``y`` is to the left, in metres. ``yaw`` is in radians,
    counter-clockwise positive; ``heading`` is the same angle in degrees.
    """

    x: float = 0.0
    y: float = 0.0
    yaw: float = 0.0

    @property
    def heading(self) -> float:
        """Which way the bot faces, in degrees (0 = the way it faced at the start, + = left)."""
        return math.degrees(self.yaw)

    def distance_to(self, other: Pose) -> float:
        """Straight-line distance to another pose, in metres."""
        return math.hypot(other.x - self.x, other.y - self.y)

    @classmethod
    def from_wire(cls, data: dict[str, Any]) -> Pose:
        return cls(
            float(data.get("x", 0.0)), float(data.get("y", 0.0)), float(data.get("yaw", 0.0))
        )

    def __str__(self) -> str:
        heading = self.heading
        if heading <= -179.95:  # show a half turn as 180°, not -180°
            heading += 360
        return f"x={self.x:.3f} m, y={self.y:.3f} m, heading={heading:.1f}°"


@dataclass(frozen=True)
class Wheel:
    ticks: int = 0
    speed: float = 0.0  # m/s


@dataclass(frozen=True)
class Encoders:
    """How far each wheel has turned (``ticks``) and how fast it turns now (``speed``, m/s).

    ``bot.encoders.left.ticks``, ``bot.encoders.right.speed``.
    """

    left: Wheel = field(default_factory=Wheel)
    right: Wheel = field(default_factory=Wheel)

    @classmethod
    def from_wire(cls, data: dict[str, Any]) -> Encoders:
        def wheel(d: dict[str, Any]) -> Wheel:
            return Wheel(int(d.get("ticks", 0)), float(d.get("speed", 0.0)))

        return cls(wheel(data.get("left", {})), wheel(data.get("right", {})))


@dataclass(frozen=True)
class StepResult:
    """What happened to one move (one plan step) on the bot."""

    seq: int
    op: str
    result: str  # "ok" | "failed" | "cancelled"
    pose: Pose
    reason: str | None = None
    t_start: int | None = None  # ms since the bot booted
    t_end: int | None = None

    @property
    def ok(self) -> bool:
        """True if the move finished normally (not failed or cancelled)."""
        return self.result == "ok"

    @property
    def duration(self) -> float | None:
        """How long the move took, in seconds."""
        if self.t_start is None or self.t_end is None:
            return None
        return (self.t_end - self.t_start) / 1000

    @classmethod
    def from_wire(cls, data: dict[str, Any]) -> StepResult:
        return cls(
            seq=int(data["seq"]),
            op=str(data.get("op", "")),
            result=str(data.get("result", "ok")),
            pose=Pose.from_wire(data.get("pose", {})),
            reason=data.get("reason"),
            t_start=data.get("t_start"),
            t_end=data.get("t_end"),
        )


@dataclass(frozen=True)
class RouteResult:
    """Planned versus actual pose for every step of a route."""

    steps: list[StepResult]
    expected: list[Pose]
    labels: list[str]

    @property
    def ok(self) -> bool:
        """True if every move of the route finished normally."""
        return all(step.ok for step in self.steps) and len(self.steps) == len(self.expected)

    @property
    def final_pose(self) -> Pose | None:
        """Where the bot ended up, as its wheels measured it."""
        return self.steps[-1].pose if self.steps else None

    @property
    def drift(self) -> float:
        """Distance (m) between where the route should have ended and where odometry says it did."""
        if not self.steps or not self.expected:
            return 0.0
        return self.expected[len(self.steps) - 1].distance_to(self.steps[-1].pose)

    def __str__(self) -> str:
        lines = [f"{'#':>3}  {'step':<22} {'result':<9} {'expected':<34} actual"]
        for i, expected in enumerate(self.expected):
            step = self.steps[i] if i < len(self.steps) else None
            result = step.result if step else "-"
            actual = str(step.pose) if step else "-"
            lines.append(f"{i + 1:>3}  {self.labels[i]:<22} {result:<9} {expected!s:<34} {actual}")
        lines.append(f"drift at the end: {self.drift * 100:.1f} cm")
        return "\n".join(lines)


# -- Wi-Fi (SPEC §12) ---------------------------------------------------------------------

WIFI_REASONS = {
    "not_found": "the network was not found (is the name right, and is it in range?)",
    "wrong_password": "the password is wrong",
    "no_ip": "it joined but did not get an address (check the static address settings)",
    "timeout": "the network did not answer in time",
    "unsupported": "the robot cannot join this kind of network (e.g. one that needs a user name)",
}


@dataclass(frozen=True)
class WifiNetwork:
    """A Wi-Fi network the bot can see: ``ssid`` (its name), ``rssi`` (signal strength in dBm:
    -40 is very strong, -80 weak), ``security`` (open, wpa, wpa2, wpa3 or enterprise)."""

    ssid: str
    rssi: int
    security: str
    channel: int | None = None

    @property
    def bars(self) -> int:
        """Signal strength as 0-4 bars, like on a phone."""
        return max(0, min(4, (self.rssi + 95) // 10))

    @property
    def needs_password(self) -> bool:
        """True unless the network is open."""
        return self.security != "open"

    def __str__(self) -> str:
        lock = "" if self.security == "open" else " (password)"
        return f"{self.ssid}  {'▮' * self.bars}{'▯' * (4 - self.bars)}{lock}"


@dataclass(frozen=True)
class WifiTest:
    """What happened when the bot tried a network: ``joined``, its ``ip`` there, ``reason``."""

    joined: bool
    ip: str | None = None
    rssi: int | None = None
    reason: str | None = None

    @property
    def message(self) -> str:
        """A sentence about the result, for people."""
        if self.joined:
            return f"joined, the robot's address there is {self.ip}"
        return WIFI_REASONS.get(self.reason or "", f"it did not work ({self.reason})")


@dataclass(frozen=True)
class WifiStatus:
    """How the bot is connected now, and what it will do after its next restart.

    ``mode``: ``"ap"`` (its own network, direct mode), ``"sta"`` (it joined a network) or
    ``"ap+sta"`` (both). ``ssid``/``ip``: the main way to reach it. ``hostname``: its name on
    a network (``<hostname>.local``). ``saved``: the settings for the next start (no
    passwords). ``pending_restart``: the saved settings are not in use yet.
    """

    mode: str
    ssid: str | None
    ip: str | None
    rssi: int | None
    hostname: str | None
    hotspot: dict[str, Any] | None  # the bot's own network, or None when it is off
    network: dict[str, Any] | None  # the network it joined (or tried to), or None
    saved: dict[str, Any]
    pending_restart: bool

    @classmethod
    def from_wire(cls, data: dict[str, Any]) -> WifiStatus:
        return cls(
            mode=str(data.get("mode", "ap")),
            ssid=data.get("ssid"),
            ip=data.get("ip"),
            rssi=data.get("rssi"),
            hostname=data.get("hostname"),
            hotspot=data.get("ap"),
            network=data.get("sta"),
            saved=dict(data.get("saved") or {}),
            pending_restart=bool(data.get("pending_restart", False)),
        )

    @property
    def address(self) -> str | None:
        """What to type to reach the bot on its network: ``movebot-xxxx.local``, or its IP."""
        if self.network and self.network.get("state") == "connected":
            return f"{self.hostname}.local" if self.hostname else self.network.get("ip")
        return self.ip

    def __str__(self) -> str:
        if self.network and self.network.get("state") == "connected":
            text = f"on the network {self.network['ssid']} at {self.network['ip']}"
            if self.hotspot:
                text += f", and its own network {self.hotspot['ssid']}"
        elif self.network:
            reason = WIFI_REASONS.get(self.network.get("reason") or "", "it could not join")
            text = f"could not join {self.network['ssid']} ({reason})"
            if self.hotspot:
                text += f"; its own network {self.hotspot['ssid']} is on"
        else:
            text = f"its own network {self.ssid} at {self.ip}"
        if self.pending_restart:
            text += " (new settings wait for a restart)"
        return text
