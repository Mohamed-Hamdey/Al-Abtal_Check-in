"""Adjust sessions-remaining dialog (v3). Theme-aware."""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QSpinBox, QPushButton,
    QHBoxLayout, QLabel,
)
from PyQt6.QtCore import Qt

from ui.theme import theme, ThemedWidget, make_secondary


class AdjustSessionsDialog(ThemedWidget, QDialog):
    def __init__(self, subscription_id: int, current_value: int, total: int, parent=None):
        QDialog.__init__(self, parent)
        self.subscription_id = subscription_id
        self.setWindowTitle("Adjust Sessions Remaining")
        self.setMinimumWidth(320)
        self._build_ui(current_value, total)
        self._init_theme()

    def _build_ui(self, current_value, total):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        self.plan_total_label = QLabel(f"Plan total: {total} sessions")
        layout.addWidget(self.plan_total_label)

        form = QFormLayout()
        self.value_input = QSpinBox()
        self.value_input.setRange(0, total)
        self.value_input.setValue(current_value)
        form.addRow("Sessions remaining", self.value_input)
        layout.addLayout(form)

        button_row = QHBoxLayout()
        cancel_button = QPushButton("Cancel")
        make_secondary(cancel_button)
        save_button = QPushButton("Save")
        save_button.setDefault(True)
        save_button.clicked.connect(self.accept)
        cancel_button.clicked.connect(self.reject)
        button_row.addStretch()
        button_row.addWidget(cancel_button)
        button_row.addWidget(save_button)
        layout.addLayout(button_row)

    def restyle(self):
        t = theme()
        self.plan_total_label.setStyleSheet(
            f"color: {t.color('text_secondary')}; font-size: 12px;"
        )

    def new_value(self) -> int:
        return self.value_input.value()