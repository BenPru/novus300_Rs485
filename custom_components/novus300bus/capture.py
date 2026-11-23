"""Bounded passive recordings of bytes already received by the serial reader."""

from datetime import datetime, timezone
from threading import Lock
from time import monotonic

CAPTURE_SECONDS = 120
CAPTURE_MAX_BYTES = 1024 * 1024
CAPTURE_MAX_CHUNKS = 2400


class PassiveRecording:
    """Keep up to two minutes without transmitting or creating another connection."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._status = "not_started"
        self._started_at: str | None = None
        self._ended_at: str | None = None
        self._deadline = 0.0
        self._bucket = -1
        self._bytes = 0
        self._chunks: list[dict[str, str]] = []

    def _finish_if_expired(self, now: float) -> None:
        if self._status == "recording" and now >= self._deadline:
            self._status = "complete"
            self._ended_at = datetime.now(timezone.utc).isoformat()

    def start(self) -> None:
        """Start explicitly; do not silently replace an ongoing recording."""
        with self._lock:
            now = monotonic()
            self._finish_if_expired(now)
            if self._status == "recording":
                raise ValueError("A passive recording is already running")
            self._status = "recording"
            self._started_at = datetime.now(timezone.utc).isoformat()
            self._ended_at = None
            self._deadline = now + CAPTURE_SECONDS
            self._bucket = -1
            self._bytes = 0
            self._chunks = []

    def feed(self, data: bytes, timestamp: str) -> None:
        """Coalesce tiny reads into 100 ms buckets, preserving all byte order."""
        with self._lock:
            now = monotonic()
            self._finish_if_expired(now)
            if self._status != "recording" or not data:
                return
            remaining = CAPTURE_MAX_BYTES - self._bytes
            bucket = int(now * 10)
            new_chunk = bucket != self._bucket
            if new_chunk and len(self._chunks) >= CAPTURE_MAX_CHUNKS:
                self._status = "truncated"
            else:
                captured = data[:remaining]
                if new_chunk:
                    self._chunks.append({"time": timestamp, "hex": captured.hex()})
                    self._bucket = bucket
                else:
                    self._chunks[-1]["hex"] += captured.hex()
                self._bytes += len(captured)
                if self._bytes >= CAPTURE_MAX_BYTES:
                    self._status = "truncated"
            if self._status == "truncated":
                self._ended_at = datetime.now(timezone.utc).isoformat()

    def snapshot(self) -> dict:
        """Return copied diagnostics, also completing recordings on a quiet bus."""
        with self._lock:
            self._finish_if_expired(monotonic())
            return {
                "status": self._status,
                "started_at": self._started_at,
                "ended_at": self._ended_at,
                "duration_limit_seconds": CAPTURE_SECONDS,
                "byte_limit": CAPTURE_MAX_BYTES,
                "received_bytes": self._bytes,
                "timestamp_resolution": "UTC; first byte of each approximately 100 ms chunk",
                "chunks": [dict(chunk) for chunk in self._chunks],
            }
