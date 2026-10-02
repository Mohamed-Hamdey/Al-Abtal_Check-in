"""
Player list screen — Arabic.
"""

import os
import sys

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QStackedWidget, QComboBox, QLabel,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from config.config_loader import load_config, get_group_label, get_plan_label
from repositories import players_repo
from services import subscription_service
from ui.dialogs.player_form_dialog import PlayerFormDialog
from ui.screens.player_detail_screen import PlayerDetailScreen
from ui.dialogs.qr_preview_dialog import QRPreviewDialog
from ui.theme import theme, ThemedWidget, GUTTER
from ui.i18n import t


# Map DB status keys → translation keys
_STATUS_KEY = {
    "active":    "players.status.active",
    "expired":   "players.status.expired",
    "suspended": "players.status.suspended",
    "none":      "players.status.none",
}


class PlayerListScreen(ThemedWidget, QWidget):
    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self._build_ui()
        self.refresh()
        self._init_theme()

    def _build_ui(self):
        self.stack = QStackedWidget()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(GUTTER, GUTTER, GUTTER, GUTTER)
        outer.addWidget(self.stack)

        list_page = QWidget()
        layout = QVBoxLayout(list_page)
        layout.setSpacing(14)

        title_row = QHBoxLayout()
        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        self.title = QLabel(t("players.title"))
        self.subtitle = QLabel(t("players.subtitle"))
        title_col.addWidget(self.title)
        title_col.addWidget(self.subtitle)
        title_row.addLayout(title_col)
        title_row.addStretch()

        add_button = QPushButton(t("players.add_player"))
        add_button.clicked.connect(self._on_add_player)
        title_row.addWidget(add_button)
        layout.addLayout(title_row)

        filters_row = QHBoxLayout()
        filters_row.setSpacing(8)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(t("players.search.placeholder"))
        self.search_input.textChanged.connect(self.refresh)
        self.search_input.setMinimumWidth(220)

        config = load_config()

        self.group_filter = QComboBox()
        self.group_filter.addItem(t("players.filter.all_groups"), None)
        for key, group in config["groups"].items():
            self.group_filter.addItem(get_group_label(key), key)
        self.group_filter.currentIndexChanged.connect(self.refresh)

        self.plan_filter = QComboBox()
        self.plan_filter.addItem(t("players.filter.all_plans"), None)
        for key, plan in config["plans"].items():
            self.plan_filter.addItem(get_plan_label(key), key)
        self.plan_filter.currentIndexChanged.connect(self.refresh)

        self.status_filter = QComboBox()
        self.status_filter.addItem(t("players.filter.all_statuses"), None)
        for key in ("active", "expired", "suspended", "none"):
            self.status_filter.addItem(t(_STATUS_KEY[key]), key)
        self.status_filter.currentIndexChanged.connect(self.refresh)

        filters_row.addWidget(self.search_input, stretch=1)
        filters_row.addWidget(self.group_filter)
        filters_row.addWidget(self.plan_filter)
        filters_row.addWidget(self.status_filter)
        layout.addLayout(filters_row)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels([
            t("players.col.id"),
            t("players.col.name"),
            t("players.col.group"),
            t("players.col.plan"),
            t("players.col.sessions"),
            t("players.col.status"),
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.table.cellDoubleClicked.connect(self._on_row_double_clicked)
        layout.addWidget(self.table, stretch=1)

        self.stack.addWidget(list_page)
        self.stack.setCurrentIndex(0)

    # ---------- theme ----------

    def restyle(self):
        t_ = theme()
        self.title.setStyleSheet(
            f"QLabel {{ color: {t_.color('text')}; background-color: transparent;"
            f" font-size: 22px; font-weight: 700; }}"
        )
        self.subtitle.setStyleSheet(
            f"QLabel {{ color: {t_.color('text_secondary')}; background-color: transparent;"
            f" font-size: 13px; }}"
        )
        if hasattr(self, "_status_items"):
            self._repaint_status_items()

    def _repaint_status_items(self):
        t_ = theme()
        token_colors = {
            "active":    t_.color("success"),
            "expired":   t_.color("danger"),
            "suspended": t_.color("warning"),
            "none":      t_.color("muted"),
        }
        soft_bg = {
            "active":    t_.color("success_soft"),
            "expired":   t_.color("danger_soft"),
            "suspended": t_.color("warning_soft"),
            "none":      t_.color("surface_alt"),
        }
        for item, kind in self._status_items:
            item.setForeground(QColor(token_colors[kind]))
            item.setBackground(QColor(soft_bg[kind]))

    # ---------- data ----------

    def refresh(self):
        search_text = self.search_input.text().strip()
        players = players_repo.search_by_name(search_text) if search_text else players_repo.list_all()

        group_filter = self.group_filter.currentData()
        plan_filter = self.plan_filter.currentData()
        status_filter = self.status_filter.currentData()

        rows = []
        for player in players:
            if group_filter and player.player_group != group_filter:
                continue
            display = subscription_service.get_display_status(player.player_id)
            if plan_filter and display["plan_type"] != plan_filter:
                continue
            if status_filter and display["status"] != status_filter:
                continue
            rows.append((player, display))

        self._render_rows(rows)

    def _render_rows(self, rows):
        self.table.setRowCount(len(rows))
        self._current_rows = [player for player, _ in rows]
        self._status_items = []

        for i, (player, display) in enumerate(rows):
            self.table.setItem(i, 0, QTableWidgetItem(str(player.player_id)))
            self.table.setItem(i, 1, QTableWidgetItem(player.full_name))

            self.table.setItem(i, 2, QTableWidgetItem(get_group_label(player.player_group)))

            if display["plan_type"]:
                self.table.setItem(i, 3, QTableWidgetItem(get_plan_label(display["plan_type"])))
                self.table.setItem(
                    i, 4,
                    QTableWidgetItem(f"{display['sessions_remaining']}/{display['sessions_total']}")
                )
            else:
                dash = t("players.col.dash")
                self.table.setItem(i, 3, QTableWidgetItem(dash))
                self.table.setItem(i, 4, QTableWidgetItem(dash))

            status_item = QTableWidgetItem(t(_STATUS_KEY.get(display["status"], "players.status.none")))
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(i, 5, status_item)
            self._status_items.append((status_item, display["status"]))

        self._repaint_status_items()

    # ---------- actions ----------

    def _on_add_player(self):
        dialog = PlayerFormDialog(parent=self)
        if dialog.exec():
            self.refresh()
            qr_path = getattr(dialog, "newly_created_qr_path", None)
            if qr_path:
                name = dialog.name_input.text().strip()
                preview = QRPreviewDialog(name, dialog.saved_player_id, qr_path, parent=self)
                preview.exec()

    def _on_row_double_clicked(self, row: int, column: int):
        player = self._current_rows[row]
        self._open_detail(player.player_id)

    def _open_detail(self, player_id: int):
        detail = PlayerDetailScreen(player_id, on_back=self._close_detail, parent=self)
        self.stack.addWidget(detail)
        self.stack.setCurrentWidget(detail)

    def _close_detail(self):
        current = self.stack.currentWidget()
        self.stack.setCurrentIndex(0)
        self.stack.removeWidget(current)
        current.deleteLater()
        self.refresh()