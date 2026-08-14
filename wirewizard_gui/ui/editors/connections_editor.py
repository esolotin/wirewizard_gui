from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from wirewizard_gui.domain.models import CableModel, ConnectionRowModel, ConnectorModel, FerruleModel
from wirewizard_gui.domain.serializer import ProjectSerializer


@dataclass
class _PartModel:
    component: str = ""
    value: str = ""


class _RouteCell(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.component_combo = QComboBox()
        self.component_combo.setEditable(True)
        self.value_combo = QComboBox()
        self.value_combo.setEditable(True)
        self.value_combo.setInsertPolicy(QComboBox.NoInsert)
        self.value_combo.setMinimumContentsLength(8)

        layout = QGridLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.addWidget(self.component_combo, 0, 0)
        layout.addWidget(self.value_combo, 0, 1)
        layout.setColumnStretch(0, 3)
        layout.setColumnStretch(1, 2)

        self.component_combo.currentTextChanged.connect(self._component_changed)

        self._component_meta: dict[str, tuple[str, list[str]]] = {}

    def set_component_options(self, ordered_components: list[tuple[str, str, list[str]]]) -> None:
        current_component = self.component()
        current_value = self.value()
        self._component_meta = {name: (kind, values) for name, kind, values in ordered_components}
        self.component_combo.blockSignals(True)
        self.component_combo.clear()
        self.component_combo.addItem("")
        for name, kind, _values in ordered_components:
            label = name if kind != "ferrule" else f"{name} (наконечник)"
            self.component_combo.addItem(label, userData=name)
        self.component_combo.blockSignals(False)
        self.set_component(current_component)
        self.set_value(current_value)
        self._component_changed()

    def component(self) -> str:
        data = self.component_combo.currentData()
        if data is None:
            text = self.component_combo.currentText().strip()
            return text if text else ""
        return str(data)

    def value(self) -> str:
        return self.value_combo.currentText().strip()

    def set_component(self, name: str) -> None:
        idx = 0
        for i in range(self.component_combo.count()):
            if self.component_combo.itemData(i) == name:
                idx = i
                break
        self.component_combo.setCurrentIndex(idx)
        self._component_changed()

    def set_value(self, value: str) -> None:
        if not value:
            self.value_combo.setCurrentText("")
            return
        idx = self.value_combo.findText(value)
        if idx >= 0:
            self.value_combo.setCurrentIndex(idx)
        else:
            self.value_combo.setCurrentText(value)

    def set_part(self, part: _PartModel) -> None:
        self.set_component(part.component)
        self.set_value(part.value)

    def part(self) -> _PartModel:
        return _PartModel(component=self.component(), value=self.value())

    def _component_changed(self) -> None:
        component_name = self.component()
        current_value = self.value()
        self.value_combo.blockSignals(True)
        self.value_combo.clear()
        self.value_combo.addItem("")
        if component_name and component_name in self._component_meta:
            _kind, values = self._component_meta[component_name]
            for value in values:
                self.value_combo.addItem(value)
        self.value_combo.blockSignals(False)
        self.set_value(current_value)


class ConnectionsEditor(QWidget):
    MAX_STEPS = 7

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.current_items: list[ConnectionRowModel] = []
        self.connectors: list[ConnectorModel] = []
        self.cables: list[CableModel] = []
        self.ferrules: list[FerruleModel] = []
        self.visible_steps = 5

        self.table = QTableWidget(0, self.MAX_STEPS)
        self.table.verticalHeader().setVisible(True)

        self.help_label = QLabel(
            "Табличный редактор соединений. В каждой ячейке выберите компонент и номер контакта или жилы. "
            "Пустые конечные ячейки игнорируются; для экрана используйте значение 's'."
        )
        self.help_label.setWordWrap(True)

        self.add_btn = QPushButton("Добавить строку")
        self.duplicate_btn = QPushButton("Дублировать выбранное")
        self.remove_btn = QPushButton("Удалить выбранное")
        self.compact_btn = QPushButton("Убрать пропуски")
        self.add_btn.clicked.connect(self.add_row)
        self.duplicate_btn.clicked.connect(self.duplicate_selected)
        self.remove_btn.clicked.connect(self.remove_selected)
        self.compact_btn.clicked.connect(self.compact_selected)

        self.steps_spin = QSpinBox()
        self.steps_spin.setRange(3, self.MAX_STEPS)
        self.steps_spin.setSingleStep(2)
        self.steps_spin.setValue(self.visible_steps)
        self.steps_spin.setPrefix("Видимых шагов: ")
        self.steps_spin.valueChanged.connect(self._set_visible_steps)

        controls = QHBoxLayout()
        controls.addWidget(self.add_btn)
        controls.addWidget(self.duplicate_btn)
        controls.addWidget(self.remove_btn)
        controls.addWidget(self.compact_btn)
        controls.addStretch(1)
        controls.addWidget(self.steps_spin)

        layout = QVBoxLayout(self)
        layout.addWidget(self.help_label)
        layout.addLayout(controls)
        layout.addWidget(self.table)

        self._rebuild_headers()
        self._set_visible_steps(self.visible_steps)

    def set_component_sources(
        self,
        connectors: list[ConnectorModel],
        cables: list[CableModel],
        ferrules: list[FerruleModel],
    ) -> None:
        self.connectors = connectors
        self.cables = cables
        self.ferrules = ferrules
        self._refresh_all_cell_options()

    def load_items(self, items: list[ConnectionRowModel]) -> None:
        self.current_items = items
        self.table.setRowCount(0)
        for item in items:
            self.add_row(item.route)

    def add_row(self, route: str = "") -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)
        for col in range(self.MAX_STEPS):
            cell = _RouteCell(self.table)
            cell.set_component_options(self._component_options())
            self.table.setCellWidget(row, col, cell)
        if route:
            self._apply_route_to_row(row, route)
        else:
            self._prefill_row(row)
        self.table.setCurrentCell(row, 0)

    def duplicate_selected(self) -> None:
        rows = sorted({idx.row() for idx in self.table.selectedIndexes()})
        if not rows and self.table.currentRow() >= 0:
            rows = [self.table.currentRow()]
        for row in rows:
            self.add_row(self._route_from_row(row))

    def remove_selected(self) -> None:
        rows = sorted({idx.row() for idx in self.table.selectedIndexes()}, reverse=True)
        if not rows and self.table.currentRow() >= 0:
            rows = [self.table.currentRow()]
        for row in rows:
            self.table.removeRow(row)

    def compact_selected(self) -> None:
        rows = sorted({idx.row() for idx in self.table.selectedIndexes()})
        if not rows and self.table.currentRow() >= 0:
            rows = [self.table.currentRow()]
        for row in rows:
            route = self._route_from_row(row)
            self._apply_route_to_row(row, route)

    def save_to_items(self) -> list[ConnectionRowModel]:
        items: list[ConnectionRowModel] = []
        for row in range(self.table.rowCount()):
            route = self._route_from_row(row)
            if route:
                items.append(ConnectionRowModel(route=route))
        self.current_items[:] = items
        return items

    def _component_options(self) -> list[tuple[str, str, list[str]]]:
        options: list[tuple[str, str, list[str]]] = []
        for item in self.connectors:
            values = [str(i) for i in range(1, max(1, item.pincount) + 1)]
            if item.pins:
                values = [str(v) for v in item.pins]
            elif item.pinlabels:
                values = [str(v) for v in item.pinlabels]
            options.append((item.name, "connector", values))
        for item in self.cables:
            values = [str(i) for i in range(1, max(1, item.wirecount) + 1)]
            if item.shield:
                values.append("s")
            options.append((item.name, "cable", values))
        for item in self.ferrules:
            options.append((item.name, "ferrule", []))
        return options

    def _rebuild_headers(self) -> None:
        self.table.setHorizontalHeaderLabels([f"Шаг {idx}" for idx in range(1, self.MAX_STEPS + 1)])
        self.table.horizontalHeader().setStretchLastSection(False)
        for col in range(self.MAX_STEPS):
            self.table.setColumnWidth(col, 220)

    def _set_visible_steps(self, value: int) -> None:
        if value % 2 == 0:
            value += 1
        self.visible_steps = max(3, min(self.MAX_STEPS, value))
        self.steps_spin.blockSignals(True)
        self.steps_spin.setValue(self.visible_steps)
        self.steps_spin.blockSignals(False)
        for col in range(self.MAX_STEPS):
            self.table.setColumnHidden(col, col >= self.visible_steps)

    def _refresh_all_cell_options(self) -> None:
        options = self._component_options()
        for row in range(self.table.rowCount()):
            for col in range(self.MAX_STEPS):
                cell = self.table.cellWidget(row, col)
                if isinstance(cell, _RouteCell):
                    cell.set_component_options(options)

    def _prefill_row(self, row: int) -> None:
        if not self.connectors or not self.cables:
            return
        left = self.connectors[0].name
        cable = self.cables[0].name
        right = self.connectors[1].name if len(self.connectors) > 1 else self.connectors[0].name
        defaults = [
            _PartModel(left, "1"),
            _PartModel(cable, "1"),
            _PartModel(right, "1"),
        ]
        for col, part in enumerate(defaults):
            cell = self.table.cellWidget(row, col)
            if isinstance(cell, _RouteCell):
                cell.set_part(part)

    def _apply_route_to_row(self, row: int, route: str) -> None:
        for col in range(self.MAX_STEPS):
            cell = self.table.cellWidget(row, col)
            if isinstance(cell, _RouteCell):
                cell.set_part(_PartModel())
        parts = [part.strip() for part in route.split("->") if part.strip()]
        for col, part in enumerate(parts[: self.MAX_STEPS]):
            component = part
            value = ""
            if ":" in part:
                component, raw_value = part.split(":", 1)
                parsed = ProjectSerializer._parse_value(raw_value.strip())
                value = ProjectSerializer._format_connection_value(parsed)
            cell = self.table.cellWidget(row, col)
            if isinstance(cell, _RouteCell):
                cell.set_part(_PartModel(component.strip(), value))
        needed = min(self.MAX_STEPS, max(3, len(parts) if len(parts) % 2 == 1 else len(parts) + 1))
        if needed > self.visible_steps:
            self._set_visible_steps(needed)

    def _route_from_row(self, row: int) -> str:
        parts: list[str] = []
        for col in range(self.MAX_STEPS):
            cell = self.table.cellWidget(row, col)
            if not isinstance(cell, _RouteCell):
                continue
            part = cell.part()
            if not part.component:
                continue
            if part.value:
                parts.append(f"{part.component}:{part.value}")
            else:
                parts.append(part.component)
        return " -> ".join(parts)
