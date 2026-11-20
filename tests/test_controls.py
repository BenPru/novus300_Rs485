"""Bus-free tests for summer ventilation, options and entity gating."""

import asyncio
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
import voluptuous as vol

from custom_components.novus300bus import _sync_bypass_entity
from custom_components.novus300bus.config_flow import NovusOptionsFlow
from custom_components.novus300bus.coordinator import NovusCoordinator
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

    async def test_no_bypass_or_unknown_configuration_cannot_write(self):
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

    async def test_loss_of_bypass_during_confirmation_is_an_error(self):
        co = coordinator({"param_1b": 0x7B})
        co._async_send.side_effect = lambda _: co._async_publish({"param_1b": 0x7F})
        with self.assertRaisesRegex(HomeAssistantError, "no longer reports a bypass"):
            await co.async_set_summer_ventilation(True)

    async def test_invalid_imbalance_is_rejected_before_any_write(self):
        co = coordinator()
        with self.assertRaises(HomeAssistantError):
            await co.async_write_settings(
                {"fan_level_1_percentage": 20, "fan_level_2_imbalance": -51}
            )
        co._async_send.assert_not_awaited()


class EntityGatingTest(unittest.TestCase):
    def test_gates_both_switches_without_overriding_user_disable(self):
        for present, disabled, expected in (
            (True, er.RegistryEntryDisabler.INTEGRATION, None),
            (False, None, er.RegistryEntryDisabler.INTEGRATION),
            (True, er.RegistryEntryDisabler.USER, "unchanged"),
            (None, None, "unchanged"),
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
                if expected == "unchanged":
                    registry.async_update_entity.assert_not_called()
                else:
                    self.assertEqual(registry.async_update_entity.call_count, 2)
                    self.assertTrue(
                        all(c.kwargs == {"disabled_by": expected} for c in registry.async_update_entity.call_args_list)
                    )


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
        fields = {marker.schema: marker for marker in schema.schema}
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
        self.assertEqual(result["errors"], {"fan_level_1_imbalance": "invalid_imbalance"})
        co.async_write_settings.assert_not_awaited()
        result = await flow.async_step_bypass_form()
        self.assertNotIn("summer", {marker.schema for marker in result["data_schema"].schema})

    async def test_unknown_installation_cannot_be_guessed(self):
        flow, co = self.flow()
        co.async_write_parameters = AsyncMock()
        result = await flow.async_step_bypass_form({"bypass": False})
        self.assertEqual(result["errors"], {"base": "configuration_unknown"})
        co.async_write_parameters.assert_not_awaited()
