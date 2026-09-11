# SPDX-License-Identifier: GPL-2.0-or-later

from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QComboBox,
    QColorDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
)

from editor.basic_editor import BasicEditor
from protocol.rgb_profiles import (
    RGB_PROFILE_MODIFIER_ALT,
    RGB_PROFILE_MODIFIER_CONTROL,
    RGB_PROFILE_MODIFIER_GUI,
    RGB_PROFILE_MODIFIER_SHIFT,
    RGB_PROFILE_SCOPE_COMBO,
    RGB_PROFILE_SCOPE_GLOBAL,
    RGB_PROFILE_SCOPE_LAYER,
    RGB_PROFILE_SCOPE_MODIFIER,
    RGB_PROFILE_UNASSIGNED,
    RGBProfile,
    RGBProfilesProtocol,
)
from vial_device import VialKeyboard


SCOPE_LABELS = {
    RGB_PROFILE_SCOPE_GLOBAL: "Global / default",
    RGB_PROFILE_SCOPE_LAYER: "Layer",
    RGB_PROFILE_SCOPE_MODIFIER: "Modifier",
    RGB_PROFILE_SCOPE_COMBO: "Combo",
}

MODIFIER_LABELS = {
    RGB_PROFILE_MODIFIER_CONTROL: "Control",
    RGB_PROFILE_MODIFIER_GUI: "GUI / Command",
    RGB_PROFILE_MODIFIER_SHIFT: "Shift",
    RGB_PROFILE_MODIFIER_ALT: "Alt / Option",
}


class RGBProfiles(BasicEditor):
    """Editor for the keyboard-specific layer/modifier/combo RGB profile protocol."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.keyboard = None
        self.capabilities = None
        self.profile = None
        self._loading = False

        help_label = QLabel(
            "Profiles resolve by precedence: combo → Control → GUI/Command → Shift → "
            "Alt/Option → layer → global. Clearing an override restores inheritance."
        )
        help_label.setWordWrap(True)
        self.addWidget(help_label)

        self.form = QGridLayout()
        self.addLayout(self.form)

        row = 0
        self.form.addWidget(QLabel("Profile scope"), row, 0)
        self.scope = QComboBox()
        self.scope.currentIndexChanged.connect(self._scope_changed)
        self.form.addWidget(self.scope, row, 1)

        row += 1
        self.form.addWidget(QLabel("Target"), row, 0)
        self.target = QComboBox()
        self.target.currentIndexChanged.connect(self._target_changed)
        self.form.addWidget(self.target, row, 1)

        row += 1
        self.effect_label = QLabel("Effect")
        self.form.addWidget(self.effect_label, row, 0)
        self.effect = QComboBox()
        self.effect.currentIndexChanged.connect(self._effect_changed)
        self.form.addWidget(self.effect, row, 1)

        row += 1
        self.color_label = QLabel("Color")
        self.form.addWidget(self.color_label, row, 0)
        self.color = QPushButton("Choose color…")
        self.color.clicked.connect(self._choose_color)
        self.form.addWidget(self.color, row, 1)

        row += 1
        self.brightness_label = QLabel("Brightness")
        self.form.addWidget(self.brightness_label, row, 0)
        self.brightness = QSpinBox()
        self.brightness.valueChanged.connect(self._brightness_changed)
        self.form.addWidget(self.brightness, row, 1)

        row += 1
        self.speed_label = QLabel("Effect speed")
        self.form.addWidget(self.speed_label, row, 0)
        self.speed = QSpinBox()
        self.speed.setRange(0, 255)
        self.speed.valueChanged.connect(self._speed_changed)
        self.form.addWidget(self.speed, row, 1)

        row += 1
        self.combo_duration_label = QLabel("Combo highlight duration (ms)")
        self.form.addWidget(self.combo_duration_label, row, 0)
        self.combo_duration = QSpinBox()
        self.combo_duration.setRange(250, 10000)
        self.combo_duration.setSingleStep(50)
        self.form.addWidget(self.combo_duration, row, 1)

        self.inheritance = QLabel("")
        self.inheritance.setWordWrap(True)
        self.addWidget(self.inheritance)

        buttons = QHBoxLayout()
        self.save_button = QPushButton("Save to Keyboard")
        self.save_button.clicked.connect(self._save)
        buttons.addWidget(self.save_button)

        self.preview_button = QPushButton("Preview")
        self.preview_button.clicked.connect(self._preview)
        buttons.addWidget(self.preview_button)

        self.cancel_preview_button = QPushButton("Cancel Preview")
        self.cancel_preview_button.clicked.connect(self._cancel_preview)
        buttons.addWidget(self.cancel_preview_button)

        self.create_button = QPushButton("Create Override")
        self.create_button.clicked.connect(self._create_override)
        buttons.addWidget(self.create_button)

        self.clear_button = QPushButton("Clear Override")
        self.clear_button.clicked.connect(self._clear)
        buttons.addWidget(self.clear_button)

        buttons.addStretch(1)
        self.addLayout(buttons)

        self.status = QLabel("")
        self.status.setWordWrap(True)
        self.addWidget(self.status)
        self.addStretch(1)

        self._set_profile_controls_enabled(False)
        self._update_scope_specific_visibility()

    def valid(self):
        return self.capabilities is not None

    def rebuild(self, device):
        super().rebuild(device)
        self.keyboard = None
        self.capabilities = None
        self.profile = None
        self.status.setText("")

        if not isinstance(device, VialKeyboard):
            return

        capabilities = RGBProfilesProtocol.probe(device.keyboard)
        if capabilities is None:
            return

        self.keyboard = device.keyboard
        self.capabilities = capabilities
        self.brightness.setRange(0, capabilities.maximum_brightness)

        self._loading = True
        self.scope.clear()
        for scope in (
            RGB_PROFILE_SCOPE_GLOBAL,
            RGB_PROFILE_SCOPE_LAYER,
            RGB_PROFILE_SCOPE_MODIFIER,
            RGB_PROFILE_SCOPE_COMBO,
        ):
            if capabilities.supports_scope(scope):
                self.scope.addItem(SCOPE_LABELS[scope], scope)

        self.effect.clear()
        self.effect.addItem("Off", 0)
        for mode in range(1, capabilities.maximum_mode + 1):
            self.effect.addItem("QMK effect {}".format(mode), mode)

        try:
            duration = RGBProfilesProtocol.get_combo_duration(self.keyboard)
            self.combo_duration.setValue(duration)
        except RuntimeError:
            self.combo_duration.setValue(2000)

        self._loading = False
        self._scope_changed()

    def _current_scope(self):
        if self.scope.currentIndex() < 0:
            return RGB_PROFILE_SCOPE_GLOBAL
        return self.scope.currentData()

    def _current_target(self):
        if self.target.currentIndex() < 0:
            return 0
        return self.target.currentData()

    def _scope_changed(self, _index=None):
        if self._loading or self.capabilities is None:
            return

        scope = self._current_scope()
        self._loading = True
        self.target.clear()
        count = self.capabilities.count_for_scope(scope)
        for index in range(count):
            if scope == RGB_PROFILE_SCOPE_GLOBAL:
                label = "Default"
            elif scope == RGB_PROFILE_SCOPE_LAYER:
                label = "Layer {}".format(index)
            elif scope == RGB_PROFILE_SCOPE_MODIFIER:
                label = MODIFIER_LABELS.get(index, "Modifier {}".format(index + 1))
            else:
                label = "Combo {}".format(index + 1)
            self.target.addItem(label, index)
        self._loading = False
        self._update_scope_specific_visibility()
        self._load_profile()

    def _target_changed(self, _index=None):
        if not self._loading:
            self._load_profile()

    def _load_profile(self):
        if self.keyboard is None or self.target.currentIndex() < 0:
            return
        try:
            self.profile = RGBProfilesProtocol.get_profile(
                self.keyboard, self._current_scope(), self._current_target()
            )
            self.status.setText("")
            self._populate_profile()
        except RuntimeError as exc:
            self.profile = None
            self._set_profile_controls_enabled(False)
            self.status.setText("Could not read this profile from the keyboard: {}".format(exc))

    def _populate_profile(self):
        if self.profile is None:
            self._set_profile_controls_enabled(False)
            return

        assigned = self.profile.assigned
        self._loading = True
        if assigned:
            effect_index = self.effect.findData(self.profile.mode)
            self.effect.setCurrentIndex(max(0, effect_index))
            self.brightness.setValue(self.profile.brightness)
            self.speed.setValue(self.profile.speed)
            self._update_color_button()
        self._loading = False

        self._set_profile_controls_enabled(assigned)
        self.create_button.setVisible(not assigned)
        self.clear_button.setVisible(assigned and self._current_scope() != RGB_PROFILE_SCOPE_GLOBAL)
        if assigned:
            self.inheritance.setText("")
        else:
            self.inheritance.setText(
                "This target has no override and inherits from the next applicable profile in the precedence chain."
            )

    def _set_profile_controls_enabled(self, enabled):
        for widget in (
            self.effect,
            self.color,
            self.brightness,
            self.speed,
            self.save_button,
            self.preview_button,
        ):
            widget.setEnabled(enabled)

    def _update_scope_specific_visibility(self):
        combo = self._current_scope() == RGB_PROFILE_SCOPE_COMBO
        self.combo_duration_label.setVisible(combo)
        self.combo_duration.setVisible(combo)

    def _effect_changed(self, _index=None):
        if self._loading or self.profile is None or self.effect.currentIndex() < 0:
            return
        self.profile.mode = self.effect.currentData()

    def _brightness_changed(self, value):
        if not self._loading and self.profile is not None:
            self.profile.brightness = value

    def _speed_changed(self, value):
        if not self._loading and self.profile is not None:
            self.profile.speed = value

    def _choose_color(self):
        if self.profile is None:
            return
        initial = QColor.fromHsv(self.profile.hue, self.profile.saturation, max(1, self.profile.brightness))
        color = QColorDialog.getColor(initial)
        if not color.isValid():
            return
        hue, saturation, _value, _alpha = color.getHsv()
        if hue < 0:
            hue = 0
        self.profile.hue = hue
        self.profile.saturation = saturation
        self._update_color_button()

    def _update_color_button(self):
        if self.profile is None:
            return
        color = QColor.fromHsv(self.profile.hue, self.profile.saturation, max(1, self.profile.brightness))
        self.color.setStyleSheet("QPushButton { background-color: %s; }" % color.name())

    def _create_override(self):
        if self.keyboard is None:
            return
        try:
            inherited = RGBProfilesProtocol.get_profile(self.keyboard, RGB_PROFILE_SCOPE_GLOBAL, 0)
            if inherited.assigned:
                self.profile = inherited.copy()
            else:
                self.profile = RGBProfile(1, 0, 0, min(128, self.capabilities.maximum_brightness), 128)
            self.status.setText("Override prepared. Save to persist it.")
        except RuntimeError:
            self.profile = RGBProfile(1, 0, 0, min(128, self.capabilities.maximum_brightness), 128)
            self.status.setText("Override prepared from defaults. Save to persist it.")
        self._populate_profile()

    def _save(self):
        if self.keyboard is None or self.profile is None or not self.profile.assigned:
            return
        try:
            RGBProfilesProtocol.set_profile(
                self.keyboard, self._current_scope(), self._current_target(), self.profile
            )
            if self._current_scope() == RGB_PROFILE_SCOPE_COMBO:
                RGBProfilesProtocol.set_combo_duration(self.keyboard, self.combo_duration.value())
            RGBProfilesProtocol.save(self.keyboard)
            self.status.setText("Saved to keyboard.")
        except RuntimeError as exc:
            self.status.setText("Save failed: {}".format(exc))

    def _preview(self):
        if self.keyboard is None or self.profile is None or not self.profile.assigned:
            return
        try:
            RGBProfilesProtocol.preview(self.keyboard, self.profile)
            self.status.setText("Previewing temporarily on the keyboard.")
        except RuntimeError as exc:
            self.status.setText("Preview failed: {}".format(exc))

    def _cancel_preview(self):
        if self.keyboard is None:
            return
        try:
            RGBProfilesProtocol.cancel_preview(self.keyboard)
            self.status.setText("Preview cancelled.")
        except RuntimeError as exc:
            self.status.setText("Could not cancel preview: {}".format(exc))

    def _clear(self):
        if self.keyboard is None or self._current_scope() == RGB_PROFILE_SCOPE_GLOBAL:
            return
        try:
            RGBProfilesProtocol.clear_profile(
                self.keyboard, self._current_scope(), self._current_target()
            )
            RGBProfilesProtocol.save(self.keyboard)
            self.profile = RGBProfile(RGB_PROFILE_UNASSIGNED, 0, 0, 0, 0)
            self.status.setText("Override cleared; this target now inherits.")
            self._populate_profile()
        except RuntimeError as exc:
            self.status.setText("Could not clear override: {}".format(exc))
