"""Tests for the Novus RS-485 protocol parser."""

import unittest

from custom_components.novus300bus.protocol import NovusFrameParser, crc16_ccitt


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
                "supply_air_temperature": 23.0,
                "outdoor_air_temperature": 10.5,
                "extract_air_temperature": 23.0,
                "exhaust_air_temperature": 14.0,
            },
        )
        self.assertEqual(readings[1], {"fan_setpoint": 40.3})

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


if __name__ == "__main__":
    unittest.main()
