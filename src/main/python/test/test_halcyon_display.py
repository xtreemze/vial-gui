import unittest

from protocol.halcyon_display import (
    HALCYON_DISPLAY_CAP_LAYER_LABELS,
    HALCYON_DISPLAY_CAP_MODIFIER_LABELS,
    HALCYON_DISPLAY_CAP_PATTERNS,
    HALCYON_DISPLAY_CAP_SPLIT_REPLICATION,
    HALCYON_DISPLAY_COMMAND,
    HALCYON_DISPLAY_OP_GET_CAPABILITIES,
    HALCYON_DISPLAY_OP_GET_LAYER,
    HALCYON_DISPLAY_OP_GET_MODIFIER_LABEL,
    HALCYON_DISPLAY_OP_RESET,
    HALCYON_DISPLAY_OP_SAVE,
    HALCYON_DISPLAY_OP_SET_LAYER,
    HALCYON_DISPLAY_OP_SET_MODIFIER_LABEL,
    DisplayLayer,
    DisplayPattern,
    HalcyonDisplayProtocol,
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
            raise AssertionError("unexpected display request: {}".format(request.hex()))
        expected_request, response = self.expected.pop(0)
        if request != expected_request:
            raise AssertionError("expected {}, got {}".format(expected_request.hex(), request.hex()))
        return response

    def finish(self):
        if self.expected:
            raise AssertionError("unconsumed requests: {}".format(self.expected))


class TestHalcyonDisplayProtocol(unittest.TestCase):
    def test_probe_capabilities(self):
        keyboard = SimulatedKeyboard()
        flags = (
            HALCYON_DISPLAY_CAP_LAYER_LABELS
            | HALCYON_DISPLAY_CAP_MODIFIER_LABELS
            | HALCYON_DISPLAY_CAP_PATTERNS
            | HALCYON_DISPLAY_CAP_SPLIT_REPLICATION
        )
        keyboard.expect(
            [HALCYON_DISPLAY_COMMAND, HALCYON_DISPLAY_OP_GET_CAPABILITIES],
            [HALCYON_DISPLAY_COMMAND, HALCYON_DISPLAY_OP_GET_CAPABILITIES, 1, flags, 13, 10, 13, 8, 4, 12, 48, 6, 4, 1],
        )
        capabilities = HalcyonDisplayProtocol.probe(keyboard)
        self.assertIsNotNone(capabilities)
        self.assertEqual(capabilities.layer_count, 13)
        self.assertEqual(capabilities.modifier_count, 10)
        self.assertEqual(capabilities.motif_count, 13)
        self.assertEqual(capabilities.layer_label_max, 8)
        self.assertEqual(capabilities.modifier_label_max, 4)
        self.assertEqual((capabilities.tile_min, capabilities.tile_max), (12, 48))
        self.assertEqual(capabilities.motion_max, 6)
        self.assertEqual(capabilities.pulse_max, 4)
        keyboard.finish()

    def test_layer_round_trip(self):
        keyboard = SimulatedKeyboard()
        label = b"NUMSYMS\0\0"
        keyboard.expect(
            [HALCYON_DISPLAY_COMMAND, HALCYON_DISPLAY_OP_GET_LAYER, 3],
            [HALCYON_DISPLAY_COMMAND, HALCYON_DISPLAY_OP_GET_LAYER, 3] + list(label) + [9, 30, 24, 2, 3],
        )
        layer = HalcyonDisplayProtocol.get_layer(keyboard, 3)
        self.assertEqual(layer.label, "NUMSYMS")
        self.assertEqual(
            (layer.pattern.motif, layer.pattern.tile_width, layer.pattern.tile_height,
             layer.pattern.motion_amplitude, layer.pattern.pulse_amplitude),
            (9, 30, 24, 2, 3),
        )

        keyboard.expect(
            [HALCYON_DISPLAY_COMMAND, HALCYON_DISPLAY_OP_SET_LAYER, 3]
            + list(label)
            + [9, 30, 24, 2, 3],
            [HALCYON_DISPLAY_COMMAND, HALCYON_DISPLAY_OP_SET_LAYER],
        )
        HalcyonDisplayProtocol.set_layer(keyboard, 3, layer)
        keyboard.finish()

    def test_modifier_labels_save_and_reset(self):
        keyboard = SimulatedKeyboard()
        keyboard.expect(
            [HALCYON_DISPLAY_COMMAND, HALCYON_DISPLAY_OP_GET_MODIFIER_LABEL, 1],
            [HALCYON_DISPLAY_COMMAND, HALCYON_DISPLAY_OP_GET_MODIFIER_LABEL, 1] + list(b"Gui\0\0"),
        )
        self.assertEqual(HalcyonDisplayProtocol.get_modifier_label(keyboard, 1), "Gui")

        keyboard.expect(
            [HALCYON_DISPLAY_COMMAND, HALCYON_DISPLAY_OP_SET_MODIFIER_LABEL, 1] + list(b"Cmd\0\0"),
            [HALCYON_DISPLAY_COMMAND, HALCYON_DISPLAY_OP_SET_MODIFIER_LABEL],
        )
        HalcyonDisplayProtocol.set_modifier_label(keyboard, 1, "Cmd")

        keyboard.expect(
            [HALCYON_DISPLAY_COMMAND, HALCYON_DISPLAY_OP_SAVE],
            [HALCYON_DISPLAY_COMMAND, HALCYON_DISPLAY_OP_SAVE],
        )
        HalcyonDisplayProtocol.save(keyboard)
        keyboard.expect(
            [HALCYON_DISPLAY_COMMAND, HALCYON_DISPLAY_OP_RESET],
            [HALCYON_DISPLAY_COMMAND, HALCYON_DISPLAY_OP_RESET],
        )
        HalcyonDisplayProtocol.reset(keyboard)
        keyboard.finish()

    def test_label_and_pattern_validation(self):
        keyboard = SimulatedKeyboard()
        with self.assertRaises(ValueError):
            HalcyonDisplayProtocol.set_modifier_label(keyboard, 0, "TOO-LONG")
        with self.assertRaises(ValueError):
            HalcyonDisplayProtocol.set_modifier_label(keyboard, 0, "é")
        with self.assertRaises(ValueError):
            DisplayPattern(256, 24, 24, 1, 1)
        with self.assertRaises(ValueError):
            HalcyonDisplayProtocol.set_layer(
                keyboard,
                0,
                DisplayLayer("TOO-LONG-LABEL", DisplayPattern(0, 24, 24, 1, 1)),
            )


if __name__ == "__main__":
    unittest.main()
