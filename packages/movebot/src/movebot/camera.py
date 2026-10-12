"""The bot's camera: pictures as numpy arrays (OpenCV-ready, BGR channel order).

Frames come from the bot's MJPEG stream. Only the newest frame is kept, so code that
is slower than the camera always works on a fresh picture instead of falling behind.
"""

from __future__ import annotations

import asyncio
import io
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit

from .errors import NotSupported
from .mjpeg import Frame, MjpegReader, jpeg_size
from .models import Pose

if TYPE_CHECKING:
    import numpy as np

    from .connection import Connection


def decode_jpeg(data: bytes) -> np.ndarray:
    """JPEG bytes -> ``height x width x 3`` uint8 array in BGR order (like OpenCV)."""
    import numpy as np

    try:
        import cv2  # type: ignore[import-not-found]
    except ImportError:
        cv2 = None
    if cv2 is not None:
        image = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
        if image is not None:
            return image
    from PIL import Image

    rgb = np.asarray(Image.open(io.BytesIO(data)).convert("RGB"))
    return np.ascontiguousarray(rgb[:, :, ::-1])


@dataclass
class CameraFrame:
    """One picture from the bot, plus when and where it was taken."""

    jpeg: bytes
    seq: int  # frame number from the bot
    t: int | None  # ms since the bot booted, at capture time
    pose: Pose | None  # where the bot thought it was when the picture was taken
    received: float  # time.monotonic() when it arrived here
    _image: Any = field(default=None, repr=False)

    @classmethod
    def from_frame(cls, frame: Frame) -> CameraFrame:
        pose = Pose(*frame.pose) if frame.pose is not None else None
        return cls(frame.jpeg, frame.seq, frame.t, pose, frame.received)

    @property
    def image(self) -> np.ndarray:
        """The picture as a numpy array (height x width x 3, BGR) - ready for OpenCV."""
        if self._image is None:
            self._image = decode_jpeg(self.jpeg)
        return self._image

    @property
    def rgb(self) -> np.ndarray:
        """The picture in RGB order (for matplotlib, Pillow, most ML models)."""
        return self.image[:, :, ::-1]

    @property
    def age(self) -> float:
        """Seconds since this frame arrived."""
        return time.monotonic() - self.received

    @property
    def size(self) -> tuple[int, int]:
        """(width, height) in pixels."""
        height, width = self.image.shape[:2]
        return width, height

    def save(self, path: str) -> str:
        """Save this picture as a JPEG file and return the path."""
        with open(path, "wb") as fh:
            fh.write(self.jpeg)
        return path


class AsyncCamera:
    def __init__(self, conn: Connection) -> None:
        self.conn = conn
        self._reader: MjpegReader | None = None
        self._expected_size: tuple[int, int] | None = None

    @property
    def available(self) -> bool:
        return bool(self.conn.hello.get("capabilities", {}).get("camera"))

    @property
    def info(self) -> dict[str, Any]:
        """Resolutions, presets and limits the bot's camera supports."""
        camera = self.conn.hello.get("capabilities", {}).get("camera")
        return camera if isinstance(camera, dict) else {}

    @property
    def stream_url(self) -> str:
        info = self._require()
        host = urlsplit(self.conn.url).hostname or "127.0.0.1"
        if ":" in host:
            host = f"[{host}]"
        return f"http://{host}:{info['stream_port']}{info.get('stream_path', '/stream')}"

    def _require(self) -> dict[str, Any]:
        info = self.info
        if not info:
            raise NotSupported("not_supported", "This MoveBot has no camera.")
        return info

    def _reader_for_url(self) -> MjpegReader:
        url = self.stream_url
        if self._reader is None or self._reader.url != url:
            self._reader = MjpegReader(url)
        return self._reader

    async def frame(self, timeout: float = 5.0) -> CameraFrame:
        """The newest frame (waits for the first one after starting the stream)."""
        return await self.next_frame(None, timeout)

    async def next_frame(self, after_seq: int | None, timeout: float = 5.0) -> CameraFrame:
        reader = self._reader_for_url()
        deadline = time.monotonic() + timeout
        while True:
            try:
                frame = await reader.wait_frame(after_seq, max(0.0, deadline - time.monotonic()))
            except asyncio.TimeoutError:  # not the builtin TimeoutError on Python 3.10
                detail = f" ({reader.error})" if reader.error else ""
                raise TimeoutError(
                    f"No picture from the camera within {timeout:g} s{detail}."
                ) from None
            # After a resolution change, skip pictures the camera took before it switched.
            if self._expected_size is None or jpeg_size(frame.jpeg) == self._expected_size:
                self._expected_size = None
                return CameraFrame.from_frame(frame)
            after_seq = frame.seq

    async def settings(self) -> dict[str, Any]:
        self._require()
        return await self.conn.request("camera.get")

    async def configure(
        self,
        preset: str | None = None,
        *,
        resolution: str | None = None,
        fps: int | None = None,
        quality: int | None = None,
    ) -> dict[str, Any]:
        self._require()
        params = {
            k: v
            for k, v in {
                "preset": preset,
                "resolution": resolution,
                "fps": fps,
                "quality": quality,
            }.items()
            if v is not None
        }
        result = await self.conn.request("camera.set", **params)
        width, _, height = str(result.get("resolution", "")).partition("x")
        if width.isdigit() and height.isdigit():
            self._expected_size = (int(width), int(height))
        return result

    async def stop(self) -> None:
        """Stop receiving pictures (the bot's privacy light goes off when nobody watches)."""
        if self._reader is not None:
            await self._reader.stop()
            self._reader = None
