# SPDX-License-Identifier: GPL-2.0-or-later

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from editor.basic_editor import BasicEditor
from editor.rgb_profiles import RGBProfiles
from vial_device import VialKeyboard


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
        # This is an intentionally observable custom-build surface. It remains
        # present when disconnected so firmware/UI mismatch is diagnosable.
        return True

    def rebuild(self, device):
        super().rebuild(device)
        self.rgb_profiles.rebuild(device)

        if not isinstance(device, VialKeyboard):
            self.connection_status.setText(
                "No Vial keyboard selected. Connect the Halcyon Ferris to inspect live capabilities."
            )
            self._set_status_values("Disconnected", "Unavailable", "Unavailable")
            return

        try:
            device_name = device.title()
        except Exception:
            device_name = "Vial keyboard"

        if self.rgb_profiles.capabilities is not None:
            self.connection_status.setText(
                "{} connected. xtreemze firmware extension protocol detected.".format(device_name)
            )
            self._set_status_values("Connected", "RGB profiles v1", "Enabled in firmware")
        else:
            self.connection_status.setText(
                "{} connected, but the xtreemze host-editable RGB protocol was not detected. "
                "Upstream Vial features remain usable; reflash the current firmware to enable "
                "the custom live controls.".format(device_name)
            )
            self._set_status_values("Connected", "Firmware update required", "Firmware-dependent")

    def activate(self):
        self.rgb_profiles.activate()

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
        status_form.addRow("Custom protocol", self.extension_value)
        status_form.addRow("Deterministic encoder-repeat policy", self.encoder_policy_value)
        layout.addWidget(status_group)

        ownership_group = QGroupBox("Where settings live")
        ownership_layout = QVBoxLayout(ownership_group)
        ownership = QLabel(
            "RGB profile precedence and per-layer/modifier/combo colors are configured here. "
            "Encoder assignments use Keymap, ordered Repeat/Alternate Repeat pairs use Alt Repeat Key, "
            "and standard lighting uses Lighting. The Halcyon TFT currently renders its layer patterns, "
            "modifier indicators, host-OS telemetry, and trace view from firmware-managed settings."
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

        behavior_group = QGroupBox("TFT display behavior")
        behavior_layout = QVBoxLayout(behavior_group)
        behavior = QLabel(
            "The current Halcyon TFT firmware has 13 animated layer styles, foreground/background "
            "HSV palettes, modifier and modifier-combination indicators, recent-modifier persistence, "
            "host OS/shortcut-family telemetry, and an OS fingerprint trace view. These values are "
            "currently compiled into firmware rather than stored through a host settings protocol."
        )
        behavior.setWordWrap(True)
        behavior_layout.addWidget(behavior)
        layout.addWidget(behavior_group)

        modules_group = QGroupBox("Module configuration")
        modules_layout = QVBoxLayout(modules_group)
        modules = QLabel(
            "Use Layout to select the Halcyon module arrangement. The current compiled default uses "
            "the right encoder module and supports the left TFT module path."
        )
        modules.setWordWrap(True)
        modules_layout.addWidget(modules)
        modules_layout.addWidget(self._nav_button("Open Layout", "Layout"), 0, Qt.AlignLeft)
        layout.addWidget(modules_group)

        os_group = QGroupBox("OS-aware shortcuts and diagnostics")
        os_layout = QVBoxLayout(os_group)
        os_text = QLabel(
            "The firmware automatically stabilizes Apple vs Ctrl-style shortcut families across "
            "macOS/iOS and Windows/Linux, persists the confirmed family, and guards resume transitions. "
            "The custom OS_TRACE_VIEW keycode toggles the TFT fingerprint diagnostics when that build "
            "feature is enabled. No manual host-family override is exposed because automatic detection "
            "is the current firmware contract."
        )
        os_text.setWordWrap(True)
        os_layout.addWidget(os_text)
        os_layout.addWidget(self._nav_button("Open Keymap", "Keymap"), 0, Qt.AlignLeft)
        layout.addWidget(os_group)

        layout.addStretch(1)
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

    def _nav_button(self, label, editor_label):
        button = QPushButton(label)
        button.clicked.connect(lambda _checked=False, target=editor_label: self.navigate_to_editor(target))
        return button
