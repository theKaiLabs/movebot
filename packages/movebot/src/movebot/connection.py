"""Async connection to a MoveBot (or simulator, or relay): requests, events, reconnects.

Requests that are waiting when the link drops are re-sent with the *same id* after
reconnecting. That is safe because every wire command is idempotent and the bot
de-duplicates request ids (protocol SPEC, "Requests").
"""

from __future__ import annotations

import asyncio
import contextlib
import itertools
import logging
import time
from collections.abc import Callable
from typing import Any
from urllib.parse import urlsplit

from websockets.asyncio.client import ClientConnection, connect
from websockets.exceptions import ConnectionClosed, InvalidHandshake, InvalidURI

from .errors import (
    BotInUse,
    BotTimeout,
    ConnectionLost,
    IncompatibleBot,
    error_from_response,
)
from .protocol import (
    CLOSE_TOO_MANY_CLIENTS,
    DEFAULT_BOT_PORT,
    PROTOCOL_VERSION,
    WS_PATH,
    decode,
    encode,
    is_compatible,
    new_token,
)

log = logging.getLogger("movebot")

MessageListener = Callable[[dict[str, Any]], None]
StateListener = Callable[[str, dict[str, Any]], None]

_CONNECT_ERRORS = (OSError, asyncio.TimeoutError, InvalidHandshake, InvalidURI, ConnectionClosed)
_ENVELOPE = frozenset({"type", "id", "cmd"})  # request fields that parameters must not shadow
_RESPONSE_ENVELOPE = frozenset({"type", "id", "ok"})


def normalize_url(target: str) -> str:
    """Accept ``"192.168.4.1"``, ``"localhost:8765"`` or a full ``ws://`` URL."""
    target = target.strip()
    if "://" not in target:
        target = "ws://" + target
    parts = urlsplit(target)
    if parts.scheme not in ("ws", "wss") or not parts.hostname:
        raise ValueError(f"not a MoveBot address: {target!r}")
    port = parts.port or DEFAULT_BOT_PORT
    path = parts.path or WS_PATH
    host = f"[{parts.hostname}]" if ":" in parts.hostname else parts.hostname
    return f"{parts.scheme}://{host}:{port}{path}"


class Connection:
    """One logical connection that survives Wi-Fi drops by reconnecting."""

    def __init__(
        self,
        url: str,
        *,
        request_timeout: float = 5.0,
        connect_timeout: float = 3.0,
        reconnect: bool = True,
    ) -> None:
        self.url = normalize_url(url)
        self.request_timeout = request_timeout
        self.connect_timeout = connect_timeout
        self.reconnect = reconnect
        self.hello: dict[str, Any] = {}
        self.latest: dict[str, dict[str, Any]] = {}  # last telemetry message per topic
        self.disconnected_since: float | None = None
        self._ws: ClientConnection | None = None
        self._prefix = new_token()
        self._ids = itertools.count(1)
        self._pending: dict[str, tuple[dict[str, Any], asyncio.Future[dict[str, Any]]]] = {}
        self._listeners: list[MessageListener] = []
        self._state_listeners: list[StateListener] = []
        self._subscriptions: dict[str, float] = {}
        self._reader: asyncio.Task[None] | None = None
        self._restore_task: asyncio.Task[None] | None = None
        self._closing = False

    # -- public --------------------------------------------------------------------------

    @property
    def connected(self) -> bool:
        return self._ws is not None

    @property
    def boot_id(self) -> str | None:
        return self.hello.get("boot_id")

    def limit(self, key: str, default: Any) -> Any:
        return self.hello.get("limits", {}).get(key, default)

    def add_listener(self, listener: MessageListener) -> None:
        """Called (on the event loop) for every ``evt`` and ``tlm`` message."""
        self._listeners.append(listener)

    def add_state_listener(self, listener: StateListener) -> None:
        """Called with ``"disconnected"`` or ``"reconnected"`` (info has ``rebooted``)."""
        self._state_listeners.append(listener)

    async def open(self) -> None:
        await self._connect_once()
        self._reader = asyncio.create_task(self._read_forever(), name="movebot-reader")

    async def close(self) -> None:
        self._closing = True
        if self._reader:
            self._reader.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await self._reader
        if self._ws is not None:
            with contextlib.suppress(Exception):
                await self._ws.close()
            self._ws = None
        self._fail_pending(ConnectionLost("The connection to MoveBot was closed."))

    async def request(
        self, cmd: str, *, timeout: float | None = None, **params: Any
    ) -> dict[str, Any]:
        """Send a command and return the result fields (raises on errors)."""
        response = await self.request_raw(cmd, params, timeout=timeout)
        if not response.get("ok"):
            raise error_from_response(cmd, response.get("error") or {})
        return {k: v for k, v in response.items() if k not in _RESPONSE_ENVELOPE}

    async def request_raw(
        self, cmd: str, params: dict[str, Any], *, timeout: float | None = None
    ) -> dict[str, Any]:
        """Send a command and return the response as-is, even if it is an error."""
        if self._closing:
            raise ConnectionLost("The connection to MoveBot is closed.")
        clash = _ENVELOPE & params.keys()
        if clash:
            raise ValueError(f"parameter name(s) {sorted(clash)} are reserved by the protocol")
        rid = f"{self._prefix}-{next(self._ids)}"
        message = {"type": "req", "id": rid, "cmd": cmd, **params}
        future: asyncio.Future[dict[str, Any]] = asyncio.get_running_loop().create_future()
        self._pending[rid] = (message, future)
        try:
            if self._ws is not None:
                # if sending fails, the request is re-sent after reconnecting
                with contextlib.suppress(ConnectionClosed):
                    await self._ws.send(encode(message))
            try:
                return await asyncio.wait_for(future, timeout or self.request_timeout)
            except asyncio.TimeoutError:
                if not self.connected:
                    raise ConnectionLost(
                        f"Lost the connection to MoveBot while sending '{cmd}'."
                    ) from None
                raise BotTimeout(f"MoveBot did not answer '{cmd}' in time.") from None
        finally:
            self._pending.pop(rid, None)

    async def subscribe(self, topics: list[str], rate_hz: float) -> None:
        for topic in topics:
            self._subscriptions[topic] = rate_hz
        await self.request("sub", topics=topics, rate_hz=rate_hz)

    async def unsubscribe(self, topics: list[str]) -> None:
        for topic in topics:
            self._subscriptions.pop(topic, None)
        await self.request("unsub", topics=topics)

    # -- internals -----------------------------------------------------------------------

    async def _connect_once(self) -> str | None:
        """Connect and read the hello. Returns the previous boot id (None on first connect)."""
        try:
            ws = await asyncio.wait_for(
                connect(
                    self.url,
                    open_timeout=self.connect_timeout,
                    ping_interval=1.0,
                    ping_timeout=2.0,
                    close_timeout=1.0,
                    max_size=2**22,
                ),
                self.connect_timeout + 1,
            )
        except ConnectionClosed as exc:
            raise _in_use_or(exc) from None
        try:
            hello = decode(await asyncio.wait_for(ws.recv(), self.connect_timeout))
        except ConnectionClosed as exc:
            raise _in_use_or(exc) from None
        except (asyncio.TimeoutError, ValueError):
            await ws.close()
            raise IncompatibleBot(f"{self.url} answered, but it is not a MoveBot.") from None
        if hello.get("type") != "hello":
            await ws.close()
            raise IncompatibleBot(f"{self.url} answered, but it is not a MoveBot.")
        if not is_compatible(str(hello.get("protocol", ""))):
            await ws.close()
            raise IncompatibleBot(
                f"This MoveBot speaks protocol {hello.get('protocol')} but this library "
                f"speaks {PROTOCOL_VERSION}. Update the MoveBot app/library or the bot firmware."
            )
        previous = self.hello.get("boot_id")
        self.hello = hello
        self._ws = ws
        self.disconnected_since = None
        return previous

    async def _read_forever(self) -> None:
        while not self._closing:
            ws = self._ws
            if ws is not None:
                try:
                    async for raw in ws:
                        self._dispatch(raw)
                except ConnectionClosed:
                    pass
            self._ws = None
            if self._closing:
                return
            self.disconnected_since = time.monotonic()
            log.warning("lost the connection to MoveBot, reconnecting...")
            self._notify("disconnected", {})
            if not self.reconnect:
                self._fail_pending(ConnectionLost("Lost the connection to MoveBot."))
                return
            previous_boot = await self._reconnect()
            if previous_boot is _CLOSED:
                return
            rebooted = previous_boot != self.boot_id
            await self._resend_pending()
            # Not awaited here: responses are read by this very task.
            self._restore_task = asyncio.create_task(self._restore_subscriptions())
            log.warning("reconnected to MoveBot%s", " (it restarted)" if rebooted else "")
            self._notify("reconnected", {"rebooted": rebooted})

    async def _reconnect(self) -> Any:
        delay = 0.1
        while not self._closing:
            try:
                return await self._connect_once()
            except (*_CONNECT_ERRORS, BotInUse, IncompatibleBot) as exc:
                log.debug("reconnect failed: %s", exc)
                await asyncio.sleep(delay)
                delay = min(delay * 2, 2.0)
        return _CLOSED

    async def _resend_pending(self) -> None:
        for message, future in list(self._pending.values()):
            if not future.done() and self._ws is not None:
                with contextlib.suppress(ConnectionClosed):
                    await self._ws.send(encode(message))

    async def _restore_subscriptions(self) -> None:
        by_rate: dict[float, list[str]] = {}
        for topic, rate in self._subscriptions.items():
            by_rate.setdefault(rate, []).append(topic)
        for rate, topics in by_rate.items():
            with contextlib.suppress(Exception):
                await self.request("sub", topics=topics, rate_hz=rate)

    def _dispatch(self, raw: str | bytes) -> None:
        try:
            message = decode(raw)
        except ValueError:
            log.warning("ignoring a malformed message from MoveBot")
            return
        kind = message.get("type")
        if kind == "res":
            entry = self._pending.get(str(message.get("id")))
            if entry and not entry[1].done():
                entry[1].set_result(message)
            return
        if kind == "tlm":
            self.latest[str(message.get("topic"))] = message
        if kind in ("evt", "tlm"):
            for listener in list(self._listeners):
                try:
                    listener(message)
                except Exception:
                    log.exception("movebot listener failed")

    def _notify(self, state: str, info: dict[str, Any]) -> None:
        for listener in list(self._state_listeners):
            try:
                listener(state, info)
            except Exception:
                log.exception("movebot state listener failed")

    def _fail_pending(self, exc: Exception) -> None:
        for _, future in self._pending.values():
            if not future.done():
                future.set_exception(exc)


_CLOSED = object()


def _in_use_or(exc: ConnectionClosed) -> Exception:
    if exc.rcvd is not None and exc.rcvd.code == CLOSE_TOO_MANY_CLIENTS:
        return BotInUse(
            "MoveBot is already connected to other programs. Close them (or run your "
            "script from the MoveBot app) and try again."
        )
    return ConnectionLost("MoveBot closed the connection while connecting.")
