"""Bus-free tests for summer ventilation, options and entity gating."""

import asyncio
from collections import deque
import json
import threading
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from homeassistant.exceptions import HomeAssistantError
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.storage import Store
import voluptuous as vol

from custom_components.novus300bus import _platforms, _register_sub_devices, _sync_bypass_entity
from custom_components.novus300bus.button import async_setup_entry as setup_buttons
from custom_components.novus300bus.capture import PassiveRecording
from custom_components.novus300bus.config_flow import NovusConfigFlow, NovusOptionsFlow
from custom_components.novus300bus.coordinator import NovusCoordinator
from custom_components.novus300bus.diagnostics import async_get_config_entry_diagnostics
from custom_components.novus300bus.fan import NovusBusFanEntity, NovusFanEntity
from custom_components.novus300bus.protocol import NovusFrameParser, build_setting_frame
from custom_components.novus300bus.sensor import NovusSensor, XOR_SENSORS
from custom_components.novus300bus.switch import NovusSummerVentilationSwitch
from custom_components.novus300bus.xor_protocol import NovusXorParser


def coordinator(values=None):
    instance = object.__new__(NovusCoordinator)
    instance._values = dict(values or {})
    instance.data = dict(instance._values)
    instance._config = {}
    instance._parameter_write_lock = asyncio.Lock()
    instance._plant_word_received = asyncio.Event()
    instance._counter_store = Mock()
    instance._stop_event = threading.Event()
    instance._serial_lock = threading.Lock()
    instance._serial = None
    instance._async_send = AsyncMock()
    instance.last_update_success = True
    instance.async_set_updated_data = Mock(
        side_effect=lambda data: setattr(instance, "data", data)
    )
    return instance


class XorStageSensorTest(unittest.TestCase):
    def test_inferred_stages_are_distinct_from_confirmed_values_and_unknown(self):
        co = coordinator()
        co._config = {"hardware_profile": "xor"}
        description = next(item for item in XOR_SENSORS if item.key == "xor_fan_stage")
        sensor = NovusSensor(co, description)
        self.assertFalse(sensor.available)
        for value, expected, status in (
            (1, 1, "capture_confirmed"),
            (2, 2, "capture_confirmed"),
            (3, 3, "capture_confirmed"),
            (4, 4, "inferred"),
            (7, 7, "capture_confirmed"),
            (0, None, "unmapped"),
            (255, None, "unmapped"),
        ):
            co.data = {"xor_fan_stage": value, "xor_fan_stage_raw": value}
            self.assertTrue(sensor.available)
            self.assertEqual(sensor.native_value, expected)
            self.assertEqual(sensor.extra_state_attributes["mapping_status"], status)
            self.assertEqual(sensor.extra_state_attributes["raw_value"], value)
        co.data = {"xor_fan_stage": "unknown", "xor_fan_stage_raw": 8}
        self.assertIsNone(sensor.native_value)
        self.assertEqual(sensor.extra_state_attributes["boost_status"], "unknown")

    def test_mode_sensor_and_boost_attribute_do_not_guess_from_stage(self):
        co = coordinator()
        co._config = {"hardware_profile": "xor"}
        mode = NovusSensor(co, next(d for d in XOR_SENSORS if d.key == "xor_operating_mode"))
        stage = NovusSensor(co, next(d for d in XOR_SENSORS if d.key == "xor_fan_stage"))
        self.assertFalse(mode.available)
        for raw, value, expected, boost in (
            (4, "boost", "boost", "active"),
            (1, "supply_extract", "supply_extract", "inactive"),
            (2, "extract_only", "extract_only", "inactive"),
            (3, "supply_only", "supply_only", "inactive"),
            (255, "unknown", None, "unknown"),
        ):
            with self.subTest(raw=raw):
                co.data = {
                    "xor_operating_mode": value, "xor_operating_mode_raw": raw,
                    "xor_fan_stage": 7, "xor_fan_stage_raw": 7,
                }
                self.assertTrue(mode.available)
                self.assertEqual(mode.native_value, expected)
                self.assertEqual(mode.extra_state_attributes["raw_value"], raw)
                self.assertEqual(stage.extra_state_attributes["boost_status"], boost)
                self.assertEqual(mode.extra_state_attributes["mapping_status"],
                                 "capture_confirmed" if raw != 255 else "unmapped")


class CoordinatorStopTest(unittest.IsolatedAsyncioTestCase):
    async def test_reload_flushes_pending_store_and_cancels_the_old_writer(self):
        with TemporaryDirectory(prefix="novus-stop-test-") as directory:
            hass = HomeAssistant(directory)
            co = coordinator({"param_1b": 0x73})
            co.hass = hass
            co._thread = None
            co._cancel_time_sync = None
            co._counter_store = Store(hass, 1, "novus-stop-test")
            await co._counter_store.async_save({"param_1b": 0x77})
            co._counter_store.async_delay_save(co._persisted_values, 0.05)

            await co.async_stop()
            replacement = Store(hass, 1, "novus-stop-test")
            self.assertEqual(await replacement.async_load(), {"param_1b": 0x73})
            await replacement.async_save({"param_1b": 0x7F})
            await asyncio.sleep(0.1)
            self.assertEqual(
                await Store(hass, 1, "novus-stop-test").async_load(),
                {"param_1b": 0x7F},
            )

    async def test_stop_joins_reader_before_flushing_current_configuration(self):
        co = coordinator({"param_1b": 0x73, "defroster_status_raw": 0x0C})
        co._cancel_time_sync = Mock()
        co._thread = Mock()
        co._thread.is_alive.return_value = False
        co._serial = Mock()
        order = []

        async def executor(func, *args):
            self.assertTrue(co._stop_event.is_set())
            order.append("join")
            return func(*args)

        async def save(values):
            order.append("save")
            self.assertEqual(values, {"param_1b": 0x73, "defroster_status_raw": 0x0C})

        co.hass = SimpleNamespace(async_add_executor_job=AsyncMock(side_effect=executor))
        co._counter_store.async_save = AsyncMock(side_effect=save)
        cancel = co._cancel_time_sync
        await co.async_stop()
        self.assertEqual(order, ["join", "save"])
        co._thread.join.assert_called_once_with(5)
        co._serial.close.assert_not_called()
        cancel.assert_called_once()
        self.assertIsNone(co._cancel_time_sync)
        co._counter_store.async_save.assert_awaited_once()

    async def test_stopped_coordinator_cannot_publish_queued_stale_values(self):
        co = coordinator({"param_1b": 0x73})
        co._stop_event.set()
        co._async_publish({"param_1b": 0x77})
        self.assertEqual(co._values["param_1b"], 0x73)
        co.async_set_updated_data.assert_not_called()
        co._counter_store.async_delay_save.assert_not_called()

    async def test_stop_reports_reader_that_has_not_finished(self):
        co = coordinator({"param_1b": 0x73})
        co._cancel_time_sync = None
        co._thread = Mock()
        co._thread.is_alive.return_value = True
        co.hass = SimpleNamespace(async_add_executor_job=AsyncMock())
        co._counter_store.async_save = AsyncMock()
        with self.assertRaisesRegex(HomeAssistantError, "reader did not stop"):
            await co.async_stop()
        co._counter_store.async_save.assert_not_awaited()


class SummerControlTest(unittest.IsolatedAsyncioTestCase):
    async def test_switch_uses_bus_feedback_and_preserves_flags(self):
        for initial, desired, expected in ((0x7B, True, 0xFB), (0xFB, False, 0x7B)):
            with self.subTest(desired=desired):
                co = coordinator({"param_1b": initial})

                async def feedback(frame):
                    self.assertEqual(int.from_bytes(frame[8:], "little"), expected)
                    self.assertEqual(co.data["param_1b"], initial)
                    co._async_publish({"param_1b": expected})

                co._async_send.side_effect = feedback
                entity = NovusSummerVentilationSwitch(co)
                await (entity.async_turn_on() if desired else entity.async_turn_off())
                self.assertEqual(entity.is_on, desired)

    async def test_installed_bypass_or_unknown_configuration_cannot_write(self):
        for values in ({}, {"param_1b": 0x7F}):
            co = coordinator(values)
            self.assertFalse(NovusSummerVentilationSwitch(co).available)
            with self.assertRaises(HomeAssistantError):
                await co.async_set_summer_ventilation(True)
            co._async_send.assert_not_awaited()

    async def test_missing_feedback_and_send_failure_are_not_success(self):
        co = coordinator({"param_1b": 0x7B})
        timeout = asyncio.timeout
        with patch(
            "custom_components.novus300bus.coordinator.asyncio.timeout",
            side_effect=lambda _: timeout(0.001),
        ):
            with self.assertRaisesRegex(HomeAssistantError, "did not confirm"):
                await co.async_set_summer_ventilation(True)
        self.assertEqual(co.data["param_1b"], 0x7B)
        co._async_send.side_effect = HomeAssistantError("Disconnected")
        with self.assertRaisesRegex(HomeAssistantError, "Disconnected"):
            await co.async_set_summer_ventilation(True)
        self.assertEqual(co.data["param_1b"], 0x7B)

    async def test_stale_installation_options_do_not_clear_summer_flag(self):
        co = coordinator({"param_1b": 0xFB})
        with patch("custom_components.novus300bus.coordinator.asyncio.sleep", new=AsyncMock()):
            await co.async_write_parameters({0x1B: 0x7F})
        self.assertEqual(co._async_send.await_args.args[0][8:], bytes.fromhex("ff00"))

    async def test_concurrent_installation_waits_for_summer_confirmation(self):
        co = coordinator({"param_1b": 0x7B})
        sent = asyncio.Event()
        co._async_send.side_effect = lambda _: sent.set()
        summer = asyncio.create_task(co.async_set_summer_ventilation(True))
        await sent.wait()
        installation = asyncio.create_task(co.async_write_parameters({0x1B: 0x7F}))
        await asyncio.sleep(0)
        self.assertEqual(co._async_send.await_count, 1)
        co._async_publish({"param_1b": 0xFB})
        await asyncio.gather(summer, installation)
        self.assertEqual(co._async_send.await_args.args[0][8:], bytes.fromhex("ff00"))

    async def test_installing_bypass_during_confirmation_is_an_error(self):
        co = coordinator({"param_1b": 0x7B})
        co._async_send.side_effect = lambda _: co._async_publish({"param_1b": 0x7F})
        with self.assertRaisesRegex(HomeAssistantError, "no longer reports a configuration without"):
            await co.async_set_summer_ventilation(True)

    async def test_invalid_imbalance_is_rejected_before_any_write(self):
        co = coordinator()
        with self.assertRaises(HomeAssistantError):
            await co.async_write_settings(
                {"fan_level_1_percentage": 20, "fan_level_2_imbalance": -51}
            )
        co._async_send.assert_not_awaited()

    async def test_half_percent_is_written_and_remembered_without_truncation(self):
        co = coordinator()
        with patch("custom_components.novus300bus.coordinator.asyncio.sleep", new=AsyncMock()):
            await co.async_write_settings({"fan_level_1_imbalance": -0.5})
        self.assertEqual(co._async_send.await_args.args[0][8:], b"\xff")
        self.assertEqual(co.setting_value("fan_level_1_imbalance"), -0.5)
        self.assertEqual(co.settings_from_bus()["fan_level_1_imbalance"], -0.5)
        self.assertNotIn("fan_level_1_imbalance", co.settings_not_read())


class FanRestoreTest(unittest.IsolatedAsyncioTestCase):
    def fan(self, co):
        entity = NovusBusFanEntity(co)
        tasks = []

        def create_task(coro):
            task = asyncio.create_task(coro)
            tasks.append(task)
            return task

        def publish(data):
            co.data = data
            entity._handle_coordinator_update()

        entity.hass = SimpleNamespace(async_create_task=create_task)
        entity.async_write_ha_state = Mock()
        co.async_set_updated_data.side_effect = publish
        return entity, tasks

    def receive(self, co, frame):
        for readings in NovusFrameParser().feed(bytes.fromhex(frame)):
            co._async_publish(readings)

    async def test_captured_panel_transitions_restore_inactive_level(self):
        frames = {
            "level_1": "01008506d4f8270001290001",
            "level_2": "010085066b53270002290002",
            "level_3": "01008506fe35270003290003",
            "automatic": "010085061ed9270006290006",
        }
        for old_mode, original, overridden in (("level_1", 20, 35), ("level_3", 75, 85)):
            key = f"fan_{old_mode}_percentage"
            for new_mode, frame in frames.items():
                with self.subTest(old_mode=old_mode, new_mode=new_mode):
                    co = coordinator({
                        "ventilation_mode": old_mode,
                        key: overridden,
                        f"orig_{key}": original,
                    })
                    _, tasks = self.fan(co)
                    with patch("custom_components.novus300bus.coordinator.asyncio.sleep", new=AsyncMock()):
                        self.receive(co, frame)
                        await asyncio.gather(*tasks)
                    if new_mode == old_mode:
                        co._async_send.assert_not_awaited()
                        self.assertEqual(co.temporary_settings(), {key: original})
                    else:
                        co._async_send.assert_awaited_once_with(build_setting_frame(key, original))
                        self.assertEqual(co.setting_value(key, actual=True), original)
                        self.assertEqual(co.temporary_settings(), {})

    async def test_restoring_inactive_level_preserves_other_active_override(self):
        first = "fan_level_1_percentage"
        third = "fan_level_3_percentage"
        co = coordinator({
            "ventilation_mode": "level_1",
            first: 35, f"orig_{first}": 20,
            third: 85, f"orig_{third}": 75,
        })
        _, tasks = self.fan(co)
        with patch("custom_components.novus300bus.coordinator.asyncio.sleep", new=AsyncMock()):
            self.receive(co, "01008506fe35270003290003")
            await asyncio.gather(*tasks)
        co._async_send.assert_awaited_once_with(build_setting_frame(first, 20))
        self.assertEqual(co.temporary_settings(), {third: 75})
        self.assertEqual(co.setting_value(third, actual=True), 85)

    async def test_failed_restore_retains_original_and_retries_after_backoff(self):
        key = "fan_level_1_percentage"
        co = coordinator({
            "ventilation_mode": "level_1",
            key: 35, f"orig_{key}": 20,
        })
        entity, tasks = self.fan(co)
        co._async_send.side_effect = HomeAssistantError("Disconnected")
        with patch("custom_components.novus300bus.fan.monotonic", return_value=100):
            self.receive(co, "010085066b53270002290002")
            with self.assertLogs("custom_components.novus300bus.fan", level="WARNING"):
                await asyncio.gather(*tasks)
        self.assertFalse(entity._busy)
        self.assertEqual(co.temporary_settings(), {key: 20})
        with patch("custom_components.novus300bus.fan.monotonic", return_value=159):
            self.receive(co, "010085066b53270002290002")
        self.assertEqual(len(tasks), 1)
        co._async_send.side_effect = None
        with (
            patch("custom_components.novus300bus.fan.monotonic", return_value=161),
            patch("custom_components.novus300bus.coordinator.asyncio.sleep", new=AsyncMock()),
        ):
            self.receive(co, "010085066b53270002290002")
            await asyncio.gather(*tasks)
        self.assertEqual(len(tasks), 2)
        self.assertEqual(co._async_send.await_args.args, (build_setting_frame(key, 20),))
        self.assertEqual(co.temporary_settings(), {})

    async def test_failed_second_override_does_not_forget_original(self):
        key = "fan_level_1_percentage"
        co = coordinator({
            "ventilation_mode": "level_1",
            key: 35, f"orig_{key}": 20,
        })
        _, tasks = self.fan(co)
        co._async_send.side_effect = HomeAssistantError("Disconnected")
        with self.assertRaises(HomeAssistantError):
            await co.async_set_temporary_setting(key, 30)
        self.assertEqual(co.temporary_settings(), {key: 20})
        co._async_send.reset_mock(side_effect=True)
        with patch("custom_components.novus300bus.coordinator.asyncio.sleep", new=AsyncMock()):
            self.receive(co, "010085066b53270002290002")
            await asyncio.gather(*tasks)
        co._async_send.assert_awaited_once_with(build_setting_frame(key, 20))
        self.assertEqual(co.temporary_settings(), {})


class EntityGatingTest(unittest.TestCase):
    def test_bypass_installation_is_independent_of_activation_and_summer_flags(self):
        for raw, expected in (
            (0x77, True), (0x7F, True), (0xF7, True), (0xFF, True),
            (0x73, False), (0x7B, False), (0xF3, False), (0xFB, False),
            (None, None), (0, None), (0x177, None), (True, None),
        ):
            with self.subTest(raw=raw):
                self.assertIs(coordinator({"param_1b": raw}).bypass_present, expected)

    def test_defroster_status_distinguishes_presence_without_guessing_type(self):
        for raw, installed in ((0x08, False), (0x0C, True), (0x1C, True), (0xFF, None)):
            with self.subTest(raw=raw):
                co = coordinator({"defroster_status_raw": raw})
                parts = co.installed_parts
                self.assertIs(parts["defroster_installed"], installed)
                expected_type_presence = False if installed is False else None
                self.assertIs(parts["defroster_present"], expected_type_presence)
                self.assertIs(parts["brine_defroster_present"], expected_type_presence)
                self.assertEqual(co._persisted_values()["defroster_status_raw"], raw)
        parts = coordinator({"defroster_status_raw": 0x0C, "param_1e": 2}).installed_parts
        self.assertTrue(parts["defroster_present"])
        self.assertFalse(parts["brine_defroster_present"])
        parts = coordinator({"defroster_status_raw": 0x08, "param_1e": 2}).installed_parts
        self.assertFalse(parts["defroster_present"])
        self.assertFalse(parts["defroster_installed"])

    def test_gates_both_switches_without_overriding_user_disable(self):
        for present, disabled, changed_key, expected in (
            (True, er.RegistryEntryDisabler.INTEGRATION, "bypass", None),
            (False, er.RegistryEntryDisabler.INTEGRATION, "summer_ventilation", None),
            (True, None, "summer_ventilation", er.RegistryEntryDisabler.INTEGRATION),
            (False, None, "bypass", er.RegistryEntryDisabler.INTEGRATION),
            (True, er.RegistryEntryDisabler.USER, None, None),
            (False, er.RegistryEntryDisabler.USER, None, None),
            (None, None, None, None),
        ):
            with self.subTest(present=present, disabled=disabled):
                registry = Mock()
                registry.async_get_entity_id.side_effect = lambda _, __, uid: f"switch.{uid}"
                registry.async_get.return_value = SimpleNamespace(disabled_by=disabled)
                entry = SimpleNamespace(runtime_data=SimpleNamespace(bypass_present=present))
                with patch(
                    "custom_components.novus300bus.er.async_get", return_value=registry
                ):
                    _sync_bypass_entity(Mock(), entry)
                if changed_key is None:
                    registry.async_update_entity.assert_not_called()
                else:
                    registry.async_update_entity.assert_called_once_with(
                        f"switch.novus300bus_{changed_key}", disabled_by=expected
                    )


class BusConfigTest(unittest.IsolatedAsyncioTestCase):
    async def test_hardware_profile_defaults_and_saved_selection(self):
        flow = NovusConfigFlow()
        flow.async_show_form = Mock(side_effect=lambda **kwargs: kwargs)
        entry = SimpleNamespace(data={}, options={})
        flow._get_reconfigure_entry = Mock(return_value=entry)
        for step in (flow.async_step_user, flow.async_step_bus):
            form = await step()
            values = form["data_schema"]({"serial_port": "socket://test:502", "baudrate": 9600, "parity": "none"})
            self.assertEqual(values["hardware_profile"], "crc16")
        entry.options["hardware_profile"] = "xor"
        form = await flow.async_step_bus()
        values = form["data_schema"]({"serial_port": "socket://test:502", "baudrate": 9600, "parity": "none"})
        self.assertEqual(values["hardware_profile"], "xor")
        flow.async_abort = Mock(side_effect=lambda **kwargs: kwargs)
        self.assertEqual((await flow.async_step_fan_control({"fan_enabled": True}))["reason"], "read_only")

    async def test_dynamic_addresses_default_off_and_follow_saved_setting(self):
        flow = NovusConfigFlow()
        flow.async_show_form = Mock(side_effect=lambda **kwargs: kwargs)
        entry = SimpleNamespace(data={}, options={})
        flow._get_reconfigure_entry = Mock(return_value=entry)
        for step in (flow.async_step_user, flow.async_step_bus):
            result = await step()
            values = result["data_schema"](
                {"serial_port": "/dev/ttyUSB0", "baudrate": 9600, "parity": "mark"}
            )
            self.assertFalse(values["dynamic_bus_addresses"])
        entry.data["dynamic_bus_addresses"] = False
        entry.options["dynamic_bus_addresses"] = True
        result = await flow.async_step_bus()
        values = result["data_schema"](
            {"serial_port": "/dev/ttyUSB0", "baudrate": 9600, "parity": "mark"}
        )
        self.assertTrue(values["dynamic_bus_addresses"])

    async def test_bus_reconfiguration_saves_enabling_and_disabling(self):
        flow = NovusConfigFlow()
        entry = SimpleNamespace(
            data={"serial_port": "/dev/ttyUSB0"}, options={"daily_time_sync": False}
        )
        flow._get_reconfigure_entry = Mock(return_value=entry)
        flow.hass = Mock()
        flow.async_abort = Mock(return_value={"type": "abort"})
        for enabled in (True, False):
            with self.subTest(enabled=enabled):
                await flow.async_step_bus({"dynamic_bus_addresses": enabled})
                changes = flow.hass.config_entries.async_update_entry.call_args.kwargs
                self.assertEqual(changes["data"]["dynamic_bus_addresses"], enabled)
                self.assertEqual(changes["options"]["dynamic_bus_addresses"], enabled)
                self.assertEqual(changes["data"]["serial_port"], "/dev/ttyUSB0")
                self.assertFalse(changes["options"]["daily_time_sync"])


class OptionsTest(unittest.IsolatedAsyncioTestCase):
    def flow(self, values=None):
        co = coordinator(values)
        co.settings_not_read = Mock(return_value=[])
        co.clear_temporary_settings = Mock()
        co.filter_interval_days = Mock(return_value=90)
        co.async_write_settings = AsyncMock()
        entry = SimpleNamespace(options={}, data={}, runtime_data=co)
        flow = NovusOptionsFlow(entry)
        flow.hass = SimpleNamespace(config=SimpleNamespace(language="de"))
        flow.async_show_form = Mock(side_effect=lambda **kwargs: kwargs)
        flow._save = Mock(return_value={"type": "create_entry"})
        return flow, co

    async def test_profile_switch_saves_only_profile_without_device_writes(self):
        for previous, selected in (("crc16", "xor"), ("xor", "crc16"), ("xor", "xor")):
            with self.subTest(previous=previous, selected=selected):
                flow, co = self.flow()
                flow._config_entry.options["hardware_profile"] = previous
                await flow.async_step_general({
                    "hardware_profile": selected,
                    "filter_interval_days": 180,
                    "fan_level_1_percentage": 20,
                })
                flow._save.assert_called_once_with({"hardware_profile": selected})
                co.async_write_settings.assert_not_awaited()
                co._async_send.assert_not_awaited()
                co.clear_temporary_settings.assert_not_called()

    async def test_xor_options_offer_only_profile_and_block_hidden_write_steps(self):
        flow, co = self.flow()
        flow._config_entry.options["hardware_profile"] = "xor"
        flow.async_show_menu = Mock(side_effect=lambda **kwargs: kwargs)
        flow.async_abort = Mock(side_effect=lambda **kwargs: kwargs)
        self.assertEqual((await flow.async_step_init())["menu_options"], ["general"])
        form = await flow.async_step_general()
        self.assertEqual([field.schema for field in form["data_schema"].schema], ["hardware_profile"])
        for method in (
            flow.async_step_plant, flow.async_step_bypass, flow.async_step_missing_restart,
            flow.async_step_plant_form, flow.async_step_bypass_form,
            flow.async_step_summer_settings, flow.async_step_bypass_settings,
        ):
            with self.subTest(method=method.__name__):
                self.assertEqual((await method({}))["reason"], "read_only")
        co._async_send.assert_not_awaited()

    async def test_unknown_imbalance_has_no_default_and_is_not_written(self):
        flow, co = self.flow()
        schema = flow._general_schema()
        group = schema.schema["fan_level_1"]
        fields = {marker.schema: marker for marker in group.schema.schema}
        self.assertIs(fields["fan_level_1_imbalance"].default, vol.UNDEFINED)
        result = await flow.async_step_general(
            {
                "fan_level_1_percentage": 20,
                "fan_level_2_percentage": 60,
                "fan_level_3_percentage": 80,
                "boost_duration_minutes": 15,
                "away_duration_minutes": 15,
                "filter_interval_days": 90,
            }
        )
        self.assertEqual(result["type"], "create_entry")
        self.assertFalse(
            any("imbalance" in key for key in co.async_write_settings.await_args.args[0])
        )

    async def test_signed_imbalance_and_write_failure(self):
        flow, co = self.flow({"fan_level_1_imbalance": -9})
        data = {
            "fan_level_1_percentage": 20,
            "fan_level_2_percentage": 60,
            "fan_level_3_percentage": 80,
            "fan_level_1_imbalance": -12,
            "boost_duration_minutes": 15,
            "away_duration_minutes": 15,
            "filter_interval_days": 90,
        }
        await flow.async_step_general(data)
        self.assertEqual(co.async_write_settings.await_args.args[0]["fan_level_1_imbalance"], -12)
        co.async_write_settings.side_effect = HomeAssistantError("Offline")
        flow._save.reset_mock()
        result = await flow.async_step_general(data)
        self.assertEqual(result["errors"], {"base": "write_failed"})
        flow._save.assert_not_called()

    async def test_invalid_imbalance_and_summer_checkbox_removed(self):
        flow, co = self.flow({"param_1b": 0x7B})
        result = await flow.async_step_general({"fan_level_1_imbalance": 50.5})
        self.assertEqual(result["errors"], {"base": "invalid_imbalance"})
        co.async_write_settings.assert_not_awaited()
        result = await flow.async_step_bypass_form()
        self.assertNotIn("summer", {marker.schema for marker in result["data_schema"].schema})

    async def test_unknown_installation_cannot_be_guessed(self):
        flow, co = self.flow()
        co.async_write_parameters = AsyncMock()
        result = await flow.async_step_bypass_form({"bypass": False})
        self.assertEqual(result["errors"], {"base": "configuration_unknown"})
        co.async_write_parameters.assert_not_awaited()

    async def test_bypass_checkbox_uses_installation_bit_and_preserves_activation(self):
        for word, present, changed in ((0x77, True, 0x73), (0x7B, False, 0x7F)):
            with self.subTest(word=word):
                flow, co = self.flow({"param_1b": word})
                co.async_write_parameters = AsyncMock()
                form = await flow.async_step_bypass_form()
                field = next(marker for marker in form["data_schema"].schema if marker.schema == "bypass")
                self.assertIs(field.default(), present)
                await flow.async_step_bypass_form({"bypass": not present})
                co.async_write_parameters.assert_awaited_once_with({0x1B: changed})

    async def test_absent_defroster_does_not_require_a_panel_type(self):
        flow, _ = self.flow({"defroster_status_raw": 0x08})
        flow._dialog = "plant"
        self.assertNotIn(0x1E, flow._missing()[1])
        flow, _ = self.flow({"defroster_status_raw": 0x0C})
        flow._dialog = "plant"
        self.assertIn(0x1E, flow._missing()[1])

    async def test_level_sections_write_flat_settings_without_group_options(self):
        flow, co = self.flow()
        self.assertEqual(
            [field.schema for field in flow._general_schema().schema][2],
            "filter_interval_days",
        )
        data = {
            "fan_level_1": {"fan_level_1_percentage": 20, "fan_level_1_imbalance": -0.5},
            "fan_level_2": {"fan_level_2_percentage": 60},
            "fan_level_3": {"fan_level_3_percentage": 80, "fan_level_3_imbalance": 5},
            "boost_duration_minutes": 15,
            "away_duration_minutes": 15,
            "filter_interval_days": 90,
        }
        await flow.async_step_general(data)
        written = co.async_write_settings.await_args.args[0]
        self.assertEqual(written["fan_level_1_imbalance"], -0.5)
        self.assertEqual(written["fan_level_3_imbalance"], 5)
        self.assertNotIn("fan_level_2_imbalance", written)
        self.assertNotIn("fan_level_1", flow._save.call_args.args[0])
        for field in flow._general_schema().schema.values():
            if hasattr(field, "options"):
                self.assertTrue(field.options["collapsed"])

    async def test_frost_and_reheating_sections_keep_register_writes(self):
        flow, co = self.flow()
        co.async_write_parameters = AsyncMock()
        form = await flow.async_step_plant_form()
        frost = form["data_schema"].schema["frost_protection"]
        self.assertIn("p47", frost.schema.schema)
        self.assertTrue(frost.options["collapsed"])
        await flow.async_step_plant_form(
            {"frost_protection": {"p47": "5.5"}, "reheating": {"p5a": "20.5"}}
        )
        co.async_write_parameters.assert_awaited_once_with({0x47: 55, 0x5A: 205})

    async def test_threshold_sections_keep_register_writes(self):
        flow, co = self.flow()
        co.async_write_parameters = AsyncMock()
        await flow.async_step_plant_form(
            {"frost_protection": {"p48": "1.0"}, "reheating": {"p5c": "2.0"}}
        )
        co.async_write_parameters.assert_awaited_once_with({0x48: 10, 0x5C: 20})

    async def test_summer_section_keeps_threshold_writes(self):
        flow, co = self.flow({"param_1b": 0x7B})
        co.async_write_parameters = AsyncMock()
        await flow.async_step_bypass_form({"summer_ventilation": {"p41": "23.5"}})
        co.async_write_parameters.assert_awaited_once_with({0x41: 235})

    async def test_automatic_moves_above_levels_and_preserves_register_bits(self):
        flow, co = self.flow({"param_63": 0x1F0})
        co.async_write_parameters = AsyncMock()
        names = [field.schema for field in flow._general_schema().schema]
        self.assertEqual(
            names[3:6], ["automatic", "show_fan_levels", "fan_level_1"]
        )
        await flow.async_step_general(
            {
                "automatic": "sensor",
                "fan_level_1": {"fan_level_1_percentage": 20},
                "fan_level_2": {"fan_level_2_percentage": 60},
                "fan_level_3": {"fan_level_3_percentage": 80},
                "boost_duration_minutes": 15,
                "away_duration_minutes": 15,
                "filter_interval_days": 90,
            }
        )
        co.async_write_parameters.assert_awaited_once_with({0x63: 0x1F8})
        self.assertNotIn("automatic", flow._save.call_args.args[0])

    async def test_read_only_values_are_last_and_threshold_menu_is_removed(self):
        flow, co = self.flow({"param_4d": 17})
        flow.async_show_menu = Mock(side_effect=lambda **kwargs: kwargs)
        menu = await flow.async_step_init()
        self.assertNotIn("extra", menu["menu_options"])
        self.assertEqual(menu["menu_options"][-1], "advanced")
        form = await flow.async_step_advanced()
        self.assertIn("0x4D", form["description_placeholders"]["values"])
        form = await flow.async_step_plant_form()
        fields = form["data_schema"].schema
        self.assertNotIn("automatic", fields)
        self.assertEqual(
            [key.schema for key in fields["frost_protection"].schema.schema][:2],
            ["defroster", "frost"],
        )

    async def test_sections_expose_known_values_as_parent_defaults(self):
        flow, co = self.flow(
            {
                "param_47": 55,
                "param_4a": 0,
                "param_21": 1,
                "param_5a": 500,
                "param_41": 230,
                "fan_level_1_percentage": 21,
                "fan_level_1_imbalance": -0.5,
            }
        )
        plant = (await flow.async_step_plant_form())["data_schema"].schema
        defaults = {marker.schema: marker.default() for marker in plant}
        self.assertEqual(defaults["frost_protection"]["p47"], "5.5")
        self.assertEqual(defaults["frost_protection"]["p4a"], "0.0")
        self.assertNotIn("frost", defaults["frost_protection"])
        self.assertEqual(defaults["reheating"], {"reheater": "1", "p5a": "50.0"})
        general = {
            marker.schema: marker.default() for marker in flow._general_schema().schema
            if marker.default is not vol.UNDEFINED
        }
        self.assertEqual(
            general["fan_level_1"],
            {"fan_level_1_percentage": 21, "fan_level_1_imbalance": -0.5},
        )
        bypass = (await flow.async_step_bypass_form())["data_schema"].schema
        summer = next(marker for marker in bypass if marker.schema == "summer_ventilation")
        self.assertEqual(summer.default(), {"p41": "23.0"})
        self.assertFalse(bypass[summer].options["collapsed"])

    async def test_section_defaults_preserve_invalid_input_for_correction(self):
        flow, co = self.flow({"param_47": 55})
        form = await flow.async_step_plant_form({"frost_protection": {"p47": "oops"}})
        self.assertEqual(form["errors"]["base"], "invalid_number")
        frost = next(
            marker for marker in form["data_schema"].schema
            if marker.schema == "frost_protection"
        )
        self.assertEqual(frost.default()["p47"], "oops")

    async def test_ewt_checkbox_preserves_installation_register_mapping(self):
        for raw, wanted, expected in ((0, True, 4), (4, False, 0)):
            with self.subTest(raw=raw):
                flow, co = self.flow({"param_24": raw})
                co.async_write_parameters = AsyncMock()
                form = await flow.async_step_plant_form()
                self.assertEqual(next(iter(form["data_schema"].schema)).schema, "ewt")
                group = form["data_schema"].schema["ewt"].schema.schema
                checkbox = next(marker for marker in group if marker.schema == "ewt")
                self.assertEqual(checkbox.default(), raw == 4)
                self.assertEqual(group[checkbox].selector_type, "boolean")
                await flow.async_step_plant_form({"ewt": {"ewt": wanted}})
                co.async_write_parameters.assert_awaited_once_with({0x24: expected})

    async def test_sections_follow_new_unit_readings_without_writing(self):
        flow, co = self.flow({"param_47": 55})
        co.async_write_parameters = AsyncMock()
        flow._config_entry.options["p47"] = "9.9"

        async def displayed_temperature():
            fields = (await flow.async_step_plant_form())["data_schema"].schema
            frost = next(key for key in fields if key.schema == "frost_protection")
            return frost.default()["p47"]

        self.assertEqual(await displayed_temperature(), "5.5")
        co._async_publish({"param_47": 60})
        self.assertEqual(await displayed_temperature(), "6.0")
        co.async_write_parameters.assert_not_awaited()
        co._async_send.assert_not_awaited()


class ReadOnlyProfileTest(unittest.IsolatedAsyncioTestCase):
    async def test_real_reader_records_and_exports_existing_connection_without_writes(self):
        co = coordinator()
        co._config.update({
            "hardware_profile": "xor", "serial_port": "socket://test:502",
            "baudrate": 9600, "parity": "none",
        })
        co._parser = NovusXorParser()
        co.raw_log = deque(maxlen=3000)
        co.passive_recording = PassiveRecording()
        co.start_passive_recording()
        co.hass = SimpleNamespace(loop=Mock())
        stream = bytes.fromhex("020001fd000a0000315920002311260301aa")
        chunks = iter(bytes((byte,)) for byte in stream)
        serial_port = MagicMock(port="socket://test:502", in_waiting=1)
        serial_port.__enter__.return_value = serial_port

        def read(_):
            value = next(chunks, b"")
            if not value:
                co._stop_event.set()
            return value

        serial_port.read.side_effect = read
        with patch(
            "custom_components.novus300bus.coordinator.serial.serial_for_url",
            return_value=serial_port,
        ) as connect:
            co._read_serial()
        connect.assert_called_once_with("socket://test:502", timeout=1)
        serial_port.write.assert_not_called()
        result = await async_get_config_entry_diagnostics(
            Mock(), SimpleNamespace(data={}, options={}, runtime_data=co)
        )
        self.assertTrue(result["read_only"])
        self.assertEqual(result["protocol"]["valid_frames"], 2)
        captured = bytes.fromhex("".join(
            chunk["hex"] for chunk in result["passive_recording"]["chunks"]
        ))
        self.assertEqual(captured, stream)
        self.assertEqual(result["passive_recording"]["received_bytes"], len(stream))
        json.dumps(result)

    async def test_every_bus_write_path_fails_before_transmission_or_mutation(self):
        co = coordinator({"param_1b": 0x7B, "fan_level_1_percentage": 20, "orig_fan_level_1_percentage": 17})
        co._config["hardware_profile"] = "xor"
        co._serial = Mock(port="socket://test:502")
        co.hass = SimpleNamespace(async_add_executor_job=AsyncMock())
        before = dict(co._values)
        operations = (
            lambda: co.async_set_ventilation_mode("level_1"),
            lambda: co.async_set_power(True),
            lambda: co.async_write_settings({"fan_level_1_percentage": 40}),
            lambda: co.async_write_parameters({0x1B: 0x7F}),
            lambda: co._async_write_parameters({0x1B: 0x7F}),
            lambda: co.async_set_summer_ventilation(True),
            lambda: co.async_set_filter_interval(90),
            co.async_reset_filter, co.async_request_dump, co.async_sync_clock,
            lambda: co.async_set_temporary_setting("fan_level_2_percentage", 42),
            co.async_restore_settings,
            lambda: NovusCoordinator._async_send(co, b"blocked"),
        )
        for operation in operations:
            with self.subTest(operation=operation):
                with self.assertRaisesRegex(HomeAssistantError, "read-only"):
                    await operation()
                self.assertEqual(co._values, before)
        with self.assertRaisesRegex(HomeAssistantError, "read-only"):
            co._send_frame(b"blocked")
        co._serial.write.assert_not_called()
        co._async_send.assert_not_awaited()
        co.hass.async_add_executor_job.assert_not_awaited()

    async def test_xor_start_does_not_restore_crc_values_or_schedule_clock_writes(self):
        with TemporaryDirectory(prefix="novus-xor-test-") as directory:
            hass = HomeAssistant(directory)
            with patch("homeassistant.helpers.frame.report_usage"):
                co = NovusCoordinator(hass, {
                    "hardware_profile": "xor", "serial_port": "socket://test:502",
                    "daily_time_sync": True, "fan_enabled": True,
                }, "test")
            co._async_restore_counters = AsyncMock()
            with patch("custom_components.novus300bus.coordinator.threading.Thread") as thread:
                with patch("custom_components.novus300bus.coordinator.async_track_time_change") as schedule:
                    await co.async_start()
            co._async_restore_counters.assert_not_awaited()
            schedule.assert_not_called()
            thread.return_value.start.assert_called_once()
            self.assertEqual(co._values, {})
            self.assertIsInstance(co._parser, NovusXorParser)
            self.assertEqual(co._counter_store.key, "novus300bus.test.counters.xor")
            self.assertIsNone(co.device_info["sw_version"])
            self.assertNotIn("fan", _platforms(co))
            self.assertNotIn("select", _platforms(co))
            self.assertNotIn("switch", _platforms(co))
            added = Mock()
            await setup_buttons(hass, SimpleNamespace(data={}, options={}, runtime_data=co), added)
            buttons = added.call_args.args[0]
            self.assertEqual([button.translation_key for button in buttons], ["passive_recording"])
            with patch.object(co, "_send_frame") as send:
                await buttons[0].async_press()
            send.assert_not_called()
            self.assertEqual(co.passive_recording.snapshot()["status"], "recording")

    async def test_existing_entries_remain_crc16_and_xor_blocks_external_fan_output(self):
        co = coordinator()
        self.assertFalse(co.read_only)
        co.ensure_writable()
        self.assertIn("fan", _platforms(co))
        co._config["hardware_profile"] = "xor"
        fan = NovusFanEntity(co, {
            "tinkerforge_host": "test", "tinkerforge_port": 4223, "tinkerforge_uid": "test",
        })
        fan._connect = Mock()
        with self.assertRaisesRegex(HomeAssistantError, "read-only"):
            fan._set_percentage(50)
        with self.assertRaisesRegex(HomeAssistantError, "read-only"):
            await fan.async_set_percentage(50)
        with self.assertRaisesRegex(HomeAssistantError, "read-only"):
            await fan.async_set_preset_mode("Automatik")
        fan._connect.assert_not_called()

    async def test_xor_removes_fallback_component_metadata(self):
        co = coordinator()
        co._config["hardware_profile"] = "xor"
        registry = Mock()
        registry.async_get_device.side_effect = [
            SimpleNamespace(id="panel", config_entries={"test"}),
            SimpleNamespace(id="fan", config_entries={"test"}),
            SimpleNamespace(id="defroster", config_entries={"test"}),
            SimpleNamespace(id="unit"),
        ]
        with patch("custom_components.novus300bus.dr.async_get", return_value=registry):
            _register_sub_devices(Mock(), SimpleNamespace(entry_id="test", runtime_data=co))
        self.assertEqual(registry.async_update_device.call_count, 4)
        registry.async_update_device.assert_any_call(
            "unit", model="Novus 300 (XOR, experimental)", sw_version=None
        )
