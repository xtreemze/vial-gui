# Copyright 2026 Carlos Velasco
# SPDX-License-Identifier: GPL-2.0-or-later
"""Modal portable palette importer for the Halcyon RGB editor."""

import json
from typing import TYPE_CHECKING, Optional

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QPlainTextEdit,
    QProgressDialog,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from protocol.halcyon_palette import PaletteBatch

if TYPE_CHECKING:
    from protocol.keyboard_comm import Keyboard

MaybeParent = Optional[QWidget]

MAX_DOCUMENT = 100000
FAILURES = (RuntimeError, ValueError, KeyError, TypeError, OSError)


class PaletteDialog(QDialog):
    """Keep preview ownership until save or successful rollback."""

    def __init__(self, keyboard: "Keyboard", parent: MaybeParent = None) -> None:
        """Create the portable document editor and transaction controls."""
        super().__init__(parent)
        self.keyboard = keyboard
        self.batch = None
        self.setWindowTitle("Unified RGB / TFT palette")
        self.setMinimumSize(560, 420)
        layout = QVBoxLayout(self)
        label = QLabel("Paste Vial Web palette JSON. Remove entries to preserve exceptions.")
        label.setWordWrap(True)
        layout.addWidget(label)
        self.document = QPlainTextEdit()
        self.document.setAccessibleName("Portable palette JSON")
        layout.addWidget(self.document)
        self.status = QLabel("Preview uses runtime memory. Save is sequential across stores.")
        self.status.setWordWrap(True)
        self.status.setTextFormat(Qt.PlainText)
        layout.addWidget(self.status)
        self.abandon = QPushButton("Close without restoring")
        self.abandon.clicked.connect(self._abandon)
        self.abandon.hide()
        layout.addWidget(self.abandon)
        self.preview = QPushButton("Preview on keyboard")
        self.save = QPushButton("Save permanently")
        self.restore = QPushButton("Restore previous")
        self.preview.clicked.connect(self._apply)
        self.save.clicked.connect(self._persist)
        self.restore.clicked.connect(self._rollback)
        for button in (self.preview, self.save, self.restore):
            layout.addWidget(button)
        close = QDialogButtonBox(QDialogButtonBox.Close)
        close.rejected.connect(self.reject)
        layout.addWidget(close)
        self._update_buttons()

    def _update_buttons(self) -> None:
        active = self.batch is not None
        self.preview.setEnabled(not active)
        self.document.setEnabled(not active)
        self.save.setEnabled(active and self.batch.applied)
        self.restore.setEnabled(active)

    def _candidate(self) -> PaletteBatch:
        text = self.document.toPlainText()
        if len(text) > MAX_DOCUMENT:
            message = "Palette document is too large"
            raise ValueError(message)
        return PaletteBatch(self.keyboard, json.loads(text))

    def _apply(self) -> None:
        progress = QProgressDialog("Applying palette…", "Cancel", 0, 100, self)
        progress.setWindowModality(Qt.ApplicationModal)
        progress.setMinimumDuration(0)
        try:
            self.batch = self._candidate()
            self.batch.apply(lambda done, total: self._progress(progress, done, total))
            self.status.setText("Runtime preview verified. Save permanently or restore.")
        except FAILURES as error:
            self.status.setText(str(error))
        finally:
            progress.close()
            self._update_buttons()

    @staticmethod
    def _progress(progress: QProgressDialog, done: int, total: int) -> bool:
        progress.setValue(int(done * 100 / max(1, total)))
        QApplication.processEvents()
        return not progress.wasCanceled()

    def _persist(self) -> None:
        try:
            self.batch.save()
            self.batch = None
            self.status.setText("Save acknowledged. Verify persistence on both master halves.")
        except FAILURES as error:
            self.status.setText(f"Save failed; one store may already be persistent: {error}")
        self._update_buttons()

    def _rollback(self) -> bool:
        try:
            if self.batch is not None:
                self.batch.restore()
            self.batch = None
            self.status.setText("Previous runtime palette restored.")
        except FAILURES as error:
            self.status.setText(
                f"Restore incomplete: {error}. Reconnect or close without restoring.",
            )
            self.abandon.show()
        self._update_buttons()
        return self.batch is None

    def _abandon(self) -> None:
        super().reject()

    def reject(self) -> None:
        """Restore an unsaved preview when the dialog closes."""
        if self.batch is None or self._rollback():
            super().reject()


def open_palette_dialog(keyboard: "Keyboard", parent: MaybeParent = None) -> None:
    """Open a connection-scoped modal palette import workflow."""
    PaletteDialog(keyboard, parent).exec_()
