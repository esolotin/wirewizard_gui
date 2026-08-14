from __future__ import annotations

from PySide6.QtWidgets import QFormLayout, QLineEdit, QPlainTextEdit, QWidget

from wirewizard_gui.domain.models import FerruleModel
from wirewizard_gui.domain.options import FERRULE_SUBTYPES, FERRULE_TYPES, WIRE_COLORS
from wirewizard_gui.ui.editors.common import build_combo, set_combo_text


class FerruleEditor(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.current_item: FerruleModel | None = None

        self.name_edit = QLineEdit()
        self.type_combo = build_combo(FERRULE_TYPES)
        self.subtype_combo = build_combo(FERRULE_SUBTYPES)
        self.color_combo = build_combo(WIRE_COLORS)
        self.notes_edit = QPlainTextEdit()

        layout = QFormLayout(self)
        layout.addRow("Обозначение", self.name_edit)
        layout.addRow("Тип", self.type_combo)
        layout.addRow("Подтип", self.subtype_combo)
        layout.addRow("Цвет", self.color_combo)
        layout.addRow("Примечания", self.notes_edit)

    def load_item(self, item: FerruleModel) -> None:
        self.current_item = item
        self.name_edit.setText(item.name)
        set_combo_text(self.type_combo, item.type)
        set_combo_text(self.subtype_combo, item.subtype)
        set_combo_text(self.color_combo, item.color)
        self.notes_edit.setPlainText(item.notes)

    def save_to_item(self) -> None:
        if not self.current_item:
            return
        self.current_item.name = self.name_edit.text().strip() or "F?"
        self.current_item.type = self.type_combo.currentText().strip() or "Обжимной наконечник"
        self.current_item.subtype = self.subtype_combo.currentText().strip() or "0.5 mm²"
        self.current_item.color = self.color_combo.currentText().strip()
        self.current_item.notes = self.notes_edit.toPlainText().strip()
