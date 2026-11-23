"""Passive decoder for the alternative protocol observed in issue #10."""

from collections import Counter, OrderedDict
from datetime import datetime
from functools import reduce
from operator import xor
from threading import Lock
from time import monotonic

from .protocol import NovusValue

# Only type/length combinations actually present in the supplied recordings.
FRAME_LENGTHS = {0x00: (10,), 0x01: (0,), 0x02: (2, 3), 0x03: (2,), 0x04: (17,), 0x0F: (0,)}


class NovusXorParser:
    """Validate XOR frames without assigning speculative register meanings."""

    def __init__(self) -> None:
        self._buffer = bytearray()
        self._lock = Lock()
        self._counts: Counter[str] = Counter()
        self._pages: OrderedDict[str, str] = OrderedDict()
        self._clock: str | None = None
        self._frames = 0
        self._discarded = 0
        self._checksum_errors = 0
        self._last_update = float("-inf")

    @staticmethod
    def _size(data: bytes | bytearray, offset: int) -> int | None:
        length, kind = data[offset + 1 : offset + 3]
        return length + 4 if length in FRAME_LENGTHS.get(kind, ()) else None

    def feed(self, data: bytes) -> list[dict[str, NovusValue]]:
        """Accept arbitrary TCP/serial chunks, including partial frames."""
        readings = []
        with self._lock:
            self._buffer.extend(data)
            while len(self._buffer) >= 4:
                size = self._size(self._buffer, 0)
                if size is not None and len(self._buffer) < size:
                    # A payload can itself contain a valid-looking short frame.
                    break
                elif size is not None:
                    frame = bytes(self._buffer[:size])
                    if reduce(xor, frame, 0) == 0xFE:
                        del self._buffer[:size]
                        self._frames += 1
                        self._counts[f"{frame[0]:02x}:{frame[2]:02x}"] += 1
                        values = self._decode(frame)
                        now = monotonic()
                        if values or now - self._last_update >= 1:
                            self._last_update = now
                            readings.append({"xor_frames_received": self._frames, **values})
                        continue
                    self._checksum_errors += 1
                del self._buffer[0]
                self._discarded += 1
        return readings

    def _decode(self, frame: bytes) -> dict[str, NovusValue]:
        address, _, kind = frame[:3]
        payload = frame[3:-1]
        if kind == 0x04:
            key = f"{address:02x}:{payload[0]:02x}"
            value = payload[1:].hex()
            old = self._pages.pop(key, None)
            self._pages[key] = value
            if len(self._pages) > 64:
                self._pages.popitem(last=False)
            if old != value:
                return {"xor_last_page": key, "xor_last_page_data": value}
        elif kind == 0x00 and address == 0:
            # BCD layout inferred from the dated captures, not yet panel-confirmed.
            bcd = [payload[index] for index in (1, 2, 3, 5, 6, 7)]
            if any(value & 0x0F > 9 or value >> 4 > 9 for value in bcd):
                return {}
            second, minute, hour, day, month, year = [
                (value >> 4) * 10 + (value & 0x0F) for value in bcd
            ]
            try:
                clock = datetime(2000 + year, month, day, hour, minute, second).isoformat()
            except ValueError:
                return {}
            if clock != self._clock:
                self._clock = clock
                return {"xor_clock": clock}
        return {}

    def diagnostics(self) -> dict:
        """Return a consistent, bounded snapshot while the reader is active."""
        with self._lock:
            return {
                "framing": "[address][payload length][type][payload][XOR]; XOR(all bytes)=fe",
                "valid_frames": self._frames,
                "discarded_bytes": self._discarded,
                "checksum_errors": self._checksum_errors,
                "buffered_bytes": len(self._buffer),
                "frames_by_address_type": dict(self._counts),
                "pages": dict(self._pages),
                "clock_interpretation": "Experimental BCD layout; confirm against the panel",
            }
