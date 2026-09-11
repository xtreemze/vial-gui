# SPDX-License-Identifier: GPL-2.0-or-later
"""Protocol adapter for host-editable Halcyon TFT labels and procedural patterns."""


HALCYON_DISPLAY_COMMAND = 0xF2
HALCYON_DISPLAY_PROTOCOL_VERSION = 1

HALCYON_DISPLAY_CAP_LAYER_LABELS = 1 << 0
HALCYON_DISPLAY_CAP_MODIFIER_LABELS = 1 << 1
HALCYON_DISPLAY_CAP_PATTERNS = 1 << 2
HALCYON_DISPLAY_CAP_SPLIT_REPLICATION = 1 << 3

HALCYON_DISPLAY_OP_GET_CAPABILITIES = 0x01
HALCYON_DISPLAY_OP_GET_LAYER = 0x02
HALCYON_DISPLAY_OP_SET_LAYER = 0x03
HALCYON_DISPLAY_OP_GET_MODIFIER_LABEL = 0x04
HALCYON_DISPLAY_OP_SET_MODIFIER_LABEL = 0x05
HALCYON_DISPLAY_OP_SAVE = 0x06
HALCYON_DISPLAY_OP_RESET = 0x07


class HalcyonDisplayProtocolError(RuntimeError):
    pass


class DisplayPattern:
    __slots__ = ("motif", "tile_width", "tile_height", "motion_amplitude", "pulse_amplitude")

    def __init__(self, motif, tile_width, tile_height, motion_amplitude, pulse_amplitude):
        self.motif = _byte("motif", motif)
        self.tile_width = _byte("tile width", tile_width)
        self.tile_height = _byte("tile height", tile_height)
        self.motion_amplitude = _byte("motion amplitude", motion_amplitude)
        self.pulse_amplitude = _byte("pulse amplitude", pulse_amplitude)

    def as_bytes(self):
        return bytes((self.motif, self.tile_width, self.tile_height, self.motion_amplitude, self.pulse_amplitude))


class DisplayLayer:
    __slots__ = ("label", "pattern")

    def __init__(self, label, pattern):
        self.label = label
        self.pattern = pattern


class DisplayCapabilities:
    __slots__ = (
        "protocol_version", "flags", "layer_count", "modifier_count", "motif_count",
        "layer_label_max", "modifier_label_max", "tile_min", "tile_max",
        "motion_max", "pulse_max", "store_version",
    )

    def __init__(self, data):
        self.protocol_version = data[2]
        self.flags = data[3]
        self.layer_count = data[4]
        self.modifier_count = data[5]
        self.motif_count = data[6]
        self.layer_label_max = data[7]
        self.modifier_label_max = data[8]
        self.tile_min = data[9]
        self.tile_max = data[10]
        self.motion_max = data[11]
        self.pulse_max = data[12]
        self.store_version = data[13]

    def supports(self, flag):
        return bool(self.flags & flag)


class HalcyonDisplayProtocol:
    @staticmethod
    def _send(keyboard, operation, payload=b""):
        message = bytes((HALCYON_DISPLAY_COMMAND, operation)) + payload
        response = keyboard.usb_send(keyboard.dev, message, retries=2)
        if len(response) < 2 or response[0] != HALCYON_DISPLAY_COMMAND or response[1] != operation:
            raise HalcyonDisplayProtocolError("keyboard did not acknowledge the Halcyon display command")
        return response

    @classmethod
    def probe(cls, keyboard):
        try:
            response = cls._send(keyboard, HALCYON_DISPLAY_OP_GET_CAPABILITIES)
            if len(response) < 14:
                return None
            capabilities = DisplayCapabilities(response)
        except (IndexError, RuntimeError, ValueError):
            return None
        if capabilities.protocol_version != HALCYON_DISPLAY_PROTOCOL_VERSION:
            return None
        if capabilities.layer_count <= 0 or capabilities.modifier_count <= 0 or capabilities.motif_count <= 0:
            return None
        return capabilities

    @classmethod
    def get_layer(cls, keyboard, index, label_max=8):
        response = cls._send(keyboard, HALCYON_DISPLAY_OP_GET_LAYER, bytes((_byte("layer", index),)))
        if len(response) < 17:
            raise HalcyonDisplayProtocolError("short Halcyon display-layer response")
        label = _decode_label(response[3:12], label_max)
        return DisplayLayer(
            label,
            DisplayPattern(response[12], response[13], response[14], response[15], response[16]),
        )

    @classmethod
    def set_layer(cls, keyboard, index, layer, label_max=8):
        payload = bytes((_byte("layer", index),)) + _encode_label(layer.label, label_max, 9) + layer.pattern.as_bytes()
        cls._send(keyboard, HALCYON_DISPLAY_OP_SET_LAYER, payload)

    @classmethod
    def get_modifier_label(cls, keyboard, index, label_max=4):
        response = cls._send(keyboard, HALCYON_DISPLAY_OP_GET_MODIFIER_LABEL, bytes((_byte("modifier", index),)))
        if len(response) < 8:
            raise HalcyonDisplayProtocolError("short Halcyon modifier-label response")
        return _decode_label(response[3:8], label_max)

    @classmethod
    def set_modifier_label(cls, keyboard, index, label, label_max=4):
        payload = bytes((_byte("modifier", index),)) + _encode_label(label, label_max, 5)
        cls._send(keyboard, HALCYON_DISPLAY_OP_SET_MODIFIER_LABEL, payload)

    @classmethod
    def save(cls, keyboard):
        cls._send(keyboard, HALCYON_DISPLAY_OP_SAVE)

    @classmethod
    def reset(cls, keyboard):
        cls._send(keyboard, HALCYON_DISPLAY_OP_RESET)


def _byte(label, value):
    value = int(value)
    if value < 0 or value > 0xFF:
        raise ValueError("{} must be an unsigned byte".format(label))
    return value


def _encode_label(value, maximum, packet_size):
    value = str(value)
    encoded = value.encode("ascii")
    if not encoded:
        raise ValueError("label cannot be empty")
    if len(encoded) > maximum:
        raise ValueError("label cannot exceed {} characters".format(maximum))
    if any(byte < 0x20 or byte > 0x7E for byte in encoded):
        raise ValueError("label must contain printable ASCII characters")
    return encoded + bytes(packet_size - len(encoded))


def _decode_label(raw, maximum):
    raw = bytes(raw)
    raw = raw.split(b"\0", 1)[0][:maximum]
    return raw.decode("ascii", errors="replace")
