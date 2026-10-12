"""A private asyncio event loop on a background thread, so beginners never see ``await``."""

from __future__ import annotations

import asyncio
import concurrent.futures
import contextlib
import threading
from collections.abc import Coroutine
from typing import Any, TypeVar

T = TypeVar("T")


async def cancel_all_tasks() -> None:
    """Cancel every other task on this loop and wait for them, before stopping the loop.

    Stopping a loop with tasks still pending leaves half-run coroutines behind, which
    Python later complains about ("Task was destroyed but it is pending").
    """
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)


class LoopThread:
    def __init__(self) -> None:
        self.loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._main, name="movebot-loop", daemon=True)
        self._thread.start()

    def _main(self) -> None:
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def run(self, coro: Coroutine[Any, Any, T], timeout: float | None = None) -> T:
        """Run ``coro`` on the loop and wait for it from the calling thread.

        Waits in short slices so Ctrl+C is noticed promptly (also on Windows).
        """
        future = asyncio.run_coroutine_threadsafe(coro, self.loop)
        waited = 0.0
        try:
            while True:
                try:
                    return future.result(0.1)
                except concurrent.futures.TimeoutError:
                    waited += 0.1
                    if timeout is not None and waited >= timeout:
                        raise TimeoutError("the operation took too long") from None
        except BaseException:
            future.cancel()
            raise

    def stop(self) -> None:
        if not self.loop.is_running():
            return

        with contextlib.suppress(Exception):  # shutting down anyway
            asyncio.run_coroutine_threadsafe(cancel_all_tasks(), self.loop).result(2)
        self.loop.call_soon_threadsafe(self.loop.stop)
        self._thread.join(2)
