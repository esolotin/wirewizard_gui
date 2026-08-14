from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QLineEdit,
    QPlainTextEdit,
    QSpinBox,
    QWidget,
)

from wirewizard_gui.domain.models import CableModel
from wirewizard_gui.domain.options import CABLE_TYPES, COLOR_CODES, GAUGES, LENGTHS
from wirewizard_gui.ui.editors.common import build_combo, set_combo_text


class CableEditor(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.current_item: CableModel | None = None

        self.name_edit = QLineEdit()
        self.type_combo = build_combo(CABLE_TYPES)
        self.gauge_combo = build_combo(GAUGES)
        self.length_combo = build_combo(LENGTHS)
        self.wirecount_spin = QSpinBox()
        self.wirecount_spin.setMinimum(1)
        self.wirecount_spin.setMaximum(999)
        self.colors_edit = QLineEdit()
        self.color_code_combo = build_combo(COLOR_CODES)
        self.wirelabels_edit = QLineEdit()
        self.shield_check = QCheckBox("Экран")
        self.bundle_check = QCheckBox("Пучок")
        self.notes_edit = QPlainTextEdit()

        layout = QFormLayout(self)
        layout.addRow("Обозначение", self.name_edit)
        layout.addRow("Тип", self.type_combo)
        layout.addRow("Сечение", self.gauge_combo)
        layout.addRow("Длина", self.length_combo)
        layout.addRow("Количество жил", self.wirecount_spin)
        layout.addRow("Цвета жил (через запятую)", self.colors_edit)
        layout.addRow("Стандарт цветов", self.color_code_combo)
        layout.addRow("Метки жил (через запятую)", self.wirelabels_edit)
        layout.addRow("", self.shield_check)
        layout.addRow("", self.bundle_check)
        layout.addRow("Примечания", self.notes_edit)

    def load_item(self, item: CableModel) -> None:
        self.current_item = item
        self.name_edit.setText(item.name)
        set_combo_text(self.type_combo, item.type)
        set_combo_text(self.gauge_combo, item.gauge)
        set_combo_text(self.length_combo, item.length)
        self.wirecount_spin.setValue(item.wirecount)
        self.colors_edit.setText(", ".join(item.colors))
        set_combo_text(self.color_code_combo, item.color_code)
        self.wirelabels_edit.setText(", ".join(item.wirelabels))
        self.shield_check.setChecked(item.shield)
        self.bundle_check.setChecked(item.bundle)
        self.notes_edit.setPlainText(item.notes)

    def save_to_item(self) -> None:
        if not self.current_item:
            return
        self.current_item.name = self.name_edit.text().strip() or "W?"
        self.current_item.type = self.type_combo.currentText().strip() or "Универсальный кабель"
        self.current_item.gauge = self.gauge_combo.currentText().strip() or "0.25 mm2"
        self.current_item.length = self.length_combo.currentText().strip() or "1 m"
        self.current_item.wirecount = self.wirecount_spin.value()
        self.current_item.colors = [x.strip() for x in self.colors_edit.text().split(",") if x.strip()]
        self.current_item.color_code = self.color_code_combo.currentText().strip()
        self.current_item.wirelabels = [x.strip() for x in self.wirelabels_edit.text().split(",") if x.strip()]
        self.current_item.shield = self.shield_check.isChecked()
        self.current_item.bundle = self.bundle_check.isChecked()
        self.current_item.notes = self.notes_edit.toPlainText().strip()
