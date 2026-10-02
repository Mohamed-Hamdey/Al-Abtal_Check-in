"""
Receptionist scan screen (v3 — Arabic).

Layout is unchanged from the English version; only strings changed.
All user-visible text comes from t("checkin.*").
"""

import os
import sys

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QListWidget, QListWidgetItem, QStackedWidget,
)
from ui.message_box import warn
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QImage, QPixmap, QColor

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from config.config_loader import get_academy_name
from repositories import players_repo
from services import attendance_service
from services.checkin_service import perform_check_in, RECORDED_BY
from logic.qr_utils import decode_qr_from_frame
from ui.cards.player_card import PlayerCardWidget
from ui.theme import (
    theme, make_danger, ThemedWidget,
    CARD_RADIUS, GUTTER, force_repaint,
)
from ui.widgets import Card, StatusPill
from ui.i18n import t

CARD_DISPLAY_MS = 2500


class ScanScreen(ThemedWidget, QWidget):
    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self._cap = None
        self._camera_timer = QTimer(self)
        self._camera_timer.timeout.connect(self._poll_camera)
        self._awaiting_clear = False
        self._build_ui()
        self._refresh_recent_checkins()
        self._init_theme()

    # ---------- construction ----------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(GUTTER, GUTTER, GUTTER, GUTTER)
        root.setSpacing(16)

        # --- title row ---
        title_row = QHBoxLayout()
        title_row.setSpacing(12)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        self.title = QLabel(t("checkin.title"))
        self.subtitle = QLabel(t("checkin.subtitle", academy=get_academy_name()))
        title_col.addWidget(self.title)
        title_col.addWidget(self.subtitle)
        title_row.addLayout(title_col)
        title_row.addStretch()

        self.camera_status_pill = StatusPill(t("checkin.status.camera_off"), "muted")
        self.start_scan_button = QPushButton(t("checkin.btn.start_scan"))
        self.stop_scan_button = QPushButton(t("checkin.btn.stop_scan"))
        make_danger(self.stop_scan_button)
        self.stop_scan_button.setEnabled(False)
        self.start_scan_button.clicked.connect(self._on_start_scan_clicked)
        self.stop_scan_button.clicked.connect(self._on_stop_scan_clicked)
        title_row.addWidget(self.camera_status_pill)
        title_row.addWidget(self.start_scan_button)
        title_row.addWidget(self.stop_scan_button)
        root.addLayout(title_row)

        # --- main row: camera card + recent card ---
        main_row = QHBoxLayout()
        main_row.setSpacing(16)

        self.camera_card = Card(t("checkin.card.camera"))
        self.stack = QStackedWidget()
        self.camera_card.body.addWidget(self.stack)

        idle = QWidget()
        idle_layout = QVBoxLayout(idle)
        idle_layout.setContentsMargins(0, 0, 0, 0)
        idle_layout.setSpacing(8)
        self.camera_label = QLabel(t("checkin.camera_off"))
        self.camera_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.camera_label.setMinimumHeight(340)
        idle_layout.addWidget(self.camera_label, stretch=1)
        self.camera_hint = QLabel(t("checkin.camera_hint"))
        self.camera_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        idle_layout.addWidget(self.camera_hint)
        self.stack.addWidget(idle)

        result = QWidget()
        result_layout = QVBoxLayout(result)
        result_layout.addStretch()
        self.player_card = PlayerCardWidget()
        result_layout.addWidget(self.player_card)
        result_layout.addStretch()
        self.stack.addWidget(result)

        self.stack.setCurrentIndex(0)
        main_row.addWidget(self.camera_card, stretch=3)

        self.recent_card = Card(t("checkin.card.recent"))
        self.recent_list = QListWidget()
        self.recent_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.recent_card.body.addWidget(self.recent_list)
        main_row.addWidget(self.recent_card, stretch=2)

        root.addLayout(main_row, stretch=1)

        # --- manual search card ---
        self.search_card = Card(t("checkin.card.manual"))
        search_row = QHBoxLayout()
        search_row.setSpacing(8)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(t("checkin.search.placeholder"))
        self.search_button = QPushButton(t("checkin.search.button"))
        search_row.addWidget(self.search_input, stretch=1)
        search_row.addWidget(self.search_button)
        self.search_card.body.addLayout(search_row)

        self.results_list = QListWidget()
        self.results_list.setMaximumHeight(140)
        self.results_list.hide()
        self.search_card.body.addWidget(self.results_list)

        self.search_button.clicked.connect(self._on_manual_search)
        self.search_input.returnPressed.connect(self._on_manual_search)
        self.results_list.itemClicked.connect(self._on_manual_result_selected)

        root.addWidget(self.search_card)

    # ---------- theming ----------

    def restyle(self):
        t_ = theme()
        self.title.setStyleSheet(
            f"QLabel {{"
            f"  color: {t_.color('text')};"
            f"  background-color: transparent;"
            f"  font-size: 22px; font-weight: 700;"
            f"}}"
        )
        self.subtitle.setStyleSheet(
            f"QLabel {{"
            f"  color: {t_.color('text_secondary')};"
            f"  background-color: transparent;"
            f"  font-size: 13px;"
            f"}}"
        )
        self.camera_hint.setStyleSheet(
            f"QLabel {{"
            f"  color: {t_.color('text_secondary')};"
            f"  background-color: transparent;"
            f"  font-size: 12px;"
            f"}}"
        )
        self.camera_label.setStyleSheet(
            f"QLabel {{"
            f"  background-color: {t_.color('surface_alt')};"
            f"  color: {t_.color('text_secondary')};"
            f"  font-size: 15px;"
            f"  border-radius: {CARD_RADIUS - 2}px;"
            f"  border: 1px dashed {t_.color('border')};"
            f"}}"
        )
        self.recent_list.setStyleSheet(
            f"QListWidget {{"
            f"  background: {t_.color('surface')};"
            f"  border: none;"
            f"  padding: 0;"
            f"}}"
            f"QListWidget::item {{"
            f"  padding: 8px 10px;"
            f"  border-radius: 6px;"
            f"  color: {t_.color('text')};"
            f"}}"
            f"QListWidget::item:hover {{"
            f"  background-color: {t_.color('surface_hover')};"
            f"}}"
        )
        force_repaint(self)

    # ---------- camera ----------

    def _on_start_scan_clicked(self):
        self.start_camera()

    def _on_stop_scan_clicked(self):
        self.stop_camera()
        self.camera_label.setText(t("checkin.camera_off"))
        self.camera_status_pill.set_status(t("checkin.status.camera_off"), "muted")
        self.start_scan_button.setEnabled(True)
        self.stop_scan_button.setEnabled(False)

    def start_camera(self, camera_index: int = 0):
        import cv2
        self._cap = cv2.VideoCapture(camera_index)
        if not self._cap.isOpened():
            self.camera_label.setText(t("checkin.camera_unavailable"))
            self.camera_status_pill.set_status(t("checkin.status.unavailable"), "danger")
            self._cap = None
            return
        self._camera_timer.start(200)
        self.camera_status_pill.set_status(t("checkin.status.scanning"), "success")
        self.start_scan_button.setEnabled(False)
        self.stop_scan_button.setEnabled(True)

    def stop_camera(self):
        self._camera_timer.stop()
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    def _poll_camera(self):
        if self._cap is None or self._awaiting_clear:
            return
        ret, frame = self._cap.read()
        if not ret:
            return
        self._render_frame(frame)
        player_id_str = decode_qr_from_frame(frame)
        if player_id_str:
            try:
                player_id = int(player_id_str)
            except ValueError:
                return
            self.handle_player_id(player_id)

    def _render_frame(self, frame):
        import cv2
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        qt_image = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888).copy()
        self.camera_label.setPixmap(
            QPixmap.fromImage(qt_image).scaled(
                self.camera_label.width(), self.camera_label.height(),
                Qt.AspectRatioMode.KeepAspectRatio,
            )
        )

    # ---------- recent check-ins ----------

    def _refresh_recent_checkins(self):
        self.recent_list.clear()
        entries = attendance_service.get_recent_with_names(limit=10)
        if not entries:
            item = QListWidgetItem(t("checkin.recent.empty"))
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.recent_list.addItem(item)
            return
        t_ = theme()
        for e in entries:
            time_part = e["scan_datetime"].split(" ")[-1][:5]
            if e["result"] == "allowed":
                dot = "✓" if not e["was_override"] else "✓*"
            else:
                dot = "✕"
            text = f"{dot}   {time_part}   {e['full_name']}"
            item = QListWidgetItem(text)
            item.setForeground(QColor(t_.color("text")))
            self.recent_list.addItem(item)

    # ---------- manual search ----------

    def _on_manual_search(self):
        query = self.search_input.text().strip()
        if not query:
            return
        self.results_list.clear()
        results = []
        if query.isdigit():
            by_id = players_repo.get_by_id(int(query))
            if by_id:
                results.append(by_id)
        if not results:
            results.extend(players_repo.search_by_name(query))

        if not results:
            self.results_list.addItem(t("checkin.search.no_match"))
            self.results_list.show()
            return
        for player in results:
            item = QListWidgetItem(f"{player.full_name}   —   ID {player.player_id}")
            item.setData(Qt.ItemDataRole.UserRole, player.player_id)
            self.results_list.addItem(item)
        self.results_list.show()

    def _on_manual_result_selected(self, item: QListWidgetItem):
        player_id = item.data(Qt.ItemDataRole.UserRole)
        if player_id is None:
            return
        self.results_list.hide()
        self.search_input.clear()
        self.handle_player_id(player_id)

    # ---------- pipeline ----------

    def handle_player_id(self, player_id: int, recorded_by: str = RECORDED_BY):
        outcome = perform_check_in(player_id, parent_widget=self, recorded_by=recorded_by)
        if outcome is None:
            warn(
                self,
                t("checkin.unknown_player_title"),
                t("checkin.unknown_player_msg", player_id=player_id),
            )
            return

        # Player already checked in today — show an informational message
        # and return to idle without touching the attendance log or the
        # session count.
        if getattr(outcome, "was_duplicate", False):
            warn(
                self,
                t("checkin.already_today_title"),
                t("checkin.already_today_msg", name=outcome.player.full_name),
            )
            return

        state = "checked_in" if outcome.checked_in else "denied"
        self.player_card.display_player(outcome.player, outcome.subscription, check_in_state=state)
        self.stack.setCurrentIndex(1)
        self._refresh_recent_checkins()
        self._schedule_return_to_idle()

    def _schedule_return_to_idle(self):
        self._awaiting_clear = True
        QTimer.singleShot(CARD_DISPLAY_MS, self._return_to_idle)

    def _return_to_idle(self):
        self.player_card.clear()
        self.stack.setCurrentIndex(0)
        self._awaiting_clear = False