# SPDX-License-Identifier: GPL-2.0-or-later

from editor.rgb_profiles import RGBProfiles
from main_window import MainWindow
from vial_device import VialKeyboard


CUSTOM_BUILD_TITLE = "Vial — xtreemze Halcyon extensions"


class ObservableRGBProfiles(RGBProfiles):
    """Keep the custom editor observable even when firmware probing fails."""

    def valid(self):
        # This fork deliberately keeps the extension tab present. A failed probe
        # is actionable diagnostic state, not a reason to make the custom build
        # visually indistinguishable from upstream Vial.
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
                "xtreemze extended RGB profile protocol v1. Flash firmware containing "
                "the host-editable RGB profile protocol, then reconnect or refresh."
            )
        else:
            self.status.setText(
                "Custom Vial UI is active. Connect the Halcyon Ferris running the "
                "xtreemze firmware to enable extended RGB profile controls."
            )


class CustomMainWindow(MainWindow):
    """Vial main window with keyboard-specific extensions kept outside upstream core."""

    def __init__(self, appctx):
        # MainWindow.__init__ may trigger rebuild() through the initial device
        # refresh, so make the extension sentinel available before calling it.
        self.rgb_profiles = None
        super().__init__(appctx)

        # Keep the fork observable even when no compatible keyboard is connected.
        # The web host also exposes its own build badge/manifest, but this title
        # identifies native builds and makes screenshots/support reports unambiguous.
        self.setWindowTitle(CUSTOM_BUILD_TITLE)

        self.rgb_profiles = ObservableRGBProfiles()
        insert_at = len(self.editors)
        for index, (_editor, label) in enumerate(self.editors):
            if label == "Lighting":
                insert_at = index + 1
                break
        self.editors.insert(insert_at, (self.rgb_profiles, "RGB Profiles"))

        self.rgb_profiles.rebuild(self.autorefresh.current_device)
        self.refresh_tabs()

    def rebuild(self):
        super().rebuild()
        if self.rgb_profiles is not None:
            self.rgb_profiles.rebuild(self.autorefresh.current_device)
