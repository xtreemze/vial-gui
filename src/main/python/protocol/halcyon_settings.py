# SPDX-License-Identifier: GPL-2.0-or-later
"""Protocol adapter for xtreemze Halcyon TFT settings and telemetry."""

import struct


HALCYON_SETTINGS_COMMAND = 0xF1
HALCYON_SETTINGS_PROTOCOL_VERSION = 1

HALCYON_CAP_LAYER_COLORS = 1 << 0
HALCYON_CAP_MOD_COLORS = 1 << 1
HALCYON_CAP_TIMINGS = 1 << 2
HALCYON_CAP_TELEMETRY = 1 << 3
HALCYON_CAP_SPLIT_REPLICATION = 1 << 4

HALCYON_OP_GET_CAPABILITIES = 0x01
HALCYON_OP_GET_LAYER_STYLE = 0x02
HALCYON_OP_SET_LAYER_STYLE = 0x03
HALCYON_OP_GET_MOD_STYLE = 0x04
HALCYON_OP_SET_MOD_STYLE = 0x05
HALCYON_OP_GET_TIMINGS = 0x06
HALCYON_OP_SET_TIMINGS = 0x07
HALCYON_OP_GET_DIM_STYLE = 0x08
HALCYON_OP_SET_DIM_STYLE = 0x09
HALCYON_OP_GET_TELEMETRY = 0x0A
HALCYON_OP_SAVE = 0x0B
HALCYON_OP_RESET = 0x0C


class HalcyonSettingsProtocolError(RuntimeError):
    pass


class HSV:
    __slots__ = ("hue", "saturation", "value")

    def __init__(self, hue, saturation, value):
        self.hue = _byte("hue", hue)
        self.saturation = _byte("saturation", saturation)
        self.value = _byte("value", value)

    def as_bytes(self):
        return bytes((self.hue, self.saturation, self.value))

    def copy(self):
        return HSV(self.hue, self.saturation, self.value)


class LayerStyle:
    __slots__ = ("foreground", "background")

    def __init__(self, foreground, background):
        self.foreground = foreground
        self.background = background


class HalcyonCapabilities:
    __slots__ = (
        "protocol_version", "flags", "layer_count", "modifier_count", "store_version",
        "pattern_min_ms", "pattern_max_ms", "modifier_recent_max_ms", "tft_present",
        "deterministic_repeat",
    )

    def __init__(self, data):
        self.protocol_version = data[2]
        self.flags = data[3]
        self.layer_count = data[4]
        self.modifier_count = data[5]
        self.store_version = data[6]
        self.pattern_min_ms = data[7] * 10
        self.pattern_max_ms = data[8] * 10
        self.modifier_recent_max_ms = data[9] * 100
        self.tft_present = bool(data[10])
        self.deterministic_repeat = bool(data[11])

    def supports(self, flag):
        return bool(self.flags & flag)


class HalcyonTelemetry:
    __slots__ = (
        "os", "shortcut_family", "source", "event", "is_master", "tft_present",
        "transport_connected",
    )

    def __init__(self, data):
        self.os = data[2]
        self.shortcut_family = data[3]
        self.source = data[4]
        self.event = data[5]
        self.is_master = bool(data[6])
        self.tft_present = bool(data[7])
        self.transport_connected = bool(data[8])


class HalcyonSettingsProtocol:
    @staticmethod
    def _send(keyboard, operation, payload=b""):
        message = bytes((HALCYON_SETTINGS_COMMAND, operation)) + payload
        response = keyboard.usb_send(keyboard.dev, message, retries=2)
        if len(response) < 2 or response[0] != HALCYON_SETTINGS_COMMAND or response[1] != operation:
            raise HalcyonSettingsProtocolError("keyboard did not acknowledge the Halcyon settings command")
        return response

    @classmethod
    def probe(cls, keyboard):
        try:
            response = cls._send(keyboard, HALCYON_OP_GET_CAPABILITIES)
            if len(response) < 12:
                return None
            capabilities = HalcyonCapabilities(response)
        except (IndexError, RuntimeError, ValueError):
            return None
        if capabilities.protocol_version != HALCYON_SETTINGS_PROTOCOL_VERSION:
            return None
        if capabilities.layer_count <= 0 or capabilities.modifier_count <= 0:
            return None
        return capabilities

    @classmethod
    def get_layer_style(cls, keyboard, index):
        response = cls._send(keyboard, HALCYON_OP_GET_LAYER_STYLE, bytes((_byte("layer", index),)))
        if len(response) < 9:
            raise HalcyonSettingsProtocolError("short Halcyon layer-style response")
        return LayerStyle(
            HSV(response[3], response[4], response[5]),
            HSV(response[6], response[7], response[8]),
        )

    @classmethod
    def set_layer_style(cls, keyboard, index, style):
        cls._send(
            keyboard,
            HALCYON_OP_SET_LAYER_STYLE,
            bytes((_byte("layer", index),)) + style.foreground.as_bytes() + style.background.as_bytes(),
        )

    @classmethod
    def get_modifier_style(cls, keyboard, index):
        response = cls._send(keyboard, HALCYON_OP_GET_MOD_STYLE, bytes((_byte("modifier", index),)))
        if len(response) < 6:
            raise HalcyonSettingsProtocolError("short Halcyon modifier-style response")
        return HSV(response[3], response[4], response[5])

    @classmethod
    def set_modifier_style(cls, keyboard, index, color):
        cls._send(
            keyboard,
            HALCYON_OP_SET_MOD_STYLE,
            bytes((_byte("modifier", index),)) + color.as_bytes(),
        )

    @classmethod
    def get_dim_style(cls, keyboard):
        response = cls._send(keyboard, HALCYON_OP_GET_DIM_STYLE)
        if len(response) < 5:
            raise HalcyonSettingsProtocolError("short Halcyon dim-style response")
        return HSV(response[2], response[3], response[4])

    @classmethod
    def set_dim_style(cls, keyboard, color):
        cls._send(keyboard, HALCYON_OP_SET_DIM_STYLE, color.as_bytes())

    @classmethod
    def get_timings(cls, keyboard):
        response = cls._send(keyboard, HALCYON_OP_GET_TIMINGS)
        if len(response) < 6:
            raise HalcyonSettingsProtocolError("short Halcyon timing response")
        return struct.unpack(">HH", response[2:6])

    @classmethod
    def set_timings(cls, keyboard, pattern_frame_ms, modifier_recent_ms):
        cls._send(
            keyboard,
            HALCYON_OP_SET_TIMINGS,
            struct.pack(">HH", _uint16("pattern frame", pattern_frame_ms), _uint16("modifier recent", modifier_recent_ms)),
        )

    @classmethod
    def get_telemetry(cls, keyboard):
        response = cls._send(keyboard, HALCYON_OP_GET_TELEMETRY)
        if len(response) < 9:
            raise HalcyonSettingsProtocolError("short Halcyon telemetry response")
        return HalcyonTelemetry(response)

    @classmethod
    def save(cls, keyboard):
        cls._send(keyboard, HALCYON_OP_SAVE)

    @classmethod
    def reset(cls, keyboard):
        cls._send(keyboard, HALCYON_OP_RESET)


def _byte(label, value):
    value = int(value)
    if value < 0 or value > 0xFF:
        raise ValueError("{} must be an unsigned byte".format(label))
    return value


def _uint16(label, value):
    value = int(value)
    if value < 0 or value > 0xFFFF:
        raise ValueError("{} must be an unsigned 16-bit integer".format(label))
    return value
