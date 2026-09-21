# SPDX-License-Identifier: GPL-2.0-or-later

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QComboBox,
    QColorDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from editor.basic_editor import BasicEditor
from editor.rgb_profiles import RGBProfiles
from protocol.halcyon_settings import (
    HALCYON_CAP_LAYER_COLORS,
    HALCYON_CAP_MOD_COLORS,
    HALCYON_CAP_TELEMETRY,
    HALCYON_CAP_TIMINGS,
    HalcyonSettingsProtocol,
)
from vial_device import VialKeyboard


DISPLAY_SCOPE_LAYER = 0
DISPLAY_SCOPE_MODIFIER = 1
DISPLAY_SCOPE_DIM = 2

MODIFIER_LABELS = (
    "Control",
    "GUI / Command",
    "Shift",
    "Alt / Option",
    "Meh",
    "Shift + Alt",
    "Shift + GUI",
    "Alt + GUI",
    "Hyper",
    "Caps Word",
)

OS_LABELS = {
    0: "Detecting / unknown",
    1: "macOS",
    2: "iOS",
    3: "Windows",
    4: "Linux",
}
SHORTCUT_LABELS = {0: "Unknown", 1: "Apple / Command", 2: "Control"}
SOURCE_LABELS = {0: "Default", 1: "Stored", 2: "Live QMK detection"}
EVENT_LABELS = {0: "Boot", 1: "Resume", 2: "Host change"}


class ObservableRGBProfiles(RGBProfiles):
    """Keep the custom RGB editor visible even when firmware probing fails."""

    def valid(self):
        return True

    def rebuild(self, device):
        super().rebuild(device)

        connection_controls = (
            self.scope,
            self.target,
            self.combo_duration,
            self.cancel_preview_button,
            self.create_button,
            self.clear_button,
        )
        supported = self.capabilities is not None
        for widget in connection_controls:
            widget.setEnabled(supported)

        if supported:
            self.status.setText(
                "xtreemze extended RGB profile protocol v1 detected; controls are live."
            )
            return

        self._set_profile_controls_enabled(False)
        self.scope.clear()
        self.target.clear()
        self.effect.clear()
        self.inheritance.setText("")

        if isinstance(device, VialKeyboard):
            self.status.setText(
                "Custom Vial UI is active, but this keyboard did not expose the "
                "xtreemze extended RGB profile protocol v1. Flash the current "
                "xtreemze Halcyon firmware, then reconnect or refresh."
            )
        else:
            self.status.setText(
                "Connect the Halcyon Ferris running the xtreemze firmware to enable "
                "extended RGB profile controls."
            )


class HalcyonEditor(BasicEditor):
    """One home for firmware-specific Halcyon behavior and configuration."""

    def __init__(self, navigate_to_editor, parent=None):
        super().__init__(parent)
        self.navigate_to_editor = navigate_to_editor
        self.rgb_profiles = ObservableRGBProfiles()
        self.halcyon_keyboard = None
        self.halcyon_capabilities = None
        self.display_foreground = None
        self.display_background = None
        self._display_loading = False

        title = QLabel("Halcyon")
        title.setStyleSheet("font-size: 18px; font-weight: 600;")
        self.addWidget(title)

        subtitle = QLabel(
            "Keyboard-specific controls and diagnostics layered on top of upstream Vial. "
            "Standard Vial editors remain authoritative for keymaps, encoders, Alt Repeat, "
            "combos, QMK settings, and VialRGB."
        )
        subtitle.setWordWrap(True)
        self.addWidget(subtitle)

        self.connection_status = QLabel("")
        self.connection_status.setWordWrap(True)
        self.addWidget(self.connection_status)

        self.sections = QTabWidget()
        self.sections.addTab(self._build_overview_page(), "Overview")
        self.sections.addTab(self._build_rgb_page(), "RGB Profiles")
        self.sections.addTab(self._build_display_page(), "Display & OS")
        self.sections.addTab(self._build_encoder_page(), "Encoder & Repeat")
        self.addWidget(self.sections, 1)

    def valid(self):
        return True

    def rebuild(self, device):
        super().rebuild(device)
        self.rgb_profiles.rebuild(device)
        self.halcyon_keyboard = None
        self.halcyon_capabilities = None
        self._set_display_controls_enabled(False)
        self.display_status.setText("")
        self._clear_telemetry()

        if not isinstance(device, VialKeyboard):
            self.connection_status.setText(
                "No Vial keyboard selected. Connect the Halcyon Ferris to inspect live capabilities."
            )
            self._set_status_values("Disconnected", "Unavailable", "Unavailable")
            return

        try:
            device_name = device.title()
        except KeyError:
            device_name = "Vial keyboard"

        self.halcyon_capabilities = HalcyonSettingsProtocol.probe(device.keyboard)
        if self.halcyon_capabilities is not None:
            self.halcyon_keyboard = device.keyboard
            self._configure_display_controls()

        extensions = []
        if self.rgb_profiles.capabilities is not None:
            extensions.append("RGB profiles v1")
        if self.halcyon_capabilities is not None:
            extensions.append("Halcyon settings v1")

        if extensions:
            self.connection_status.setText(
                "{} connected. xtreemze firmware extensions detected.".format(device_name)
            )
            policy = (
                "Enabled"
                if self.halcyon_capabilities is not None
                and self.halcyon_capabilities.deterministic_repeat
                else "Firmware-dependent"
            )
            self._set_status_values("Connected", ", ".join(extensions), policy)
        else:
            self.connection_status.setText(
                "{} connected, but the xtreemze host-editable protocols were not detected. "
                "Upstream Vial features remain usable; flash the current Halcyon firmware "
                "to enable the custom live controls.".format(device_name)
            )
            self._set_status_values("Connected", "Firmware update required", "Firmware-dependent")

    def activate(self):
        self.rgb_profiles.activate()
        if self.halcyon_keyboard is not None:
            self._refresh_telemetry()

    def deactivate(self):
        self.rgb_profiles.deactivate()

    def on_container_clicked(self):
        if self.sections.currentWidget() is self.rgb_page:
            self.rgb_profiles.on_container_clicked()

    def _set_status_values(self, device, extension, policy):
        self.device_value.setText(device)
        self.extension_value.setText(extension)
        self.encoder_policy_value.setText(policy)

    def _build_overview_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)

        status_group = QGroupBox("Runtime status")
        status_form = QFormLayout(status_group)
        self.device_value = QLabel("Disconnected")
        self.extension_value = QLabel("Unavailable")
        self.encoder_policy_value = QLabel("Unavailable")
        status_form.addRow("Device", self.device_value)
        status_form.addRow("Custom protocols", self.extension_value)
        status_form.addRow("Deterministic encoder-repeat policy", self.encoder_policy_value)
        layout.addWidget(status_group)

        ownership_group = QGroupBox("Where settings live")
        ownership_layout = QVBoxLayout(ownership_group)
        ownership = QLabel(
            "RGB profile precedence and per-layer/modifier/combo lighting are configured here. "
            "Halcyon TFT palettes, animation timing, modifier persistence, and host telemetry are "
            "configured in Display & OS when the v1 settings protocol is present. Encoder assignments "
            "use Keymap, ordered Repeat/Alternate Repeat pairs use Alt Repeat Key, and standard "
            "lighting uses Lighting."
        )
        ownership.setWordWrap(True)
        ownership_layout.addWidget(ownership)
        layout.addWidget(ownership_group)

        actions = QHBoxLayout()
        actions.addWidget(self._nav_button("Open Keymap", "Keymap"))
        actions.addWidget(self._nav_button("Open Alt Repeat", "Alt Repeat Key"))
        actions.addWidget(self._nav_button("Open Lighting", "Lighting"))
        actions.addStretch(1)
        layout.addLayout(actions)
        layout.addStretch(1)
        return page

    def _build_rgb_page(self):
        self.rgb_page = QWidget()
        self.rgb_page.setLayout(self.rgb_profiles)
        return self.rgb_page

    def _build_display_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)

        settings_group = QGroupBox("TFT appearance")
        settings_form = QFormLayout(settings_group)

        self.display_scope = QComboBox()
        self.display_scope.addItem("Layer palette", DISPLAY_SCOPE_LAYER)
        self.display_scope.addItem("Modifier indicator", DISPLAY_SCOPE_MODIFIER)
        self.display_scope.addItem("Inactive / dim indicator", DISPLAY_SCOPE_DIM)
        self.display_scope.currentIndexChanged.connect(self._display_scope_changed)
        settings_form.addRow("Setting", self.display_scope)

        self.display_target_label = QLabel("Target")
        self.display_target = QComboBox()
        self.display_target.currentIndexChanged.connect(self._load_display_style)
        settings_form.addRow(self.display_target_label, self.display_target)

        self.display_foreground_label = QLabel("Foreground")
        self.display_foreground_button = QPushButton("Choose color…")
        self.display_foreground_button.clicked.connect(self._choose_display_foreground)
        settings_form.addRow(self.display_foreground_label, self.display_foreground_button)

        self.display_background_label = QLabel("Background")
        self.display_background_button = QPushButton("Choose color…")
        self.display_background_button.clicked.connect(self._choose_display_background)
        settings_form.addRow(self.display_background_label, self.display_background_button)

        layout.addWidget(settings_group)

        timing_group = QGroupBox("Animation and persistence")
        timing_form = QFormLayout(timing_group)

        pattern_controls = QHBoxLayout()
        self.pattern_timing = QSlider(Qt.Horizontal)
        self.pattern_timing.setRange(50, 1000)
        self.pattern_timing.setSingleStep(10)
        self.pattern_timing.setPageStep(50)
        self.pattern_timing.valueChanged.connect(self._pattern_timing_changed)
        pattern_controls.addWidget(self.pattern_timing, 1)
        self.pattern_timing_value = QLabel("200 ms")
        pattern_controls.addWidget(self.pattern_timing_value)
        timing_form.addRow("Layer animation frame", pattern_controls)

        recent_controls = QHBoxLayout()
        self.mod_recent_timing = QSlider(Qt.Horizontal)
        self.mod_recent_timing.setRange(0, 10000)
        self.mod_recent_timing.setSingleStep(100)
        self.mod_recent_timing.setPageStep(500)
        self.mod_recent_timing.valueChanged.connect(self._mod_recent_timing_changed)
        recent_controls.addWidget(self.mod_recent_timing, 1)
        self.mod_recent_timing_value = QLabel("2.2 s")
        recent_controls.addWidget(self.mod_recent_timing_value)
        timing_form.addRow("Recent modifier visibility", recent_controls)

        layout.addWidget(timing_group)

        buttons = QHBoxLayout()
        self.display_apply_button = QPushButton("Apply")
        self.display_apply_button.clicked.connect(self._apply_display_settings)
        buttons.addWidget(self.display_apply_button)
        self.display_save_button = QPushButton("Save to Keyboard")
        self.display_save_button.clicked.connect(self._save_display_settings)
        buttons.addWidget(self.display_save_button)
        self.display_reset_button = QPushButton("Reset TFT Defaults")
        self.display_reset_button.clicked.connect(self._reset_display_settings)
        buttons.addWidget(self.display_reset_button)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        self.display_status = QLabel(
            "Connect current xtreemze Halcyon firmware to enable persistent TFT controls."
        )
        self.display_status.setWordWrap(True)
        layout.addWidget(self.display_status)

        telemetry_group = QGroupBox("Host and split telemetry")
        telemetry_form = QFormLayout(telemetry_group)
        self.telemetry_os = QLabel("Unavailable")
        self.telemetry_shortcuts = QLabel("Unavailable")
        self.telemetry_source = QLabel("Unavailable")
        self.telemetry_event = QLabel("Unavailable")
        self.telemetry_role = QLabel("Unavailable")
        self.telemetry_transport = QLabel("Unavailable")
        self.telemetry_tft = QLabel("Unavailable")
        telemetry_form.addRow("Detected OS", self.telemetry_os)
        telemetry_form.addRow("Shortcut family", self.telemetry_shortcuts)
        telemetry_form.addRow("Detection source", self.telemetry_source)
        telemetry_form.addRow("Last host event", self.telemetry_event)
        telemetry_form.addRow("Keyboard role", self.telemetry_role)
        telemetry_form.addRow("Split transport", self.telemetry_transport)
        telemetry_form.addRow("TFT capability", self.telemetry_tft)
        self.telemetry_refresh_button = QPushButton("Refresh Telemetry")
        self.telemetry_refresh_button.clicked.connect(self._refresh_telemetry)
        telemetry_form.addRow("", self.telemetry_refresh_button)
        layout.addWidget(telemetry_group)

        modules_group = QGroupBox("Module configuration and diagnostics")
        modules_layout = QHBoxLayout(modules_group)
        modules_layout.addWidget(self._nav_button("Open Layout", "Layout"))
        modules_layout.addWidget(self._nav_button("Open Keymap", "Keymap"))
        modules_layout.addStretch(1)
        layout.addWidget(modules_group)
        layout.addStretch(1)

        self._set_display_controls_enabled(False)
        return page

    def _build_encoder_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)

        encoder_group = QGroupBox("Encoder assignments")
        encoder_layout = QVBoxLayout(encoder_group)
        encoder_text = QLabel(
            "Encoder bindings remain part of Vial's dynamic keymap. The compiled layer-3 right-encoder "
            "default is CCW = Alternate Repeat and CW = Repeat. Change encoder assignments in Keymap "
            "rather than maintaining a second custom mapping model here."
        )
        encoder_text.setWordWrap(True)
        encoder_layout.addWidget(encoder_text)
        encoder_layout.addWidget(self._nav_button("Edit encoder mappings", "Keymap"), 0, Qt.AlignLeft)
        layout.addWidget(encoder_group)

        repeat_group = QGroupBox("Consistent ordered pairs")
        repeat_layout = QVBoxLayout(repeat_group)
        repeat_text = QLabel(
            "Ordered pairs are authored in Vial's Alt Repeat Key editor. For bidirectional pairs, the "
            "xtreemze encoder policy treats the Vial Key side as primary and Alt Key as alternate, so "
            "CW requests primary and CCW requests alternate regardless of which member was pressed last."
        )
        repeat_text.setWordWrap(True)
        repeat_layout.addWidget(repeat_text)
        repeat_layout.addWidget(self._nav_button("Edit ordered pairs", "Alt Repeat Key"), 0, Qt.AlignLeft)
        layout.addWidget(repeat_group)

        combo_group = QGroupBox("Combo integration")
        combo_layout = QVBoxLayout(combo_group)
        combo_text = QLabel(
            "Combos stay in Vial's Combos editor. The Halcyon RGB profile extension can assign a "
            "temporary highlight profile to each combo without changing the combo definition itself."
        )
        combo_text.setWordWrap(True)
        combo_layout.addWidget(combo_text)
        combo_layout.addWidget(self._nav_button("Open Combos", "Combos"), 0, Qt.AlignLeft)
        layout.addWidget(combo_group)

        layout.addStretch(1)
        return page

    def _configure_display_controls(self):
        caps = self.halcyon_capabilities
        self._display_loading = True
        self.pattern_timing.setRange(caps.pattern_min_ms, caps.pattern_max_ms)
        self.mod_recent_timing.setRange(0, caps.modifier_recent_max_ms)
        self._display_loading = False
        self._set_display_controls_enabled(True)
        self._display_scope_changed()
        self._load_display_timings()
        self._refresh_telemetry()
        if not caps.tft_present:
            self.display_status.setText(
                "Halcyon settings v1 is available, but this half does not report an active TFT. "
                "Settings remain persistent and synchronize to the other half."
            )
        else:
            self.display_status.setText("Halcyon settings v1 detected; TFT controls are live.")

    def _set_display_controls_enabled(self, enabled):
        for widget in (
            self.display_scope,
            self.display_target,
            self.display_foreground_button,
            self.display_background_button,
            self.pattern_timing,
            self.mod_recent_timing,
            self.display_apply_button,
            self.display_save_button,
            self.display_reset_button,
            self.telemetry_refresh_button,
        ):
            widget.setEnabled(enabled)

    def _display_scope_changed(self, _index=None):
        if self._display_loading or self.halcyon_capabilities is None:
            return
        scope = self.display_scope.currentData()
        self._display_loading = True
        self.display_target.clear()
        if scope == DISPLAY_SCOPE_LAYER:
            for index in range(self.halcyon_capabilities.layer_count):
                self.display_target.addItem("Layer {}".format(index), index)
        elif scope == DISPLAY_SCOPE_MODIFIER:
            for index in range(self.halcyon_capabilities.modifier_count):
                label = MODIFIER_LABELS[index] if index < len(MODIFIER_LABELS) else "Modifier {}".format(index + 1)
                self.display_target.addItem(label, index)
        else:
            self.display_target.addItem("Inactive / recent", 0)
        self._display_loading = False
        is_layer = scope == DISPLAY_SCOPE_LAYER
        self.display_target_label.setVisible(scope != DISPLAY_SCOPE_DIM)
        self.display_target.setVisible(scope != DISPLAY_SCOPE_DIM)
        self.display_background_label.setVisible(is_layer)
        self.display_background_button.setVisible(is_layer)
        self.display_foreground_label.setText("Foreground" if is_layer else "Indicator color")
        self._load_display_style()

    def _load_display_style(self, _index=None):
        if self._display_loading or self.halcyon_keyboard is None:
            return
        try:
            scope = self.display_scope.currentData()
            target = self.display_target.currentData() if self.display_target.currentIndex() >= 0 else 0
            if scope == DISPLAY_SCOPE_LAYER:
                style = HalcyonSettingsProtocol.get_layer_style(self.halcyon_keyboard, target)
                self.display_foreground = style.foreground
                self.display_background = style.background
            elif scope == DISPLAY_SCOPE_MODIFIER:
                self.display_foreground = HalcyonSettingsProtocol.get_modifier_style(self.halcyon_keyboard, target)
                self.display_background = None
            else:
                self.display_foreground = HalcyonSettingsProtocol.get_dim_style(self.halcyon_keyboard)
                self.display_background = None
            self._update_display_color_buttons()
            self.display_status.setText("Loaded current TFT setting from keyboard.")
        except RuntimeError as exc:
            self.display_foreground = None
            self.display_background = None
            self.display_status.setText("Could not read TFT setting: {}".format(exc))

    def _load_display_timings(self):
        if self.halcyon_keyboard is None:
            return
        try:
            pattern_ms, recent_ms = HalcyonSettingsProtocol.get_timings(self.halcyon_keyboard)
            self._display_loading = True
            self.pattern_timing.setValue(pattern_ms)
            self.mod_recent_timing.setValue(recent_ms)
            self._display_loading = False
            self._pattern_timing_changed(pattern_ms)
            self._mod_recent_timing_changed(recent_ms)
        except RuntimeError as exc:
            self.display_status.setText("Could not read TFT timing settings: {}".format(exc))

    def _choose_display_foreground(self):
        if self.display_foreground is None:
            return
        color = self._choose_hsv(self.display_foreground)
        if color is not None:
            self.display_foreground = color
            self._update_display_color_buttons()

    def _choose_display_background(self):
        if self.display_background is None:
            return
        color = self._choose_hsv(self.display_background)
        if color is not None:
            self.display_background = color
            self._update_display_color_buttons()

    def _choose_hsv(self, hsv):
        initial = QColor.fromHsvF(hsv.hue / 255.0, hsv.saturation / 255.0, max(1, hsv.value) / 255.0)
        selected = QColorDialog.getColor(initial)
        if not selected.isValid():
            return None
        hue, saturation, value, _alpha = selected.getHsvF()
        if hue < 0:
            hue = 0
        from protocol.halcyon_settings import HSV
        return HSV(
            min(255, max(0, int(round(255 * hue)))),
            min(255, max(0, int(round(255 * saturation)))),
            min(255, max(0, int(round(255 * value)))),
        )

    def _update_display_color_buttons(self):
        self._set_color_button(self.display_foreground_button, self.display_foreground)
        self._set_color_button(self.display_background_button, self.display_background)

    @staticmethod
    def _set_color_button(button, hsv):
        if hsv is None:
            button.setStyleSheet("")
            return
        color = QColor.fromHsvF(hsv.hue / 255.0, hsv.saturation / 255.0, max(1, hsv.value) / 255.0)
        button.setStyleSheet("QPushButton { background-color: %s; }" % color.name())
        button.setToolTip("HSV {}, {}, {}".format(hsv.hue, hsv.saturation, hsv.value))

    def _pattern_timing_changed(self, value):
        self.pattern_timing_value.setText("{} ms".format(value))
        self.pattern_timing.setToolTip("{} ms per animation frame".format(value))

    def _mod_recent_timing_changed(self, value):
        self.mod_recent_timing_value.setText("{:.1f} s".format(value / 1000.0))
        self.mod_recent_timing.setToolTip("{} ms".format(value))

    def _apply_display_settings(self):
        if self.halcyon_keyboard is None or self.display_foreground is None:
            return False
        try:
            scope = self.display_scope.currentData()
            target = self.display_target.currentData() if self.display_target.currentIndex() >= 0 else 0
            if scope == DISPLAY_SCOPE_LAYER:
                from protocol.halcyon_settings import LayerStyle
                HalcyonSettingsProtocol.set_layer_style(
                    self.halcyon_keyboard,
                    target,
                    LayerStyle(self.display_foreground, self.display_background),
                )
            elif scope == DISPLAY_SCOPE_MODIFIER:
                HalcyonSettingsProtocol.set_modifier_style(
                    self.halcyon_keyboard, target, self.display_foreground
                )
            else:
                HalcyonSettingsProtocol.set_dim_style(
                    self.halcyon_keyboard, self.display_foreground
                )
            HalcyonSettingsProtocol.set_timings(
                self.halcyon_keyboard,
                self.pattern_timing.value(),
                self.mod_recent_timing.value(),
            )
            self.display_status.setText(
                "Applied in memory on both halves. Save to Keyboard to persist across reboot."
            )
            return True
        except RuntimeError as exc:
            self.display_status.setText("Apply failed: {}".format(exc))
            return False

    def _save_display_settings(self):
        if not self._apply_display_settings():
            return
        try:
            HalcyonSettingsProtocol.save(self.halcyon_keyboard)
            self.display_status.setText("Saved TFT settings to both halves.")
        except RuntimeError as exc:
            self.display_status.setText("Save failed: {}".format(exc))

    def _reset_display_settings(self):
        if self.halcyon_keyboard is None:
            return
        try:
            HalcyonSettingsProtocol.reset(self.halcyon_keyboard)
            HalcyonSettingsProtocol.save(self.halcyon_keyboard)
            self._load_display_timings()
            self._load_display_style()
            self._refresh_telemetry()
            self.display_status.setText("Restored and saved compiled TFT defaults on both halves.")
        except RuntimeError as exc:
            self.display_status.setText("Reset failed: {}".format(exc))

    def _refresh_telemetry(self):
        if self.halcyon_keyboard is None:
            self._clear_telemetry()
            return
        try:
            telemetry = HalcyonSettingsProtocol.get_telemetry(self.halcyon_keyboard)
            self.telemetry_os.setText(OS_LABELS.get(telemetry.os, "Unknown ({})".format(telemetry.os)))
            self.telemetry_shortcuts.setText(SHORTCUT_LABELS.get(telemetry.shortcut_family, "Unknown"))
            self.telemetry_source.setText(SOURCE_LABELS.get(telemetry.source, "Unknown"))
            self.telemetry_event.setText(EVENT_LABELS.get(telemetry.event, "Unknown"))
            self.telemetry_role.setText("USB master" if telemetry.is_master else "Secondary half")
            self.telemetry_transport.setText("Connected" if telemetry.transport_connected else "Disconnected")
            self.telemetry_tft.setText("Present" if telemetry.tft_present else "Not on USB half")
        except RuntimeError as exc:
            self._clear_telemetry()
            self.display_status.setText("Telemetry refresh failed: {}".format(exc))

    def _clear_telemetry(self):
        for label in (
            self.telemetry_os,
            self.telemetry_shortcuts,
            self.telemetry_source,
            self.telemetry_event,
            self.telemetry_role,
            self.telemetry_transport,
            self.telemetry_tft,
        ):
            label.setText("Unavailable")

    def _nav_button(self, label, editor_label):
        button = QPushButton(label)
        button.clicked.connect(lambda _checked=False, target=editor_label: self.navigate_to_editor(target))
        return button
