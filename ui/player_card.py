"""
Player card widget — Arabic.
"""

import os
import sys

from PyQt6.QtWidgets import QVBoxLayout, QHBoxLayout, QLabel, QFrame
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from config.config_loader import get_plan_label, get_group, get_group_label
from ui.theme import theme, ThemedWidget, CARD_RADIUS, BUTTON_RADIUS
from ui.widgets import StatusPill
from ui.i18n import t

PHOTO_SIZE = 120


class PlayerCardWidget(QFrame, ThemedWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("playerCard")
        self._build_ui()
        self._init_theme()

    def _build_ui(self):
        outer = QHBoxLayout(self)
        outer.setContentsMargins(18, 18, 18, 18)
        outer.setSpacing(18)

        self.photo_label = QLabel()
        self.photo_label.setFixedSize(PHOTO_SIZE, PHOTO_SIZE)
        self.photo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.photo_label.setText("لا\nصورة")
        outer.addWidget(self.photo_label)

        info = QVBoxLayout()
        info.setSpacing(2)

        self.name_label = QLabel()
        self.id_label = QLabel()
        self.group_label = QLabel()
        self.plan_label = QLabel()
        self.sessions_label = QLabel()

        pill_row = QHBoxLayout()
        self.status_label = StatusPill("", "muted")
        self.status_label.setVisible(False)
        pill_row.addWidget(self.status_label)
        pill_row.addStretch()

        info.addWidget(self.name_label)
        info.addWidget(self.id_label)
        info.addSpacing(6)
        info.addWidget(self.group_label)
        info.addWidget(self.plan_label)
        info.addWidget(self.sessions_label)
        info.addSpacing(6)
        info.addLayout(pill_row)
        info.addStretch()

        outer.addLayout(info, stretch=1)

    def restyle(self):
        t_ = theme()
        self.setStyleSheet(
            f"QFrame#playerCard {{"
            f"  background-color: {t_.color('surface')};"
            f"  border: 1px solid {t_.color('border')};"
            f"  border-radius: {CARD_RADIUS}px;"
            f"}}"
        )
        self.photo_label.setStyleSheet(
            f"border: 1px solid {t_.color('border')};"
            f"border-radius: {BUTTON_RADIUS}px;"
            f"background-color: {t_.color('surface_alt')};"
            f"color: {t_.color('text_secondary')};"
        )
        self.name_label.setStyleSheet(
            f"color: {t_.color('text')}; font-size: 20px; font-weight: 700;"
        )
        self.id_label.setStyleSheet(
            f"color: {t_.color('text_secondary')}; font-size: 12px;"
        )
        for lbl in (self.group_label, self.plan_label, self.sessions_label):
            lbl.setStyleSheet(
                f"color: {t_.color('text_secondary')}; font-size: 13px;"
            )

    def set_photo(self, photo_path):
        if photo_path and os.path.exists(photo_path):
            pixmap = QPixmap(photo_path).scaled(
                PHOTO_SIZE, PHOTO_SIZE,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.photo_label.setPixmap(pixmap)
        else:
            self.photo_label.setPixmap(QPixmap())
            self.photo_label.setText("لا\nصورة")

    def display_player(self, player, subscription=None, check_in_state=None):
        self.set_photo(player.photo_path)
        self.name_label.setText(player.full_name)
        self.id_label.setText(f"ID: {player.player_id}")

        group = get_group(player.player_group)
        self.group_label.setText(
            t("card.group",
              group=get_group_label(player.player_group),
              time=group["time"])
        )

        if subscription:
            plan_label = get_plan_label(subscription.plan_type)
            self.plan_label.setText(t("card.plan", plan=plan_label))
            self.sessions_label.setText(
                t("card.sessions",
                  remaining=subscription.sessions_remaining,
                  total=subscription.sessions_total)
            )
        else:
            self.plan_label.setText(t("card.plan_none"))
            self.sessions_label.setText(t("card.no_subscription"))

        if check_in_state == "checked_in":
            self.status_label.set_status(t("card.status.checked_in"), "success")
            self.status_label.setVisible(True)
        elif check_in_state == "denied":
            self.status_label.set_status(t("card.status.denied"), "danger")
            self.status_label.setVisible(True)
        else:
            self.status_label.setVisible(False)

    def clear(self):
        self.set_photo(None)
        self.name_label.setText("")
        self.id_label.setText("")
        self.group_label.setText("")
        self.plan_label.setText("")
        self.sessions_label.setText("")
        self.status_label.setVisible(False)