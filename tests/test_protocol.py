"""Tests for the Novus RS-485 protocol parser."""

import unittest
from datetime import datetime

from custom_components.novus300bus.protocol import (
    NovusFrameParser,
    build_date_frame,
    build_filter_interval_frame,
    build_filter_reset_frame,
    build_power_frame,
    build_setting_frame,
    build_time_frame,
    crc16_ccitt,
)


class NovusFrameParserTest(unittest.TestCase):
    """Validate frames captured from the live Novus 300 bus."""

    def test_decodes_temperatures_and_fan_setpoint(self) -> None:
        parser = NovusFrameParser()
        frames = bytes.fromhex(
            "01008513a89b44008c8100e600820069008300e60084008c00"
            "01008519afa609004120202020202020202020202020202025003655009301"
        )

        readings = parser.feed(frames)

        self.assertEqual(
            readings[0],
            {
                "register_44": 140,
                "supply_air_temperature": 23.0,
                "outdoor_air_temperature": 10.5,
                "extract_air_temperature": 23.0,
                "exhaust_air_temperature": 14.0,
            },
        )
        self.assertEqual(
            readings[1],
            {"message_code": 65, "message": "filter_change", "fan_setpoint": 40.3},
        )

    def test_decodes_closed_bypass_status(self) -> None:
        parser = NovusFrameParser()

        readings = parser.feed(bytes.fromhex("0100850335771a000d"))

        self.assertEqual(
            readings,
            [
                {
                    "air_path": "heat_recovery",
                    "bypass_open": False,
                    "status_word": 13,
                }
            ],
        )

    def test_repairs_missing_frame_marker(self) -> None:
        parser = NovusFrameParser()

        readings = parser.feed(bytes.fromhex("0000850329331d0001"))

        self.assertEqual(readings, [{"run_state": "running", "run_state_raw": 1}])

    def test_decodes_panel_ventilation_mode(self) -> None:
        parser = NovusFrameParser()
        payload = bytes.fromhex("270000")
        header = bytes((0x01, 0x00, 0x85, len(payload)))
        crc = crc16_ccitt(header + payload)

        readings = parser.feed(
            header + bytes((crc & 0xFF, crc >> 8)) + payload
        )

        self.assertEqual(
            readings,
            [{"ventilation_mode": "standby", "ventilation_mode_raw": 0}],
        )

        payload = bytes.fromhex("270006")
        header = bytes((0x01, 0x00, 0x85, len(payload)))
        crc = crc16_ccitt(header + payload)

        readings = parser.feed(
            header + bytes((crc & 0xFF, crc >> 8)) + payload
        )

        self.assertEqual(
            readings,
            [{"ventilation_mode": "automatic", "ventilation_mode_raw": 6}],
        )

        payload = bytes.fromhex("270005")
        header = bytes((0x01, 0x00, 0x85, len(payload)))
        crc = crc16_ccitt(header + payload)
        readings = parser.feed(
            header + bytes((crc & 0xFF, crc >> 8)) + payload
        )

        self.assertEqual(
            readings,
            [{"ventilation_mode": "away", "ventilation_mode_raw": 5}],
        )

    def test_decodes_clock_broadcast(self) -> None:
        parser = NovusFrameParser()

        readings = parser.feed(bytes.fromhex("0000000ec8b0010001110b1a0200230716040000"))

        self.assertEqual(readings, [{"clock": "2026-11-17T22:07:35"}])

    def test_builds_panel_clock_frames(self) -> None:
        self.assertEqual(
            build_time_frame(datetime(2026, 11, 17, 21, 7, 6)).hex(),
            "010085055c570200060715",
        )
        self.assertEqual(
            build_date_frame(datetime(2026, 11, 17, 21, 7, 6)).hex(),
            "010085069953010001110b1a",
        )

    def test_decodes_and_builds_unit_settings(self) -> None:
        parser = NovusFrameParser()

        readings = parser.feed(
            bytes.fromhex("010085097a2c2e002331000062000b")
            + bytes.fromhex("01008503db453b0014")
            + bytes.fromhex("0100850301613c001e")
        )

        self.assertEqual(
            readings,
            [
                {"fan_level_1_percentage": 35, "register_62": 11},
                {"boost_duration_minutes": 20},
                {"away_duration_minutes": 30},
            ],
        )
        self.assertEqual(
            build_setting_frame("boost_duration_minutes", 20).hex(),
            "01008503db453b0014",
        )
        self.assertEqual(
            build_setting_frame("fan_level_3_percentage", 90).hex(),
            "01008503201c30005a",
        )

    def test_filter_frames_match_panel(self):
        self.assertEqual(build_filter_interval_frame(110).hex(), "01008507c2e43d0000006e0000")
        self.assertEqual(build_filter_interval_frame(90).hex(), "01008507a7fd3d0000005a0000")
        self.assertEqual(
            build_filter_reset_frame(110).hex(), "0100850e838e3d0000006e00003e0000006e0000"
        )
        self.assertEqual(
            build_filter_reset_frame(90).hex(), "0100850e48973d0000005a00003e0000005a0000"
        )

    def test_builds_power_frames(self):
        self.assertEqual(build_power_frame(False).hex(), "01008503aaa7070000")
        self.assertEqual(build_power_frame(True).hex(), "0100850693bd070001900000")

    def test_decodes_stored_message(self):
        frame = bytes.fromhex(
            "0100853d9d7a0a008354656d7046726f6d427553444546520b00050d061a0c00292c0a"
            "0f0000120000150000180000190053575a30303235423236411a00001b007b00"
        )
        readings = {}
        for part in NovusFrameParser().feed(frame):
            readings.update(part)
        self.assertEqual(
            readings["message_log_0"], "2026-06-13T10:44:41|131|TempFromBuSDEFR"
        )


if __name__ == "__main__":
    unittest.main()
