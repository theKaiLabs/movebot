"""Relay: one connection to the bot, shared with every program on this computer.

An ESP32 bot only handles a few connections and usually a single camera viewer. The
relay owns that one connection (and the one camera stream) and serves the very same
protocol to local programs, so ``Bot()`` works the same whether it talks to a bot, a relay
or the simulator (protocol SPEC §11, ADR 0002)::

    movebot relay 192.168.4.1        # then, in any number of programs: Bot()

What the relay does on top of forwarding:

* fans out events, telemetry (each client at its own rate) and the camera stream;
* keeps request ids unique towards the bot and replays answers to repeated local ids;
* applies the bot's safety rules to *local* connections: when the program that is driving
  manually disconnects, the bot is stopped; plans follow their ``on_disconnect`` policy
  when the program that owns them disconnects;
* if the bot restarts, local programs are disconnected so they notice the new boot id.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import threading
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any

from websockets.asyncio.server import Server, ServerConnection, serve
from websockets.exceptions import ConnectionClosed

from ._runtime import cancel_all_tasks
from ._version import __version__
from .camera import AsyncCamera
from .connection import Connection
from .errors import BotTimeout, ConnectionLost
from .mjpeg import Frame, MjpegReader, MjpegServer
from .protocol import (
    CLOSE_TOO_MANY_CLIENTS,
    DEFAULT_LOCAL_PORT,
    MAX_TELEMETRY_HZ,
    TERMINAL_PLAN_STATES,
    TOPICS,
    WS_PATH,
    Err,
    decode,
    encode,
    new_token,
)

log = logging.getLogger("movebot.relay")

CLOSE_BOT_RESTARTED = 1012  # "service restart": the bot rebooted, reconnect to see it
REPLY_CACHE_SIZE = 256
MANUAL_COMMANDS = frozenset({"motor.write", "drive.velocity"})


@dataclass
class _Local:
    ws: ServerConnection
    id: str = field(default_factory=new_token)
    subs: dict[str, float] = field(default_factory=dict)  # topic -> requested rate (Hz)
    due: dict[str, float] = field(default_factory=dict)
    # Everything for this client goes through one queue, so replies, events and telemetry
    # arrive in the order the relay saw them.
    outbox: asyncio.Queue[dict[str, Any]] = field(default_factory=asyncio.Queue)


class Relay:
    def __init__(
        self,
        upstream: str,
        *,
        host: str = "127.0.0.1",
        port: int = DEFAULT_LOCAL_PORT,
        camera_port: int | None = None,
        max_clients: int = 8,
    ) -> None:
        self.conn = Connection(upstream)
        self.host = host
        self.port = port
        self.camera_port = camera_port if camera_port is not None else (port + 1 if port else 0)
        self.max_clients = max_clients
        self._server: Server | None = None
        self._clients: dict[str, _Local] = {}
        self._replies: OrderedDict[Any, dict[str, Any]] = OrderedDict()
        self._modules: list[dict[str, Any]] = []
        self._manual_owner: str | None = None
        self._plan_owners: dict[str, tuple[str, str]] = {}  # plan_id -> (client, policy)
        self._cancel_when_paused: set[str] = set()
        self._upstream_subs: dict[str, float] = {}
        self._ready = asyncio.Event()
        self._last_t = 0
        self._tasks: set[asyncio.Task[Any]] = set()
        self._camera_reader: MjpegReader | None = None
        self._mjpeg: MjpegServer | None = None

    @property
    def url(self) -> str:
        return f"ws://{self.host}:{self.port}{WS_PATH}"

    # -- lifecycle -------------------------------------------------------------------------

    async def start(self) -> None:
        await self.conn.open()
        self.conn.add_listener(self._on_upstream_message)
        self.conn.add_state_listener(self._on_upstream_state)
        self._modules = list(self.conn.hello.get("modules", []))
        self._ready.set()
        camera = AsyncCamera(self.conn)
        if camera.available:
            self._camera_reader = MjpegReader(camera.stream_url)
            self._mjpeg = MjpegServer(
                self._camera_frame,
                host=self.host,
                port=self.camera_port,
                on_clients=self._camera_clients,
            )
            await self._mjpeg.start()
            self.camera_port = self._mjpeg.port
        self._server = await serve(
            self._handle, self.host, self.port, ping_interval=None, max_size=2**20
        )
        self.port = self._server.sockets[0].getsockname()[1]
        log.info("relaying %s on %s", self.conn.url, self.url)

    async def stop(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
        if self._mjpeg is not None:
            await self._mjpeg.stop()
        if self._camera_reader is not None:
            await self._camera_reader.stop()
        for task in list(self._tasks):
            task.cancel()
        await self.conn.close()

    def _spawn(self, coro: Any) -> None:
        task = asyncio.create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    # -- local connections -----------------------------------------------------------------

    def _hello(self) -> dict[str, Any]:
        hello = {k: v for k, v in self.conn.hello.items() if k != "type"}
        hello["modules"] = list(self._modules)
        hello["limits"] = {**hello.get("limits", {}), "max_clients": self.max_clients}
        caps = dict(hello.get("capabilities", {}))
        if caps.get("camera") and self._mjpeg is not None:
            caps["camera"] = {**caps["camera"], "stream_port": self.camera_port}
        hello["capabilities"] = caps
        hello["relay"] = {"version": __version__, "upstream": self.conn.url}
        return {"type": "hello", **hello}

    async def _handle(self, ws: ServerConnection) -> None:
        if len(self._clients) >= self.max_clients:
            await ws.close(
                CLOSE_TOO_MANY_CLIENTS, "the relay has its maximum number of connections"
            )
            return
        try:
            await asyncio.wait_for(self._ready.wait(), 10)
        except asyncio.TimeoutError:
            await ws.close(CLOSE_TOO_MANY_CLIENTS, "the relay cannot reach MoveBot right now")
            return
        local = _Local(ws)
        self._clients[local.id] = local
        local.outbox.put_nowait(self._hello())
        sender = asyncio.create_task(self._sender(local))
        try:
            async for raw in ws:
                await self._on_local_message(local, raw)
        except ConnectionClosed:
            pass
        finally:
            sender.cancel()
            del self._clients[local.id]
            await self._local_gone(local)

    async def _sender(self, local: _Local) -> None:
        with contextlib.suppress(ConnectionClosed):
            while True:
                await local.ws.send(encode(await local.outbox.get()))

    async def _on_local_message(self, local: _Local, raw: str | bytes) -> None:
        try:
            msg = decode(raw)
        except ValueError:
            self._send(local, _error(None, Err.BAD_REQUEST, "message is not a JSON object"))
            return
        rid = msg.get("id")
        if msg.get("type") != "req" or isinstance(rid, bool) or not isinstance(rid, (str, int)):
            self._send(local, _error(None, Err.BAD_REQUEST, "expected a request with an id"))
            return
        cmd = msg.get("cmd")
        params = {k: v for k, v in msg.items() if k not in ("type", "id", "cmd")}
        reply = self._replies.get(rid)
        if reply is None:
            if cmd in ("sub", "unsub"):
                reply = await self._subscription(local, rid, cmd, params)
            else:
                reply = await self._forward(local, rid, str(cmd), params)
            self._replies[rid] = reply
            while len(self._replies) > REPLY_CACHE_SIZE:
                self._replies.popitem(last=False)
        self._send(local, reply)

    async def _forward(
        self, local: _Local, rid: Any, cmd: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        try:
            response = await self.conn.request_raw(cmd, params)
        except (ConnectionLost, BotTimeout) as exc:
            return _error(rid, Err.INTERNAL, f"the relay could not reach MoveBot: {exc}")
        except ValueError as exc:  # parameters that clash with the envelope
            return _error(rid, Err.BAD_REQUEST, str(exc))
        reply = {**response, "type": "res", "id": rid}
        if response.get("ok"):
            self._track(local, cmd, params)
            if cmd == "sim.reboot":
                self._ready.clear()  # the simulator is about to drop us, like a real reboot
        return reply

    def _track(self, local: _Local, cmd: str, params: dict[str, Any]) -> None:
        """Remember who drives and who owns which plan, for the disconnect rules."""
        if cmd in MANUAL_COMMANDS:
            self._manual_owner = local.id
        elif cmd == "stop":
            self._manual_owner = None
        plan_id = params.get("plan_id")
        if cmd.startswith("plan.") and isinstance(plan_id, str):
            if cmd == "plan.load" and plan_id not in self._plan_owners:
                policy = params.get("on_disconnect", "continue")
                self._plan_owners[plan_id] = (local.id, str(policy))
            elif plan_id in self._plan_owners:
                self._plan_owners[plan_id] = (local.id, self._plan_owners[plan_id][1])

    async def _local_gone(self, local: _Local) -> None:
        with contextlib.suppress(Exception):
            await self._update_upstream_subscriptions()
        if self._manual_owner == local.id:
            self._manual_owner = None
            with contextlib.suppress(Exception):
                await self.conn.request("drive.velocity", v=0.0, w=0.0)
            self._broadcast(
                {"type": "evt", "evt": "motion.stopped", "t": self._last_t, "reason": "disconnect"}
            )
        for plan_id, (owner, policy) in list(self._plan_owners.items()):
            if owner != local.id:
                continue
            with contextlib.suppress(Exception):
                if policy == "stop":
                    await self.conn.request("plan.cancel", plan_id=plan_id)
                elif policy == "finish_step":
                    status = await self.conn.request("plan.pause", plan_id=plan_id)
                    if status.get("state") == "paused":
                        await self.conn.request("plan.cancel", plan_id=plan_id)
                    elif status.get("state") not in TERMINAL_PLAN_STATES:
                        self._cancel_when_paused.add(plan_id)

    # -- subscriptions -----------------------------------------------------------------------

    def _known_topic(self, topic: Any) -> bool:
        if not isinstance(topic, str):
            return False
        if topic in TOPICS:
            return True
        return topic.startswith("module.") and any(
            m.get("id") == topic[len("module.") :] for m in self._modules
        )

    async def _subscription(
        self, local: _Local, rid: Any, cmd: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        topics = params.get("topics")
        if not isinstance(topics, list) or not all(self._known_topic(t) for t in topics):
            return _error(rid, Err.INVALID_PARAM, "'topics' must be a list of known topics")
        if cmd == "unsub":
            for topic in topics:
                local.subs.pop(topic, None)
        else:
            rate = params.get("rate_hz", 10)
            if isinstance(rate, bool) or not isinstance(rate, (int, float)) or rate <= 0:
                return _error(rid, Err.INVALID_PARAM, "'rate_hz' must be a positive number")
            for topic in topics:
                local.subs[topic] = min(float(rate), MAX_TELEMETRY_HZ)
                local.due[topic] = 0.0
        try:
            await self._update_upstream_subscriptions()
        except (ConnectionLost, BotTimeout) as exc:
            return _error(rid, Err.INTERNAL, f"the relay could not reach MoveBot: {exc}")
        return {"type": "res", "id": rid, "ok": True, "topics": sorted(local.subs)}

    async def _update_upstream_subscriptions(self) -> None:
        wanted: dict[str, float] = {}
        for local in self._clients.values():
            for topic, rate in local.subs.items():
                wanted[topic] = max(rate, wanted.get(topic, 0.0))
        gone = [t for t in self._upstream_subs if t not in wanted]
        if gone:
            await self.conn.unsubscribe(gone)
        by_rate: dict[float, list[str]] = {}
        for topic, rate in wanted.items():
            if self._upstream_subs.get(topic) != rate:
                by_rate.setdefault(rate, []).append(topic)
        for rate, topics in by_rate.items():
            await self.conn.subscribe(topics, rate)
        self._upstream_subs = wanted

    # -- traffic from the bot ---------------------------------------------------------------

    def _on_upstream_message(self, message: dict[str, Any]) -> None:
        if isinstance(message.get("t"), int):
            self._last_t = message["t"]
        if message.get("type") == "tlm":
            self._fan_out_telemetry(message)
            return
        evt = message.get("evt")
        if evt == "module.added" and isinstance(message.get("module"), dict):
            self._modules = [m for m in self._modules if m.get("id") != message["module"].get("id")]
            self._modules.append(message["module"])
        elif evt == "module.removed":
            self._modules = [m for m in self._modules if m.get("id") != message.get("module_id")]
        plan_id = message.get("plan_id")
        if evt == "plan.paused" and plan_id in self._cancel_when_paused:
            self._cancel_when_paused.discard(plan_id)
            self._spawn(self.conn.request("plan.cancel", plan_id=plan_id))
        elif evt in ("plan.done", "plan.failed", "plan.cancelled"):
            self._plan_owners.pop(str(plan_id), None)
            self._cancel_when_paused.discard(str(plan_id))
        self._broadcast(message)

    def _fan_out_telemetry(self, message: dict[str, Any]) -> None:
        topic = message.get("topic")
        now = asyncio.get_running_loop().time()
        for local in self._clients.values():
            rate = local.subs.get(str(topic))
            if rate and now >= local.due.get(str(topic), 0.0):
                local.due[str(topic)] = now + 1 / rate - 0.005  # small slack for jitter
                if local.outbox.qsize() < 100:  # a slow reader gets fewer samples
                    self._send(local, message)

    def _on_upstream_state(self, state: str, info: dict[str, Any]) -> None:
        if state == "disconnected":
            self._ready.clear()
            return
        self._modules = list(self.conn.hello.get("modules", []))
        self._ready.set()
        if info.get("rebooted"):
            # Plans and settings are gone; local programs must notice the new boot id.
            self._manual_owner = None
            self._plan_owners.clear()
            self._cancel_when_paused.clear()
            self._upstream_subs = {}
            for local in list(self._clients.values()):
                self._spawn(local.ws.close(CLOSE_BOT_RESTARTED, "MoveBot restarted"))

    def _broadcast(self, message: dict[str, Any]) -> None:
        for local in list(self._clients.values()):
            self._send(local, message)

    def _send(self, local: _Local, message: dict[str, Any]) -> None:
        local.outbox.put_nowait(message)

    # -- camera -------------------------------------------------------------------------------

    async def _camera_frame(self, after_seq: int | None) -> Frame:
        assert self._camera_reader is not None
        return await self._camera_reader.wait_frame(after_seq, timeout=10)

    def _camera_clients(self, count: int) -> None:
        # Only keep the bot's (single) stream open while someone here is watching.
        if count == 0 and self._camera_reader is not None:
            self._spawn(self._camera_reader.stop())


class RelayThread:
    """A relay on its own thread and event loop (for tests and non-asyncio tools)."""

    def __init__(self, upstream: str, *, port: int = 0, max_clients: int = 8) -> None:
        self.loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self.loop.run_forever, name="movebot-relay", daemon=True
        )
        self._upstream = upstream
        self._port = port
        self._max_clients = max_clients
        self.relay: Relay | None = None

    @property
    def url(self) -> str:
        assert self.relay is not None
        return self.relay.url

    def start(self) -> RelayThread:
        self._thread.start()

        async def create() -> Relay:
            relay = Relay(self._upstream, port=self._port, max_clients=self._max_clients)
            await relay.start()
            return relay

        self.relay = asyncio.run_coroutine_threadsafe(create(), self.loop).result(10)
        return self

    def stop(self) -> None:
        if self.relay is not None:
            asyncio.run_coroutine_threadsafe(self.relay.stop(), self.loop).result(10)
        asyncio.run_coroutine_threadsafe(cancel_all_tasks(), self.loop).result(5)
        self.loop.call_soon_threadsafe(self.loop.stop)
        self._thread.join(5)

    def __enter__(self) -> RelayThread:
        return self.start()

    def __exit__(self, *exc: object) -> None:
        self.stop()


def _error(rid: Any, code: str, msg: str) -> dict[str, Any]:
    return {"type": "res", "id": rid, "ok": False, "error": {"code": code, "msg": msg}}
