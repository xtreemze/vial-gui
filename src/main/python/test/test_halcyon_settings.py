import unittest

from protocol.halcyon_settings import (
    HALCYON_CAP_LAYER_COLORS,
    HALCYON_CAP_MOD_COLORS,
    HALCYON_CAP_SPLIT_REPLICATION,
    HALCYON_CAP_TELEMETRY,
    HALCYON_CAP_TIMINGS,
    HALCYON_OP_GET_CAPABILITIES,
    HALCYON_OP_GET_DIM_STYLE,
    HALCYON_OP_GET_LAYER_STYLE,
    HALCYON_OP_GET_MOD_STYLE,
    HALCYON_OP_GET_TELEMETRY,
    HALCYON_OP_GET_TIMINGS,
    HALCYON_OP_RESET,
    HALCYON_OP_SAVE,
    HALCYON_OP_SET_DIM_STYLE,
    HALCYON_OP_SET_LAYER_STYLE,
    HALCYON_OP_SET_MOD_STYLE,
    HALCYON_OP_SET_TIMINGS,
    HALCYON_SETTINGS_COMMAND,
    HSV,
    HalcyonSettingsProtocol,
)
from util import MSG_LEN


class SimulatedKeyboard:
    def __init__(self):
        self.dev = object()
        self.expected = []

    def expect(self, request, response):
        self.expected.append((bytes(request), bytes(response) + b"\x00" * (MSG_LEN - len(response))))

    def usb_send(self, dev, request, retries=1):
        if dev is not self.dev:
            raise AssertionError("wrong device passed to transport")
        if not self.expected:
            raise AssertionError("unexpected Halcyon settings request: {}".format(request.hex()))
        expected_request, response = self.expected.pop(0)
        if request != expected_request:
            raise AssertionError(
                "expected {}, got {}".format(expected_request.hex(), request.hex())
            )
        return response

    def finish(self):
        if self.expected:
            raise AssertionError("unconsumed requests: {}".format(self.expected))


class TestHalcyonSettingsProtocol(unittest.TestCase):
    def test_probe_capabilities(self):
        keyboard = SimulatedKeyboard()
        flags = (
            HALCYON_CAP_LAYER_COLORS
            | HALCYON_CAP_MOD_COLORS
            | HALCYON_CAP_TIMINGS
            | HALCYON_CAP_TELEMETRY
            | HALCYON_CAP_SPLIT_REPLICATION
        )
        keyboard.expect(
            [HALCYON_SETTINGS_COMMAND, HALCYON_OP_GET_CAPABILITIES],
            [HALCYON_SETTINGS_COMMAND, HALCYON_OP_GET_CAPABILITIES, 1, flags, 13, 10, 1, 5, 100, 100, 1, 1],
        )

        capabilities = HalcyonSettingsProtocol.probe(keyboard)

        self.assertIsNotNone(capabilities)
        self.assertEqual(capabilities.layer_count, 13)
        self.assertEqual(capabilities.modifier_count, 10)
        self.assertEqual(capabilities.pattern_min_ms, 50)
        self.assertEqual(capabilities.pattern_max_ms, 1000)
        self.assertEqual(capabilities.modifier_recent_max_ms, 10000)
        self.assertTrue(capabilities.tft_present)
        self.assertTrue(capabilities.deterministic_repeat)
        self.assertTrue(capabilities.supports(HALCYON_CAP_SPLIT_REPLICATION))
        keyboard.finish()

    def test_probe_rejects_unsupported_version(self):
        keyboard = SimulatedKeyboard()
        keyboard.expect(
            [HALCYON_SETTINGS_COMMAND, HALCYON_OP_GET_CAPABILITIES],
            [HALCYON_SETTINGS_COMMAND, HALCYON_OP_GET_CAPABILITIES, 2, 0x1F, 13, 10, 1, 5, 100, 100, 1, 1],
        )
        self.assertIsNone(HalcyonSettingsProtocol.probe(keyboard))
        keyboard.finish()

    def test_layer_style_round_trip(self):
        keyboard = SimulatedKeyboard()
        keyboard.expect(
            [HALCYON_SETTINGS_COMMAND, HALCYON_OP_GET_LAYER_STYLE, 3],
            [HALCYON_SETTINGS_COMMAND, HALCYON_OP_GET_LAYER_STYLE, 3, 11, 22, 33, 44, 55, 66],
        )
        style = HalcyonSettingsProtocol.get_layer_style(keyboard, 3)
        self.assertEqual(
            (style.foreground.hue, style.foreground.saturation, style.foreground.value),
            (11, 22, 33),
        )
        self.assertEqual(
            (style.background.hue, style.background.saturation, style.background.value),
            (44, 55, 66),
        )

        keyboard.expect(
            [HALCYON_SETTINGS_COMMAND, HALCYON_OP_SET_LAYER_STYLE, 3, 11, 22, 33, 44, 55, 66],
            [HALCYON_SETTINGS_COMMAND, HALCYON_OP_SET_LAYER_STYLE],
        )
        HalcyonSettingsProtocol.set_layer_style(keyboard, 3, style)
        keyboard.finish()

    def test_modifier_dim_and_timing_commands(self):
        keyboard = SimulatedKeyboard()
        keyboard.expect(
            [HALCYON_SETTINGS_COMMAND, HALCYON_OP_GET_MOD_STYLE, 4],
            [HALCYON_SETTINGS_COMMAND, HALCYON_OP_GET_MOD_STYLE, 4, 90, 80, 70],
        )
        modifier = HalcyonSettingsProtocol.get_modifier_style(keyboard, 4)
        self.assertEqual((modifier.hue, modifier.saturation, modifier.value), (90, 80, 70))

        keyboard.expect(
            [HALCYON_SETTINGS_COMMAND, HALCYON_OP_SET_MOD_STYLE, 4, 90, 80, 70],
            [HALCYON_SETTINGS_COMMAND, HALCYON_OP_SET_MOD_STYLE],
        )
        HalcyonSettingsProtocol.set_modifier_style(keyboard, 4, modifier)

        keyboard.expect(
            [HALCYON_SETTINGS_COMMAND, HALCYON_OP_GET_DIM_STYLE],
            [HALCYON_SETTINGS_COMMAND, HALCYON_OP_GET_DIM_STYLE, 98, 23, 146],
        )
        dim = HalcyonSettingsProtocol.get_dim_style(keyboard)
        self.assertEqual((dim.hue, dim.saturation, dim.value), (98, 23, 146))

        keyboard.expect(
            [HALCYON_SETTINGS_COMMAND, HALCYON_OP_SET_DIM_STYLE, 98, 23, 146],
            [HALCYON_SETTINGS_COMMAND, HALCYON_OP_SET_DIM_STYLE],
        )
        HalcyonSettingsProtocol.set_dim_style(keyboard, dim)

        keyboard.expect(
            [HALCYON_SETTINGS_COMMAND, HALCYON_OP_GET_TIMINGS],
            [HALCYON_SETTINGS_COMMAND, HALCYON_OP_GET_TIMINGS, 0x00, 0xC8, 0x08, 0x98],
        )
        self.assertEqual(HalcyonSettingsProtocol.get_timings(keyboard), (200, 2200))

        keyboard.expect(
            [HALCYON_SETTINGS_COMMAND, HALCYON_OP_SET_TIMINGS, 0x00, 0xFA, 0x09, 0xC4],
            [HALCYON_SETTINGS_COMMAND, HALCYON_OP_SET_TIMINGS],
        )
        HalcyonSettingsProtocol.set_timings(keyboard, 250, 2500)
        keyboard.finish()

    def test_telemetry_save_and_reset(self):
        keyboard = SimulatedKeyboard()
        keyboard.expect(
            [HALCYON_SETTINGS_COMMAND, HALCYON_OP_GET_TELEMETRY],
            [HALCYON_SETTINGS_COMMAND, HALCYON_OP_GET_TELEMETRY, 1, 1, 2, 2, 1, 1, 1],
        )
        telemetry = HalcyonSettingsProtocol.get_telemetry(keyboard)
        self.assertEqual(telemetry.os, 1)
        self.assertEqual(telemetry.shortcut_family, 1)
        self.assertEqual(telemetry.source, 2)
        self.assertEqual(telemetry.event, 2)
        self.assertTrue(telemetry.is_master)
        self.assertTrue(telemetry.tft_present)
        self.assertTrue(telemetry.transport_connected)

        keyboard.expect(
            [HALCYON_SETTINGS_COMMAND, HALCYON_OP_SAVE],
            [HALCYON_SETTINGS_COMMAND, HALCYON_OP_SAVE],
        )
        HalcyonSettingsProtocol.save(keyboard)

        keyboard.expect(
            [HALCYON_SETTINGS_COMMAND, HALCYON_OP_RESET],
            [HALCYON_SETTINGS_COMMAND, HALCYON_OP_RESET],
        )
        HalcyonSettingsProtocol.reset(keyboard)
        keyboard.finish()

    def test_value_validation(self):
        with self.assertRaises(ValueError):
            HSV(256, 0, 0)
        with self.assertRaises(ValueError):
            HalcyonSettingsProtocol.set_timings(SimulatedKeyboard(), 70000, 1000)


if __name__ == "__main__":
    unittest.main()
