from __future__ import annotations

from PySide6.QtWidgets import QCheckBox, QFormLayout, QLineEdit, QPlainTextEdit, QWidget

from wirewizard_gui.domain.models import FerruleModel
from wirewizard_gui.domain.options import FERRULE_SUBTYPES, FERRULE_TYPES, WIRE_COLORS
from wirewizard_gui.ui.editors.common import (
    WIRE_COLOR_HELP,
    build_combo,
    set_combo_hint,
    set_combo_text,
    set_text_hint,
)


class FerruleEditor(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.current_item: FerruleModel | None = None

        self.name_edit = QLineEdit()
        self.type_combo = build_combo(FERRULE_TYPES)
        self.subtype_combo = build_combo(FERRULE_SUBTYPES)
        self.color_combo = build_combo(WIRE_COLORS)
        self.pn_edit = QLineEdit()
        self.manufacturer_edit = QLineEdit()
        self.mpn_edit = QLineEdit()
        self.supplier_edit = QLineEdit()
        self.spn_edit = QLineEdit()
        self.ignore_in_bom_check = QCheckBox("Не включать в BOM")
        self.notes_edit = QPlainTextEdit()

        set_text_hint(self.name_edit, "Например: F1", "Уникальное обозначение наконечника.")
        set_combo_hint(self.type_combo, "Выберите или введите тип наконечника")
        set_combo_hint(
            self.subtype_combo,
            "Например: 0.5 mm²",
            "Размер наконечника по сечению провода.",
        )
        set_combo_hint(self.color_combo, "Например: OG", WIRE_COLOR_HELP)
        set_text_hint(self.pn_edit, "Например: FERRULE-050", "Внутренний номер детали в BOM.")
        set_text_hint(self.manufacturer_edit, "Например: Phoenix Contact")
        set_text_hint(self.mpn_edit, "Артикул производителя", "Артикул производителя (MPN).")
        set_text_hint(self.supplier_edit, "Например: Mouser")
        set_text_hint(self.spn_edit, "Артикул поставщика", "Артикул поставщика (SPN).")
        self.ignore_in_bom_check.setToolTip("Не добавлять наконечник в спецификацию WireViz.")
        set_text_hint(self.notes_edit, "Свободный комментарий к наконечнику")

        layout = QFormLayout(self)
        layout.addRow("Обозначение", self.name_edit)
        layout.addRow("Тип", self.type_combo)
        layout.addRow("Подтип", self.subtype_combo)
        layout.addRow("Цвет", self.color_combo)
        layout.addRow("Внутренний P/N", self.pn_edit)
        layout.addRow("Производитель", self.manufacturer_edit)
        layout.addRow("MPN производителя", self.mpn_edit)
        layout.addRow("Поставщик", self.supplier_edit)
        layout.addRow("Артикул поставщика (SPN)", self.spn_edit)
        layout.addRow("", self.ignore_in_bom_check)
        layout.addRow("Примечания", self.notes_edit)

    def load_item(self, item: FerruleModel) -> None:
        self.current_item = item
        self.name_edit.setText(item.name)
        set_combo_text(self.type_combo, item.type)
        set_combo_text(self.subtype_combo, item.subtype)
        set_combo_text(self.color_combo, item.color)
        self.pn_edit.setText(item.pn)
        self.manufacturer_edit.setText(item.manufacturer)
        self.mpn_edit.setText(item.mpn)
        self.supplier_edit.setText(item.supplier)
        self.spn_edit.setText(item.spn)
        self.ignore_in_bom_check.setChecked(item.ignore_in_bom)
        self.notes_edit.setPlainText(item.notes)

    def save_to_item(self) -> None:
        if not self.current_item:
            return
        self.current_item.name = self.name_edit.text().strip() or "F?"
        self.current_item.type = self.type_combo.currentText().strip() or "Обжимной наконечник"
        self.current_item.subtype = self.subtype_combo.currentText().strip() or "0.5 mm²"
        self.current_item.color = self.color_combo.currentText().strip()
        self.current_item.pn = self.pn_edit.text().strip()
        self.current_item.manufacturer = self.manufacturer_edit.text().strip()
        self.current_item.mpn = self.mpn_edit.text().strip()
        self.current_item.supplier = self.supplier_edit.text().strip()
        self.current_item.spn = self.spn_edit.text().strip()
        self.current_item.ignore_in_bom = self.ignore_in_bom_check.isChecked()
        self.current_item.notes = self.notes_edit.toPlainText().strip()
