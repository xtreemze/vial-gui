# Copyright 2026 Carlos Velasco
# SPDX-License-Identifier: GPL-2.0-or-later
"""Apply portable Vial Web v1 palettes through the existing protocol owners.

No color generation or runtime precedence is duplicated here. The JSON export
contains explicit RGB and TFT values; unsupported targets fail before writes.
"""

from typing import TYPE_CHECKING, Callable, Dict, Optional, Set, Tuple, Union

from protocol.halcyon_settings import HSV, HalcyonCapabilities, LayerStyle
from protocol.halcyon_settings import HalcyonSettingsProtocol as TftProtocol
from protocol.rgb_profiles import RGBProfile, RGBProfileCapabilities
from protocol.rgb_profiles import RGBProfilesProtocol as RgbProtocol

if TYPE_CHECKING:
    from protocol.keyboard_comm import Keyboard

MAX_BYTE = 255
COLOR_FIELDS = 14
MAX_SCOPE = 3
ProfileValue = Union[RGBProfile, LayerStyle, HSV]
Document = Dict[str, object]
ColorDocument = Dict[str, int]
MaybeCapabilities = Optional[HalcyonCapabilities]
ScopeKey = Union[str, int]
MaybeError = Optional[str]


def validate_palette(
    plan: Document, caps: RGBProfileCapabilities, tft: MaybeCapabilities,
) -> Document:
    """Validate a complete plan before reading or mutating a keyboard."""
    if plan.get("version") != 1 or caps.protocol_version != 1 or caps.precedence_version != 1:
        msg = "unsupported palette or precedence version"
        raise ValueError(msg)
    if caps.field_flags & COLOR_FIELDS != COLOR_FIELDS:
        msg = "device does not support palette color fields"
        raise ValueError(msg)
    seen = set()
    _validate_rgb(plan, caps, seen)
    _validate_tft(plan, tft, seen)
    return plan


def _byte(value: int) -> int:
    if type(value) is not int or not 0 <= value <= MAX_BYTE:
        msg = "palette fields must be unsigned bytes"
        raise ValueError(msg)
    return value


def _validate_hsv(color: ColorDocument) -> None:
    for key in ("hue", "saturation", "value"):
        _byte(color[key])


Targets = Set[Tuple[Union[str, int], int]]


def _target(kind: ScopeKey, index: int, count: int, seen: Targets) -> None:
    if type(index) is not int or not 0 <= index < count or (kind, index) in seen:
        msg = "invalid or duplicate palette target"
        raise ValueError(msg)
    seen.add((kind, index))


def _validate_rgb(plan: Document, caps: RGBProfileCapabilities, seen: Targets) -> None:
    counts = [1, caps.layer_count, caps.modifier_count, caps.combo_count]
    for item in plan["rgb"]:
        scope = _byte(item["scope"])
        if scope > MAX_SCOPE or not caps.supports_scope(scope):
            msg = "unsupported RGB scope"
            raise ValueError(msg)
        _target(scope, item["index"], counts[scope], seen)
        p = item["rgb"]
        for field in ("mode", "hue", "saturation", "brightness", "speed"):
            _byte(p[field])
        if p["mode"] > caps.maximum_mode or p["brightness"] > caps.maximum_brightness:
            msg = "palette exceeds RGB device limits"
            raise ValueError(msg)


def _validate_tft(plan: Document, tft: MaybeCapabilities, seen: Targets) -> None:
    for kind, flag, count in (
        ("tftLayers", 1, tft.layer_count if tft else 0),
        ("tftModifiers", 2, tft.modifier_count if tft else 0),
    ):
        for item in plan[kind]:
            if not tft or not tft.flags & flag:
                msg = "unsupported TFT scope"
                raise ValueError(msg)
            _target(kind, item["index"], count, seen)
            if kind == "tftLayers":
                _validate_hsv(item["style"]["foreground"])
                _validate_hsv(item["style"]["background"])
            else:
                _validate_hsv(item["color"])


def _hsv(value: ColorDocument) -> HSV:
    return HSV(value["hue"], value["saturation"], value["value"])


class PaletteBatch:
    """A connection-scoped reversible runtime transaction, with explicit save."""

    def __init__(self, keyboard: "Keyboard", plan: Document) -> None:
        """Bind explicit target colors to a single device session."""
        self.keyboard = keyboard
        caps = RgbProtocol.probe(keyboard)
        if caps is None:
            msg = "RGB palette protocol is unavailable"
            raise ValueError(msg)
        self.plan = validate_palette(plan, caps, TftProtocol.probe(keyboard))
        self.before = []
        self.after = []
        self.applied = False
        self.device = keyboard.dev

    def _check_device(self) -> None:
        if self.keyboard.dev is not self.device:
            msg = "keyboard session changed; reconnect and import again"
            raise RuntimeError(msg)

    def _read(self, kind: str, item: Document) -> ProfileValue:
        self._check_device()
        if kind == "rgb":
            return RgbProtocol.get_profile(self.keyboard, item["scope"], item["index"])
        if kind == "tftLayers":
            return TftProtocol.get_layer_style(self.keyboard, item["index"])
        return TftProtocol.get_modifier_style(self.keyboard, item["index"])

    def _write(self, kind: str, item: Document, value: ProfileValue) -> None:
        self._check_device()
        if kind == "rgb":
            RgbProtocol.set_profile(self.keyboard, item["scope"], item["index"], value)
        elif kind == "tftLayers":
            TftProtocol.set_layer_style(self.keyboard, item["index"], value)
        else:
            TftProtocol.set_modifier_style(self.keyboard, item["index"], value)

    @staticmethod
    def _bytes(kind: str, value: ProfileValue) -> bytes:
        if kind == "tftLayers":
            return value.foreground.as_bytes() + value.background.as_bytes()
        return value.as_bytes()

    @staticmethod
    def _replacement(kind: str, item: Document, old: ProfileValue) -> ProfileValue:
        if kind == "rgb":
            p = item["rgb"]
            new = RGBProfile(
                p["mode"] if old.mode == MAX_BYTE else old.mode,
                p["hue"],
                p["saturation"],
                p["brightness"],
                old.speed,
            )
        elif kind == "tftLayers":
            new = LayerStyle(_hsv(item["style"]["foreground"]), old.background)
        else:
            new = _hsv(item["color"])
        return new

    def apply(self, progress: Callable[[int, int], bool] = lambda _done, _total: True) -> None:
        """Snapshot everything first. Callback false cancels with rollback."""
        self.before = []
        self.after = []
        for kind in ("rgb", "tftLayers", "tftModifiers"):
            for item in self.plan[kind]:
                old = self._read(kind, item)
                self.before.append((kind, item, old))
                new = self._replacement(kind, item, old)
                self.after.append((kind, item, new))
        try:
            for done, (kind, item, new) in enumerate(self.after):
                self._check_progress(progress, done, len(self.after))
                self._write(kind, item, new)
            self.verify()
            self.applied = True
        except (RuntimeError, ValueError, KeyError, TypeError, OSError) as failure:
            try:
                self.restore()
            except (RuntimeError, ValueError, KeyError, TypeError, OSError) as rollback:
                msg = f"palette failed; rollback incomplete: {rollback}"
                raise RuntimeError(msg) from failure
            raise

    @staticmethod
    def _check_progress(progress: Callable[[int, int], bool], done: int, total: int) -> None:
        if not progress(done, total):
            msg = "palette preview cancelled"
            raise RuntimeError(msg)

    def _verify_value(self, kind: str, item: Document, expected: ProfileValue) -> None:
        if self._bytes(kind, self._read(kind, item)) != self._bytes(kind, expected):
            msg = "palette readback mismatch"
            raise RuntimeError(msg)

    def _restore_target(self, kind: str, item: Document, old: ProfileValue) -> MaybeError:
        try:
            self._write(kind, item, old)
            self._verify_value(kind, item, old)
        except (RuntimeError, ValueError, KeyError, TypeError, OSError) as error:
            return str(error)
        return None

    def verify(self) -> None:
        """Read back each explicit target before allowing persistence."""
        for kind, item, expected in self.after:
            if self._bytes(kind, self._read(kind, item)) != self._bytes(kind, expected):
                msg = "palette readback mismatch"
                raise RuntimeError(msg)

    def restore(self) -> None:
        """Attempt every rollback target, reporting incomplete restoration."""
        failures = []
        for kind, item, old in self.before:
            error = self._restore_target(kind, item, old)
            if error:
                failures.append(error)
        if failures:
            raise RuntimeError("; ".join(failures))
        self.applied = False

    def save(self) -> None:
        """Persist only a verified preview; namespace saves are sequential."""
        if not self.applied:
            msg = "preview and verify before saving"
            raise RuntimeError(msg)
        self._check_device()
        self.verify()
        RgbProtocol.save(self.keyboard)
        if self.plan["tftLayers"] or self.plan["tftModifiers"]:
            TftProtocol.save(self.keyboard)
        self.applied = False
