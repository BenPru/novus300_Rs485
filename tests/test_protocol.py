"""Tests for the Novus RS-485 protocol parser."""

import unittest
from datetime import datetime

from custom_components.novus300bus.protocol import (
    NovusFrameParser,
    build_date_frame,
    build_filter_interval_frame,
    build_filter_reset_frame,
    build_parameter_frame,
    build_select_frame,
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

    def test_fan_stage_frame_and_decode(self):
        frame = build_setting_frame("fan_stage_3_percentage", 47)
        self.assertEqual(frame.hex(), "01008503b28036002f")
        readings = NovusFrameParser().feed(frame)
        self.assertEqual(readings, [{"fan_stage_3_percentage": 47}])

    def test_decodes_startup_parameter_block(self):
        from custom_components.novus300bus.protocol import _decode_registers

        readings = _decode_registers(
            bytes.fromhex(
                "3f0000000b0000400002"
                "4100e6004200a50043000544008c450096460069470032004800054900b4004a0000"
                "004b00ecff4c00b0ff4d00114e00114f005a50005a5100285200115300c854006455"
                "008f015600dc005700005800145900055a00f4015b0032005c00055d00285e00005f"
                "0032006000dc006100056200006300f801"
            )
        )
        self.assertEqual(readings["param_41"], 230)
        self.assertEqual(readings["param_4b"], -20)
        self.assertEqual(readings["param_4c"], -80)
        self.assertEqual(readings["param_56"], 220)
        self.assertEqual(readings["param_63"], 504)
        self.assertEqual(readings["register_44"], 140)
        self.assertEqual(readings["fan_setpoint"], 39.9)

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

    def test_parameter_frames(self) -> None:
        frame = build_parameter_frame(0x41, 235)
        self.assertEqual(frame[3], 4)
        self.assertEqual(frame[6:], bytes.fromhex("4100eb00"))
        self.assertEqual(build_parameter_frame(0x43, 5)[6:], bytes.fromhex("430005"))
        self.assertEqual(build_parameter_frame(0x4B, -20)[6:], bytes.fromhex("4b00ecff"))
        with self.assertRaises(ValueError):
            build_parameter_frame(0x41, 900)

    def test_select_frames(self) -> None:
        self.assertEqual(build_select_frame(0x1E, 3)[6:], bytes.fromhex("1e000c7f0003"))
        self.assertEqual(build_select_frame(0x21, 0)[6:], bytes.fromhex("210000800000"))
        self.assertEqual(build_select_frame(0x1B, 0xFB)[6:], bytes.fromhex("1b00fb00"))
        self.assertEqual(build_select_frame(0x63, 0x1F8)[6:], bytes.fromhex("6300f801"))
        self.assertEqual(build_select_frame(0x24, 4)[6:], bytes.fromhex("240004"))
        with self.assertRaises(ValueError):
            build_select_frame(0x1E, 9)

    def test_decodes_install_registers_from_startup_dump(self) -> None:
        from custom_components.novus300bus.protocol import _decode_registers

        stream = bytes.fromhex(
            "0f0000" "120000" "150000" "180000"
            "1900" + "53575a30303235423236 41".replace(" ", "") +
            "1a0000" "1b007b00"
        )
        readings = _decode_registers(stream)
        self.assertEqual(readings["param_1b"], 0x7B)
        block = bytes.fromhex("1c00" + "5354303030363445323441" + "1d0000" "1e000c" "210000" "240000" "250036")
        readings = _decode_registers(block)
        self.assertEqual(readings["param_21"], 0)
        self.assertEqual(readings["param_24"], 0)
        self.assertNotIn("param_1e", readings)
        self.assertEqual(_decode_registers(bytes.fromhex("7b000000"))["param_7b"], 0)
        tail = bytes.fromhex(
            "76005555555 5aaaaaaaa7700aaaf02000000000078000000000000000000".replace(" ", "")
            + "79004b" "7a0001" "7b0000" "7c0005"
        )
        self.assertEqual(_decode_registers(tail)["param_7b"], 0)
        self.assertEqual(_decode_registers(tail)["param_79"], 0x4B)
        # panel format keeps its four bytes
        self.assertEqual(_decode_registers(bytes.fromhex("21000c800003"))["param_21"], 3)

    def test_maps_manual_error_codes(self) -> None:
        from custom_components.novus300bus.protocol import MESSAGES

        self.assertEqual(MESSAGES[0xC7], "defroster_comm_error")
        self.assertEqual(MESSAGES[0x85], "supply_air_too_low")


if __name__ == "__main__":
    unittest.main()
