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
from wirewizard_gui.ui.editors.common import (
    WIRE_COLOR_HELP,
    build_combo,
    set_combo_hint,
    set_combo_text,
    set_text_hint,
)


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
        self.pn_edit = QLineEdit()
        self.manufacturer_edit = QLineEdit()
        self.mpn_edit = QLineEdit()
        self.supplier_edit = QLineEdit()
        self.spn_edit = QLineEdit()
        self.ignore_in_bom_check = QCheckBox("Не включать в BOM")
        self.notes_edit = QPlainTextEdit()

        set_text_hint(
            self.name_edit,
            "Например: W1",
            "Уникальное обозначение кабеля в проекте: W1, W2 и т. п.",
        )
        set_combo_hint(self.type_combo, "Выберите или введите тип кабеля")
        set_combo_hint(
            self.gauge_combo,
            "Например: 0.25 mm2",
            "Сечение одной жилы. Пример формата WireViz: 0.25 mm2.",
        )
        set_combo_hint(
            self.length_combo,
            "Например: 0.5 m",
            "Длина кабеля с единицей измерения. Пример: 0.5 m.",
        )
        self.wirecount_spin.setToolTip(
            "Количество жил. Цвета и метки перечисляются в том же порядке: первая запись для жилы 1."
        )
        set_text_hint(
            self.colors_edit,
            "Например: RD, BK, GNYE",
            f"Цвета жил через запятую; порядок соответствует номерам жил. {WIRE_COLOR_HELP}",
        )
        set_combo_hint(
            self.color_code_combo,
            "Например: DIN",
            "Встроенная последовательность цветов WireViz: DIN, IEC или TEL. "
            "Оставьте пустым при явном списке цветов.",
        )
        set_text_hint(
            self.wirelabels_edit,
            "Например: +24V, GND, CAN_H",
            "Метки жил через запятую; первая метка относится к жиле 1, вторая — к жиле 2 и т. д.",
        )
        self.shield_check.setToolTip(
            "Добавить общий экран кабеля. В соединениях экран выбирается значением s."
        )
        self.bundle_check.setToolTip("Экспортировать кабель как category: bundle.")
        set_text_hint(self.pn_edit, "Например: CABLE-001", "Внутренний номер детали в вашей BOM.")
        set_text_hint(self.manufacturer_edit, "Например: LAPP")
        set_text_hint(self.mpn_edit, "Артикул производителя", "Артикул производителя (MPN).")
        set_text_hint(self.supplier_edit, "Например: Чип и Дип")
        set_text_hint(self.spn_edit, "Артикул поставщика", "Артикул поставщика (SPN).")
        self.ignore_in_bom_check.setToolTip("Не добавлять этот кабель в спецификацию WireViz.")
        set_text_hint(self.notes_edit, "Свободный комментарий к кабелю")

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
        layout.addRow("Внутренний P/N", self.pn_edit)
        layout.addRow("Производитель", self.manufacturer_edit)
        layout.addRow("MPN производителя", self.mpn_edit)
        layout.addRow("Поставщик", self.supplier_edit)
        layout.addRow("Артикул поставщика (SPN)", self.spn_edit)
        layout.addRow("", self.ignore_in_bom_check)
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
        self.current_item.pn = self.pn_edit.text().strip()
        self.current_item.manufacturer = self.manufacturer_edit.text().strip()
        self.current_item.mpn = self.mpn_edit.text().strip()
        self.current_item.supplier = self.supplier_edit.text().strip()
        self.current_item.spn = self.spn_edit.text().strip()
        self.current_item.ignore_in_bom = self.ignore_in_bom_check.isChecked()
        self.current_item.notes = self.notes_edit.toPlainText().strip()
