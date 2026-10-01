"""
Main application window — bilingual shell.

Sidebar (always dark) has brand + nav only. A header strip at the top of
the content area holds the language and theme toggles.

Language change triggers a full window rebuild so every t("...") string
gets re-resolved and RTL/LTR flips correctly.
"""

import os
import sys

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QStackedWidget, QFrame, QApplication,
)
from PyQt6.QtCore import Qt, QSize, QSettings
from PyQt6.QtGui import QPixmap

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from config.config_loader import get_academy_name, get_academy_logo, load_config
from ui.scan_screen import ScanScreen
from ui.player_list_screen import PlayerListScreen
from ui.theme import theme, theme_toggle_button, language_toggle_button
from ui import i18n
from ui.i18n import t

EXPANDED_WIDTH  = 220
COLLAPSED_WIDTH = 54
LOGO_SIZE       = 40

NAV_ICONS = {
    "nav.check_in":       "▶",
    "nav.manage_players": "▤",
}

_SETTINGS_ORG = "MembershipSystem"
_SETTINGS_APP = "app"


# ---------------------------------------------------------------------------
# Module-level language-change hook.
#
# The language button lives deep inside the widget tree, but switching
# language means rebuilding the top-level window — so we need a way to
# call back up to the app. We keep a module-level reference to the current
# MainWindow (set in MainWindow.__init__) and a public function the button
# calls.
# ---------------------------------------------------------------------------

_current_window: "MainWindow" = None


def request_language_change():
    """Called by the language toggle button. Flips the language, rebuilds
    the main window, and re-flips layout direction."""
    if _current_window is None:
        return
    _current_window._switch_language()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        global _current_window
        _current_window = self

        self.setWindowTitle(t("app.window_title"))
        self.resize(1040, 700)
        self._collapsed = False

        central = QWidget()
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ---------------- Sidebar ----------------
        self.sidebar = QWidget()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(EXPANDED_WIDTH)
        side_layout = QVBoxLayout(self.sidebar)
        side_layout.setContentsMargins(0, 0, 0, 0)
        side_layout.setSpacing(0)

        # Logo row
        self.logo_row = QWidget()
        self.logo_row.setObjectName("logoRow")
        self.logo_row.setCursor(Qt.CursorShape.PointingHandCursor)
        self.logo_row.setToolTip(t("sidebar.collapse"))
        self.logo_row.mousePressEvent = self._on_logo_clicked
        logo_layout = QHBoxLayout(self.logo_row)
        logo_layout.setContentsMargins(12, 16, 12, 16)
        logo_layout.setSpacing(10)

        self.logo_label = QLabel()
        self.logo_label.setFixedSize(LOGO_SIZE, LOGO_SIZE)
        self.logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._load_logo()
        logo_layout.addWidget(self.logo_label)

        brand_col = QVBoxLayout()
        brand_col.setContentsMargins(0, 0, 0, 0)
        brand_col.setSpacing(2)

        cfg = load_config()
        # In Arabic we show Arabic first then English; in English, the
        # reverse. The "primary" name follows the active language.
        name_ar = cfg.get("academy_name_ar", "")
        name_en = cfg.get("academy_name", "")
        if i18n.current_language() == "ar":
            primary, secondary = name_ar, name_en
        else:
            primary, secondary = name_en, name_ar

        self.brand_primary = QLabel(primary)
        self.brand_primary.setWordWrap(True)
        self.brand_secondary = QLabel(secondary)
        self.brand_secondary.setWordWrap(True)
        brand_col.addWidget(self.brand_primary)
        brand_col.addWidget(self.brand_secondary)

        logo_layout.addLayout(brand_col, stretch=1)
        side_layout.addWidget(self.logo_row)

        self.hairline = QFrame()
        self.hairline.setFrameShape(QFrame.Shape.HLine)
        self.hairline.setFixedHeight(1)
        side_layout.addWidget(self.hairline)

        # Nav
        self.nav_list = QListWidget()
        self.nav_list.setObjectName("navList")
        side_layout.addWidget(self.nav_list, stretch=1)

        # ---------------- Right side: header + pages ----------------
        right_side = QWidget()
        right_layout = QVBoxLayout(right_side)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        # ---- Header strip ----
        self.header = QWidget()
        self.header.setObjectName("header")
        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(16, 12, 16, 12)
        header_layout.setSpacing(8)

        # header content will be pushed to the "far end" which flips
        # automatically with RTL
        header_layout.addStretch()

        self.language_button = language_toggle_button()
        self.theme_button = theme_toggle_button()
        header_layout.addWidget(self.language_button)
        header_layout.addWidget(self.theme_button)

        right_layout.addWidget(self.header)

        # ---- Pages ----
        self.pages = QStackedWidget()
        self.pages.setContentsMargins(0, 0, 0, 0)

        self.scan_screen = ScanScreen()
        self.player_list_screen = PlayerListScreen()
        self._add_nav_item("nav.check_in", self.scan_screen)
        self._add_nav_item("nav.manage_players", self.player_list_screen)

        self.nav_list.currentRowChanged.connect(self._on_nav_changed)
        self.nav_list.setCurrentRow(0)

        right_layout.addWidget(self.pages, stretch=1)

        layout.addWidget(self.sidebar)
        layout.addWidget(right_side, stretch=1)
        self.setCentralWidget(central)

        # Initial paint
        self._restyle_sidebar()
        self._restyle_header()
        self._restyle_content()
        self._apply_collapse_state()

        theme().on_change(lambda _m: self._on_theme_changed())

    # ---------- nav ----------

    def _add_nav_item(self, label_key, page):
        item = QListWidgetItem()
        item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        item.setData(Qt.ItemDataRole.UserRole, label_key)
        self.nav_list.addItem(item)
        self.pages.addWidget(page)
        self._render_nav_item(item, label_key, collapsed=False)

    def _render_nav_item(self, item, label_key, collapsed):
        glyph = NAV_ICONS.get(label_key, "•")
        label = t(label_key)
        if collapsed:
            item.setText(glyph)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item.setToolTip(label)
            item.setSizeHint(QSize(0, 40))
        else:
            item.setText(f"  {glyph}   {label}")
            item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            item.setToolTip("")
            item.setSizeHint(QSize(0, 42))

    def _on_nav_changed(self, index):
        self.pages.setCurrentIndex(index)

    # ---------- collapse / expand ----------

    def _on_logo_clicked(self, event):
        self._collapsed = not self._collapsed
        self._apply_collapse_state()

    def _apply_collapse_state(self):
        if self._collapsed:
            self.sidebar.setFixedWidth(COLLAPSED_WIDTH)
            self.brand_primary.setVisible(False)
            self.brand_secondary.setVisible(False)
            self.logo_row.setToolTip(t("sidebar.expand"))
            self.logo_row.layout().setContentsMargins(8, 16, 8, 16)
            self.logo_row.layout().setAlignment(
                self.logo_label, Qt.AlignmentFlag.AlignCenter
            )
        else:
            self.sidebar.setFixedWidth(EXPANDED_WIDTH)
            self.brand_primary.setVisible(True)
            self.brand_secondary.setVisible(True)
            self.logo_row.setToolTip(t("sidebar.collapse"))
            self.logo_row.layout().setContentsMargins(12, 16, 12, 16)
            self.logo_row.layout().setAlignment(
                self.logo_label, Qt.AlignmentFlag.AlignLeft
            )

        self.nav_list.setProperty("collapsed", "true" if self._collapsed else "false")
        self.nav_list.style().unpolish(self.nav_list)
        self.nav_list.style().polish(self.nav_list)

        for i in range(self.nav_list.count()):
            item = self.nav_list.item(i)
            label_key = item.data(Qt.ItemDataRole.UserRole)
            self._render_nav_item(item, label_key, collapsed=self._collapsed)

        self._restyle_sidebar()

    # ---------- theming ----------

    def _on_theme_changed(self):
        self._restyle_sidebar()
        self._restyle_header()
        self._restyle_content()

    def _restyle_sidebar(self):
        t_ = theme()
        self.sidebar.setStyleSheet(
            f"QWidget#sidebar {{ background-color: {t_.color('nav_bg')}; }}"
        )
        self.logo_row.setStyleSheet(
            f"QWidget#logoRow {{ background-color: transparent; }}"
        )
        self.logo_label.setStyleSheet(
            f"QLabel {{"
            f"  background-color: #2A3042;"
            f"  color: #FFFFFF;"
            f"  font-size: 15px; font-weight: 800;"
            f"  border-radius: 10px;"
            f"}}"
        )
        self.brand_primary.setStyleSheet(
            f"QLabel {{"
            f"  color: {t_.color('nav_brand')};"
            f"  background-color: transparent;"
            f"  font-size: 13px; font-weight: 700;"
            f"}}"
        )
        self.brand_secondary.setStyleSheet(
            f"QLabel {{"
            f"  color: {t_.color('nav_item')};"
            f"  background-color: transparent;"
            f"  font-size: 10px; font-weight: 500;"
            f"}}"
        )
        self.hairline.setStyleSheet(
            f"background-color: {t_.color('nav_hairline')}; border: none;"
        )

    def _restyle_header(self):
        t_ = theme()
        self.header.setStyleSheet(
            f"QWidget#header {{"
            f"  background-color: {t_.color('bg')};"
            f"  border-bottom: 1px solid {t_.color('border')};"
            f"}}"
        )

    def _restyle_content(self):
        bg = theme().color("bg")
        self.pages.setStyleSheet(f"QStackedWidget {{ background-color: {bg}; }}")
        for i in range(self.pages.count()):
            page = self.pages.widget(i)
            if page is None:
                continue
            page.update()

    # ---------- logo ----------

    def _load_logo(self):
        path = get_academy_logo()
        if path:
            pix = QPixmap(path).scaled(
                LOGO_SIZE, LOGO_SIZE,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.logo_label.setPixmap(pix)
        else:
            initials = "".join(w[0] for w in get_academy_name().split()[:3]).upper()
            self.logo_label.setText(initials or "A")

    # ---------- language switch ----------

    def _switch_language(self):
        """Flip language, persist it, rebuild the UI from scratch."""
        current = i18n.current_language()
        new_lang = "en" if current == "ar" else "ar"
        i18n.load(new_lang)
        QSettings(_SETTINGS_ORG, _SETTINGS_APP).setValue("language", new_lang)

        app = QApplication.instance()
        if app is not None:
            if i18n.is_rtl():
                app.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
            else:
                app.setLayoutDirection(Qt.LayoutDirection.LeftToRight)

        # Tear down the current window and rebuild from scratch so every
        # t("...") call re-resolves against the new language.
        self.close()
        global _current_window
        new_window = MainWindow()
        _current_window = new_window
        new_window.show()

    # ---------- lifecycle ----------

    def closeEvent(self, event):
        # Only stop the camera on real user-initiated close, not on the
        # programmatic close from _switch_language (which would kill the
        # camera between the two windows).
        try:
            self.scan_screen.stop_camera()
        except Exception:
            pass
        super().closeEvent(event)