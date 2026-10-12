"""MJPEG over HTTP: a tiny reader (client) and server, without extra dependencies.

Wire format (protocol SPEC §7): ``GET /stream`` answers ``multipart/x-mixed-replace`` with
one JPEG per part. Each part carries ``Content-Length`` and, from MoveBot, ``X-Timestamp``
(ms since boot), ``X-Frame`` (frame number) and ``X-Pose`` (``x,y,yaw`` at capture time).
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit

log = logging.getLogger("movebot")

BOUNDARY = "movebotframe"
MAX_HEADER_BYTES = 8192
MAX_FRAME_BYTES = 8 * 1024 * 1024


@dataclass(frozen=True)
class Frame:
    """One camera image as it arrived from the bot."""

    jpeg: bytes
    seq: int
    t: int | None = None  # ms since the bot booted, when the image was captured
    pose: tuple[float, float, float] | None = None  # odometry (x, y, yaw) at capture
    received: float = field(default_factory=time.monotonic)

    def headers(self) -> dict[str, str]:
        headers = {"X-Frame": str(self.seq)}
        if self.t is not None:
            headers["X-Timestamp"] = str(self.t)
        if self.pose is not None:
            headers["X-Pose"] = ",".join(f"{v:.4f}" for v in self.pose)
        return headers


def jpeg_size(data: bytes) -> tuple[int, int] | None:
    """(width, height) from a JPEG's frame header, without decoding the image."""
    i = 2
    while i + 9 < len(data):
        if data[i] != 0xFF:
            return None
        marker = data[i + 1]
        if marker == 0xFF:  # padding
            i += 1
            continue
        length = int.from_bytes(data[i + 2 : i + 4], "big")
        if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):  # start of frame
            height = int.from_bytes(data[i + 5 : i + 7], "big")
            width = int.from_bytes(data[i + 7 : i + 9], "big")
            return width, height
        i += 2 + length
    return None


def parse_part_headers(lines: list[str]) -> dict[str, str]:
    headers: dict[str, str] = {}
    for line in lines:
        name, sep, value = line.partition(":")
        if sep:
            headers[name.strip().lower()] = value.strip()
    return headers


def frame_from_part(jpeg: bytes, headers: dict[str, str], fallback_seq: int) -> Frame:
    def number(key: str) -> int | None:
        try:
            return int(float(headers[key]))
        except (KeyError, ValueError):
            return None

    pose = None
    if "x-pose" in headers:
        with contextlib.suppress(ValueError):
            x, y, yaw = (float(v) for v in headers["x-pose"].split(","))
            pose = (x, y, yaw)
    seq = number("x-frame")
    return Frame(jpeg, seq if seq is not None else fallback_seq, number("x-timestamp"), pose)


class MjpegReader:
    """Keeps reading an MJPEG stream and remembers only the newest frame.

    Old frames are dropped rather than queued, so a slow consumer always gets the most
    recent image (what you want for control loops). Reconnects by itself.
    """

    def __init__(self, url: str, *, connect_timeout: float = 3.0) -> None:
        self.url = url
        self.connect_timeout = connect_timeout
        self.latest: Frame | None = None
        self.error: str | None = None
        self._changed = asyncio.Condition()
        self._task: asyncio.Task[None] | None = None
        self._count = 0

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    def start(self) -> None:
        if not self.running:
            self._task = asyncio.create_task(self._run(), name="movebot-mjpeg")

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await self._task
            self._task = None

    async def wait_frame(self, after_seq: int | None = None, timeout: float = 5.0) -> Frame:
        """Return the newest frame, waiting for one newer than ``after_seq`` if needed."""
        self.start()

        def ready() -> bool:
            return self.latest is not None and (after_seq is None or self.latest.seq != after_seq)

        async with self._changed:
            await asyncio.wait_for(self._changed.wait_for(ready), timeout)
            assert self.latest is not None
            return self.latest

    async def _run(self) -> None:
        delay = 0.2
        while True:
            try:
                await self._read_stream()
                delay = 0.2
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.error = f"{exc.__class__.__name__}: {exc}"
                log.debug("camera stream failed: %s", self.error)
            await asyncio.sleep(delay)
            delay = min(delay * 2, 2.0)

    async def _read_stream(self) -> None:
        parts = urlsplit(self.url)
        host, port = parts.hostname or "127.0.0.1", parts.port or 80
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), self.connect_timeout
        )
        try:
            path = parts.path or "/stream"
            request = f"GET {path} HTTP/1.1\r\nHost: {host}:{port}\r\nConnection: close\r\n\r\n"
            writer.write(request.encode("ascii"))
            await writer.drain()
            status = await asyncio.wait_for(reader.readline(), self.connect_timeout)
            if b" 200 " not in status:
                raise ConnectionError(f"camera answered {status.decode(errors='replace').strip()}")
            while (await reader.readline()).strip():  # skip the response headers
                pass
            self.error = None
            while True:
                line = await reader.readline()
                if not line:
                    raise ConnectionError("camera stream ended")
                if not line.startswith(b"--"):
                    continue  # blank lines between parts
                header_lines: list[str] = []
                while True:
                    raw = await reader.readline()
                    if not raw.strip():
                        break
                    header_lines.append(raw.decode("latin-1"))
                    if len(header_lines) > 32:
                        raise ConnectionError("too many part headers")
                headers = parse_part_headers(header_lines)
                length = int(headers.get("content-length", "0"))
                if not 0 < length <= MAX_FRAME_BYTES:
                    raise ConnectionError("camera frame without a sensible Content-Length")
                jpeg = await reader.readexactly(length)
                self._count += 1
                frame = frame_from_part(jpeg, headers, self._count)
                async with self._changed:
                    self.latest = frame
                    self._changed.notify_all()
        finally:
            writer.close()
            with contextlib.suppress(Exception):
                await writer.wait_closed()


FrameSource = Callable[[int | None], Awaitable[Frame]]


class MjpegServer:
    """Serve ``/stream`` (MJPEG) and ``/capture`` (one JPEG) from a frame source.

    ``source(after_seq)`` must return a frame newer than ``after_seq``. ``on_clients`` is
    called with the number of stream clients whenever it changes.
    """

    def __init__(
        self,
        source: FrameSource,
        *,
        host: str = "127.0.0.1",
        port: int = 0,
        on_clients: Callable[[int], Any] | None = None,
    ) -> None:
        self.source = source
        self.host = host
        self.port = port
        self.on_clients = on_clients
        self.clients = 0
        self._server: asyncio.Server | None = None

    async def start(self) -> None:
        self._server = await asyncio.start_server(self._handle, self.host, self.port)
        self.port = self._server.sockets[0].getsockname()[1]

    async def stop(self) -> None:
        if self._server is not None:
            self._server.close()
            with contextlib.suppress(Exception):
                await asyncio.wait_for(self._server.wait_closed(), 1)

    def _set_clients(self, delta: int) -> None:
        self.clients += delta
        if self.on_clients is not None:
            self.on_clients(self.clients)

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            request = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), 5)
        except (asyncio.TimeoutError, asyncio.IncompleteReadError, asyncio.LimitOverrunError):
            writer.close()
            return
        path = request.split(b" ", 2)[1].decode("latin-1") if b" " in request else "/"
        path = path.split("?", 1)[0]
        try:
            if path == "/stream":
                await self._stream(reader, writer)
            elif path == "/capture":
                await self._capture(writer)
            else:
                writer.write(b"HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\n\r\n")
                await writer.drain()
        except (ConnectionError, asyncio.TimeoutError):
            pass
        finally:
            writer.close()
            with contextlib.suppress(Exception):
                await writer.wait_closed()

    async def _capture(self, writer: asyncio.StreamWriter) -> None:
        frame = await self.source(None)
        extra = "".join(f"{k}: {v}\r\n" for k, v in frame.headers().items())
        writer.write(
            (
                "HTTP/1.1 200 OK\r\nContent-Type: image/jpeg\r\n"
                f"Content-Length: {len(frame.jpeg)}\r\n{extra}"
                "Access-Control-Allow-Origin: *\r\nConnection: close\r\n\r\n"
            ).encode("latin-1")
            + frame.jpeg
        )
        await writer.drain()

    async def _stream(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        writer.write(
            (
                "HTTP/1.1 200 OK\r\n"
                f"Content-Type: multipart/x-mixed-replace;boundary={BOUNDARY}\r\n"
                "Cache-Control: no-store\r\nAccess-Control-Allow-Origin: *\r\n"
                "Connection: close\r\n\r\n"
            ).encode("latin-1")
        )
        self._set_clients(+1)
        # A viewer that goes away is noticed by its socket closing, not only by a failed
        # write (which can take very long) - so the privacy light goes off promptly.
        closed = asyncio.ensure_future(reader.read())
        try:
            seq: int | None = None
            while True:
                next_frame = asyncio.ensure_future(self.source(seq))
                await asyncio.wait({next_frame, closed}, return_when=asyncio.FIRST_COMPLETED)
                if closed.done():
                    next_frame.cancel()
                    return
                frame = next_frame.result()
                seq = frame.seq
                extra = "".join(f"{k}: {v}\r\n" for k, v in frame.headers().items())
                writer.write(
                    (
                        f"--{BOUNDARY}\r\nContent-Type: image/jpeg\r\n"
                        f"Content-Length: {len(frame.jpeg)}\r\n{extra}\r\n"
                    ).encode("latin-1")
                    + frame.jpeg
                    + b"\r\n"
                )
                await writer.drain()
        finally:
            closed.cancel()
            self._set_clients(-1)
