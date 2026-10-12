"""Client side of plans: upload numbered steps, keep the bot's queue fed, survive drops.

The bot is the source of truth. Events (``plan.step_done`` ...) are used as fast
hints; ``plan.status`` / ``plan.results`` are used to catch up after a reconnect or
whenever events might have been missed.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from typing import Any

from .connection import Connection
from .errors import (
    BotTimeout,
    CommandError,
    ConnectionLost,
    MoveCancelled,
    MoveFailed,
    PlanLost,
)
from .models import StepResult
from .protocol import TERMINAL_PLAN_STATES, new_token

log = logging.getLogger("movebot")

POLL_INTERVAL = 1.0  # s; safety net in case an event was missed
LOST_AFTER = 30.0  # s without a connection before waiting moves give up

_FAILURE_TEXT = {
    "stalled": "the wheels could not turn (is something blocking MoveBot?)",
    "timeout": "it took much longer than expected",
    "max_duration": "the plan ran longer than the bot allows",
    "low_battery": "the battery is too low",
    "disconnect": "the connection was lost and the plan was set to stop",
}


class Plan:
    """A plan this client owns. ``open_ended`` plans accept more steps over time."""

    def __init__(
        self,
        conn: Connection,
        *,
        open_ended: bool,
        on_disconnect: str = "continue",
        autostart: bool = True,
    ) -> None:
        self.conn = conn
        self.plan_id = new_token(6)
        self.open_ended = open_ended
        self.on_disconnect = on_disconnect
        self.autostart = autostart
        self.boot_id = conn.boot_id
        self.steps: list[dict[str, Any]] = []
        self.results: dict[int, StepResult] = {}
        self.state = "new"
        self.loaded = False
        self.acked = 0  # the bot holds steps 1..acked
        self.end_acked = False
        self.queue_free = int(conn.limit("plan_queue", 16))
        self.error: Exception | None = None
        self._waiters: dict[int, list[asyncio.Future[StepResult]]] = {}
        self._wake = asyncio.Event()
        self._finished = asyncio.Event()
        self._needs_sync = False
        self._task: asyncio.Task[None] | None = None

    # -- building ------------------------------------------------------------------------

    @property
    def finished(self) -> bool:
        return self._finished.is_set()

    @property
    def ended(self) -> bool:
        """Finished, or known to be over on the bot (no new steps can join it)."""
        return self.finished or self.state in (*TERMINAL_PLAN_STATES, "lost")

    def add(self, step: dict[str, Any]) -> int:
        if self.finished:
            raise RuntimeError("cannot add steps to a finished plan")
        self.steps.append(step)
        self._kick()
        return len(self.steps)

    def _kick(self) -> None:
        self._wake.set()
        if self._task is None:
            self._task = asyncio.create_task(self._supervise(), name=f"movebot-plan-{self.plan_id}")

    # -- waiting -------------------------------------------------------------------------

    async def result(self, seq: int) -> StepResult:
        """Wait for one step; raises MoveFailed / MoveCancelled / PlanLost / ConnectionLost."""
        if seq not in self.results and not self.finished:
            future: asyncio.Future[StepResult] = asyncio.get_running_loop().create_future()
            self._waiters.setdefault(seq, []).append(future)
            return await future
        return self._outcome(seq)

    async def wait_finished(self) -> None:
        await self._finished.wait()

    async def wait_idle(self) -> None:
        """Wait until every step added so far has an outcome (errors are swallowed)."""
        if self.steps:
            with contextlib.suppress(Exception):
                await self.result(len(self.steps))

    # -- control -------------------------------------------------------------------------

    async def pause(self) -> None:
        self._apply(await self.conn.request("plan.pause", plan_id=self.plan_id))

    async def resume(self) -> None:
        self._apply(await self.conn.request("plan.resume", plan_id=self.plan_id))

    async def cancel(self) -> None:
        if self.loaded and not self.finished:
            with contextlib.suppress(CommandError):
                self._apply(await self.conn.request("plan.cancel", plan_id=self.plan_id))
        if not self.finished:
            self._finish("cancelled")

    # -- wiring from the bot -------------------------------------------------------------

    def on_event(self, event: dict[str, Any]) -> None:
        name = event.get("evt")
        if "queue_free" in event:
            self.queue_free = int(event["queue_free"])
        if name == "plan.step_done":
            self._record(StepResult.from_wire(event))
        elif name in ("plan.done", "plan.failed", "plan.cancelled"):
            self.state = name.split(".", 1)[1]
            self._needs_sync = True  # fetch any results we did not see as events
        self._kick()

    def on_reconnect(self, rebooted: bool) -> None:
        if rebooted or self.conn.boot_id != self.boot_id:
            self._lose()
        else:
            self._needs_sync = True
            self._kick()

    # -- the supervisor ------------------------------------------------------------------

    async def _supervise(self) -> None:
        while not self.finished:
            try:
                if self.conn.connected:
                    if self._needs_sync:
                        await self._sync()
                    if not self.finished:
                        await self._pump()
                elif (
                    self.conn.disconnected_since is not None
                    and time.monotonic() - self.conn.disconnected_since > LOST_AFTER
                ):
                    self._finish(
                        "lost",
                        ConnectionLost(
                            f"Lost the connection to MoveBot for more than {LOST_AFTER:.0f} s."
                        ),
                    )
                    return
            except (ConnectionLost, BotTimeout):
                self._needs_sync = True
            except CommandError as exc:
                if exc.code == "invalid_state":
                    self._needs_sync = True  # the plan just ended on the bot; catch up
                else:
                    if exc.code == "unknown_plan":
                        self._lose()
                    else:
                        self._finish("error", exc)
                    return
            if self.finished:
                return
            self._wake.clear()
            try:
                await asyncio.wait_for(self._wake.wait(), POLL_INTERVAL)
            except asyncio.TimeoutError:
                if self.loaded:
                    self._needs_sync = True

    async def _pump(self) -> None:
        """Send steps the bot does not have yet, as far as its queue has room."""
        while self.state not in TERMINAL_PLAN_STATES:
            unsent = self.steps[self.acked :]
            want_end = not self.open_ended and not self.end_acked
            if not unsent and not (want_end and self.loaded):
                return
            room = self.queue_free if self.loaded else int(self.conn.limit("plan_queue", 16))
            if unsent and room <= 0:
                return  # wait for a step_started / step_done event to free space
            chunk = unsent[: max(room, 0)]
            include_end = want_end and len(chunk) == len(unsent)
            wire = [{"seq": self.acked + 1 + i, **step} for i, step in enumerate(chunk)]
            params: dict[str, Any] = {"plan_id": self.plan_id, "steps": wire, "end": include_end}
            try:
                if not self.loaded:
                    response = await self.conn.request(
                        "plan.load",
                        autostart=self.autostart,
                        on_disconnect=self.on_disconnect,
                        **params,
                    )
                    self.loaded = True
                else:
                    response = await self.conn.request("plan.append", **params)
            except CommandError as exc:
                if exc.code != "gap":
                    raise
                self.acked = int(exc.detail.get("next_seq", 1)) - 1
                continue
            self._apply(response)
            if include_end and self.acked >= len(self.steps):
                self.end_acked = True
            if wire and self.acked < wire[-1]["seq"]:
                return  # the bot's queue filled up; wait for room

    async def _sync(self) -> None:
        self._needs_sync = False
        if not self.loaded:
            return
        status = await self.conn.request("plan.status", plan_id=self.plan_id)
        if status.get("boot_id") != self.boot_id:
            self._lose()
            return
        self._apply(status)
        missing = [
            seq for seq in range(1, int(status.get("done_seq", 0)) + 1) if seq not in self.results
        ]
        if missing:
            response = await self.conn.request(
                "plan.results", plan_id=self.plan_id, from_seq=missing[0]
            )
            for entry in response.get("results", []):
                self._record(StepResult.from_wire(entry))
        if self.state in TERMINAL_PLAN_STATES:
            self._finish(self.state)

    def _apply(self, status: dict[str, Any]) -> None:
        if "next_seq" in status:
            self.acked = int(status["next_seq"]) - 1
        if "queue_free" in status:
            self.queue_free = int(status["queue_free"])
        state = status.get("state")
        if state and state != "none":
            self.state = state
            if state in TERMINAL_PLAN_STATES:
                self._needs_sync = True
                self._wake.set()

    def _record(self, result: StepResult) -> None:
        if result.seq in self.results:
            return
        self.results[result.seq] = result
        if result.result in ("failed", "cancelled"):
            # A failed or cancelled step always ends the plan (SPEC §6.4). Mark it now, so a
            # move started right after this one starts a new plan instead of joining this one.
            self.state = result.result
            self._needs_sync = True
        for future in self._waiters.pop(result.seq, []):
            if not future.done():
                self._settle(future, result.seq)

    def _finish(self, state: str, error: Exception | None = None) -> None:
        if self.finished:
            return
        if state in ("done", "failed", "cancelled"):
            self.state = state
        self.error = error
        self._finished.set()
        for seq, futures in list(self._waiters.items()):
            for future in futures:
                if not future.done():
                    self._settle(future, seq)
        self._waiters.clear()

    def _lose(self) -> None:
        if self.finished:
            return
        self.error = PlanLost(
            "MoveBot restarted, so it forgot the moves it was doing. Start them again."
        )
        self.state = "lost"
        self._finish("lost", self.error)

    def _settle(self, future: asyncio.Future[StepResult], seq: int) -> None:
        try:
            future.set_result(self._outcome(seq))
        except Exception as exc:
            future.set_exception(exc)

    def _outcome(self, seq: int) -> StepResult:
        result = self.results.get(seq)
        if result is not None:
            if result.ok:
                return result
            if result.result == "failed":
                why = _FAILURE_TEXT.get(result.reason or "", result.reason or "unknown reason")
                raise MoveFailed(
                    f"Move {seq} ({result.op}) failed: {why}.", seq=seq, reason=result.reason
                )
            raise MoveCancelled(f"Move {seq} ({result.op}) was cancelled ({result.reason}).")
        if self.error is not None:
            raise self.error
        if self.state == "failed":
            raise MoveCancelled(f"Move {seq} did not run because an earlier move failed.")
        raise MoveCancelled(f"Move {seq} did not run (the plan was {self.state}).")
