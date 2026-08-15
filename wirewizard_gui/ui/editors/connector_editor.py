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
from wirewizard_gui.ui.editors.common import (
    WIRE_COLOR_HELP,
    build_help_field,
    build_combo,
    set_combo_hint,
    set_combo_text,
    set_text_hint,
)


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
        self.pn_edit = QLineEdit()
        self.manufacturer_edit = QLineEdit()
        self.mpn_edit = QLineEdit()
        self.supplier_edit = QLineEdit()
        self.spn_edit = QLineEdit()
        self.ignore_in_bom_check = QCheckBox("Не включать в BOM")
        self.notes_edit = QPlainTextEdit()
        self.simple_check.toggled.connect(self._update_simple_state)

        set_text_hint(
            self.name_edit,
            "Например: X1",
            "Уникальное обозначение разъёма в проекте: X1, X2, J1 и т. п.",
        )
        set_combo_hint(self.type_combo, "Выберите или введите тип разъёма")
        set_combo_hint(
            self.subtype_combo,
            "Например: male или female",
            "Технический подтип WireViz: male, female, plug или socket.",
        )
        self.pincount_spin.setToolTip(
            "Общее число контактов. Списки обозначений и меток обычно содержат столько же элементов."
        )
        set_text_hint(
            self.pins_edit,
            "Например: 1, 2, A, B",
            "Обозначения контактов через запятую в порядке подключения. "
            "Их можно использовать вместо числовых индексов в соединениях.",
        )
        set_text_hint(
            self.pinlabels_edit,
            "Например: +24V, GND, SIGNAL",
            "Понятные подписи контактов через запятую. Порядок соответствует списку контактов.",
        )
        set_combo_hint(
            self.color_combo,
            "Например: BK",
            "Цвет корпуса или обозначения. Нажмите ? для легенды кодов.",
        )
        self.color_field, self.color_help_btn = build_help_field(
            self.color_combo, "Коды цветов WireViz", WIRE_COLOR_HELP
        )
        self.simple_check.setToolTip(
            "Экспортировать как style: simple без количества и списка контактов."
        )
        set_text_hint(self.pn_edit, "Например: CONN-001", "Внутренний номер детали в вашей BOM.")
        set_text_hint(self.manufacturer_edit, "Например: Molex")
        set_text_hint(self.mpn_edit, "Например: 22-01-2027", "Артикул производителя (MPN).")
        set_text_hint(self.supplier_edit, "Например: Mouser")
        set_text_hint(self.spn_edit, "Например: 538-22-01-2027", "Артикул поставщика (SPN).")
        self.ignore_in_bom_check.setToolTip("Не добавлять этот компонент в спецификацию WireViz.")
        set_text_hint(self.notes_edit, "Свободный комментарий к разъёму")

        layout = QFormLayout(self)
        layout.addRow("Обозначение", self.name_edit)
        layout.addRow("Тип", self.type_combo)
        layout.addRow("Подтип", self.subtype_combo)
        layout.addRow("Количество контактов", self.pincount_spin)
        layout.addRow("Контакты / обозначения (через запятую)", self.pins_edit)
        layout.addRow("Метки контактов (через запятую)", self.pinlabels_edit)
        layout.addRow("Цвет", self.color_field)
        layout.addRow("", self.simple_check)
        layout.addRow("Внутренний P/N", self.pn_edit)
        layout.addRow("Производитель", self.manufacturer_edit)
        layout.addRow("MPN производителя", self.mpn_edit)
        layout.addRow("Поставщик", self.supplier_edit)
        layout.addRow("Артикул поставщика (SPN)", self.spn_edit)
        layout.addRow("", self.ignore_in_bom_check)
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
        self.pn_edit.setText(item.pn)
        self.manufacturer_edit.setText(item.manufacturer)
        self.mpn_edit.setText(item.mpn)
        self.supplier_edit.setText(item.supplier)
        self.spn_edit.setText(item.spn)
        self.ignore_in_bom_check.setChecked(item.ignore_in_bom)
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
        self.current_item.pn = self.pn_edit.text().strip()
        self.current_item.manufacturer = self.manufacturer_edit.text().strip()
        self.current_item.mpn = self.mpn_edit.text().strip()
        self.current_item.supplier = self.supplier_edit.text().strip()
        self.current_item.spn = self.spn_edit.text().strip()
        self.current_item.ignore_in_bom = self.ignore_in_bom_check.isChecked()
        self.current_item.notes = self.notes_edit.toPlainText().strip()
