# SPDX-License-Identifier: GPL-2.0-or-later

from editor.rgb_profiles import RGBProfiles
from main_window import MainWindow


class CustomMainWindow(MainWindow):
    """Vial main window with keyboard-specific extensions kept outside upstream core."""

    def __init__(self, appctx):
        # MainWindow.__init__ may trigger rebuild() through the initial device
        # refresh, so make the extension sentinel available before calling it.
        self.rgb_profiles = None
        super().__init__(appctx)

        self.rgb_profiles = RGBProfiles()
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
