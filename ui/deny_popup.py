"""Deny popup — Arabic."""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QFrame,
)
from ui.message_box import warn
from ui.theme import theme, ThemedWidget, make_danger, make_secondary, CARD_RADIUS
from ui.i18n import t


class DenyPopup(ThemedWidget, QDialog):
    def __init__(self, player_name, reason, parent=None):
        QDialog.__init__(self, parent)
        self.setWindowTitle(t("dlg.deny.title"))
        self.setModal(True)
        self.setMinimumWidth(420)

        self._override_confirmed = False
        self._override_note = ""

        self._build_ui(player_name, reason)
        self._init_theme()

    def _build_ui(self, player_name, reason):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(12)

        self.name_label = QLabel(player_name)
        layout.addWidget(self.name_label)

        reason_box = QFrame()
        reason_box.setObjectName("reasonBox")
        rl = QVBoxLayout(reason_box)
        rl.setContentsMargins(14, 12, 14, 12)
        self.reason_label = QLabel(t("dlg.deny.reason_prefix", reason=reason))
        self.reason_label.setWordWrap(True)
        rl.addWidget(self.reason_label)
        self.reason_box = reason_box
        layout.addWidget(reason_box)

        self.note_hint = QLabel(t("dlg.deny.note_hint"))
        layout.addWidget(self.note_hint)

        self.note_input = QLineEdit()
        self.note_input.setPlaceholderText(t("dlg.deny.note_placeholder"))
        layout.addWidget(self.note_input)

        button_row = QHBoxLayout()
        button_row.setSpacing(8)
        self.dismiss_button = QPushButton(t("dlg.deny.dismiss"))
        make_secondary(self.dismiss_button)
        self.override_button = QPushButton(t("dlg.deny.override"))
        make_danger(self.override_button)

        button_row.addStretch()
        button_row.addWidget(self.dismiss_button)
        button_row.addWidget(self.override_button)
        layout.addLayout(button_row)

        self.override_button.clicked.connect(self._on_override_clicked)
        self.dismiss_button.clicked.connect(self.reject)

    def restyle(self):
        t_ = theme()
        self.name_label.setStyleSheet(
            f"color: {t_.color('text')}; font-size: 18px; font-weight: 700;"
        )
        self.reason_box.setStyleSheet(
            f"QFrame#reasonBox {{"
            f"  background-color: {t_.color('danger_soft')};"
            f"  border: 1px solid {t_.color('danger')};"
            f"  border-radius: {CARD_RADIUS - 4}px;"
            f"}}"
        )
        self.reason_label.setStyleSheet(
            f"color: {t_.color('danger')}; font-size: 14px; font-weight: 600;"
        )
        self.note_hint.setStyleSheet(
            f"color: {t_.color('text_secondary')}; font-size: 12px; font-weight: 600;"
        )

    def _on_override_clicked(self):
        note = self.note_input.text().strip()
        if not note:
            warn(
                self, t("dlg.deny.note_required_title"),
                t("dlg.deny.note_required_msg"),
            )
            return
        self._override_note = note
        self._override_confirmed = True
        self.accept()

    def result_data(self):
        return self._override_confirmed, (self._override_note or None)