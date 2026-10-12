"""Wire-protocol constants and helpers shared by the library and the simulator.

The normative description lives in ``protocol/SPEC.md``; keep the two in sync.
"""

from __future__ import annotations

import json
import math
import secrets
from typing import Any

PROTOCOL_VERSION = "0.1"

WS_PATH = "/ws"
DEFAULT_BOT_HOST = "192.168.4.1"  # the bot's own access point (direct mode)
DEFAULT_BOT_PORT = 80
DEFAULT_LOCAL_PORT = 8765  # simulator / local relay on the host


class Err:
    """Error codes carried in ``res.error.code``."""

    BAD_REQUEST = "bad_request"
    UNKNOWN_COMMAND = "unknown_command"
    INVALID_PARAM = "invalid_param"
    INVALID_STATE = "invalid_state"
    BUSY = "busy"
    UNKNOWN_PLAN = "unknown_plan"
    UNKNOWN_MODULE = "unknown_module"
    GAP = "gap"
    NOT_SUPPORTED = "not_supported"
    INTERNAL = "internal"


PLAN_STATES = ("loaded", "running", "paused", "done", "failed", "cancelled")
ACTIVE_PLAN_STATES = frozenset({"loaded", "running", "paused"})
TERMINAL_PLAN_STATES = frozenset({"done", "failed", "cancelled"})
ON_DISCONNECT_POLICIES = ("continue", "finish_step", "stop")

STEP_OPS = (
    "drive",
    "turn",
    "turn_to",
    "arc",
    "drive_for",
    "wait",
    "light",
    "status",
    "speed",
    "marker",
    "stop",
)
FAILURE_REASONS = ("timeout", "stalled", "cancelled", "low_battery", "max_duration", "disconnect")

TOPICS = ("odom", "encoders", "power", "net", "status")  # plus "module.<id>" per module
CAMERA_PRESETS = ("fast", "balanced", "detail")
STATUS_PATTERNS = ("off", "on", "blink", "blink_fast", "pulse")
MAX_TELEMETRY_HZ = 50.0

# WebSocket close code a bot uses when it already has its maximum number of clients.
CLOSE_TOO_MANY_CLIENTS = 1013


def encode(message: dict[str, Any]) -> str:
    """Serialise a message as compact JSON (NaN/Infinity are not valid on the wire)."""
    return json.dumps(message, separators=(",", ":"), allow_nan=False)


def decode(text: str | bytes) -> dict[str, Any]:
    """Parse one wire message; raises ``ValueError`` if it is not a JSON object."""
    message = json.loads(text)
    if not isinstance(message, dict):
        raise ValueError("a message must be a JSON object")
    return message


def parse_version(version: str) -> tuple[int, int]:
    major, minor = version.split(".", 1)
    return int(major), int(minor)


def is_compatible(remote: str, local: str = PROTOCOL_VERSION) -> bool:
    """Can a client speaking ``local`` talk to a bot speaking ``remote``?

    Same major version is required. Before 1.0 the minor version must match exactly;
    from 1.0 on, minor versions only add features, so the bot's minor must be >= ours.
    """
    try:
        r_major, r_minor = parse_version(remote)
        l_major, l_minor = parse_version(local)
    except (ValueError, AttributeError):
        return False
    if r_major != l_major:
        return False
    return r_minor == l_minor if l_major == 0 else r_minor >= l_minor


def new_token(nbytes: int = 4) -> str:
    """Random hex token, used for client id prefixes, plan ids and boot ids."""
    return secrets.token_hex(nbytes)


def wrap_angle(angle: float) -> float:
    """Wrap an angle in radians to [-pi, pi)."""
    return (angle + math.pi) % (2 * math.pi) - math.pi
