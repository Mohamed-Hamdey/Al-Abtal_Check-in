"""
Progress panel — Arabic.
"""

import os
import sys
import calendar
from datetime import date, datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGroupBox, QGridLayout,
    QTableWidget, QTableWidgetItem, QHeaderView, QComboBox,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from config.config_loader import get_plan, get_plan_label
from models.subscription import get_subscription_history, get_active_subscription
from models.attendance import get_attendance_for_player
from ui.theme import theme, ThemedWidget
from ui.widgets import StatCard
from ui.i18n import t

MONTH_KEYS = [
    "month.january", "month.february", "month.march", "month.april",
    "month.may", "month.june", "month.july", "month.august",
    "month.september", "month.october", "month.november", "month.december",
]

# English weekday name → i18n key. Used to test membership in the plan's
# allowed_days list (which stays English in the config), while displaying
# the localized name.
WEEKDAY_KEYS = {
    "Monday":    "weekday.monday",
    "Tuesday":   "weekday.tuesday",
    "Wednesday": "weekday.wednesday",
    "Thursday":  "weekday.thursday",
    "Friday":    "weekday.friday",
    "Saturday":  "weekday.saturday",
    "Sunday":    "weekday.sunday",
}


class ProgressPanel(ThemedWidget, QWidget):
    def __init__(self, player_id, parent=None):
        QWidget.__init__(self, parent)
        self.player_id = player_id
        self._build_ui()
        self._init_theme()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(14)

        counters_row = QHBoxLayout()
        counters_row.setSpacing(12)
        self.total_card = StatCard(t("progress.total"), "0", accent="primary")
        self.cycle_card = StatCard(t("progress.cycle"), "0", accent="success")
        self.denial_card = StatCard(t("progress.denials"), "0", accent="danger")
        for c in (self.total_card, self.cycle_card, self.denial_card):
            counters_row.addWidget(c, stretch=1)
        root.addLayout(counters_row)

        month_box = QGroupBox(t("progress.monthly_group"))
        month_layout = QVBoxLayout(month_box)

        nav_row = QHBoxLayout()
        self.month_selector = QComboBox()
        today = date.today()
        self._month_options = []
        for i in range(5, -1, -1):
            m = today.month - i
            y = today.year
            while m <= 0:
                m += 12
                y -= 1
            self._month_options.append((y, m))
            self.month_selector.addItem(f"{t(MONTH_KEYS[m-1])} {y}")
        self.month_selector.setCurrentIndex(len(self._month_options) - 1)
        self.month_selector.currentIndexChanged.connect(self._render_month_grid)

        self.month_label = QLabel(t("progress.month_label"))
        nav_row.addWidget(self.month_label)
        nav_row.addWidget(self.month_selector)
        nav_row.addStretch()
        month_layout.addLayout(nav_row)

        self.month_grid_container = QWidget()
        self.month_grid_layout = QGridLayout(self.month_grid_container)
        month_layout.addWidget(self.month_grid_container)
        root.addWidget(month_box)

        history_box = QGroupBox(t("progress.history_group"))
        history_layout = QVBoxLayout(history_box)
        self.history_table = QTableWidget(0, 4)
        self.history_table.setHorizontalHeaderLabels([
            t("progress.history.plan"),
            t("progress.history.start"),
            t("progress.history.expiry"),
            t("progress.history.status"),
        ])
        self.history_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.history_table.verticalHeader().setVisible(False)
        self.history_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.history_table.setAlternatingRowColors(True)
        self.history_table.setShowGrid(False)
        history_layout.addWidget(self.history_table)
        root.addWidget(history_box)

    def restyle(self):
        if hasattr(self, "_month_options"):
            self._render_month_grid()
        self._render_history()

    # ---------- data ----------

    def refresh(self):
        attendance = get_attendance_for_player(self.player_id)
        active_sub = get_active_subscription(self.player_id)

        total_attended = sum(1 for e in attendance if e.result == "allowed")
        denial_count = sum(1 for e in attendance if e.result == "denied")
        cycle_attended = 0
        if active_sub:
            cycle_attended = sum(
                1 for e in attendance
                if e.result == "allowed" and e.subscription_id == active_sub.subscription_id
            )

        self.total_card.set_value(total_attended)
        self.cycle_card.set_value(cycle_attended)
        self.denial_card.set_value(denial_count)

        self._attendance_cache = attendance
        self._active_sub_cache = active_sub
        self._render_month_grid()
        self._render_history()

    def _render_history(self):
        history = get_subscription_history(self.player_id)
        self.history_table.setRowCount(len(history))
        t_ = theme()
        for i, sub in enumerate(history):
            self.history_table.setItem(i, 0, QTableWidgetItem(get_plan_label(sub.plan_type)))
            self.history_table.setItem(i, 1, QTableWidgetItem(sub.start_date))
            self.history_table.setItem(i, 2, QTableWidgetItem(sub.expiry_date))

            status_key = {
                "active":    "progress.sub.status.active",
                "expired":   "progress.sub.status.expired",
                "suspended": "progress.sub.status.suspended",
            }.get(sub.status, "players.status.none")

            status_item = QTableWidgetItem(t(status_key))
            color_token = {
                "active": "success", "expired": "danger", "suspended": "warning",
            }.get(sub.status, "muted")
            status_item.setForeground(QColor(t_.color(color_token)))
            self.history_table.setItem(i, 3, status_item)

    def _render_month_grid(self):
        while self.month_grid_layout.count():
            item = self.month_grid_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        if not hasattr(self, "_month_options"):
            return

        t_ = theme()
        year, month = self._month_options[self.month_selector.currentIndex()]

        active_sub = getattr(self, "_active_sub_cache", None)
        attendance = getattr(self, "_attendance_cache", [])
        attended_dates = {
            datetime.fromisoformat(e.scan_datetime).date()
            for e in attendance if e.result == "allowed"
        }

        allowed_weekday_names = set()
        if active_sub:
            plan = get_plan(active_sub.plan_type)
            allowed_weekday_names = set(plan["allowed_days"])

        today = date.today()
        days_in_month = calendar.monthrange(year, month)[1]

        col = 0
        row = 0
        max_cols = 7
        for day_num in range(1, days_in_month + 1):
            d = date(year, month, day_num)
            weekday_name = d.strftime("%A")
            if weekday_name not in allowed_weekday_names:
                continue

            if d in attended_dates:
                text, color = f"{day_num} ✓", t_.color("success")
                bg = t_.color("success_soft")
            elif d < today:
                text, color = f"{day_num} ✕", t_.color("danger")
                bg = t_.color("danger_soft")
            else:
                text, color = f"{day_num} —", t_.color("muted")
                bg = t_.color("surface_alt")

            cell = QLabel(text)
            cell.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cell.setStyleSheet(
                f"border: 1px solid {t_.color('border')};"
                f"border-radius: 6px; padding: 10px;"
                f"color: {color}; font-weight: 700;"
                f"background-color: {bg};"
            )
            self.month_grid_layout.addWidget(cell, row, col)
            col += 1
            if col >= max_cols:
                col = 0
                row += 1

        if not active_sub:
            note = QLabel(t("progress.month.no_sub_note"))
            note.setStyleSheet(
                f"color: {t_.color('muted')}; font-style: italic; padding: 8px;"
            )
            self.month_grid_layout.addWidget(note, row + 1, 0, 1, max_cols)