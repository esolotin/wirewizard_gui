from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt, Signal
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
    content_changed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._suppress_content_changed = False
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
        self.value_combo.currentTextChanged.connect(self._value_changed)

        self._component_meta: dict[str, tuple[str, list[str]]] = {}

    def set_component_options(self, ordered_components: list[tuple[str, str, list[str]]]) -> None:
        previous = self._suppress_content_changed
        self._suppress_content_changed = True
        try:
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
        finally:
            self._suppress_content_changed = previous

    def component(self) -> str:
        data = self.component_combo.currentData()
        if data is None:
            text = self.component_combo.currentText().strip()
            return text if text else ""
        return str(data)

    def value(self) -> str:
        return self.value_combo.currentText().strip()

    def set_component(self, name: str) -> None:
        idx = -1
        for i in range(self.component_combo.count()):
            if self.component_combo.itemData(i) == name:
                idx = i
                break
        if idx >= 0:
            self.component_combo.setCurrentIndex(idx)
        else:
            self.component_combo.setCurrentIndex(-1)
            self.component_combo.setEditText(name)
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
        previous = self._suppress_content_changed
        self._suppress_content_changed = True
        try:
            self.set_component(part.component)
            self.set_value(part.value)
        finally:
            self._suppress_content_changed = previous

    def part(self) -> _PartModel:
        return _PartModel(component=self.component(), value=self.value())

    def _component_changed(self) -> None:
        notify = not self._suppress_content_changed
        previous = self._suppress_content_changed
        self._suppress_content_changed = True
        try:
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
        finally:
            self._suppress_content_changed = previous
        if notify:
            self.content_changed.emit()

    def _value_changed(self) -> None:
        if not self._suppress_content_changed:
            self.content_changed.emit()


class ConnectionsEditor(QWidget):
    content_changed = Signal()

    INITIAL_STEPS = 7
    MAX_MANUAL_STEPS = 99

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._suppress_content_changed = False
        self.current_items: list[ConnectionRowModel] = []
        self.connectors: list[ConnectorModel] = []
        self.cables: list[CableModel] = []
        self.ferrules: list[FerruleModel] = []
        self.visible_steps = 5

        self.table = QTableWidget(0, self.INITIAL_STEPS)
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
        self.steps_spin.setRange(3, self.MAX_MANUAL_STEPS)
        self.steps_spin.setSingleStep(1)
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
        previous = self._suppress_content_changed
        self._suppress_content_changed = True
        try:
            self.current_items = items
            self.table.setRowCount(0)
            for item in items:
                self.add_row(item.route)
        finally:
            self._suppress_content_changed = previous

    def add_row(self, route: str = "") -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)
        for col in range(self.table.columnCount()):
            cell = _RouteCell(self.table)
            cell.set_component_options(self._component_options())
            cell.content_changed.connect(self._emit_content_changed)
            self.table.setCellWidget(row, col, cell)
        if route:
            self._apply_route_to_row(row, route)
        else:
            self._prefill_row(row)
        self.table.setCurrentCell(row, 0)
        self._emit_content_changed()

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
        if rows:
            self._emit_content_changed()

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
        self.table.setHorizontalHeaderLabels([f"Шаг {idx}" for idx in range(1, self.table.columnCount() + 1)])
        self.table.horizontalHeader().setStretchLastSection(False)
        for col in range(self.table.columnCount()):
            self.table.setColumnWidth(col, 220)

    def _set_visible_steps(self, value: int) -> None:
        self._ensure_step_count(value)
        self.visible_steps = max(3, value)
        self.steps_spin.blockSignals(True)
        self.steps_spin.setValue(self.visible_steps)
        self.steps_spin.blockSignals(False)
        for col in range(self.table.columnCount()):
            self.table.setColumnHidden(col, col >= self.visible_steps)

    def _ensure_step_count(self, count: int) -> None:
        count = max(3, count)
        old_count = self.table.columnCount()
        if count <= old_count:
            return

        self.table.setColumnCount(count)
        self.steps_spin.setMaximum(max(self.steps_spin.maximum(), count))
        options = self._component_options()
        for row in range(self.table.rowCount()):
            for col in range(old_count, count):
                cell = _RouteCell(self.table)
                cell.set_component_options(options)
                cell.content_changed.connect(self._emit_content_changed)
                self.table.setCellWidget(row, col, cell)
        self._rebuild_headers()

    def _emit_content_changed(self) -> None:
        if not self._suppress_content_changed:
            self.content_changed.emit()

    def _refresh_all_cell_options(self) -> None:
        options = self._component_options()
        for row in range(self.table.rowCount()):
            for col in range(self.table.columnCount()):
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
        parts = ProjectSerializer._split_route(route)
        self._ensure_step_count(len(parts))
        for col in range(self.table.columnCount()):
            cell = self.table.cellWidget(row, col)
            if isinstance(cell, _RouteCell):
                cell.set_part(_PartModel())
        for col, part in enumerate(parts):
            component = part
            value = ""
            parsed = ProjectSerializer._parse_connection_part(part)
            if isinstance(parsed, dict) and parsed:
                component, parsed_value = next(iter(parsed.items()))
                value = ProjectSerializer._format_connection_value(parsed_value)
            cell = self.table.cellWidget(row, col)
            if isinstance(cell, _RouteCell):
                cell.set_part(_PartModel(str(component).strip(), value))
        needed = max(3, len(parts))
        if needed > self.visible_steps:
            self._set_visible_steps(needed)

    def _route_from_row(self, row: int) -> str:
        parts: list[str] = []
        for col in range(self.table.columnCount()):
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
