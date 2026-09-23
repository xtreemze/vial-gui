import json
import os
import unittest

from protocol.halcyon_display import DisplayLayer, DisplayPattern, HalcyonDisplayProtocol
from protocol.halcyon_settings import HalcyonSettingsProtocol
from protocol.rgb_profiles import RGBProfilesProtocol
from util import MSG_LEN


FIXTURE_PATH = os.path.join(
    os.path.dirname(__file__),
    "fixtures",
    "configurator-protocol-v1-vectors.json",
)


class GoldenVectorKeyboard:
    def __init__(self, vector):
        self.dev = object()
        self.vector = vector
        self.used = False

    def usb_send(self, dev, request, retries=1):
        if dev is not self.dev:
            raise AssertionError("wrong device passed to transport")
        if self.used:
            raise AssertionError("golden vector was consumed more than once")

        expected = bytes(self.vector["request"])
        if request != expected:
            raise AssertionError(
                "{} expected {}, got {}".format(
                    self.vector["name"],
                    expected.hex(),
                    request.hex(),
                )
            )

        self.used = True
        response = bytes(self.vector["response"])
        return response + b"\x00" * (MSG_LEN - len(response))


def load_vectors():
    with open(FIXTURE_PATH, "r") as handle:
        document = json.load(handle)
    if document["schema_version"] != 1:
        raise AssertionError("unsupported configurator golden-vector schema")
    return {vector["name"]: vector for vector in document["vectors"]}


class TestConfiguratorProtocolGoldenVectors(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.vectors = load_vectors()

    def keyboard(self, name):
        return GoldenVectorKeyboard(self.vectors[name])

    def test_rgb_profile_capabilities_follow_firmware_vector(self):
        keyboard = self.keyboard("rgb_profiles_get_capabilities")
        capabilities = RGBProfilesProtocol.probe(keyboard)

        self.assertTrue(keyboard.used)
        self.assertIsNotNone(capabilities)
        self.assertEqual(capabilities.layer_count, 13)
        self.assertEqual(capabilities.modifier_count, 4)
        self.assertEqual(capabilities.combo_count, 32)
        self.assertEqual(capabilities.maximum_brightness, 255)
        self.assertEqual(capabilities.maximum_mode, 44)

    def test_halcyon_settings_capabilities_cover_both_targets(self):
        display_keyboard = self.keyboard(
            "halcyon_settings_get_capabilities_display_target"
        )
        display_capabilities = HalcyonSettingsProtocol.probe(display_keyboard)
        self.assertTrue(display_keyboard.used)
        self.assertIsNotNone(display_capabilities)
        self.assertTrue(display_capabilities.tft_present)

        encoder_keyboard = self.keyboard(
            "halcyon_settings_get_capabilities_encoder_target"
        )
        encoder_capabilities = HalcyonSettingsProtocol.probe(encoder_keyboard)
        self.assertTrue(encoder_keyboard.used)
        self.assertIsNotNone(encoder_capabilities)
        self.assertFalse(encoder_capabilities.tft_present)

    def test_halcyon_display_capabilities_follow_firmware_vector(self):
        keyboard = self.keyboard("halcyon_display_get_capabilities")
        capabilities = HalcyonDisplayProtocol.probe(keyboard)

        self.assertTrue(keyboard.used)
        self.assertIsNotNone(capabilities)
        self.assertEqual(capabilities.layer_count, 13)
        self.assertEqual(capabilities.modifier_count, 10)
        self.assertEqual(capabilities.motif_count, 13)
        self.assertEqual(capabilities.layer_label_max, 8)

    def test_halcyon_display_qwerty_write_matches_firmware_vector(self):
        keyboard = self.keyboard("halcyon_display_set_layer_qwerty")
        layer = DisplayLayer("QWERTY", DisplayPattern(1, 24, 24, 1, 1))

        HalcyonDisplayProtocol.set_layer(keyboard, 1, layer)

        self.assertTrue(keyboard.used)

    def test_halcyon_timing_write_is_big_endian_per_firmware_vector(self):
        keyboard = self.keyboard("halcyon_settings_set_timings")

        HalcyonSettingsProtocol.set_timings(keyboard, 200, 2200)

        self.assertTrue(keyboard.used)


if __name__ == "__main__":
    unittest.main()
