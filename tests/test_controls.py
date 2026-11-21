"""Bus-free tests for summer ventilation, options and entity gating."""

import asyncio
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
import voluptuous as vol

from custom_components.novus300bus import _sync_bypass_entity
from custom_components.novus300bus.config_flow import NovusConfigFlow, NovusOptionsFlow
from custom_components.novus300bus.coordinator import NovusCoordinator
from custom_components.novus300bus.fan import NovusBusFanEntity
from custom_components.novus300bus.protocol import NovusFrameParser, build_setting_frame
from custom_components.novus300bus.switch import NovusSummerVentilationSwitch


def coordinator(values=None):
    instance = object.__new__(NovusCoordinator)
    instance._values = dict(values or {})
    instance.data = dict(instance._values)
    instance._config = {}
    instance._parameter_write_lock = asyncio.Lock()
    instance._plant_word_received = asyncio.Event()
    instance._counter_store = Mock()
    instance._async_send = AsyncMock()
    instance.last_update_success = True
    instance.async_set_updated_data = Mock(
        side_effect=lambda data: setattr(instance, "data", data)
    )
    return instance


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
            [field.schema for field in flow._general_schema().schema][1],
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
            names[2:5], ["automatic", "show_fan_levels", "fan_level_1"]
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
