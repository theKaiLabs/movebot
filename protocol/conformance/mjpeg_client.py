"""Minimal blocking MJPEG/HTTP client for the conformance suite (standard library only)."""

from __future__ import annotations

import socket
from dataclasses import dataclass
from urllib.parse import urlsplit


@dataclass
class Part:
    headers: dict[str, str]
    jpeg: bytes

    @property
    def size(self) -> tuple[int, int] | None:
        return jpeg_size(self.jpeg)


def jpeg_size(data: bytes) -> tuple[int, int] | None:
    """(width, height) from the JPEG start-of-frame segment."""
    if data[:2] != b"\xff\xd8":
        return None
    i = 2
    while i + 9 < len(data):
        if data[i] != 0xFF:
            return None
        marker = data[i + 1]
        if marker == 0xFF:
            i += 1
            continue
        length = int.from_bytes(data[i + 2 : i + 4], "big")
        if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
            return int.from_bytes(data[i + 7 : i + 9], "big"), int.from_bytes(
                data[i + 5 : i + 7], "big"
            )
        i += 2 + length
    return None


def camera_base(ws_url: str, camera: dict) -> tuple[str, int]:
    return urlsplit(ws_url).hostname or "127.0.0.1", int(camera["stream_port"])


class HttpStream:
    def __init__(self, host: str, port: int, path: str, timeout: float = 5.0) -> None:
        self.sock = socket.create_connection((host, port), timeout=timeout)
        self.file = self.sock.makefile("rb")
        request = f"GET {path} HTTP/1.1\r\nHost: {host}:{port}\r\nConnection: close\r\n\r\n"
        self.sock.sendall(request.encode("ascii"))
        self.status = self.file.readline().decode("latin-1").strip()
        self.headers = self._headers()

    def _headers(self) -> dict[str, str]:
        headers = {}
        while True:
            line = self.file.readline().decode("latin-1").strip()
            if not line:
                return headers
            name, _, value = line.partition(":")
            headers[name.strip().lower()] = value.strip()

    def body(self) -> bytes:
        return self.file.read(int(self.headers["content-length"]))

    def next_part(self) -> Part:
        while True:
            line = self.file.readline()
            if not line:
                raise ConnectionError("stream ended")
            if line.startswith(b"--"):
                break
        headers = self._headers()
        return Part(headers, self.file.read(int(headers["content-length"])))

    def close(self) -> None:
        self.file.close()
        self.sock.close()

    def __enter__(self) -> HttpStream:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
