"""
Small reusable UI pieces. All of these are theme-aware and re-render
themselves when the mode flips.

Note on shadows: we deliberately avoid QGraphicsDropShadowEffect on Card.
Qt renders widgets that have a graphics effect via a separate path that
can skip stylesheet repaints during a theme flip, which is exactly the
"stuck banner behind the title" bug. Instead, Card uses a subtle border
and a very slightly different background to look elevated.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QLabel, QFrame, QVBoxLayout, QHBoxLayout, QWidget,
)

from ui.theme import (
    theme, ThemedWidget, CARD_RADIUS, GUTTER, force_repaint,
)


class Card(QFrame, ThemedWidget):
    """A rounded surface with an optional title row."""

    def __init__(self, title: str = "", parent=None):
        super().__init__(parent)
        self._title_text = title
        self.setObjectName("card")
        # Attribute so QSS can find it on children
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._build_ui()
        self._init_theme()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(GUTTER, 14, GUTTER, GUTTER)
        outer.setSpacing(10)

        self.title_label = QLabel(self._title_text)
        self.title_label.setVisible(bool(self._title_text))
        # Make sure the title paints its own background explicitly
        self.title_label.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        outer.addWidget(self.title_label)

        self.body = QVBoxLayout()
        self.body.setSpacing(8)
        outer.addLayout(self.body)

    def set_title(self, text: str):
        self._title_text = text
        self.title_label.setText(text)
        self.title_label.setVisible(bool(text))

    def restyle(self):
        t = theme()
        # The Card itself
        self.setStyleSheet(
            f"QFrame#card {{"
            f"  background-color: {t.color('surface')};"
            f"  border: 1px solid {t.color('border')};"
            f"  border-radius: {CARD_RADIUS}px;"
            f"}}"
            f"QFrame#card > QWidget {{"
            f"  background-color: transparent;"
            f"}}"
        )
        # The title label — explicit background so nothing shows through
        self.title_label.setStyleSheet(
            f"QLabel {{"
            f"  color: {t.color('text_secondary')};"
            f"  background-color: {t.color('surface')};"
            f"  font-size: 11px;"
            f"  font-weight: 700;"
            f"  letter-spacing: 0.5px;"
            f"  padding: 2px 0;"
            f"}}"
        )
        force_repaint(self)


class SectionHeader(QLabel, ThemedWidget):
    """Small uppercase label for a section inside a card."""

    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._init_theme()

    def restyle(self):
        t = theme()
        self.setStyleSheet(
            f"QLabel {{"
            f"  color: {t.color('text_secondary')};"
            f"  background-color: transparent;"
            f"  font-size: 11px; font-weight: 700;"
            f"  letter-spacing: 0.6px;"
            f"}}"
        )
        force_repaint(self)


class StatCard(QFrame, ThemedWidget):
    """A big-number card: value + caption."""

    def __init__(self, caption: str, value: str = "0",
                 accent: str = "primary", parent=None):
        super().__init__(parent)
        self._caption = caption
        self._value = value
        self._accent = accent
        self.setObjectName("statCard")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._build_ui()
        self._init_theme()

    def _build_ui(self):
        v = QVBoxLayout(self)
        v.setContentsMargins(14, 12, 14, 12)
        v.setSpacing(2)
        self.value_label = QLabel(self._value)
        self.caption_label = QLabel(self._caption)
        v.addWidget(self.value_label)
        v.addWidget(self.caption_label)

    def set_value(self, value):
        self._value = str(value)
        self.value_label.setText(self._value)

    def restyle(self):
        t = theme()
        self.setStyleSheet(
            f"QFrame#statCard {{"
            f"  background-color: {t.color('surface')};"
            f"  border: 1px solid {t.color('border')};"
            f"  border-radius: {CARD_RADIUS}px;"
            f"}}"
        )
        self.value_label.setStyleSheet(
            f"QLabel {{"
            f"  color: {t.color(self._accent)};"
            f"  background-color: transparent;"
            f"  font-size: 24px; font-weight: 700;"
            f"}}"
        )
        self.caption_label.setStyleSheet(
            f"QLabel {{"
            f"  color: {t.color('text_secondary')};"
            f"  background-color: transparent;"
            f"  font-size: 11px; font-weight: 600;"
            f"  letter-spacing: 0.4px;"
            f"}}"
        )
        force_repaint(self)


class StatusPill(QLabel, ThemedWidget):
    """Colored pill for status text."""

    def __init__(self, text: str = "", kind: str = "muted", parent=None):
        super().__init__(text, parent)
        self._kind = kind
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._init_theme()

    def set_status(self, text: str, kind: str):
        self._kind = kind
        self.setText(text)
        self.restyle()

    def restyle(self):
        t = theme()
        fg = t.color(self._kind) if self._kind in (
            "primary", "danger", "success", "warning", "muted"
        ) else t.color("muted")
        soft_token = {
            "success": "success_soft",
            "danger": "danger_soft",
            "warning": "warning_soft",
            "primary": "primary_soft",
        }.get(self._kind)
        bg = t.color(soft_token) if soft_token else t.color("surface_alt")
        self.setStyleSheet(
            f"QLabel {{"
            f"  color: {fg};"
            f"  background-color: {bg};"
            f"  border: none;"
            f"  border-radius: 10px;"
            f"  padding: 3px 10px;"
            f"  font-weight: 700;"
            f"  font-size: 11px;"
            f"  letter-spacing: 0.4px;"
            f"}}"
        )
        force_repaint(self)


def hairline(parent=None) -> QFrame:
    """A 1px horizontal divider that follows the theme."""
    line = QFrame(parent)
    line.setFrameShape(QFrame.Shape.HLine)
    line.setFixedHeight(1)
    line.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

    def _restyle():
        line.setStyleSheet(
            f"background-color: {theme().color('divider')}; border: none;"
        )

    _restyle()
    theme().on_change(lambda _m: _restyle())
    return line