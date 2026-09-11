# SPDX-License-Identifier: GPL-2.0-or-later
"""Protocol adapter for xtreemze's extended RGB profile firmware feature."""

import struct


RGB_PROFILE_COMMAND = 0xF0
RGB_PROFILE_PROTOCOL_VERSION = 1
RGB_PROFILE_UNASSIGNED = 0xFF

RGB_PROFILE_SCOPE_GLOBAL = 0
RGB_PROFILE_SCOPE_LAYER = 1
RGB_PROFILE_SCOPE_MODIFIER = 2
RGB_PROFILE_SCOPE_COMBO = 3

RGB_PROFILE_MODIFIER_CONTROL = 0
RGB_PROFILE_MODIFIER_GUI = 1
RGB_PROFILE_MODIFIER_SHIFT = 2
RGB_PROFILE_MODIFIER_ALT = 3

RGB_PROFILE_OP_GET_CAPABILITIES = 0x01
RGB_PROFILE_OP_GET_PROFILE = 0x02
RGB_PROFILE_OP_SET_PROFILE = 0x03
RGB_PROFILE_OP_SAVE = 0x04
RGB_PROFILE_OP_PREVIEW = 0x05
RGB_PROFILE_OP_GET_COMBO_DURATION = 0x06
RGB_PROFILE_OP_SET_COMBO_DURATION = 0x07
RGB_PROFILE_OP_CANCEL_PREVIEW = 0x08


class RGBProfileProtocolError(RuntimeError):
    pass


class RGBProfile:
    __slots__ = ("mode", "hue", "saturation", "brightness", "speed")

    def __init__(self, mode, hue, saturation, brightness, speed):
        self.mode = _byte("mode", mode)
        self.hue = _byte("hue", hue)
        self.saturation = _byte("saturation", saturation)
        self.brightness = _byte("brightness", brightness)
        self.speed = _byte("speed", speed)

    @property
    def assigned(self):
        return self.mode != RGB_PROFILE_UNASSIGNED

    def as_bytes(self):
        return bytes((self.mode, self.hue, self.saturation, self.brightness, self.speed))

    def copy(self):
        return RGBProfile(self.mode, self.hue, self.saturation, self.brightness, self.speed)


class RGBProfileCapabilities:
    __slots__ = (
        "protocol_version", "scope_flags", "layer_count", "modifier_count", "combo_count",
        "maximum_brightness", "maximum_mode", "field_flags", "precedence_version",
    )

    def __init__(self, data):
        self.protocol_version = data[2]
        self.scope_flags = data[3]
        self.layer_count = data[4]
        self.modifier_count = data[5]
        self.combo_count = data[6]
        self.maximum_brightness = data[7]
        self.maximum_mode = data[8]
        self.field_flags = data[9]
        self.precedence_version = data[10]

    def supports_scope(self, scope):
        return bool(self.scope_flags & (1 << scope))

    def count_for_scope(self, scope):
        if scope == RGB_PROFILE_SCOPE_GLOBAL:
            return 1
        if scope == RGB_PROFILE_SCOPE_LAYER:
            return self.layer_count
        if scope == RGB_PROFILE_SCOPE_MODIFIER:
            return self.modifier_count
        if scope == RGB_PROFILE_SCOPE_COMBO:
            return self.combo_count
        return 0


class RGBProfilesProtocol:
    """Send the keyboard-specific 0xF0 protocol over Vial's existing raw HID transport."""

    @staticmethod
    def _send(keyboard, operation, payload=b""):
        message = bytes((RGB_PROFILE_COMMAND, operation)) + payload
        response = keyboard.usb_send(keyboard.dev, message, retries=2)
        if len(response) < 2 or response[0] != RGB_PROFILE_COMMAND or response[1] != operation:
            raise RGBProfileProtocolError("keyboard did not acknowledge the RGB profile command")
        return response

    @classmethod
    def probe(cls, keyboard):
        try:
            response = cls._send(keyboard, RGB_PROFILE_OP_GET_CAPABILITIES)
            capabilities = RGBProfileCapabilities(response)
        except (IndexError, RuntimeError, ValueError):
            return None

        if (
            capabilities.protocol_version != RGB_PROFILE_PROTOCOL_VERSION
            or capabilities.layer_count <= 0
            or capabilities.modifier_count <= 0
            or capabilities.maximum_mode <= 0
        ):
            return None
        return capabilities

    @classmethod
    def get_profile(cls, keyboard, scope, index):
        response = cls._send(
            keyboard,
            RGB_PROFILE_OP_GET_PROFILE,
            bytes((_byte("scope", scope), _byte("index", index))),
        )
        if len(response) < 9:
            raise RGBProfileProtocolError("short RGB profile response")
        return RGBProfile(response[4], response[5], response[6], response[7], response[8])

    @classmethod
    def set_profile(cls, keyboard, scope, index, profile):
        cls._send(
            keyboard,
            RGB_PROFILE_OP_SET_PROFILE,
            bytes((_byte("scope", scope), _byte("index", index))) + profile.as_bytes(),
        )

    @classmethod
    def clear_profile(cls, keyboard, scope, index):
        if scope == RGB_PROFILE_SCOPE_GLOBAL:
            raise ValueError("the global RGB profile cannot be cleared")
        cls.set_profile(keyboard, scope, index, RGBProfile(RGB_PROFILE_UNASSIGNED, 0, 0, 0, 0))

    @classmethod
    def save(cls, keyboard):
        cls._send(keyboard, RGB_PROFILE_OP_SAVE)

    @classmethod
    def preview(cls, keyboard, profile):
        cls._send(keyboard, RGB_PROFILE_OP_PREVIEW, profile.as_bytes())

    @classmethod
    def cancel_preview(cls, keyboard):
        cls._send(keyboard, RGB_PROFILE_OP_CANCEL_PREVIEW)

    @classmethod
    def get_combo_duration(cls, keyboard):
        response = cls._send(keyboard, RGB_PROFILE_OP_GET_COMBO_DURATION)
        if len(response) < 4:
            raise RGBProfileProtocolError("short combo duration response")
        return struct.unpack(">H", response[2:4])[0]

    @classmethod
    def set_combo_duration(cls, keyboard, duration_ms):
        value = _uint16("combo duration", duration_ms)
        cls._send(keyboard, RGB_PROFILE_OP_SET_COMBO_DURATION, struct.pack(">H", value))


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
