"""Whitelist regression tests; never connect to the serial bus."""

import importlib.util
from pathlib import Path
import unittest

from custom_components.novus300bus.protocol import (
    _build_register_write,
    build_select_frame,
    build_setting_frame,
)
spec = importlib.util.spec_from_file_location(
    "novus_bridge",
    Path(__file__).resolve().parents[1] / "tools" / "novus300_serial_bridge.py",
)
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)
is_allowed_frame = bridge.is_allowed_frame


class BridgeWhitelistTest(unittest.TestCase):
    def test_all_imbalance_stages_accept_signed_limits(self):
        for level in range(1, 4):
            for value in (-50, -1, 0, 1, 50):
                with self.subTest(level=level, value=value):
                    self.assertTrue(
                        is_allowed_frame(build_setting_frame(f"fan_level_{level}_imbalance", value))
                    )

    def test_rejects_bad_imbalance_and_unrelated_status_writes(self):
        for register, value in ((0x31, -51), (0x32, 51), (0x33, 127), (0x1A, 0x20)):
            with self.subTest(register=register, value=value):
                self.assertFalse(
                    is_allowed_frame(
                        _build_register_write(bytes((register, 0, value & 0xFF)))
                    )
                )

    def test_summer_frames_remain_allowed_but_bad_crc_does_not(self):
        for value in (0x7B, 0xFB):
            frame = build_select_frame(0x1B, value)
            self.assertTrue(is_allowed_frame(frame))
            corrupt = bytearray(frame)
            corrupt[4] ^= 1
            self.assertFalse(is_allowed_frame(bytes(corrupt)))
