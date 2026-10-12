"""The beginner API: a MoveBot you can control with plain function calls."""

from __future__ import annotations

import atexit
import contextlib
import weakref
from collections.abc import Callable
from typing import Any

from . import _studio
from ._runtime import LoopThread
from .aio import AsyncBot, AsyncRouteHandle
from .camera import CameraFrame
from .models import Encoders, Pose, RouteResult, StepResult
from .modules import Modules
from .plans import Plan
from .route import Route


class Bot:
    """A connection to one MoveBot.

    >>> bot = Bot()            # finds the bot (or use Bot("192.168.4.1"))
    >>> bot = Bot("sim")       # or a simulated bot, no hardware needed
    >>> bot.forward(0.5)       # metres; waits until the move is done
    >>> bot.left()             # 90 degrees
    >>> bot.lights.on()
    >>> print(bot.pose)

    When your program ends, the bot stops.
    """

    def __init__(self, target: Any = None, *, timeout: float = 5.0) -> None:
        self._rt = LoopThread()
        try:
            self._abot = self._rt.run(AsyncBot.connect(target, timeout=timeout))
        except BaseException:
            self._rt.stop()
            raise
        self._closed = False
        self.lights = Lights(self)
        self.status_led = StatusLed(self)
        colour_leds = self._abot.color_led_names
        self.rgb_led: RgbLed | None = RgbLed(self, colour_leds[0]) if colour_leds else None
        self.camera = Camera(self)
        self.modules = Modules(self)
        self.sim = SimControl(self) if self._abot.sim_server is not None else None
        ref = weakref.ref(self)
        atexit.register(lambda: (bot := ref()) is not None and bot.close())

    @classmethod
    def simulated(
        cls,
        *,
        time_scale: float = 1.0,
        noise: float = 0.0,
        seed: int | None = None,
        world: str = "ball_arena",
        modules: list[str] | None = None,
    ) -> Bot:
        """A bot simulated inside this program.

        ``time_scale=10`` runs 10x faster than real time. ``modules`` adds simulated
        add-ons, e.g. ``["distance:front_distance", "imu"]``.
        """
        sim = _studio.load("sim", "The simulator (Bot.simulated)")
        options = sim.SimOptions(
            time_scale=time_scale, noise=noise, seed=seed, world=world, modules=modules or []
        )
        return cls(options)

    def _run(self, coro: Any, timeout: float | None = None) -> Any:
        try:
            return self._rt.run(coro, timeout)
        except KeyboardInterrupt:
            with contextlib.suppress(BaseException):
                self._rt.run(self._abot.stop(), timeout=2)  # Ctrl+C always stops the bot
            raise

    # -- connection ----------------------------------------------------------------------

    def close(self) -> None:
        """Stop the bot and disconnect."""
        if self._closed:
            return
        self._closed = True
        with contextlib.suppress(BaseException):
            self._rt.run(self._abot.close(), timeout=5)
        self._rt.stop()

    def __enter__(self) -> Bot:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def __repr__(self) -> str:
        state = "connected" if self.connected else "disconnected"
        return f"<Bot {self.name!r} at {self._abot.conn.url} ({state})>"

    @property
    def connected(self) -> bool:
        """True while the bot is connected (the library reconnects by itself)."""
        return self._abot.conn.connected

    @property
    def name(self) -> str:
        """The bot's name, e.g. ``"MoveBot-3F2A"``."""
        return self._abot.name

    @property
    def info(self) -> dict[str, Any]:
        """What the bot told us about itself: firmware, protocol, size, limits, ..."""
        return self._abot.info

    # -- where am I ----------------------------------------------------------------------

    @property
    def pose(self) -> Pose:
        """Position and heading measured by the wheel encoders (``x``, ``y``, ``heading``)."""
        return self._run(self._abot.get_pose())

    @property
    def encoders(self) -> Encoders:
        """Encoder ticks and wheel speeds: ``bot.encoders.left.ticks``."""
        return self._run(self._abot.get_encoders())

    @property
    def battery(self) -> float | None:
        """Battery level in percent."""
        return self._abot.battery

    def reset_odometry(self) -> None:
        """Make where the bot is now the new starting point (x=0, y=0, heading 0)."""
        self._run(self._abot.reset_odometry())

    # -- moves (each waits until done, unless wait=False) --------------------------------

    def forward(self, distance: float, *, speed: float | None = None, wait: bool = True) -> Any:
        """Drive ``distance`` metres forward. ``speed`` in m/s (optional)."""
        return self._move(self._abot.forward(distance, speed=speed, wait=wait))

    def back(self, distance: float, *, speed: float | None = None, wait: bool = True) -> Any:
        """Drive ``distance`` metres backward."""
        return self._move(self._abot.back(distance, speed=speed, wait=wait))

    def left(self, degrees: float = 90, *, wait: bool = True) -> Any:
        """Turn left on the spot (90 degrees unless you say otherwise)."""
        return self._move(self._abot.left(degrees, wait=wait))

    def right(self, degrees: float = 90, *, wait: bool = True) -> Any:
        """Turn right on the spot (90 degrees unless you say otherwise)."""
        return self._move(self._abot.right(degrees, wait=wait))

    def turn(self, degrees: float, *, speed: float | None = None, wait: bool = True) -> Any:
        """Turn on the spot: positive = left, negative = right. ``speed`` in degrees/s."""
        return self._move(self._abot.turn(degrees, speed=speed, wait=wait))

    def u_turn(self, *, wait: bool = True) -> Any:
        """Turn around on the spot (180 degrees)."""
        return self._move(self._abot.u_turn(wait=wait))

    def spin(self, degrees: float = 360, *, wait: bool = True) -> Any:
        """Spin on the spot, a full turn unless you say otherwise (+ = left)."""
        return self._move(self._abot.spin(degrees, wait=wait))

    def turn_to(self, heading: float, *, wait: bool = True) -> Any:
        """Face ``heading`` degrees (0 = the way the bot faced at the start)."""
        return self._move(self._abot.turn_to(heading, wait=wait))

    def arc(self, radius: float, degrees: float, *, wait: bool = True) -> Any:
        """Drive along a circle of ``radius`` metres for ``degrees`` (+ left, - right)."""
        return self._move(self._abot.arc(radius, degrees, wait=wait))

    def wait(self, seconds: float, *, wait: bool = True) -> Any:
        """Pause between moves. The bot does the waiting, so the order is always kept."""
        return self._move(self._abot.wait(seconds, wait=wait))

    def _move(self, coro: Any) -> StepResult | MoveHandle:
        result = self._run(coro)
        if isinstance(result, tuple):
            plan, seq = result
            return MoveHandle(self, plan, seq)
        return result

    # -- continuous control --------------------------------------------------------------

    def drive(self, speed: float, turn_rate: float = 0.0, *, seconds: float | None = None) -> Any:
        """Drive at ``speed`` m/s while turning at ``turn_rate`` degrees/s (+ = left).

        Without ``seconds`` the bot keeps driving until ``stop()`` or another move.
        """
        return self._move(self._abot.drive(speed, turn_rate, seconds=seconds))

    def motors(self, left: float, right: float) -> None:
        """Raw motor power for each wheel, from -1 to 1, until ``stop()``."""
        self._run(self._abot.motors(left, right))

    def stop(self) -> None:
        """Stop now. Cancels moves that are running or queued."""
        self._run(self._abot.stop())

    # -- speed ---------------------------------------------------------------------------

    @property
    def speed(self) -> float:
        """Speed limit for moves, in percent of the bot's top speed. ``bot.speed = 50``."""
        return self._run(self._abot.get_speed())

    @speed.setter
    def speed(self, percent: float) -> None:
        self._run(self._abot.set_speed(percent))

    # -- routes --------------------------------------------------------------------------

    def route(self) -> Route:
        """Start building a route: ``bot.route().forward(0.5).left().run()``."""
        return Route(self)

    def run_route(
        self, route: Route, *, wait: bool = True, on_disconnect: str = "continue"
    ) -> RouteResult | RouteHandle:
        """Run a route built with ``bot.route()`` (same as ``route.run()``)."""
        result = self._run(self._abot.run_route(route, wait=wait, on_disconnect=on_disconnect))
        return RouteHandle(self, result) if isinstance(result, AsyncRouteHandle) else result

    # -- events --------------------------------------------------------------------------

    def on(self, event: str, callback: Callable[[Any], Any]) -> None:
        """Run ``callback(data)`` when ``event`` happens.

        Events: ``marker``, ``step_done``, ``move_failed``, ``stopped``, ``telemetry``,
        ``disconnected``, ``reconnected``, ``rebooted``.
        """
        self._abot.on(event, callback)


class MoveHandle:
    """A move that was started with ``wait=False``."""

    def __init__(self, bot: Bot, plan: Plan, seq: int) -> None:
        self._bot = bot
        self._plan = plan
        self.seq = seq

    @property
    def done(self) -> bool:
        """True once the move has finished (or the plan ended)."""
        return self.seq in self._plan.results or self._plan.finished

    def wait(self, timeout: float | None = None) -> StepResult:
        """Wait until the move is finished and return what happened."""
        return self._bot._run(self._plan.result(self.seq), timeout)

    def __repr__(self) -> str:
        return f"<MoveHandle #{self.seq} {'done' if self.done else 'running'}>"


class RouteHandle:
    """A route that was started with ``wait=False``."""

    def __init__(self, bot: Bot, handle: AsyncRouteHandle) -> None:
        self._bot = bot
        self._handle = handle

    @property
    def done(self) -> bool:
        """True once the route has finished."""
        return self._handle.done

    @property
    def progress(self) -> tuple[int, int]:
        """(moves finished, moves in total)."""
        return self._handle.progress

    def wait(self, timeout: float | None = None) -> RouteResult:
        """Wait until the route is finished and return what happened."""
        return self._bot._run(self._handle.wait(), timeout)

    def pause(self) -> None:
        """Pause after the current move."""
        self._bot._run(self._handle.pause())

    def resume(self) -> None:
        """Carry on after ``pause()``."""
        self._bot._run(self._handle.resume())

    def cancel(self) -> None:
        """Stop the route; moves not started yet are dropped."""
        self._bot._run(self._handle.cancel())


class Lights:
    """``bot.lights.on()``, ``bot.lights.left.off()``, ``bot.lights.level = 0.5``."""

    def __init__(self, bot: Bot, name: str | None = None) -> None:
        self._bot = bot
        self._name = name
        if name is None:
            for light in bot._abot.light_names:
                short = light.removeprefix("light_")
                if short.isidentifier() and not hasattr(self, short):
                    setattr(self, short, Lights(bot, light))

    def on(self) -> None:
        """Full brightness."""
        self.level = 1.0

    def off(self) -> None:
        """Off."""
        self.level = 0.0

    def toggle(self) -> None:
        """On if off, off if on."""
        self.level = 0.0 if self.level > 0 else 1.0

    @property
    def level(self) -> float:
        """Brightness from 0 (off) to 1 (full)."""
        return self._bot._abot.light_level(self._name)

    @level.setter
    def level(self, value: float) -> None:
        self._bot._run(self._bot._abot.set_light(value, self._name))


class StatusLed:
    """The controller board's own LED: ``bot.status_led.blink()``.

    Patterns: off, on, blink, blink_fast, pulse.
    """

    def __init__(self, bot: Bot) -> None:
        self._bot = bot
        names = bot._abot.status_led_names
        plain = [n for n in names if n not in bot._abot.color_led_names]
        self._name = "status" if "status" in names else (plain[0] if plain else None)

    def set(self, pattern: str) -> None:
        """Show a pattern: ``off``, ``on``, ``blink``, ``blink_fast`` or ``pulse``."""
        self._bot._run(self._bot._abot.set_status_led(pattern, self._name))

    def on(self) -> None:
        """Light up."""
        self.set("on")

    def off(self) -> None:
        """Go dark."""
        self.set("off")

    def blink(self, fast: bool = False) -> None:
        """Blink (``fast=True`` for quick blinks)."""
        self.set("blink_fast" if fast else "blink")

    def pulse(self) -> None:
        """Fade slowly in and out."""
        self.set("pulse")


class RgbLed:
    """The RGB status LED, in any colour: ``bot.rgb_led.on("green")``.

    Colours: a name (red, orange, yellow, green, cyan, blue, purple, magenta, pink, white),
    a code like ``"#ff8800"``, or ``(red, green, blue)`` with each 0-255. Without a colour
    the LED keeps the last one.
    """

    def __init__(self, bot: Bot, name: str) -> None:
        self._bot = bot
        self._name = name

    def set(self, pattern: str, color: Any = None) -> None:
        """Show a pattern (``off``, ``on``, ``blink``, ``blink_fast``, ``pulse``) in a colour."""
        self._bot._run(self._bot._abot.set_status_led(pattern, self._name, color))

    def on(self, color: Any = None) -> None:
        """Light up, e.g. ``on("blue")``."""
        self.set("on", color)

    def off(self) -> None:
        """Go dark."""
        self.set("off")

    def blink(self, color: Any = None, fast: bool = False) -> None:
        """Blink in a colour (``fast=True`` for quick blinks)."""
        self.set("blink_fast" if fast else "blink", color)

    def pulse(self, color: Any = None) -> None:
        """Fade slowly in and out, in a colour."""
        self.set("pulse", color)


class Camera:
    """The bot's camera.

    >>> image = bot.camera.frame()          # newest picture, numpy array (BGR, like OpenCV)
    >>> for image in bot.camera.frames():   # a new picture each time round the loop
    ...     ...
    >>> bot.camera.configure("balanced")    # presets: fast, balanced, detail
    """

    def __init__(self, bot: Bot) -> None:
        self._bot = bot

    @property
    def _cam(self) -> Any:
        return self._bot._abot.camera

    @property
    def available(self) -> bool:
        """True if this bot has a camera."""
        return self._cam.available

    @property
    def info(self) -> dict[str, Any]:
        """Resolutions and presets this camera supports."""
        return self._cam.info

    def frame(self, timeout: float = 5.0) -> Any:
        """The newest picture as a numpy array (height x width x 3, BGR)."""
        return self.latest(timeout).image

    def latest(self, timeout: float = 5.0) -> CameraFrame:
        """The newest picture with its details (``.image``, ``.t``, ``.pose``, ``.save()``)."""
        return self._bot._run(self._cam.frame(timeout))

    def frames(self, timeout: float = 5.0) -> Any:
        """Yield pictures forever, always the newest one (never an old, queued picture)."""
        seq: int | None = None
        while True:
            frame = self._bot._run(self._cam.next_frame(seq, timeout))
            seq = frame.seq
            yield frame.image

    def save(self, path: str = "movebot.jpg") -> str:
        """Save the newest picture as a JPEG file and return the path."""
        return self.latest().save(path)

    @property
    def settings(self) -> dict[str, Any]:
        """Current preset, resolution, fps and quality."""
        return self._bot._run(self._cam.settings())

    def configure(
        self,
        preset: str | None = None,
        *,
        resolution: str | None = None,
        fps: int | None = None,
        quality: int | None = None,
    ) -> dict[str, Any]:
        """Choose a preset (``fast``, ``balanced``, ``detail``) and/or custom values.

        ``resolution`` like ``"640x480"`` (see ``camera.info["resolutions"]``), ``fps``
        1-30 (an upper limit), ``quality`` 1-100.
        """
        return self._bot._run(
            self._cam.configure(preset, resolution=resolution, fps=fps, quality=quality)
        )

    def stop(self) -> None:
        """Stop receiving pictures (the privacy light goes off when nobody is watching)."""
        self._bot._run(self._cam.stop())


class SimControl:
    """Extra controls when the bot is simulated inside this program (``Bot("sim")``)."""

    def __init__(self, bot: Bot) -> None:
        self._bot = bot

    @property
    def _server(self) -> Any:
        return self._bot._abot.sim_server

    def _call(self, fn: Callable[[], Any]) -> Any:
        async def run() -> Any:
            return fn()

        return self._bot._run(run())

    @property
    def truth(self) -> Pose:
        """Where the simulated bot really is (odometry only estimates this)."""
        t = self._call(lambda: self._server.bot.drive.truth)
        return Pose(t.x, t.y, t.yaw)

    def block_wheels(self, blocked: bool = True) -> None:
        """Pretend something is stuck in the wheels."""
        self._call(lambda: setattr(self._server.bot.drive, "blocked", blocked))

    def drop_connection(self) -> None:
        """Pretend the Wi-Fi dropped (the library reconnects by itself)."""
        self._bot._run(self._server.drop_connections())

    def reboot(self) -> None:
        """Pretend the bot restarted (anything it was doing is forgotten)."""
        self._call(self._server.bot.reboot)

    def attach(self, module: str) -> None:
        """Plug in a simulated module, e.g. ``"distance:front_distance"``."""
        self._bot._run(self._bot._abot.conn.request("sim.attach", module=module))

    def detach(self, module_id: str) -> None:
        """Unplug a simulated module."""
        self._bot._run(self._bot._abot.conn.request("sim.detach", module_id=module_id))

    def place_ball(self, x: float, y: float, color: str = "blue") -> None:
        """Put a ball of ``color`` (blue, red, green, yellow) at (x, y) metres."""
        world = _studio.load("sim.world", "The simulator")

        rgb = getattr(world, color.upper())
        ball = world.Ball(x, y, color=rgb, name=color)
        self._call(lambda: self._server.bot.world.balls.append(ball))

    def clear_balls(self) -> None:
        """Take every ball out of the simulated world."""
        self._call(lambda: self._server.bot.world.balls.clear())
