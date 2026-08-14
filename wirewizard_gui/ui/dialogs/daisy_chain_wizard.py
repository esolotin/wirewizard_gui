from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from wirewizard_gui.domain.models import CableModel, ConnectorModel
from wirewizard_gui.ui.editors.common import build_combo


@dataclass
class DaisyChainPlan:
    connectors: list[str]
    cable_template: str
    start_pin: int
    pin_count: int
    zig_zag: bool


class DaisyChainWizard(QDialog):
    def __init__(self, connectors: list[ConnectorModel], cables: list[CableModel], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Мастер шлейфового соединения")
        self.resize(460, 420)
        self._connectors = connectors
        self._cables = cables

        info = QLabel(
            "Выберите не менее двух разъёмов в порядке соединения, выберите кабель "
            "и задайте диапазон контактов.\n"
            "Мастер создаст новые сегменты на основе выбранного шаблона кабеля "
            "и по одной строке соединения для каждого контакта каждого сегмента."
        )
        info.setWordWrap(True)

        self.connectors_list = QListWidget()
        self.connectors_list.setSelectionMode(QListWidget.MultiSelection)
        for connector in connectors:
            item = QListWidgetItem(self._connector_display(connector))
            item.setData(Qt.UserRole, connector.name)
            item.setSelected(True)
            self.connectors_list.addItem(item)

        self.cable_combo = build_combo([cable.name for cable in cables], editable=False)
        self.start_pin_spin = QSpinBox()
        self.start_pin_spin.setMinimum(1)
        self.start_pin_spin.setMaximum(999)
        self.pin_count_spin = QSpinBox()
        self.pin_count_spin.setMinimum(1)
        self.pin_count_spin.setMaximum(999)
        self.pin_count_spin.setValue(2)
        self.zig_zag_check = QCheckBox("Разворачивать порядок контактов в каждом втором сегменте")

        self.limit_label = QLabel()
        self.limit_label.setWordWrap(True)

        form_widget = QWidget()
        form = QFormLayout(form_widget)
        form.addRow(info)
        form.addRow("Порядок разъёмов", self.connectors_list)
        form.addRow("Шаблон кабеля", self.cable_combo)
        form.addRow("Начальный контакт", self.start_pin_spin)
        form.addRow("Количество контактов", self.pin_count_spin)
        form.addRow("", self.zig_zag_check)
        form.addRow("Ограничения", self.limit_label)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("Создать")
        buttons.button(QDialogButtonBox.Cancel).setText("Отмена")
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(form_widget)
        layout.addWidget(buttons)

        self.connectors_list.itemSelectionChanged.connect(self._update_limits)
        self.cable_combo.currentTextChanged.connect(self._update_limits)
        self._update_limits()

    def _connector_display(self, connector: ConnectorModel) -> str:
        if connector.pins:
            capacity = len(connector.pins)
        else:
            capacity = max(1, connector.pincount)
        return f"{connector.name} (контактов: {capacity})"

    def _selected_connector_models(self) -> list[ConnectorModel]:
        order = []
        by_name = {c.name: c for c in self._connectors}
        for item in self.connectors_list.selectedItems():
            name = item.data(Qt.UserRole)
            if name in by_name:
                order.append(by_name[name])
        return order

    def _current_cable(self) -> CableModel | None:
        name = self.cable_combo.currentText().strip()
        for cable in self._cables:
            if cable.name == name:
                return cable
        return None

    def _connector_capacity(self, connector: ConnectorModel) -> int:
        if connector.pins:
            return len(connector.pins)
        return max(1, connector.pincount)

    def _update_limits(self) -> None:
        selected = self._selected_connector_models()
        cable = self._current_cable()
        connector_limit = min((self._connector_capacity(c) for c in selected), default=1)
        cable_limit = max(1, cable.wirecount) if cable else 1
        max_pin_count = max(1, min(connector_limit, cable_limit))

        self.pin_count_spin.blockSignals(True)
        self.start_pin_spin.blockSignals(True)
        self.pin_count_spin.setMaximum(max_pin_count)
        if self.pin_count_spin.value() > max_pin_count:
            self.pin_count_spin.setValue(max_pin_count)
        max_start = max(1, connector_limit - self.pin_count_spin.value() + 1)
        self.start_pin_spin.setMaximum(max_start)
        if self.start_pin_spin.value() > max_start:
            self.start_pin_spin.setValue(max_start)
        self.pin_count_spin.blockSignals(False)
        self.start_pin_spin.blockSignals(False)

        cable_name = cable.name if cable else "<не выбран>"
        self.limit_label.setText(
            f"Выбрано разъёмов: {len(selected)} | Шаблон: {cable_name} | "
            f"Максимум доступных контактов за шаг: {max_pin_count}"
        )
        self.pin_count_spin.valueChanged.connect(self._update_limits_start_only)

    def _update_limits_start_only(self) -> None:
        selected = self._selected_connector_models()
        connector_limit = min((self._connector_capacity(c) for c in selected), default=1)
        max_start = max(1, connector_limit - self.pin_count_spin.value() + 1)
        self.start_pin_spin.setMaximum(max_start)
        if self.start_pin_spin.value() > max_start:
            self.start_pin_spin.setValue(max_start)

    def _accept(self) -> None:
        selected = self._selected_connector_models()
        if len(selected) < 2:
            QMessageBox.warning(self, "Шлейфовое соединение", "Выберите не менее двух разъёмов.")
            return
        cable = self._current_cable()
        if cable is None:
            QMessageBox.warning(self, "Шлейфовое соединение", "Выберите кабель.")
            return
        connector_limit = min(self._connector_capacity(c) for c in selected)
        if self.start_pin_spin.value() + self.pin_count_spin.value() - 1 > connector_limit:
            QMessageBox.warning(
                self,
                "Шлейфовое соединение",
                "Выбранный диапазон контактов не помещается во всех выбранных разъёмах.",
            )
            return
        if self.pin_count_spin.value() > max(1, cable.wirecount):
            QMessageBox.warning(
                self,
                "Шлейфовое соединение",
                "В выбранном кабеле недостаточно жил для этого соединения.",
            )
            return
        self.accept()

    def selected_connectors(self) -> list[str]:
        return [connector.name for connector in self._selected_connector_models()]

    def plan(self) -> DaisyChainPlan:
        return DaisyChainPlan(
            connectors=self.selected_connectors(),
            cable_template=self.cable_combo.currentText().strip(),
            start_pin=self.start_pin_spin.value(),
            pin_count=self.pin_count_spin.value(),
            zig_zag=self.zig_zag_check.isChecked(),
        )
