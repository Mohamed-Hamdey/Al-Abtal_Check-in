"""
Global app theme + runtime light/dark mode (v3.1).

Rules:
  1. No hex color literals anywhere outside this file.
  2. Anywhere a widget needs a color, it asks theme().color("token").
  3. Any widget whose styling depends on the mode subclasses ThemedWidget
     and implements restyle().

The sidebar (nav) is intentionally always dark in both modes — it reads as
"chrome" rather than "content", the way VS Code / Slack / Discord do it.

v3.1 adds sweep_restyle(): on every theme flip, the app walks the entire
widget tree and calls restyle() on any widget that defines it. This is the
guaranteed fix for stuck widgets — it doesn't depend on listeners being
alive, or on widgets remembering to register themselves.
"""

from __future__ import annotations

from typing import Callable, Optional

from PyQt6.QtCore import QObject, QSettings, pyqtSignal, QEasingCurve, QPropertyAnimation
from PyQt6.QtGui import QPalette, QColor
from PyQt6.QtWidgets import (
    QApplication, QPushButton, QWidget, QGraphicsOpacityEffect,
    QGroupBox, QTabWidget, QTableWidget, QHeaderView,
)


# ---------------------------------------------------------------------------
# Palettes
# ---------------------------------------------------------------------------

LIGHT = {
    "primary":         "#3B5BA5",
    "primary_hover":   "#2E4880",
    "primary_pressed": "#243869",
    "primary_soft":    "#E5EAF5",

    "danger":          "#B3261E",
    "danger_hover":    "#8C1D18",
    "danger_pressed":  "#6B1512",
    "danger_soft":     "#FBEAE9",

    "success":         "#1F7A4D",
    "success_soft":    "#E4F3EB",

    "warning":         "#B5730A",
    "warning_soft":    "#FBF1DF",

    "muted":           "#8A8E96",

    "bg":              "#F5F6F8",
    "surface":         "#FFFFFF",
    "surface_alt":     "#FAFBFC",
    "surface_hover":   "#ECEEF1",
    "surface_pressed": "#E0E2E6",
    "border":          "#E3E5E9",
    "divider":         "#EEF0F2",
    "shadow":          "#CBD0D8",

    "text":            "#1A1D23",
    "text_secondary":  "#5B6270",
    "text_disabled":   "#C3C6CC",
    "text_on_accent":  "#FFFFFF",

    "btn_disabled_bg":   "#D3D5DA",
    "btn_disabled_text": "#8A8E96",

    "nav_bg":          "#EEF1F7",
    "nav_item":        "#5B6270",
    "nav_item_hover":  "#E3E7EE",
    "nav_item_sel":    "#DDE3EC",
    "nav_text_sel":    "#1A1D23",
    "nav_brand":       "#1A1D23",
    "nav_hairline":    "#DDE2EC",
}

DARK = {
    "primary":         "#5B8DEF",
    "primary_hover":   "#4A7CDB",
    "primary_pressed": "#3A66BE",
    "primary_soft":    "#1F2A44",

    "danger":          "#F87171",
    "danger_hover":    "#EF5A5A",
    "danger_pressed":  "#D94848",
    "danger_soft":     "#3A1F22",

    "success":         "#34D399",
    "success_soft":    "#16332A",

    "warning":         "#FBBF24",
    "warning_soft":    "#3A2F14",

    "muted":           "#9AA3B5",

    "bg":              "#12151C",
    "surface":         "#1B1F2A",
    "surface_alt":     "#232838",
    "surface_hover":   "#2A3042",
    "surface_pressed": "#323A50",
    "border":          "#2E3446",
    "divider":         "#262C3B",
    "shadow":          "#0A0C10",

    "text":            "#E8ECF4",
    "text_secondary":  "#9AA3B5",
    "text_disabled":   "#555C6E",
    "text_on_accent":  "#FFFFFF",

    "btn_disabled_bg":   "#2A3042",
    "btn_disabled_text": "#555C6E",

    "nav_bg":          "#0F1218",
    "nav_item":        "#9AA3B5",
    "nav_item_hover":  "#1A1F2A",
    "nav_item_sel":    "#1F2636",
    "nav_text_sel":    "#FFFFFF",
    "nav_brand":       "#FFFFFF",
    "nav_hairline":    "#1C212C",
}

PALETTES = {"light": LIGHT, "dark": DARK}


# ---------------------------------------------------------------------------
# Backward-compat exports
# ---------------------------------------------------------------------------
PRIMARY         = LIGHT["primary"]
PRIMARY_HOVER   = LIGHT["primary_hover"]
PRIMARY_PRESSED = LIGHT["primary_pressed"]

DANGER          = LIGHT["danger"]
DANGER_HOVER    = LIGHT["danger_hover"]
DANGER_PRESSED  = LIGHT["danger_pressed"]

SUCCESS = LIGHT["success"]
WARNING = LIGHT["warning"]
MUTED   = LIGHT["muted"]

BG             = LIGHT["bg"]
SURFACE        = LIGHT["surface"]
BORDER         = LIGHT["border"]
TEXT_PRIMARY   = LIGHT["text"]
TEXT_SECONDARY = LIGHT["text_secondary"]


# ---------------------------------------------------------------------------
# Design constants
# ---------------------------------------------------------------------------
CARD_RADIUS   = 12
BUTTON_RADIUS = 8
PILL_RADIUS   = 999
GUTTER        = 16
SECTION_GAP   = 24


# ---------------------------------------------------------------------------
# Stylesheet
# ---------------------------------------------------------------------------

def build_stylesheet(p: dict) -> str:
    return f"""
* {{
    font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
    color: {p['text']};
}}

QMainWindow, QDialog {{
    background-color: {p['bg']};
}}

QWidget {{
    background-color: transparent;
}}

QGroupBox {{
    font-weight: 600;
    font-size: 12px;
    color: {p['text_secondary']};
    border: 1px solid {p['border']};
    border-radius: {CARD_RADIUS}px;
    margin-top: 16px;
    padding: 18px 14px 14px 14px;
    background-color: {p['surface']};
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    left: 14px;
    padding: 0 8px;
    color: {p['text_secondary']};
    background-color: {p['surface']};
}}

QLabel {{
    background-color: transparent;
    color: {p['text']};
}}

QPushButton {{
    background-color: {p['primary']};
    color: {p['text_on_accent']};
    border: none;
    border-radius: {BUTTON_RADIUS}px;
    padding: 9px 18px;
    font-weight: 600;
    min-height: 18px;
}}

QPushButton:hover   {{ background-color: {p['primary_hover']}; }}
QPushButton:pressed {{ background-color: {p['primary_pressed']}; }}
QPushButton:focus   {{ outline: none; }}

QPushButton:disabled {{
    background-color: {p['btn_disabled_bg']};
    color: {p['btn_disabled_text']};
}}

QPushButton[cssClass="danger"] {{
    background-color: {p['danger']};
}}
QPushButton[cssClass="danger"]:hover   {{ background-color: {p['danger_hover']}; }}
QPushButton[cssClass="danger"]:pressed {{ background-color: {p['danger_pressed']}; }}
QPushButton[cssClass="danger"]:disabled {{
    background-color: {p['btn_disabled_bg']};
    color: {p['btn_disabled_text']};
}}

QPushButton[cssClass="secondary"] {{
    background-color: {p['surface']};
    color: {p['text']};
    border: 1px solid {p['border']};
}}
QPushButton[cssClass="secondary"]:hover   {{ background-color: {p['surface_hover']}; }}
QPushButton[cssClass="secondary"]:pressed {{ background-color: {p['surface_pressed']}; }}
QPushButton[cssClass="secondary"]:disabled {{
    background-color: {p['surface_alt']};
    color: {p['text_disabled']};
    border: 1px solid {p['border']};
}}

QPushButton[cssClass="ghost"] {{
    background-color: transparent;
    color: {p['text_secondary']};
    border: none;
    padding: 6px 10px;
}}
QPushButton[cssClass="ghost"]:hover {{
    background-color: {p['surface_hover']};
    color: {p['text']};
}}

QLineEdit, QComboBox, QDateEdit, QDoubleSpinBox, QSpinBox, QTextEdit {{
    border: 1px solid {p['border']};
    border-radius: {BUTTON_RADIUS}px;
    padding: 8px 12px;
    background-color: {p['surface']};
    color: {p['text']};
    selection-background-color: {p['primary']};
    selection-color: {p['text_on_accent']};
    min-height: 18px;
}}

QLineEdit:focus, QComboBox:focus, QDateEdit:focus,
QDoubleSpinBox:focus, QSpinBox:focus, QTextEdit:focus {{
    border: 1px solid {p['primary']};
}}

QLineEdit::placeholder {{ color: {p['text_secondary']}; }}

QComboBox::drop-down {{
    border: none;
    width: 22px;
}}
QComboBox::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {p['text_secondary']};
    margin-right: 8px;
}}

QComboBox QAbstractItemView {{
    background-color: {p['surface']};
    color: {p['text']};
    border: 1px solid {p['border']};
    border-radius: {BUTTON_RADIUS}px;
    selection-background-color: {p['primary_soft']};
    selection-color: {p['text']};
    padding: 4px;
}}

QTableWidget {{
    border: 1px solid {p['border']};
    border-radius: {CARD_RADIUS}px;
    gridline-color: {p['divider']};
    background-color: {p['surface']};
    alternate-background-color: {p['surface_alt']};
    selection-background-color: {p['primary_soft']};
    selection-color: {p['text']};
    outline: none;
}}

QTableWidget::item {{
    padding: 8px 10px;
    border: none;
}}

QHeaderView::section {{
    background-color: {p['surface_alt']};
    color: {p['text_secondary']};
    padding: 10px;
    border: none;
    border-bottom: 1px solid {p['border']};
    font-weight: 600;
    font-size: 12px;
}}

QTabWidget::pane {{
    border: 1px solid {p['border']};
    border-radius: {CARD_RADIUS}px;
    background-color: {p['surface']};
    top: -1px;
}}

QTabBar::tab {{
    background-color: transparent;
    color: {p['text_secondary']};
    padding: 10px 20px;
    border-bottom: 2px solid transparent;
    margin-right: 4px;
    font-weight: 600;
}}

QTabBar::tab:selected {{
    color: {p['primary']};
    border-bottom: 2px solid {p['primary']};
}}

QTabBar::tab:hover:!selected {{ color: {p['text']}; }}

QListWidget {{
    border: 1px solid {p['border']};
    border-radius: {CARD_RADIUS}px;
    background-color: {p['surface']};
    color: {p['text']};
    outline: none;
    padding: 4px;
}}

QListWidget::item {{
    padding: 10px 10px;
    border-radius: 6px;
    margin: 1px 2px;
}}

QListWidget::item:hover {{
    background-color: {p['surface_hover']};
}}

QListWidget::item:selected {{
    background-color: {p['primary_soft']};
    color: {p['text']};
}}

QListWidget#navList {{
    background-color: {p['nav_bg']};
    border: none;
    border-radius: 0px;
    padding: 8px 4px;
}}

QListWidget#navList::item {{
    color: {p['nav_item']};
    padding: 10px 14px;
    border-radius: 8px;
    border: none;
    margin: 2px 2px;
    font-weight: 500;
    font-size: 15px;
}}

/* Collapsed rail: tighter items so the glyph centers cleanly. */
QListWidget#navList[collapsed="true"] {{
    padding: 8px 4px;
}}

QListWidget#navList[collapsed="true"]::item {{
    padding: 0px;
    margin: 4px 6px;
    font-size: 20px;
}}
QListWidget#navList::item:hover:!selected {{
    background-color: {p['nav_item_hover']};
    color: {p['nav_brand']};
}}

QListWidget#navList::item:selected {{
    background-color: {p['nav_item_sel']};
    color: {p['nav_text_sel']};
    font-weight: 600;
}}

QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: {p['border']};
    border-radius: 5px;
    min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{ background: {p['muted']}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}

QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
    margin: 2px;
}}
QScrollBar::handle:horizontal {{
    background: {p['border']};
    border-radius: 5px;
    min-width: 24px;
}}
QScrollBar::handle:horizontal:hover {{ background: {p['muted']}; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

QToolTip {{
    background-color: {p['surface']};
    color: {p['text']};
    border: 1px solid {p['border']};
    border-radius: 6px;
    padding: 6px 8px;
}}
"""


APP_STYLESHEET = build_stylesheet(LIGHT)


# ---------------------------------------------------------------------------
# ThemeManager
# ---------------------------------------------------------------------------

_SETTINGS_ORG = "MembershipSystem"
_SETTINGS_APP = "theme"


class ThemeManager(QObject):
    theme_changed = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        s = QSettings(_SETTINGS_ORG, _SETTINGS_APP)
        saved = s.value("mode", "light")
        self._mode = saved if saved in PALETTES else "light"
        self._listeners: list = []

    @property
    def mode(self) -> str:
        return self._mode

    def is_dark(self) -> bool:
        return self._mode == "dark"

    def palette(self) -> dict:
        return PALETTES[self._mode]

    def color(self, token: str) -> str:
        try:
            return self.palette()[token]
        except KeyError:
            raise KeyError(f"Unknown theme token: {token!r}")

    def build_palette(self) -> QPalette:
        p = self.palette()
        pal = QPalette()
        pal.setColor(QPalette.ColorRole.Window, QColor(p["bg"]))
        pal.setColor(QPalette.ColorRole.WindowText, QColor(p["text"]))
        pal.setColor(QPalette.ColorRole.Base, QColor(p["surface"]))
        pal.setColor(QPalette.ColorRole.AlternateBase, QColor(p["surface_alt"]))
        pal.setColor(QPalette.ColorRole.Text, QColor(p["text"]))
        pal.setColor(QPalette.ColorRole.Button, QColor(p["surface"]))
        pal.setColor(QPalette.ColorRole.ButtonText, QColor(p["text"]))
        pal.setColor(QPalette.ColorRole.Highlight, QColor(p["primary"]))
        pal.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFFFFF"))
        pal.setColor(QPalette.ColorRole.ToolTipBase, QColor(p["surface"]))
        pal.setColor(QPalette.ColorRole.ToolTipText, QColor(p["text"]))
        pal.setColor(QPalette.ColorRole.PlaceholderText, QColor(p["text_secondary"]))
        pal.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text,
                     QColor(p["text_disabled"]))
        pal.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText,
                     QColor(p["text_disabled"]))
        return pal

    # ----- mode switching -----

    def set_mode(self, mode: str, app: Optional[QApplication] = None):
        if mode not in PALETTES or mode == self._mode:
            return
        self._mode = mode
        QSettings(_SETTINGS_ORG, _SETTINGS_APP).setValue("mode", mode)

        app = app or QApplication.instance()
        if app is not None:
            self.apply(app)

        # Notify anyone listening (mostly for want-to-know widgets)
        self.theme_changed.emit(self._mode)
        for cb in list(self._listeners):
            try:
                cb(self._mode)
            except Exception:
                pass

    def toggle(self, app: Optional[QApplication] = None):
        self.set_mode("dark" if self._mode == "light" else "light", app=app)

    # ----- the important part -----

    def apply(self, app: QApplication):
        """
        Apply the current mode to the whole app, then let Qt schedule
        repaints naturally (update() only — no forced repaint(), no
        processEvents(), no recursive repaint loops).

        Forcing synchronous repaints is what produced the
        'QPainter::begin: A paint device can only be painted by one
        painter at a time' warnings — those happen when we call
        widget.repaint() while Qt is already mid-paint.
        """
        app.setStyleSheet(build_stylesheet(self.palette()))
        app.setPalette(self.build_palette())

        tops = list(app.topLevelWidgets())

        # Recursive unpolish/polish — this is safe (does not paint).
        for top in tops:
            self._deep_repolish(top)

        # Call restyle() everywhere it exists.
        sweep_restyle()

        # Nudge the widgets that cache their sub-controls. Use update()
        # only — never repaint().
        for top in tops:
            self._repaint_cached_controls(top)

        # Schedule a repaint on each top-level window. update() is
        # asynchronous and won't collide with an in-flight paint.
        for top in tops:
            top.update()

    @staticmethod
    def _deep_repolish(widget):
        try:
            widget.style().unpolish(widget)
            widget.style().polish(widget)
            widget.update()
        except Exception:
            pass
        for child in widget.findChildren(object):
            if not hasattr(child, "style"):
                continue
            try:
                child.style().unpolish(child)
                child.style().polish(child)
                child.update()
            except Exception:
                pass

    @staticmethod
    def _repaint_cached_controls(top):
        """
        Nudge widgets whose rendered sub-controls Qt caches.
        Only uses update() — never repaint() — so nothing collides with
        an in-flight paint event.
        """
        for gb in top.findChildren(QGroupBox):
            gb.update()
        for tw in top.findChildren(QTabWidget):
            tw.update()
            try:
                tw.tabBar().update()
            except Exception:
                pass
        for tbl in top.findChildren(QTableWidget):
            try:
                tbl.viewport().update()
                tbl.horizontalHeader().viewport().update()
                tbl.verticalHeader().viewport().update()
            except Exception:
                pass
        for hdr in top.findChildren(QHeaderView):
            try:
                hdr.viewport().update()
            except Exception:
                pass
        # Widgets with a graphics effect — still only update(), not repaint().
        for w in top.findChildren(object):
            if not hasattr(w, "graphicsEffect"):
                continue
            try:
                if w.graphicsEffect() is not None:
                    w.update()
            except Exception:
                pass
    # ----- listener registration -----

    def on_change(self, callback: Callable[[str], None]):
        """Register a callback fired after each mode switch. Held for the
        lifetime of the process, so lambdas won't be GC'd mid-flight."""
        self._listeners.append(callback)
        return callback


_theme: Optional[ThemeManager] = None


def theme() -> ThemeManager:
    global _theme
    if _theme is None:
        _theme = ThemeManager()
    return _theme


# ---------------------------------------------------------------------------
# Sweep — call restyle() on any widget that has one
# ---------------------------------------------------------------------------

def sweep_restyle():
    """
    Walk every widget in the app and call restyle() on any widget that
    defines it — whether it subclasses ThemedWidget, registered with
    register_themed(), or is just duck-typed.

    This is the guaranteed fix for stuck widgets: it doesn't rely on
    listeners being alive or widgets remembering to register.
    """
    app = QApplication.instance()
    if app is None:
        return
    seen = set()
    for top in app.topLevelWidgets():
        # top itself
        _maybe_restyle(top, seen)
        # every descendant
        for w in top.findChildren(object):
            _maybe_restyle(w, seen)


def _maybe_restyle(widget, seen):
    if id(widget) in seen:
        return
    seen.add(id(widget))
    fn = getattr(widget, "restyle", None)
    if callable(fn):
        try:
            fn()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# ThemedWidget — the pattern every screen uses
# ---------------------------------------------------------------------------

class ThemedWidget:
    """
    Mixin for QWidget/QDialog subclasses whose styling depends on the
    current mode. Override restyle(); it runs once at construction and
    again on every theme flip.

        class MyScreen(ThemedWidget, QWidget):
            def __init__(self, ...):
                QWidget.__init__(self, ...)
                self._build_ui()
                self._init_theme()    # call LAST, after widgets exist

            def restyle(self):
                t = theme()
                self.title.setStyleSheet(f"color: {t.color('text')}; ...")
    """

    def _init_theme(self):
        # Push the current palette so native controls (QLineEdit frames,
        # QComboBox arrows, scrollbars) are born with the correct mode.
        try:
            self.setPalette(theme().build_palette())
        except Exception:
            pass

        # Modal dialogs are their own top-level windows and do NOT inherit
        # the app QSS the way child widgets do. The `QDialog { background }`
        # rule in build_stylesheet never reaches them — Windows paints the
        # native frame and the dialog ends up dark in light mode. Apply a
        # local background rule so the dialog window itself is themed.
        try:
            from PyQt6.QtWidgets import QDialog
            if isinstance(self, QDialog):
                self.setStyleSheet(
                    f"QDialog {{ background-color: {theme().color('bg')}; }}"
                )
        except Exception:
            pass

        # Paint once immediately
        self.restyle()

        # Register for future flips
        theme().on_change(self._on_theme_change)

        # Dialogs are top-level windows; force a repolish scoped to this
        # widget's subtree so it starts in the right mode.
        try:
            ThemeManager._deep_repolish(self)
            top = self.window() if hasattr(self, "window") else self
            if top is not None:
                top.update()
        except Exception:
            pass

    def _on_theme_change(self, _mode):
        try:
            from PyQt6.QtWidgets import QDialog
            if isinstance(self, QDialog):
                self.setStyleSheet(
                    f"QDialog {{ background-color: {theme().color('bg')}; }}"
                )
        except Exception:
            pass
        try:
            self.restyle()
        except Exception:
            pass

    def restyle(self):
        """Override. Must be idempotent."""
        pass


# ---------------------------------------------------------------------------
# register_themed — opt-in for duck-typed widgets
# ---------------------------------------------------------------------------

def register_themed(widget):
    """
    Opt-in registration for widgets that restyle themselves with
    setStyleSheet() but don't subclass ThemedWidget.

    The widget must expose a restyle() method. It runs once immediately,
    and again on every theme flip (both via listener and via sweep).
    """
    try:
        widget.restyle()
    except Exception:
        pass

    def _on_change(_mode, w=widget):
        try:
            w.restyle()
        except Exception:
            pass

    theme().on_change(_on_change)


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def polish_widget(widget):
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


def make_danger(button: QPushButton):
    button.setProperty("cssClass", "danger")
    polish_widget(button)


def make_secondary(button: QPushButton):
    button.setProperty("cssClass", "secondary")
    polish_widget(button)


def make_ghost(button: QPushButton):
    button.setProperty("cssClass", "ghost")
    polish_widget(button)


def theme_toggle_button() -> QPushButton:
    """Light/dark toggle. Lives in the top-right header of the content area."""
    btn = QPushButton()
    btn.setObjectName("themeToggle")
    make_secondary(btn)
    btn.setStyleSheet(
        f"QPushButton {{"
        f"  padding: 8px 14px;"
        f"  border-radius: {BUTTON_RADIUS}px;"
        f"  font-weight: 600;"
        f"}}"
    )
    _refresh_toggle_label(btn)

    def _on_click():
        theme().toggle()
        _refresh_toggle_label(btn)

    btn.clicked.connect(_on_click)
    theme().on_change(lambda _m: _refresh_toggle_label(btn))
    return btn
def language_toggle_button() -> QPushButton:
    """Arabic/English toggle. Lives in the top-right header of the content area."""
    from ui import i18n

    btn = QPushButton()
    btn.setObjectName("languageToggle")
    make_secondary(btn)
    btn.setStyleSheet(
        f"QPushButton {{"
        f"  padding: 8px 14px;"
        f"  border-radius: {BUTTON_RADIUS}px;"
        f"  font-weight: 600;"
        f"}}"
    )

    def _refresh_label():
        if i18n.current_language() == "ar":
            btn.setText("🌐   English")
            btn.setToolTip(t("language.tooltip_en"))
        else:
            btn.setText("🌐   العربية")
            btn.setToolTip(t("language.tooltip_ar"))

    from ui.i18n import t as _t
    t = _t
    _refresh_label()

    def _on_click():
        # Notify the app — the actual reload + rebuild is handled by the
        # MainWindow listener (see main_window.py).
        from ui.main_window import request_language_change  # noqa
        request_language_change()

    btn.clicked.connect(_on_click)
    return btn
def _refresh_toggle_label(btn: QPushButton):
    from ui.i18n import t
    if theme().is_dark():
        btn.setText("☀   " + t("theme.light_mode"))
        btn.setToolTip(t("theme.switch_to_light"))
    else:
        btn.setText("☾   " + t("theme.dark_mode"))
        btn.setToolTip(t("theme.switch_to_dark"))


# ---------------------------------------------------------------------------
# Fade helper (light page transition)
# ---------------------------------------------------------------------------

def fade_in(widget: QWidget, duration_ms: int = 180):
    """Short opacity fade-in for a widget that just became visible."""
    effect = QGraphicsOpacityEffect(widget)
    widget.setGraphicsEffect(effect)
    anim = QPropertyAnimation(effect, b"opacity", widget)
    anim.setDuration(duration_ms)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    anim.setEasingCurve(QEasingCurve.Type.OutCubic)
    widget._fade_anim = anim  # keep ref so it isn't GC'd mid-flight
    anim.start()
    
def force_repaint(widget):
    """
    Repolish a widget and its subtree, and schedule a repaint.
    Uses update() only — never repaint() — so we never collide with an
    in-flight paint event (which is what produced the 'Painter not
    active' warnings).
    """
    try:
        widget.style().unpolish(widget)
        widget.style().polish(widget)
    except Exception:
        pass
    widget.update()
    for child in widget.findChildren(object):
        if not hasattr(child, "style"):
            continue
        try:
            child.style().unpolish(child)
            child.style().polish(child)
            child.update()
        except Exception:
            pass