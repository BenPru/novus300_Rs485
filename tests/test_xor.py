"""Offline tests for alternative framing and strictly passive recordings."""

from functools import reduce
from operator import xor
import unittest
from unittest.mock import patch

from custom_components.novus300bus.capture import PassiveRecording
from custom_components.novus300bus.protocol import NovusFrameParser
from custom_components.novus300bus.xor_protocol import NovusXorParser

HEARTBEAT = bytes.fromhex("020001fd")
PAGE = bytes.fromhex("0411041011325009000f0011000f0f5a02640100a6")
CLOCK = bytes.fromhex("000a0000315920002311260301aa")


def frame(address, kind, payload):
    data = bytes((address, len(payload), kind)) + payload
    return data + bytes((reduce(xor, data, 0xFE),))


class XorProtocolTest(unittest.TestCase):
    def test_recorded_stage_changes_ignore_request_echoes_and_bad_checksums(self):
        stage_2 = bytes.fromhex("04110400030157007f00000300c505000201010004")
        stage_1 = bytes.fromhex("04110400030157007f00000300c505000101010007")
        request = bytes.fromhex("01110420030157007f00000300c505000201010021")
        bad = stage_2[:-1] + bytes((stage_2[-1] ^ 1,))
        stream = stage_1 + request + bad + stage_2 + stage_1
        for size in (1, 7, len(stream)):
            with self.subTest(size=size):
                parser = NovusXorParser()
                stages = [
                    reading["xor_fan_stage"]
                    for offset in range(0, len(stream), size)
                    for reading in parser.feed(stream[offset:offset + size])
                    if "xor_fan_stage" in reading
                ]
                self.assertEqual(stages, [1, 2, 1])

    def test_all_seven_stages_and_unmapped_values_replace_previous_stage(self):
        parser = NovusXorParser()
        for stage in (1, 2, 3, 4, 5, 6, 7, 0, 8, 255, 1):
            payload = bytearray(17)
            payload[13] = stage
            readings = parser.feed(frame(4, 4, payload))
            self.assertEqual(readings[-1]["xor_fan_stage_raw"], stage)
            self.assertEqual(
                readings[-1]["xor_fan_stage"],
                stage if 1 <= stage <= 7 else "unknown",
            )
        diagnostics = parser.diagnostics()["fan_stage_interpretation"]
        self.assertEqual(diagnostics["capture_confirmed"], [1, 2])
        self.assertEqual(diagnostics["inferred"], [3, 4, 5, 6, 7])
        self.assertFalse(any(
            "xor_fan_stage" in reading
            for reading in parser.feed(frame(4, 4, b"\x10" + bytes(16)))
        ))

    def test_public_frames_survive_every_chunk_boundary_and_deduplicate(self):
        stream = HEARTBEAT + CLOCK + PAGE + PAGE
        for size in (1, 2, 3, 7, len(stream)):
            with self.subTest(size=size):
                parser = NovusXorParser()
                readings = []
                for offset in range(0, len(stream), size):
                    readings.extend(parser.feed(stream[offset : offset + size]))
                values = {key: value for reading in readings for key, value in reading.items()}
                self.assertEqual(values["xor_clock"], "2026-11-23T20:59:31")
                self.assertEqual(values["xor_last_page"], "04:10")
                self.assertEqual(values["xor_last_page_data"], PAGE[4:-1].hex())
                self.assertEqual(parser.diagnostics()["valid_frames"], 4)
                self.assertEqual(parser.diagnostics()["discarded_bytes"], 0)
                self.assertEqual(len([v for v in readings if "xor_last_page" in v]), 1)
                self.assertNotIn("outdoor_air_temperature", values)
                self.assertEqual(NovusFrameParser(dynamic_bus_addresses=True).feed(stream), [])

    def test_checksum_noise_false_header_and_incomplete_tail_are_bounded(self):
        parser = NovusXorParser()
        bad = PAGE[:-1] + bytes((PAGE[-1] ^ 1,))
        parser.feed(b"\xff\xff\xff" + bad + HEARTBEAT + CLOCK + PAGE[:8])
        diagnostics = parser.diagnostics()
        self.assertEqual(diagnostics["valid_frames"], 2)
        self.assertGreaterEqual(diagnostics["checksum_errors"], 1)
        self.assertEqual(diagnostics["buffered_bytes"], 8)
        parser.feed(PAGE[8:])
        self.assertEqual(parser.diagnostics()["valid_frames"], 3)
        parser.feed(b"\xff" * 10000)
        self.assertLessEqual(parser.diagnostics()["buffered_bytes"], 20)
        parser.feed(b"\x04\x11\x04" + HEARTBEAT + b"\xff" * 21)
        self.assertEqual(parser.diagnostics()["valid_frames"], 4)

    def test_partial_payload_may_contain_a_complete_short_frame(self):
        parser = NovusXorParser()
        packet = frame(4, 4, b"\x10" + HEARTBEAT + bytes(12))
        parser.feed(packet[:10])
        self.assertEqual(parser.diagnostics()["valid_frames"], 0)
        parser.feed(packet[10:])
        self.assertEqual(parser.diagnostics()["valid_frames"], 1)
        self.assertEqual(parser.diagnostics()["pages"]["04:10"], packet[4:-1].hex())

    def test_invalid_clock_is_not_published_and_raw_pages_stay_bounded(self):
        for payload in (
            bytes.fromhex("0031592000231a260301"),
            bytes.fromhex("00315920003102260301"),
        ):
            readings = NovusXorParser().feed(frame(0, 0, payload))
            self.assertFalse(any("xor_clock" in reading for reading in readings))
        parser = NovusXorParser()
        for page in range(100):
            parser.feed(frame(4, 4, bytes((page,)) + bytes(16)))
        self.assertEqual(len(parser.diagnostics()["pages"]), 64)
        self.assertNotIn("04:00", parser.diagnostics()["pages"])

    def test_heartbeat_only_stream_updates_count_at_most_once_per_second(self):
        parser = NovusXorParser()
        with patch("custom_components.novus300bus.xor_protocol.monotonic", return_value=0):
            self.assertEqual(len(parser.feed(HEARTBEAT * 100)), 1)
        with patch("custom_components.novus300bus.xor_protocol.monotonic", return_value=1):
            self.assertEqual(parser.feed(HEARTBEAT), [{"xor_frames_received": 101}])


class PassiveRecordingTest(unittest.TestCase):
    def test_manual_start_coalesces_bytes_and_completes_even_without_new_input(self):
        now = [0.0]
        with patch("custom_components.novus300bus.capture.monotonic", side_effect=lambda: now[0]):
            capture = PassiveRecording()
            capture.feed(b"ignored", "before")
            capture.start()
            with self.assertRaisesRegex(ValueError, "already running"):
                capture.start()
            capture.feed(b"\x01", "first")
            now[0] = 0.05
            capture.feed(b"\x02", "second")
            now[0] = 0.2
            capture.feed(b"\x03", "third")
            snapshot = capture.snapshot()
            snapshot["chunks"][0]["hex"] = "changed"
            now[0] = 121
            capture.feed(b"late", "late")
            snapshot = capture.snapshot()
            self.assertEqual(snapshot["status"], "complete")
            self.assertEqual(snapshot["received_bytes"], 3)
            self.assertEqual(snapshot["chunks"], [
                {"time": "first", "hex": "0102"}, {"time": "third", "hex": "03"}
            ])
            self.assertIsNotNone(snapshot["ended_at"])
            capture.start()
            now[0] = 242
            self.assertEqual(capture.snapshot()["status"], "complete")
            self.assertEqual(capture.snapshot()["received_bytes"], 0)

    def test_byte_and_chunk_limits_report_truncation_without_dropping_retained_bytes(self):
        with patch("custom_components.novus300bus.capture.CAPTURE_MAX_BYTES", 5):
            capture = PassiveRecording()
            capture.start()
            capture.feed(b"123456789", "first")
            capture.feed(b"ignored", "later")
            snapshot = capture.snapshot()
            self.assertEqual(snapshot["status"], "truncated")
            self.assertEqual(snapshot["received_bytes"], 5)
            self.assertEqual(snapshot["chunks"][0]["hex"], b"12345".hex())
        with patch("custom_components.novus300bus.capture.CAPTURE_MAX_CHUNKS", 1):
            with patch("custom_components.novus300bus.capture.monotonic", return_value=0):
                capture = PassiveRecording()
                capture.start()
                capture.feed(b"first", "first")
            with patch("custom_components.novus300bus.capture.monotonic", return_value=1):
                capture.feed(b"later", "later")
                self.assertEqual(capture.snapshot()["status"], "truncated")
                self.assertEqual(capture.snapshot()["received_bytes"], 5)
