"""Async API. Beginners use :class:`movebot.Bot`; this is what it runs underneath.

Use it directly from asyncio programs::

    bot = await AsyncBot.connect("sim")
    await bot.forward(0.5)
    await bot.close()
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import math
import os
from collections.abc import Callable
from typing import Any

from websockets.exceptions import InvalidHandshake

from . import _studio
from .camera import AsyncCamera
from .colors import to_rgb
from .connection import Connection
from .errors import BotBusy, BotNotFound, BotTimeout, ConnectionLost
from .models import (
    Encoders,
    Pose,
    RouteResult,
    StepResult,
    WifiNetwork,
    WifiStatus,
    WifiTest,
)
from .plans import Plan
from .protocol import DEFAULT_BOT_HOST, DEFAULT_LOCAL_PORT, WS_PATH
from .route import CompiledStep, Route

log = logging.getLogger("movebot")

_CONNECT_ERRORS = (OSError, asyncio.TimeoutError, ConnectionLost, InvalidHandshake)
_TELEMETRY = ["odom", "encoders", "power", "status"]

# bot events -> names used with bot.on(...)
_EVENT_NAMES = {
    "plan.marker": "marker",
    "plan.step_done": "step_done",
    "plan.failed": "move_failed",
    "motion.stopped": "stopped",
    "module.added": "module_added",
    "module.removed": "module_removed",
    "module.event": "module_event",
    "camera.streaming": "camera_streaming",
}


class AsyncBot:
    def __init__(self, conn: Connection, *, sim_server: Any = None) -> None:
        self.conn = conn
        self.sim_server = sim_server
        self._session: Plan | None = None  # plan used for single moves like forward()
        self._plans: list[Plan] = []
        self._hold: tuple[str, dict[str, Any]] | None = None  # velocity/raw command to keep alive
        self._hold_task: asyncio.Task[None] | None = None
        self._callbacks: dict[str, list[Callable[[Any], Any]]] = {}
        self._lights: dict[str, float] = {}
        self.camera = AsyncCamera(conn)
        self.module_descriptors: dict[str, dict[str, Any]] = {}
        self._load_modules()

    # -- connecting ----------------------------------------------------------------------

    @classmethod
    async def connect(cls, target: Any = None, *, timeout: float = 5.0) -> AsyncBot:
        """Connect to a bot.

        ``target`` can be an address (``"192.168.4.1"``, ``"ws://..."``), ``"sim"`` (a
        simulator inside this program; comes with the MoveBot app), simulator options, or
        ``None``: then ``$MOVEBOT_URL``, a simulator or app on this computer (port 8765)
        and the bot's own Wi-Fi (192.168.4.1) are tried.
        """
        if target is None:
            target = os.environ.get("MOVEBOT_URL") or None
        sim_server = None
        if target == "sim" or (target is not None and not isinstance(target, str)):
            sim = _studio.load("sim", "The simulator (Bot('sim'))")
            sim_server = sim.SimServer(port=0, options=None if target == "sim" else target)
            await sim_server.start()
            target = sim_server.url
        if target is not None:
            conn = Connection(str(target), request_timeout=timeout)
            try:
                await conn.open()
            except _CONNECT_ERRORS as exc:
                raise BotNotFound(
                    f"Could not reach MoveBot at {conn.url} ({exc.__class__.__name__}). "
                    "Is it switched on, and is this computer on the same Wi-Fi?"
                ) from None
        else:
            conn = await _discover(timeout)
        bot = cls(conn, sim_server=sim_server)
        await bot._setup()
        return bot

    async def _setup(self) -> None:
        self.conn.add_listener(self._on_message)
        self.conn.add_state_listener(self._on_state)
        await self.conn.subscribe(_TELEMETRY, 10)
        self._lights = dict((await self.conn.request("light.get")).get("lights", {}))

    async def close(self, *, stop: bool = True) -> None:
        """Disconnect. By default the bot is stopped first (your program is done with it)."""
        self._hold = None
        if stop and self.conn.connected:
            with contextlib.suppress(Exception):
                await self.conn.request("stop", timeout=2)
        if self._hold_task:
            self._hold_task.cancel()
        for plan in self._plans:
            if not plan.finished:
                plan._finish("cancelled")
        await self.camera.stop()
        await self.conn.close()
        if self.sim_server is not None:
            await self.sim_server.stop()

    async def __aenter__(self) -> AsyncBot:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()

    # -- information ---------------------------------------------------------------------

    @property
    def info(self) -> dict[str, Any]:
        """Everything the bot said about itself when we connected (its ``hello``)."""
        return self.conn.hello

    @property
    def name(self) -> str:
        return str(self.conn.hello.get("name", "MoveBot"))

    @property
    def light_names(self) -> list[str]:
        return list(self.conn.hello.get("capabilities", {}).get("lights", []))

    @property
    def status_led_names(self) -> list[str]:
        return list(self.conn.hello.get("capabilities", {}).get("status_leds", []))

    @property
    def color_led_names(self) -> list[str]:
        """Status LEDs that also take a colour (the RGB LED)."""
        return list(self.conn.hello.get("capabilities", {}).get("color_leds", []))

    async def get_pose(self) -> Pose:
        return Pose.from_wire(await self.conn.request("odom.get"))

    async def get_encoders(self) -> Encoders:
        return Encoders.from_wire(await self.conn.request("encoder.get"))

    @property
    def battery(self) -> float | None:
        """Battery level in percent (from telemetry), or None if not known yet."""
        power = self.conn.latest.get("power")
        return float(power["percent"]) if power else None

    async def reset_odometry(self) -> None:
        """Make the current position the new origin (x=0, y=0, heading=0)."""
        await self.conn.request("odom.reset")

    # -- single moves --------------------------------------------------------------------

    async def forward(
        self, distance: float, *, speed: float | None = None, wait: bool = True
    ) -> Any:
        return await self._move(_one(Route().forward(distance, speed=speed)), wait)

    async def back(self, distance: float, *, speed: float | None = None, wait: bool = True) -> Any:
        return await self._move(_one(Route().back(distance, speed=speed)), wait)

    async def turn(self, degrees: float, *, speed: float | None = None, wait: bool = True) -> Any:
        return await self._move(_one(Route().turn(degrees, speed=speed)), wait)

    async def left(self, degrees: float = 90, *, wait: bool = True) -> Any:
        return await self.turn(abs(degrees), wait=wait)

    async def right(self, degrees: float = 90, *, wait: bool = True) -> Any:
        return await self.turn(-abs(degrees), wait=wait)

    async def u_turn(self, *, wait: bool = True) -> Any:
        return await self.turn(180, wait=wait)

    async def spin(self, degrees: float = 360, *, wait: bool = True) -> Any:
        return await self.turn(degrees, wait=wait)

    async def turn_to(self, heading: float, *, wait: bool = True) -> Any:
        return await self._move(_one(Route().turn_to(heading)), wait)

    async def arc(self, radius: float, degrees: float, *, wait: bool = True) -> Any:
        return await self._move(_one(Route().arc(radius, degrees)), wait)

    async def wait(self, seconds: float, *, wait: bool = True) -> Any:
        """Pause between moves (the bot waits, so it stays in order with other moves)."""
        return await self._move(_one(Route().wait(seconds)), wait)

    async def _move(self, step: dict[str, Any], wait: bool) -> StepResult | tuple[Plan, int]:
        self._hold = None
        plan = self._session
        if plan is None or plan.ended:
            plan = self._session = self._new_plan(open_ended=True)
        seq = plan.add(step)
        if not wait:
            return plan, seq
        return await plan.result(seq)

    # -- continuous control --------------------------------------------------------------

    async def drive(
        self,
        speed: float,
        turn_rate: float = 0.0,
        *,
        seconds: float | None = None,
        wait: bool = True,
    ) -> Any:
        """Drive at ``speed`` m/s, turning at ``turn_rate`` degrees/s (+ = left).

        Without ``seconds`` the bot keeps going until you call ``stop()`` or another move
        (and stops by itself if this program ends or the connection drops).
        """
        if seconds is not None:
            return await self._move(_one(Route().drive(speed, turn_rate, seconds=seconds)), wait)
        await self._hold_command(
            "drive.velocity", {"v": float(speed), "w": math.radians(turn_rate)}
        )
        return None

    async def motors(self, left: float, right: float) -> None:
        """Raw motor power from -1 (full reverse) to 1 (full forward), held until stop()."""
        await self._hold_command("motor.write", {"left": float(left), "right": float(right)})

    async def stop(self) -> None:
        """Stop now: cancels running and queued moves and any drive()/motors() command."""
        self._hold = None
        await self.conn.request("stop")
        if self._session is not None:
            self._session._needs_sync = True
            self._session._kick()
        self._session = None

    async def _hold_command(self, cmd: str, params: dict[str, Any]) -> None:
        try:
            await self.conn.request(cmd, **params)
        except BotBusy:
            raise BotBusy(
                "busy",
                "MoveBot is still doing a move. Wait for it to finish (or call bot.stop()) "
                "before using drive() or motors().",
            ) from None
        self._hold = (cmd, params)
        if self._hold_task is None or self._hold_task.done():
            self._hold_task = asyncio.create_task(self._keep_alive(), name="movebot-hold")

    async def _keep_alive(self) -> None:
        interval = float(self.conn.limit("command_timeout_ms", 500)) / 1000 / 3
        while self._hold is not None:
            await asyncio.sleep(interval)
            hold = self._hold
            if hold is None or not self.conn.connected:
                continue
            try:
                await self.conn.request(hold[0], **hold[1])
            except BotBusy:
                self._hold = None
            except (ConnectionLost, BotTimeout):
                pass

    # -- speed, lights, status LED -------------------------------------------------------

    async def get_speed(self) -> float:
        """Current speed limit in percent of the bot's maximum."""
        current = await self.conn.request("speed.get")
        return 100 * float(current["linear"]) / float(self.conn.limit("max_linear", 0.4))

    async def set_speed(self, percent: float) -> None:
        """Set the speed limit for moves, in percent of the bot's maximum (1-100)."""
        fraction = max(1.0, min(float(percent), 100.0)) / 100
        await self.conn.request(
            "speed.set",
            linear=fraction * float(self.conn.limit("max_linear", 0.4)),
            angular=fraction * float(self.conn.limit("max_angular", 4.0)),
        )

    async def set_light(self, level: float, name: str | None = None) -> None:
        """Set one light (or all, if ``name`` is None) to ``level`` between 0 and 1."""
        for light in [name] if name else self.light_names:
            await self.conn.request("light.set", name=light, level=float(level))
            self._lights[light] = float(level)

    def light_level(self, name: str | None = None) -> float:
        if name:
            return self._lights.get(name, 0.0)
        return max(self._lights.values(), default=0.0)

    async def set_status_led(
        self, pattern: str, name: str | None = None, color: Any = None
    ) -> None:
        """``pattern`` is one of off, on, blink, blink_fast, pulse. ``color`` (a name such as
        ``"red"``, ``"#ff8800"`` or ``(r, g, b)``) is for the RGB LED only."""
        params: dict[str, Any] = {"pattern": pattern}
        if color is not None:
            params["color"] = list(to_rgb(color))
        for led in [name] if name else self.status_led_names:
            await self.conn.request("status.set", name=led, **params)

    # -- setting up: Wi-Fi, name, restart (SPEC §12) -----------------------------------------

    async def wifi_status(self) -> WifiStatus:
        """How the bot is connected now, and what is saved for its next start."""
        return WifiStatus.from_wire(await self.conn.request("wifi.status"))

    async def wifi_scan(self, timeout: float = 4.0) -> list[WifiNetwork]:
        """The Wi-Fi networks the bot can see, strongest first."""
        ms = round(min(max(timeout, 0.5), 10.0) * 1000)
        found = await self.conn.request("wifi.scan", timeout_ms=ms, timeout=timeout + 5)
        return [
            WifiNetwork(str(n["ssid"]), int(n["rssi"]), str(n["security"]), n.get("channel"))
            for n in found.get("networks", [])
        ]

    async def wifi_test(
        self, ssid: str, password: str = "", *, static: dict[str, str] | None = None,
        timeout: float = 15.0,
    ) -> WifiTest:  # fmt: skip
        """Let the bot try a network without changing anything (it stays reachable)."""
        ms = round(min(max(timeout, 1.0), 20.0) * 1000)
        result = await self.conn.request(
            "wifi.test", ssid=ssid, password=password, timeout_ms=ms, timeout=timeout + 5,
            **(static or {}),
        )  # fmt: skip
        return WifiTest(bool(result.get("joined")), result.get("ip"), result.get("rssi"),
                        result.get("reason"))  # fmt: skip

    async def wifi_save(self, **settings: Any) -> dict[str, Any]:
        """Save Wi-Fi settings (the ``wifi.set`` fields); they apply after a restart."""
        return (await self.conn.request("wifi.set", **settings))["saved"]

    async def wifi_reset(self) -> dict[str, Any]:
        """Back to factory Wi-Fi settings (its own network); applies after a restart."""
        return (await self.conn.request("wifi.reset_ap"))["saved"]

    async def rename(self, name: str) -> None:
        """Give the bot a new name (also of its own network); applies after a restart."""
        await self.conn.request("device.set", name=name)

    async def restart(self, *, wait: bool = True, timeout: float = 20.0) -> None:
        """Restart the bot. With ``wait``, return once it is back and connected again."""
        before = self.conn.boot_id
        await self.conn.request("system.restart", delay_ms=300)
        if not wait:
            return
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        while not (self.conn.connected and self.conn.boot_id != before):
            if loop.time() > deadline:
                raise ConnectionLost(
                    "MoveBot restarted but did not come back on this network. If it joined "
                    "another Wi-Fi network, connect this computer to that network too."
                )
            await asyncio.sleep(0.2)

    # -- modules ---------------------------------------------------------------------------

    def _load_modules(self) -> None:
        self.module_descriptors = {
            str(m["id"]): m for m in self.conn.hello.get("modules", []) if isinstance(m, dict)
        }

    async def read_module(self, module_id: str) -> dict[str, Any]:
        """Fresh values from a module, e.g. ``{"distance": 0.42, "valid": True}``."""
        return (await self.conn.request("module.read", module_id=module_id))["values"]

    async def call_module(self, module_id: str, action: str, **args: Any) -> dict[str, Any]:
        response = await self.conn.request(
            "module.call", module_id=module_id, action=action, args=args
        )
        return response.get("result", {})

    # -- routes --------------------------------------------------------------------------

    def route(self) -> Route:
        return Route(self)

    async def run_route(
        self, route: Route, *, wait: bool = True, on_disconnect: str = "continue"
    ) -> Any:
        compiled = route.compile(await self.get_pose(), self.conn.hello)
        self._hold = None
        if self._session is not None and not self._session.ended:
            await self._session.wait_idle()
            await self._session.cancel()  # idle, so this stops nothing; frees the bot for the route
        self._session = None
        plan = self._new_plan(open_ended=False, on_disconnect=on_disconnect)
        handle = AsyncRouteHandle(plan, compiled)
        if not compiled:
            plan._finish("done")
            return handle.build_result() if wait else handle
        for item in compiled:
            plan.add(item.step)
        if wait:
            return await handle.wait()
        return handle

    def _new_plan(self, *, open_ended: bool, on_disconnect: str = "continue") -> Plan:
        self._plans = [p for p in self._plans if not p.finished]
        plan = Plan(self.conn, open_ended=open_ended, on_disconnect=on_disconnect)
        self._plans.append(plan)
        return plan

    # -- events --------------------------------------------------------------------------

    def on(self, event: str, callback: Callable[[Any], Any]) -> None:
        """Call ``callback(data)`` when something happens.

        Events: ``marker``, ``step_done``, ``move_failed``, ``stopped``, ``telemetry``,
        ``disconnected``, ``reconnected``, ``rebooted``. Callbacks run on a worker thread.
        """
        self._callbacks.setdefault(event, []).append(callback)

    def _fire(self, event: str, data: Any) -> None:
        loop = asyncio.get_running_loop()
        for callback in self._callbacks.get(event, []):
            future = loop.run_in_executor(None, callback, data)
            future.add_done_callback(_log_callback_error)

    def _on_message(self, message: dict[str, Any]) -> None:
        if message.get("type") == "tlm":
            self._fire("telemetry", message)
            return
        evt = str(message.get("evt", ""))
        if evt.startswith("plan."):
            for plan in self._plans:
                if plan.plan_id == message.get("plan_id"):
                    plan.on_event(message)
        if evt == "module.added" and isinstance(message.get("module"), dict):
            module = message["module"]
            self.module_descriptors[str(module.get("id"))] = module
        elif evt == "module.removed":
            self.module_descriptors.pop(str(message.get("module_id")), None)
        if evt in _EVENT_NAMES:
            self._fire(_EVENT_NAMES[evt], message)

    def _on_state(self, state: str, info: dict[str, Any]) -> None:
        if state == "reconnected":
            rebooted = bool(info.get("rebooted"))
            self._load_modules()  # modules may have changed while we were away
            for plan in self._plans:
                plan.on_reconnect(rebooted)
            self._fire("reconnected", info)
            if rebooted:
                self._fire("rebooted", info)
        else:
            self._fire(state, info)


class AsyncRouteHandle:
    """A route that is running (or has run) on the bot."""

    def __init__(self, plan: Plan, compiled: list[CompiledStep]) -> None:
        self.plan = plan
        self.compiled = compiled

    @property
    def done(self) -> bool:
        return self.plan.finished

    @property
    def progress(self) -> tuple[int, int]:
        """(moves finished, moves in total)."""
        return len(self.plan.results), len(self.compiled)

    async def wait(self) -> RouteResult:
        """Wait for the route to finish.

        Raises if a move failed; the exception's ``route_result`` has the details.
        """
        await self.plan.wait_finished()
        result = self.build_result()
        for seq in range(1, len(self.compiled) + 1):
            try:
                self.plan._outcome(seq)
            except Exception as exc:
                exc.route_result = result  # type: ignore[attr-defined]
                raise
        return result

    def build_result(self) -> RouteResult:
        steps = [self.plan.results[s] for s in sorted(self.plan.results)]
        return RouteResult(
            steps=steps,
            expected=[c.expected for c in self.compiled],
            labels=[c.label for c in self.compiled],
        )

    async def pause(self) -> None:
        await self.plan.pause()

    async def resume(self) -> None:
        await self.plan.resume()

    async def cancel(self) -> None:
        await self.plan.cancel()


def _one(route: Route) -> dict[str, Any]:
    (compiled,) = route.compile(Pose())
    return compiled.step


def _log_callback_error(future: asyncio.Future[Any]) -> None:
    if not future.cancelled() and future.exception() is not None:
        log.error("a bot.on(...) callback failed", exc_info=future.exception())


async def _discover(timeout: float) -> Connection:
    candidates = [
        (f"ws://127.0.0.1:{DEFAULT_LOCAL_PORT}{WS_PATH}", 0.5),  # simulator or app on this computer
        (f"ws://{DEFAULT_BOT_HOST}{WS_PATH}", 2.0),  # the bot's own Wi-Fi (direct mode)
    ]
    for url, connect_timeout in candidates:
        conn = Connection(url, request_timeout=timeout, connect_timeout=connect_timeout)
        try:
            await conn.open()
            return conn
        except _CONNECT_ERRORS:
            continue
    tried = ", ".join(url for url, _ in candidates)
    raise BotNotFound(
        f"No MoveBot found (tried {tried}). Connect this computer to the MoveBot-XXXX Wi-Fi, "
        "give the address like Bot('192.168.1.42'), or try the simulator with Bot('sim')."
    )
