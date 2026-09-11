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
    QLineEdit,
    QPushButton,
    QSlider,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from editor.basic_editor import BasicEditor
from editor.rgb_configurator import VIALRGB_EFFECTS
from editor.rgb_profiles import RGBProfiles
from protocol.halcyon_display import (
    DisplayLayer,
    DisplayPattern,
    HalcyonDisplayProtocol,
)
from protocol.halcyon_settings import (
    HSV,
    HalcyonSettingsProtocol,
    LayerStyle,
)
from vial_device import VialKeyboard
from widgets.clickable_label import ClickableLabel


MODIFIER_NAMES = (
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

MOTIF_NAMES = (
    "Pulse Diamond",
    "Cardinal Cluster",
    "Diamond Ring",
    "Horizontal Pair",
    "Vertical Pair",
    "Corner Satellites",
    "Diagonal Cross",
    "Horizontal Edge Nodes",
    "Vertical Edge Nodes",
    "Cardinal Orbit",
    "Wide Pulse Pair",
    "Corner Frame",
    "Diagonal Pair",
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


def qmk_matrix_effect_name(mode):
    """Map QMK RGB Matrix mode numbers to the names Vial already exposes.

    VialRGB inserts Direct Control at index 1; native QMK RGB Matrix does not.
    Therefore QMK mode 1 (Solid Color) maps to VialRGB effect index 2.
    """
    mode = int(mode)
    if mode == 0:
        return "Off"
    vial_index = mode + 1
    if 0 <= vial_index < len(VIALRGB_EFFECTS):
        return VIALRGB_EFFECTS[vial_index].name
    return "Unknown RGB Matrix effect ({})".format(mode)


def _hsv_color(hsv):
    return QColor.fromHsvF(
        hsv.hue / 255.0,
        hsv.saturation / 255.0,
        max(1, hsv.value) / 255.0,
    )


def _set_color_field(field, hsv):
    field.setStyleSheet("QWidget { background-color: %s; }" % _hsv_color(hsv).name())
    field.setToolTip("H {}  S {}  V {}".format(hsv.hue, hsv.saturation, hsv.value))


def _hsv_from_qcolor(color, keep_value=None):
    hue, saturation, value, _alpha = color.getHsvF()
    if hue < 0:
        hue = 0
    byte_value = int(round(255 * value)) if keep_value is None else int(keep_value)
    return HSV(
        min(255, max(0, int(round(255 * hue)))),
        min(255, max(0, int(round(255 * saturation)))),
        min(255, max(0, byte_value)),
    )


class VialStyleRGBProfiles(RGBProfiles):
    """Extended RGB profiles using Vial's own RGB control vocabulary and dialog model."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.dlg_color = None

        # Match Vial's Lighting editor: a clickable color well plus a non-blocking
        # QColorDialog. The previous blocking getColor() path is unsuitable in WASM.
        old_color = self.color
        self.form.removeWidget(old_color)
        old_color.deleteLater()
        self.color = ClickableLabel(" ")
        self.color.setMinimumHeight(24)
        self.color.clicked.connect(self._choose_color)
        self.form.addWidget(self.color, 3, 1)

    def valid(self):
        return True

    def rebuild(self, device):
        super().rebuild(device)
        if self.capabilities is None:
            self._set_profile_controls_enabled(False)
            self.scope.clear()
            self.target.clear()
            self.effect.clear()
            if isinstance(device, VialKeyboard):
                self.status.setText(
                    "This keyboard does not expose xtreemze RGB Profiles v1. "
                    "Standard Vial Lighting remains independent of this extension."
                )
            else:
                self.status.setText("Connect the Halcyon Ferris to edit RGB profiles.")
            return

        self._loading = True
        self.effect.clear()
        for mode in range(0, self.capabilities.maximum_mode + 1):
            self.effect.addItem(qmk_matrix_effect_name(mode), mode)
        self._loading = False
        self._load_profile()
        self.status.setText("RGB Profiles v1 detected; effect names and color controls use Vial's Lighting model.")

    def _choose_color(self):
        if self.profile is None:
            return
        self.dlg_color = QColorDialog()
        self.dlg_color.setModal(True)
        self.dlg_color.finished.connect(self._color_finished)
        current = HSV(self.profile.hue, self.profile.saturation, max(1, self.profile.brightness))
        self.dlg_color.setCurrentColor(_hsv_color(current))
        self.dlg_color.show()

    def _color_finished(self, _result=None):
        if self.dlg_color is None or self.profile is None:
            return
        color = self.dlg_color.selectedColor()
        if not color.isValid():
            return
        selected = _hsv_from_qcolor(color, keep_value=self.profile.brightness)
        self.profile.hue = selected.hue
        self.profile.saturation = selected.saturation
        self._update_color_button()

    def _update_color_button(self):
        if self.profile is None:
            return
        _set_color_field(
            self.color,
            HSV(self.profile.hue, self.profile.saturation, max(1, self.profile.brightness)),
        )


class HalcyonEditor(BasicEditor):
    """Editors only for capabilities that are genuinely additional to upstream Vial."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.rgb_profiles = VialStyleRGBProfiles()
        self.keyboard = None
        self.settings_caps = None
        self.display_caps = None
        self.layer_style = None
        self.layer_display = None
        self.modifier_color = None
        self.dim_color = None
        self._loading = False
        self._color_dialog = None
        self._color_target = None

        title = QLabel("Halcyon")
        title.setStyleSheet("font-size: 18px; font-weight: 600;")
        self.addWidget(title)

        subtitle = QLabel(
            "Only Halcyon-specific state is edited here. Standard keymap, encoder, "
            "Alt Repeat, combo, QMK Settings and VialRGB controls remain in their native Vial editors."
        )
        subtitle.setWordWrap(True)
        self.addWidget(subtitle)

        self.connection_status = QLabel("")
        self.connection_status.setWordWrap(True)
        self.addWidget(self.connection_status)

        self.sections = QTabWidget()
        self.sections.addTab(self._build_rgb_page(), "RGB Profiles")
        self.sections.addTab(self._build_layers_page(), "TFT Layers")
        self.sections.addTab(self._build_modifiers_page(), "TFT Modifiers")
        self.sections.addTab(self._build_host_page(), "Host & Split")
        self.addWidget(self.sections, 1)

    def valid(self):
        return True

    def rebuild(self, device):
        super().rebuild(device)
        self.rgb_profiles.rebuild(device)
        self.keyboard = None
        self.settings_caps = None
        self.display_caps = None
        self._set_tft_enabled(False)
        self._clear_host_values()

        if not isinstance(device, VialKeyboard):
            self.connection_status.setText("Connect the Halcyon Ferris to edit its custom firmware state.")
            return

        self.keyboard = device.keyboard
        self.settings_caps = HalcyonSettingsProtocol.probe(self.keyboard)
        self.display_caps = HalcyonDisplayProtocol.probe(self.keyboard)

        detected = []
        if self.rgb_profiles.capabilities is not None:
            detected.append("RGB Profiles v1")
        if self.settings_caps is not None:
            detected.append("TFT palette/timing v1")
        if self.display_caps is not None:
            detected.append("TFT labels/patterns v1")

        if detected:
            self.connection_status.setText("Live extensions: {}.".format(", ".join(detected)))
        else:
            self.connection_status.setText(
                "No xtreemze Halcyon extensions were detected. Flash current firmware and reconnect."
            )

        if self.settings_caps is not None and self.display_caps is not None:
            self._configure_tft_ranges()
            self._set_tft_enabled(True)
            self._populate_layer_targets()
            self._populate_modifier_targets()
            self._load_layer()
            self._load_modifier()
        else:
            self.layer_status.setText("Current firmware is required for TFT label and pattern editing.")
            self.modifier_status.setText("Current firmware is required for TFT modifier editing.")

        if self.settings_caps is not None:
            self._refresh_host()

    def activate(self):
        self.rgb_profiles.activate()
        if self.keyboard is not None and self.settings_caps is not None:
            self._refresh_host()

    def deactivate(self):
        self.rgb_profiles.deactivate()

    def on_container_clicked(self):
        if self.sections.currentWidget() is self.rgb_page:
            self.rgb_profiles.on_container_clicked()

    def _build_rgb_page(self):
        self.rgb_page = QWidget()
        self.rgb_page.setLayout(self.rgb_profiles)
        return self.rgb_page

    def _build_layers_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)

        group = QGroupBox("Layer indicator and procedural animation")
        form = QFormLayout(group)

        self.layer_target = QComboBox()
        self.layer_target.currentIndexChanged.connect(self._load_layer)
        form.addRow("Layer", self.layer_target)

        self.layer_label = QLineEdit()
        form.addRow("Display label", self.layer_label)

        self.layer_foreground = ClickableLabel(" ")
        self.layer_foreground.setMinimumHeight(24)
        self.layer_foreground.clicked.connect(lambda: self._open_color("layer_foreground"))
        form.addRow("Foreground", self.layer_foreground)

        self.layer_background = ClickableLabel(" ")
        self.layer_background.setMinimumHeight(24)
        self.layer_background.clicked.connect(lambda: self._open_color("layer_background"))
        form.addRow("Background", self.layer_background)

        self.layer_motif = QComboBox()
        for index, name in enumerate(MOTIF_NAMES):
            self.layer_motif.addItem(name, index)
        form.addRow("Pattern", self.layer_motif)

        self.tile_width, self.tile_width_value, row = self._slider_row(12, 48, 1, "24 px")
        form.addRow("Tile width", row)
        self.tile_height, self.tile_height_value, row = self._slider_row(12, 48, 1, "24 px")
        form.addRow("Tile height", row)
        self.motion, self.motion_value, row = self._slider_row(0, 6, 1, "1 px")
        form.addRow("Motion amplitude", row)
        self.pulse, self.pulse_value, row = self._slider_row(0, 4, 1, "1 px")
        form.addRow("Pulse amplitude", row)
        self.pattern_frame, self.pattern_frame_value, row = self._slider_row(50, 1000, 10, "200 ms")
        form.addRow("Animation frame", row)

        self.tile_width.valueChanged.connect(lambda value: self.tile_width_value.setText("{} px".format(value)))
        self.tile_height.valueChanged.connect(lambda value: self.tile_height_value.setText("{} px".format(value)))
        self.motion.valueChanged.connect(lambda value: self.motion_value.setText("{} px".format(value)))
        self.pulse.valueChanged.connect(lambda value: self.pulse_value.setText("{} px".format(value)))
        self.pattern_frame.valueChanged.connect(lambda value: self.pattern_frame_value.setText("{} ms".format(value)))

        layout.addWidget(group)

        buttons = QHBoxLayout()
        self.layer_apply = QPushButton("Apply")
        self.layer_apply.clicked.connect(self._apply_layer)
        buttons.addWidget(self.layer_apply)
        self.layer_save = QPushButton("Save to Keyboard")
        self.layer_save.clicked.connect(self._save_layer)
        buttons.addWidget(self.layer_save)
        self.layer_reset = QPushButton("Reset TFT Defaults")
        self.layer_reset.clicked.connect(self._reset_tft)
        buttons.addWidget(self.layer_reset)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        self.layer_status = QLabel("")
        self.layer_status.setWordWrap(True)
        layout.addWidget(self.layer_status)
        layout.addStretch(1)
        return page

    def _build_modifiers_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)

        group = QGroupBox("Modifier indicator")
        form = QFormLayout(group)

        self.modifier_target = QComboBox()
        self.modifier_target.currentIndexChanged.connect(self._load_modifier)
        form.addRow("Modifier", self.modifier_target)

        self.modifier_label = QLineEdit()
        form.addRow("Display label", self.modifier_label)

        self.modifier_active = ClickableLabel(" ")
        self.modifier_active.setMinimumHeight(24)
        self.modifier_active.clicked.connect(lambda: self._open_color("modifier_active"))
        form.addRow("Active color", self.modifier_active)

        self.modifier_dim = ClickableLabel(" ")
        self.modifier_dim.setMinimumHeight(24)
        self.modifier_dim.clicked.connect(lambda: self._open_color("modifier_dim"))
        form.addRow("Inactive / dim color", self.modifier_dim)

        self.modifier_recent, self.modifier_recent_value, row = self._slider_row(0, 10000, 100, "2.20 s")
        self.modifier_recent.valueChanged.connect(
            lambda value: self.modifier_recent_value.setText("{:.2f} s".format(value / 1000.0))
        )
        form.addRow("Recent visibility", row)
        layout.addWidget(group)

        buttons = QHBoxLayout()
        self.modifier_apply = QPushButton("Apply")
        self.modifier_apply.clicked.connect(self._apply_modifier)
        buttons.addWidget(self.modifier_apply)
        self.modifier_save = QPushButton("Save to Keyboard")
        self.modifier_save.clicked.connect(self._save_modifier)
        buttons.addWidget(self.modifier_save)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        self.modifier_status = QLabel("")
        self.modifier_status.setWordWrap(True)
        layout.addWidget(self.modifier_status)
        layout.addStretch(1)
        return page

    def _build_host_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        group = QGroupBox("Host and split telemetry")
        form = QFormLayout(group)
        self.host_os = QLabel("Unavailable")
        self.host_shortcuts = QLabel("Unavailable")
        self.host_source = QLabel("Unavailable")
        self.host_event = QLabel("Unavailable")
        self.host_role = QLabel("Unavailable")
        self.host_transport = QLabel("Unavailable")
        self.host_tft = QLabel("Unavailable")
        form.addRow("Detected OS", self.host_os)
        form.addRow("Shortcut family", self.host_shortcuts)
        form.addRow("Detection source", self.host_source)
        form.addRow("Last host event", self.host_event)
        form.addRow("Keyboard role", self.host_role)
        form.addRow("Split transport", self.host_transport)
        form.addRow("TFT capability", self.host_tft)
        self.host_refresh = QPushButton("Refresh")
        self.host_refresh.clicked.connect(self._refresh_host)
        form.addRow("", self.host_refresh)
        layout.addWidget(group)
        layout.addStretch(1)
        return page

    @staticmethod
    def _slider_row(minimum, maximum, step, text):
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        slider = QSlider(Qt.Horizontal)
        slider.setRange(minimum, maximum)
        slider.setSingleStep(step)
        slider.setPageStep(max(step, (maximum - minimum) // 10))
        value = QLabel(text)
        layout.addWidget(slider, 1)
        layout.addWidget(value)
        return slider, value, row

    def _configure_tft_ranges(self):
        self.layer_label.setMaxLength(self.display_caps.layer_label_max)
        self.modifier_label.setMaxLength(self.display_caps.modifier_label_max)
        self.tile_width.setRange(self.display_caps.tile_min, self.display_caps.tile_max)
        self.tile_height.setRange(self.display_caps.tile_min, self.display_caps.tile_max)
        self.motion.setRange(0, self.display_caps.motion_max)
        self.pulse.setRange(0, self.display_caps.pulse_max)
        self.pattern_frame.setRange(self.settings_caps.pattern_min_ms, self.settings_caps.pattern_max_ms)
        self.modifier_recent.setRange(0, self.settings_caps.modifier_recent_max_ms)

        self.layer_motif.clear()
        for index in range(self.display_caps.motif_count):
            name = MOTIF_NAMES[index] if index < len(MOTIF_NAMES) else "Motif {}".format(index + 1)
            self.layer_motif.addItem(name, index)

    def _populate_layer_targets(self):
        self._loading = True
        self.layer_target.clear()
        for index in range(self.display_caps.layer_count):
            self.layer_target.addItem("Layer {}".format(index), index)
        self._loading = False

    def _populate_modifier_targets(self):
        self._loading = True
        self.modifier_target.clear()
        for index in range(self.display_caps.modifier_count):
            name = MODIFIER_NAMES[index] if index < len(MODIFIER_NAMES) else "Modifier {}".format(index + 1)
            self.modifier_target.addItem(name, index)
        self._loading = False

    def _load_layer(self, _index=None):
        if self._loading or not self._tft_ready() or self.layer_target.currentIndex() < 0:
            return
        index = self.layer_target.currentData()
        try:
            self.layer_display = HalcyonDisplayProtocol.get_layer(
                self.keyboard, index, self.display_caps.layer_label_max
            )
            self.layer_style = HalcyonSettingsProtocol.get_layer_style(self.keyboard, index)
            pattern_frame, _recent = HalcyonSettingsProtocol.get_timings(self.keyboard)
        except (RuntimeError, ValueError) as exc:
            self.layer_status.setText("Could not read layer settings: {}".format(exc))
            return

        self._loading = True
        self.layer_label.setText(self.layer_display.label)
        self.layer_target.setItemText(
            self.layer_target.currentIndex(), "Layer {} — {}".format(index, self.layer_display.label)
        )
        _set_color_field(self.layer_foreground, self.layer_style.foreground)
        _set_color_field(self.layer_background, self.layer_style.background)
        motif_index = self.layer_motif.findData(self.layer_display.pattern.motif)
        self.layer_motif.setCurrentIndex(max(0, motif_index))
        self.tile_width.setValue(self.layer_display.pattern.tile_width)
        self.tile_height.setValue(self.layer_display.pattern.tile_height)
        self.motion.setValue(self.layer_display.pattern.motion_amplitude)
        self.pulse.setValue(self.layer_display.pattern.pulse_amplitude)
        self.pattern_frame.setValue(pattern_frame)
        self._loading = False
        self.layer_status.setText("Live TFT layer settings loaded from the keyboard.")

    def _load_modifier(self, _index=None):
        if self._loading or not self._tft_ready() or self.modifier_target.currentIndex() < 0:
            return
        index = self.modifier_target.currentData()
        try:
            label = HalcyonDisplayProtocol.get_modifier_label(
                self.keyboard, index, self.display_caps.modifier_label_max
            )
            self.modifier_color = HalcyonSettingsProtocol.get_modifier_style(self.keyboard, index)
            self.dim_color = HalcyonSettingsProtocol.get_dim_style(self.keyboard)
            _pattern_frame, recent = HalcyonSettingsProtocol.get_timings(self.keyboard)
        except (RuntimeError, ValueError) as exc:
            self.modifier_status.setText("Could not read modifier settings: {}".format(exc))
            return

        self._loading = True
        self.modifier_label.setText(label)
        _set_color_field(self.modifier_active, self.modifier_color)
        _set_color_field(self.modifier_dim, self.dim_color)
        self.modifier_recent.setValue(recent)
        self._loading = False
        self.modifier_status.setText("Live TFT modifier settings loaded from the keyboard.")

    def _open_color(self, target):
        hsv = {
            "layer_foreground": None if self.layer_style is None else self.layer_style.foreground,
            "layer_background": None if self.layer_style is None else self.layer_style.background,
            "modifier_active": self.modifier_color,
            "modifier_dim": self.dim_color,
        }.get(target)
        if hsv is None:
            return
        self._color_target = target
        self._color_dialog = QColorDialog()
        self._color_dialog.setModal(True)
        self._color_dialog.finished.connect(self._color_finished)
        self._color_dialog.setCurrentColor(_hsv_color(hsv))
        self._color_dialog.show()

    def _color_finished(self, _result=None):
        if self._color_dialog is None or self._color_target is None:
            return
        color = self._color_dialog.selectedColor()
        if not color.isValid():
            return
        hsv = _hsv_from_qcolor(color)
        if self._color_target == "layer_foreground" and self.layer_style is not None:
            self.layer_style.foreground = hsv
            _set_color_field(self.layer_foreground, hsv)
        elif self._color_target == "layer_background" and self.layer_style is not None:
            self.layer_style.background = hsv
            _set_color_field(self.layer_background, hsv)
        elif self._color_target == "modifier_active":
            self.modifier_color = hsv
            _set_color_field(self.modifier_active, hsv)
        elif self._color_target == "modifier_dim":
            self.dim_color = hsv
            _set_color_field(self.modifier_dim, hsv)

    def _apply_layer(self):
        if not self._tft_ready() or self.layer_style is None:
            return False
        index = self.layer_target.currentData()
        pattern = DisplayPattern(
            self.layer_motif.currentData(),
            self.tile_width.value(),
            self.tile_height.value(),
            self.motion.value(),
            self.pulse.value(),
        )
        layer = DisplayLayer(self.layer_label.text(), pattern)
        try:
            HalcyonDisplayProtocol.set_layer(
                self.keyboard, index, layer, self.display_caps.layer_label_max
            )
            HalcyonSettingsProtocol.set_layer_style(self.keyboard, index, self.layer_style)
            _old_frame, recent = HalcyonSettingsProtocol.get_timings(self.keyboard)
            HalcyonSettingsProtocol.set_timings(self.keyboard, self.pattern_frame.value(), recent)
        except (RuntimeError, ValueError) as exc:
            self.layer_status.setText("Apply failed: {}".format(exc))
            return False
        self.layer_display = layer
        self.layer_target.setItemText(
            self.layer_target.currentIndex(), "Layer {} — {}".format(index, layer.label)
        )
        self.layer_status.setText("Applied in memory. Save to persist on both halves.")
        return True

    def _save_layer(self):
        if not self._apply_layer():
            return
        try:
            HalcyonSettingsProtocol.save(self.keyboard)
            HalcyonDisplayProtocol.save(self.keyboard)
            self.layer_status.setText("Saved layer palette, label and procedural animation to both halves.")
        except RuntimeError as exc:
            self.layer_status.setText("Save failed: {}".format(exc))

    def _apply_modifier(self):
        if not self._tft_ready() or self.modifier_color is None or self.dim_color is None:
            return False
        index = self.modifier_target.currentData()
        try:
            HalcyonDisplayProtocol.set_modifier_label(
                self.keyboard, index, self.modifier_label.text(), self.display_caps.modifier_label_max
            )
            HalcyonSettingsProtocol.set_modifier_style(self.keyboard, index, self.modifier_color)
            HalcyonSettingsProtocol.set_dim_style(self.keyboard, self.dim_color)
            frame, _old_recent = HalcyonSettingsProtocol.get_timings(self.keyboard)
            HalcyonSettingsProtocol.set_timings(self.keyboard, frame, self.modifier_recent.value())
        except (RuntimeError, ValueError) as exc:
            self.modifier_status.setText("Apply failed: {}".format(exc))
            return False
        self.modifier_status.setText("Applied in memory. Save to persist on both halves.")
        return True

    def _save_modifier(self):
        if not self._apply_modifier():
            return
        try:
            HalcyonSettingsProtocol.save(self.keyboard)
            HalcyonDisplayProtocol.save(self.keyboard)
            self.modifier_status.setText("Saved modifier label, colors and persistence to both halves.")
        except RuntimeError as exc:
            self.modifier_status.setText("Save failed: {}".format(exc))

    def _reset_tft(self):
        if not self._tft_ready():
            return
        try:
            HalcyonSettingsProtocol.reset(self.keyboard)
            HalcyonDisplayProtocol.reset(self.keyboard)
            HalcyonSettingsProtocol.save(self.keyboard)
            HalcyonDisplayProtocol.save(self.keyboard)
            self._load_layer()
            self._load_modifier()
            self.layer_status.setText("Restored and saved compiled TFT defaults.")
        except RuntimeError as exc:
            self.layer_status.setText("Reset failed: {}".format(exc))

    def _refresh_host(self):
        if self.keyboard is None or self.settings_caps is None:
            self._clear_host_values()
            return
        try:
            telemetry = HalcyonSettingsProtocol.get_telemetry(self.keyboard)
        except RuntimeError as exc:
            self.host_os.setText("Read failed: {}".format(exc))
            return
        self.host_os.setText(OS_LABELS.get(telemetry.os, "Unknown ({})".format(telemetry.os)))
        self.host_shortcuts.setText(SHORTCUT_LABELS.get(telemetry.shortcut_family, "Unknown"))
        self.host_source.setText(SOURCE_LABELS.get(telemetry.source, "Unknown"))
        self.host_event.setText(EVENT_LABELS.get(telemetry.event, "Unknown"))
        self.host_role.setText("Master" if telemetry.is_master else "Slave")
        self.host_transport.setText("Connected" if telemetry.transport_connected else "Disconnected")
        self.host_tft.setText("Present" if telemetry.tft_present else "Not present on this half")

    def _clear_host_values(self):
        for widget in (
            self.host_os,
            self.host_shortcuts,
            self.host_source,
            self.host_event,
            self.host_role,
            self.host_transport,
            self.host_tft,
        ):
            widget.setText("Unavailable")

    def _tft_ready(self):
        return self.keyboard is not None and self.settings_caps is not None and self.display_caps is not None

    def _set_tft_enabled(self, enabled):
        widgets = (
            self.layer_target,
            self.layer_label,
            self.layer_foreground,
            self.layer_background,
            self.layer_motif,
            self.tile_width,
            self.tile_height,
            self.motion,
            self.pulse,
            self.pattern_frame,
            self.layer_apply,
            self.layer_save,
            self.layer_reset,
            self.modifier_target,
            self.modifier_label,
            self.modifier_active,
            self.modifier_dim,
            self.modifier_recent,
            self.modifier_apply,
            self.modifier_save,
        )
        for widget in widgets:
            widget.setEnabled(enabled)
