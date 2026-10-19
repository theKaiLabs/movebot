"""Exceptions raised by the movebot library.

Messages are written for beginners: say what happened and what to try next.
"""

from __future__ import annotations

from typing import Any


class MoveBotError(Exception):
    """Base class for every movebot error."""


class NeedsMoveBotApp(MoveBotError, ImportError):
    """The simulator or the UI kit was used outside the MoveBot app."""


class BotNotFound(MoveBotError):
    """No MoveBot (or simulator) answered at any of the addresses we tried."""


class BotInUse(MoveBotError):
    """The bot refused the connection because another program is already connected."""


class IncompatibleBot(MoveBotError):
    """The bot speaks a protocol version this library does not understand."""


class ConnectionLost(MoveBotError):
    """The connection dropped and did not come back in time."""


class BotTimeout(MoveBotError):
    """The bot is connected but did not answer in time."""


class PlanLost(MoveBotError):
    """The bot restarted, so the moves it was holding are gone."""


class CommandError(MoveBotError):
    """The bot rejected a command. ``code`` is the protocol error code."""

    def __init__(self, code: str, message: str, detail: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.detail = detail or {}


class BotBusy(CommandError):
    """The bot is in the middle of something else (usually a move)."""


class InvalidParameter(CommandError):
    """A value sent to the bot was out of range or of the wrong type."""


class NotSupported(CommandError):
    """This bot does not have that feature (for example no camera, or no such module)."""


class MoveFailed(MoveBotError):
    """A move could not be completed (blocked wheels, timeout, ...)."""

    def __init__(self, message: str, *, seq: int | None = None, reason: str | None = None) -> None:
        super().__init__(message)
        self.seq = seq
        self.reason = reason


class MoveCancelled(MoveBotError):
    """A move was cancelled (``bot.stop()``, a route was cancelled, ...)."""


class WifiJoinFailed(MoveBotError):
    """The bot could not join a Wi-Fi network. ``reason`` says why (see ``WifiTest``)."""

    def __init__(self, message: str, *, reason: str | None = None) -> None:
        super().__init__(message)
        self.reason = reason


_FRIENDLY = {
    "busy": "MoveBot is busy: {msg}. Wait for the current move to finish, or call bot.stop().",
    "invalid_param": "MoveBot did not accept a value: {msg}",
    "not_supported": "This MoveBot cannot do that: {msg}",
    "unknown_module": "{msg}. Check bot.modules for what is plugged in.",
}


def error_from_response(cmd: str, error: dict[str, Any]) -> CommandError:
    """Turn a ``res.error`` object into the matching exception."""
    code = str(error.get("code", "internal"))
    msg = str(error.get("msg", "")) or code
    detail = {k: v for k, v in error.items() if k not in ("code", "msg")}
    text = _FRIENDLY.get(code, "MoveBot rejected '{cmd}': {msg} ({code})").format(
        cmd=cmd, msg=msg, code=code
    )
    cls = {
        "busy": BotBusy,
        "invalid_param": InvalidParameter,
        "not_supported": NotSupported,
        "unknown_module": NotSupported,
    }.get(code, CommandError)
    return cls(code, text, detail)
