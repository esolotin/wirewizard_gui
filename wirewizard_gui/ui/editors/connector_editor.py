from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QLineEdit,
    QPlainTextEdit,
    QSpinBox,
    QWidget,
)

from wirewizard_gui.domain.models import ConnectorModel
from wirewizard_gui.domain.options import CONNECTOR_SUBTYPES, CONNECTOR_TYPES, WIRE_COLORS
from wirewizard_gui.ui.editors.common import build_combo, set_combo_text


class ConnectorEditor(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.current_item: ConnectorModel | None = None

        self.name_edit = QLineEdit()
        self.type_combo = build_combo(CONNECTOR_TYPES)
        self.subtype_combo = build_combo(CONNECTOR_SUBTYPES)
        self.pincount_spin = QSpinBox()
        self.pincount_spin.setMinimum(1)
        self.pincount_spin.setMaximum(999)
        self.pins_edit = QLineEdit()
        self.pinlabels_edit = QLineEdit()
        self.color_combo = build_combo(WIRE_COLORS)
        self.simple_check = QCheckBox("Упрощённый разъём")
        self.notes_edit = QPlainTextEdit()
        self.simple_check.toggled.connect(self._update_simple_state)

        layout = QFormLayout(self)
        layout.addRow("Обозначение", self.name_edit)
        layout.addRow("Тип", self.type_combo)
        layout.addRow("Подтип", self.subtype_combo)
        layout.addRow("Количество контактов", self.pincount_spin)
        layout.addRow("Контакты / обозначения (через запятую)", self.pins_edit)
        layout.addRow("Метки контактов (через запятую)", self.pinlabels_edit)
        layout.addRow("Цвет", self.color_combo)
        layout.addRow("", self.simple_check)
        layout.addRow("Примечания", self.notes_edit)

    def _update_simple_state(self, checked: bool) -> None:
        self.pincount_spin.setEnabled(not checked)
        self.pins_edit.setEnabled(not checked)
        self.pinlabels_edit.setEnabled(not checked)

    def load_item(self, item: ConnectorModel) -> None:
        self.current_item = item
        self.name_edit.setText(item.name)
        set_combo_text(self.type_combo, item.type)
        set_combo_text(self.subtype_combo, item.subtype)
        self.pincount_spin.setValue(item.pincount)
        self.pins_edit.setText(", ".join(item.pins))
        self.pinlabels_edit.setText(", ".join(item.pinlabels))
        set_combo_text(self.color_combo, item.color)
        self.simple_check.setChecked(item.simple)
        self.notes_edit.setPlainText(item.notes)
        self._update_simple_state(item.simple)

    def save_to_item(self) -> None:
        if not self.current_item:
            return
        self.current_item.name = self.name_edit.text().strip() or "X?"
        self.current_item.type = self.type_combo.currentText().strip() or "Универсальный разъём"
        self.current_item.subtype = self.subtype_combo.currentText().strip()
        self.current_item.pincount = self.pincount_spin.value()
        self.current_item.pins = [x.strip() for x in self.pins_edit.text().split(",") if x.strip()]
        self.current_item.pinlabels = [x.strip() for x in self.pinlabels_edit.text().split(",") if x.strip()]
        self.current_item.color = self.color_combo.currentText().strip()
        self.current_item.simple = self.simple_check.isChecked()
        self.current_item.notes = self.notes_edit.toPlainText().strip()
