"""QR preview dialog — Arabic."""

import shutil

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QFileDialog,
 QFrame,
)
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt
from ui.message_box import info
from ui.theme import theme, ThemedWidget, make_secondary, CARD_RADIUS
from ui.widgets import StatusPill
from ui.i18n import t


class QRPreviewDialog(ThemedWidget, QDialog):
    def __init__(self, player_name, player_id, qr_path, parent=None):
        QDialog.__init__(self, parent)
        self.qr_path = qr_path
        self.player_name = player_name
        self.setWindowTitle(t("dlg.qr.title"))
        self.setMinimumWidth(360)
        self._build_ui(player_id)
        self._init_theme()

    def _build_ui(self, player_id):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        self.title = QLabel(self.player_name)
        self.title.setWordWrap(True)
        layout.addWidget(self.title)

        header_row = QHBoxLayout()
        self.id_label = QLabel(t("dlg.qr.player_id", player_id=player_id))
        header_row.addWidget(self.id_label)
        header_row.addStretch()
        self.success_pill = StatusPill(t("dlg.qr.created_badge"), "success")
        header_row.addWidget(self.success_pill)
        layout.addLayout(header_row)

        qr_frame = QFrame()
        qr_frame.setObjectName("qrFrame")
        qr_layout = QVBoxLayout(qr_frame)
        qr_layout.setContentsMargins(16, 16, 16, 16)
        self.qr_label = QLabel()
        self.qr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pixmap = QPixmap(self.qr_path).scaled(
            220, 220, Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.qr_label.setPixmap(pixmap)
        qr_layout.addWidget(self.qr_label)
        self.qr_frame = qr_frame
        layout.addWidget(qr_frame)

        self.hint = QLabel(t("dlg.qr.hint"))
        self.hint.setWordWrap(True)
        layout.addWidget(self.hint)

        button_row = QHBoxLayout()
        self.save_as_button = QPushButton(t("dlg.qr.save_as"))
        self.close_button = QPushButton(t("dlg.qr.done"))
        make_secondary(self.save_as_button)
        self.save_as_button.clicked.connect(self._on_save_as)
        self.close_button.clicked.connect(self.accept)
        button_row.addWidget(self.save_as_button)
        button_row.addStretch()
        button_row.addWidget(self.close_button)
        layout.addLayout(button_row)

    def restyle(self):
        t_ = theme()
        self.title.setStyleSheet(
            f"color: {t_.color('text')}; font-size: 18px; font-weight: 700;"
        )
        self.id_label.setStyleSheet(
            f"color: {t_.color('text_secondary')}; font-size: 12px;"
        )
        self.qr_frame.setStyleSheet(
            f"QFrame#qrFrame {{"
            f"  background-color: {t_.color('surface_alt')};"
            f"  border: 1px solid {t_.color('border')};"
            f"  border-radius: {CARD_RADIUS}px;"
            f"}}"
        )
        self.hint.setStyleSheet(
            f"color: {t_.color('text_secondary')}; font-style: italic; font-size: 12px;"
        )

    def _on_save_as(self):
        default_name = f"{self.player_name.replace(' ', '_')}_QR.png"
        dest_path, _ = QFileDialog.getSaveFileName(
            self, t("dlg.qr.save_dialog_title"), default_name, t("dlg.qr.png_filter")
        )
        if dest_path:
            shutil.copy(self.qr_path, dest_path)
            info(
                self, t("dlg.qr.saved_title"),
                t("dlg.qr.saved_msg", path=dest_path),
            )