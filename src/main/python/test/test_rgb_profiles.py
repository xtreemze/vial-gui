import unittest

from protocol.rgb_profiles import (
    RGB_PROFILE_COMMAND,
    RGB_PROFILE_OP_CANCEL_PREVIEW,
    RGB_PROFILE_OP_GET_CAPABILITIES,
    RGB_PROFILE_OP_GET_COMBO_DURATION,
    RGB_PROFILE_OP_GET_PROFILE,
    RGB_PROFILE_OP_PREVIEW,
    RGB_PROFILE_OP_SAVE,
    RGB_PROFILE_OP_SET_COMBO_DURATION,
    RGB_PROFILE_OP_SET_PROFILE,
    RGB_PROFILE_SCOPE_COMBO,
    RGB_PROFILE_SCOPE_GLOBAL,
    RGB_PROFILE_SCOPE_LAYER,
    RGB_PROFILE_UNASSIGNED,
    RGBProfile,
    RGBProfilesProtocol,
)
from util import MSG_LEN


class SimulatedKeyboard:
    def __init__(self):
        self.dev = object()
        self.expected = []

    def expect(self, request, response):
        self.expected.append((bytes(request), bytes(response) + b"\x00" * (MSG_LEN - len(response))))

    def usb_send(self, dev, request, retries=1):
        self.assert_device(dev)
        if not self.expected:
            raise AssertionError("unexpected RGB profile request: {}".format(request.hex()))
        expected_request, response = self.expected.pop(0)
        if request != expected_request:
            raise AssertionError(
                "expected {}, got {}".format(expected_request.hex(), request.hex())
            )
        return response

    def assert_device(self, dev):
        if dev is not self.dev:
            raise AssertionError("wrong device passed to transport")

    def finish(self):
        if self.expected:
            raise AssertionError("unconsumed requests: {}".format(self.expected))


class TestRGBProfilesProtocol(unittest.TestCase):
    def test_probe_capabilities(self):
        keyboard = SimulatedKeyboard()
        keyboard.expect(
            [RGB_PROFILE_COMMAND, RGB_PROFILE_OP_GET_CAPABILITIES],
            [RGB_PROFILE_COMMAND, RGB_PROFILE_OP_GET_CAPABILITIES, 1, 0x0F, 13, 4, 32, 180, 44, 0x1F, 1],
        )

        capabilities = RGBProfilesProtocol.probe(keyboard)

        self.assertIsNotNone(capabilities)
        self.assertEqual(capabilities.layer_count, 13)
        self.assertEqual(capabilities.modifier_count, 4)
        self.assertEqual(capabilities.combo_count, 32)
        self.assertEqual(capabilities.maximum_brightness, 180)
        self.assertEqual(capabilities.maximum_mode, 44)
        self.assertTrue(capabilities.supports_scope(RGB_PROFILE_SCOPE_GLOBAL))
        self.assertTrue(capabilities.supports_scope(RGB_PROFILE_SCOPE_LAYER))
        self.assertEqual(capabilities.count_for_scope(RGB_PROFILE_SCOPE_COMBO), 32)
        keyboard.finish()

    def test_probe_rejects_unsupported_protocol(self):
        keyboard = SimulatedKeyboard()
        keyboard.expect(
            [RGB_PROFILE_COMMAND, RGB_PROFILE_OP_GET_CAPABILITIES],
            [RGB_PROFILE_COMMAND, RGB_PROFILE_OP_GET_CAPABILITIES, 2, 0x0F, 13, 4, 32, 180, 44, 0x1F, 1],
        )
        self.assertIsNone(RGBProfilesProtocol.probe(keyboard))
        keyboard.finish()

    def test_profile_round_trip_commands(self):
        keyboard = SimulatedKeyboard()
        keyboard.expect(
            [RGB_PROFILE_COMMAND, RGB_PROFILE_OP_GET_PROFILE, RGB_PROFILE_SCOPE_LAYER, 3],
            [RGB_PROFILE_COMMAND, RGB_PROFILE_OP_GET_PROFILE, RGB_PROFILE_SCOPE_LAYER, 3, 7, 11, 22, 123, 99],
        )
        profile = RGBProfilesProtocol.get_profile(keyboard, RGB_PROFILE_SCOPE_LAYER, 3)
        self.assertEqual((profile.mode, profile.hue, profile.saturation, profile.brightness, profile.speed),
                         (7, 11, 22, 123, 99))

        keyboard.expect(
            [RGB_PROFILE_COMMAND, RGB_PROFILE_OP_SET_PROFILE, RGB_PROFILE_SCOPE_LAYER, 3, 7, 11, 22, 123, 99],
            [RGB_PROFILE_COMMAND, RGB_PROFILE_OP_SET_PROFILE],
        )
        RGBProfilesProtocol.set_profile(keyboard, RGB_PROFILE_SCOPE_LAYER, 3, profile)

        keyboard.expect(
            [RGB_PROFILE_COMMAND, RGB_PROFILE_OP_PREVIEW, 7, 11, 22, 123, 99],
            [RGB_PROFILE_COMMAND, RGB_PROFILE_OP_PREVIEW],
        )
        RGBProfilesProtocol.preview(keyboard, profile)

        keyboard.expect(
            [RGB_PROFILE_COMMAND, RGB_PROFILE_OP_SAVE],
            [RGB_PROFILE_COMMAND, RGB_PROFILE_OP_SAVE],
        )
        RGBProfilesProtocol.save(keyboard)

        keyboard.expect(
            [RGB_PROFILE_COMMAND, RGB_PROFILE_OP_CANCEL_PREVIEW],
            [RGB_PROFILE_COMMAND, RGB_PROFILE_OP_CANCEL_PREVIEW],
        )
        RGBProfilesProtocol.cancel_preview(keyboard)
        keyboard.finish()

    def test_clear_and_combo_duration(self):
        keyboard = SimulatedKeyboard()
        keyboard.expect(
            [RGB_PROFILE_COMMAND, RGB_PROFILE_OP_SET_PROFILE, RGB_PROFILE_SCOPE_COMBO, 5,
             RGB_PROFILE_UNASSIGNED, 0, 0, 0, 0],
            [RGB_PROFILE_COMMAND, RGB_PROFILE_OP_SET_PROFILE],
        )
        RGBProfilesProtocol.clear_profile(keyboard, RGB_PROFILE_SCOPE_COMBO, 5)

        keyboard.expect(
            [RGB_PROFILE_COMMAND, RGB_PROFILE_OP_GET_COMBO_DURATION],
            [RGB_PROFILE_COMMAND, RGB_PROFILE_OP_GET_COMBO_DURATION, 0x07, 0xD0],
        )
        self.assertEqual(RGBProfilesProtocol.get_combo_duration(keyboard), 2000)

        keyboard.expect(
            [RGB_PROFILE_COMMAND, RGB_PROFILE_OP_SET_COMBO_DURATION, 0x09, 0xC4],
            [RGB_PROFILE_COMMAND, RGB_PROFILE_OP_SET_COMBO_DURATION],
        )
        RGBProfilesProtocol.set_combo_duration(keyboard, 2500)
        keyboard.finish()

    def test_global_profile_cannot_be_cleared(self):
        keyboard = SimulatedKeyboard()
        with self.assertRaises(ValueError):
            RGBProfilesProtocol.clear_profile(keyboard, RGB_PROFILE_SCOPE_GLOBAL, 0)
        keyboard.finish()

    def test_profile_rejects_out_of_range_fields(self):
        with self.assertRaises(ValueError):
            RGBProfile(1, 0, 0, 256, 0)


if __name__ == "__main__":
    unittest.main()
