from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QFileDialog,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QToolBar,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
    QDialog,
)

from wirewizard_gui.domain.models import (
    CableModel,
    ConnectionRowModel,
    ConnectorModel,
    FerruleModel,
    ProjectModel,
)
from wirewizard_gui.domain.serializer import ProjectSerializer
from wirewizard_gui.domain.validation import ProjectValidator
from wirewizard_gui.services.project_service import ProjectService
from wirewizard_gui.services.wireviz_service import WireVizService
from wirewizard_gui.ui.dialogs.daisy_chain_wizard import DaisyChainWizard
from wirewizard_gui.ui.editors.cable_editor import CableEditor
from wirewizard_gui.ui.editors.connections_editor import ConnectionsEditor
from wirewizard_gui.ui.editors.connector_editor import ConnectorEditor
from wirewizard_gui.ui.editors.ferrule_editor import FerruleEditor
from wirewizard_gui.ui.editors.project_editor import ProjectEditor
from wirewizard_gui.ui.panels.svg_preview import SvgPreviewPanel
from wirewizard_gui.ui.panels.yaml_preview import YamlPreviewPanel


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("WireWizardGUI")
        self.resize(1450, 850)

        self.project = self._create_demo_project()
        self.current_path: str | None = None
        self.current_path_kind: str = "json"

        self.project_tree = QTreeWidget()
        self.project_tree.setHeaderLabels(["Состав проекта"])
        self.project_tree.itemSelectionChanged.connect(self._on_tree_selection_changed)
        self.project_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.project_tree.customContextMenuRequested.connect(self._show_tree_context_menu)

        self.project_editor = ProjectEditor()
        self.connector_editor = ConnectorEditor()
        self.cable_editor = CableEditor()
        self.ferrule_editor = FerruleEditor()
        self.connections_editor = ConnectionsEditor()
        self.connections_editor.set_component_sources(self.project.connectors, self.project.cables, self.project.ferrules)
        self.placeholder = QLabel("Выбери элемент в дереве слева.")
        self.placeholder.setAlignment(Qt.AlignCenter)

        self.editor_stack = QStackedWidget()
        self.editor_stack.addWidget(self.placeholder)
        self.editor_stack.addWidget(self.project_editor)
        self.editor_stack.addWidget(self.connector_editor)
        self.editor_stack.addWidget(self.cable_editor)
        self.editor_stack.addWidget(self.ferrule_editor)
        self.editor_stack.addWidget(self.connections_editor)

        self.yaml_preview = YamlPreviewPanel()
        self.svg_preview = SvgPreviewPanel()

        center = QWidget()
        self.setCentralWidget(center)
        layout = QVBoxLayout(center)

        splitter_main = QSplitter(Qt.Horizontal)
        splitter_right = QSplitter(Qt.Vertical)
        splitter_right.addWidget(self.yaml_preview)
        splitter_right.addWidget(self.svg_preview)
        splitter_right.setSizes([350, 450])

        splitter_main.addWidget(self.project_tree)
        splitter_main.addWidget(self.editor_stack)
        splitter_main.addWidget(splitter_right)
        splitter_main.setSizes([280, 420, 700])
        layout.addWidget(splitter_main)

        self._build_toolbar()
        self._refresh_tree()
        self.refresh_preview()

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("Основная панель")
        self.addToolBar(toolbar)

        buttons: list[tuple[str, callable]] = [
            ("Новый проект", self.new_project),
            ("Открыть проект", self.open_project),
            ("Импорт YAML", self.import_yaml),
            ("Сохранить", self.save_project),
            ("Сохранить как", self.save_project_as),
            ("Экспорт YAML", self.export_yaml),
            ("Построить в WireViz", self.run_wireviz),
            ("Создать шлейф", self.open_daisy_chain_wizard),
            ("Обновить предпросмотр", self.refresh_preview),
        ]
        for text, callback in buttons:
            btn = QPushButton(text)
            btn.clicked.connect(callback)
            toolbar.addWidget(btn)

    def _create_demo_project(self) -> ProjectModel:
        return ProjectModel(
            title="Демонстрационный жгут",
            description="Простой начальный проект WireWizardGUI",
            connectors=[
                ConnectorModel(name="X1", type="Molex KK 254", subtype="гнездовой", pincount=2, pinlabels=["A", "B"]),
                ConnectorModel(name="X2", type="Molex KK 254", subtype="гнездовой", pincount=2, pinlabels=["A", "B"]),
                ConnectorModel(name="X3", type="Клеммная колодка", subtype="вилка", pincount=2, pinlabels=["1", "2"]),
            ],
            cables=[
                CableModel(name="W1", type="Монтажный провод", gauge="0.25 mm2", length="0.5 m", wirecount=2, colors=["RD", "BK"]),
                CableModel(name="W2", type="Пучок проводов", gauge="0.25 mm2", length="0.2 m", wirecount=1, bundle=True),
            ],
            ferrules=[
                FerruleModel(name="F1", type="Обжимной наконечник", subtype="0.5 mm²", color="OG"),
            ],
            connections=[
                ConnectionRowModel(route="X1:1 -> W1:1 -> X2:1"),
                ConnectionRowModel(route="X1:2 -> W1:2 -> F1 -> W2:1 -> X2:2"),
            ],
        )

    def _refresh_tree(self) -> None:
        self.project_tree.clear()
        root = QTreeWidgetItem([self.project.title])
        root.setData(0, Qt.UserRole, ("project", self.project))
        self.project_tree.addTopLevelItem(root)

        connectors_root = QTreeWidgetItem(["Разъёмы"])
        cables_root = QTreeWidgetItem(["Кабели"])
        ferrules_root = QTreeWidgetItem(["Наконечники"])
        connections_root = QTreeWidgetItem(["Соединения"])
        connectors_root.setData(0, Qt.UserRole, ("group_connectors", None))
        cables_root.setData(0, Qt.UserRole, ("group_cables", None))
        ferrules_root.setData(0, Qt.UserRole, ("group_ferrules", None))
        connections_root.setData(0, Qt.UserRole, ("group_connections", None))

        root.addChild(connectors_root)
        root.addChild(cables_root)
        root.addChild(ferrules_root)
        root.addChild(connections_root)

        for item in self.project.connectors:
            node = QTreeWidgetItem([item.name])
            node.setData(0, Qt.UserRole, ("connector", item))
            connectors_root.addChild(node)

        for item in self.project.cables:
            node = QTreeWidgetItem([item.name])
            node.setData(0, Qt.UserRole, ("cable", item))
            cables_root.addChild(node)

        for item in self.project.ferrules:
            node = QTreeWidgetItem([item.name])
            node.setData(0, Qt.UserRole, ("ferrule", item))
            ferrules_root.addChild(node)

        node = QTreeWidgetItem([f"Строк: {len(self.project.connections)}"])
        node.setData(0, Qt.UserRole, ("connections", self.project.connections))
        connections_root.addChild(node)

        self.project_tree.expandAll()
        self.connections_editor.set_component_sources(self.project.connectors, self.project.cables, self.project.ferrules)

    def _save_current_editor(self) -> None:
        idx = self.editor_stack.currentIndex()
        if idx == 1:
            self.project_editor.save_to_item()
        elif idx == 2:
            self.connector_editor.save_to_item()
        elif idx == 3:
            self.cable_editor.save_to_item()
        elif idx == 4:
            self.ferrule_editor.save_to_item()
        elif idx == 5:
            self.project.connections = self.connections_editor.save_to_items()

    def _on_tree_selection_changed(self) -> None:
        self._save_current_editor()
        items = self.project_tree.selectedItems()
        if not items:
            self.editor_stack.setCurrentIndex(0)
            return
        payload = items[0].data(0, Qt.UserRole)
        if not payload:
            self.editor_stack.setCurrentIndex(0)
            return
        kind, obj = payload
        if kind == "project":
            self.project_editor.load_item(obj)
            self.editor_stack.setCurrentIndex(1)
        elif kind == "connector":
            self.connector_editor.load_item(obj)
            self.editor_stack.setCurrentIndex(2)
        elif kind == "cable":
            self.cable_editor.load_item(obj)
            self.editor_stack.setCurrentIndex(3)
        elif kind == "ferrule":
            self.ferrule_editor.load_item(obj)
            self.editor_stack.setCurrentIndex(4)
        elif kind == "connections":
            self.connections_editor.load_items(obj)
            self.editor_stack.setCurrentIndex(5)
        else:
            self.editor_stack.setCurrentIndex(0)

    def _selected_payload(self):
        items = self.project_tree.selectedItems()
        if not items:
            return None
        return items[0].data(0, Qt.UserRole)

    def _show_tree_context_menu(self, pos) -> None:
        item = self.project_tree.itemAt(pos)
        if item is not None:
            self.project_tree.setCurrentItem(item)
        menu = QMenu(self)

        def add_action(text: str, callback) -> QAction:
            action = menu.addAction(text)
            action.triggered.connect(callback)
            return action

        payload = item.data(0, Qt.UserRole) if item else None
        kind = payload[0] if payload else None

        add_action("Открыть проект", self.open_project)
        add_action("Импортировать YAML", self.import_yaml)
        add_action("Сохранить проект", self.save_project)
        add_action("Экспортировать YAML", self.export_yaml)
        add_action("Построить в WireViz", self.run_wireviz)
        menu.addSeparator()

        if kind in {"project", "group_connectors", None}:
            add_action("Добавить разъём", self.add_connector)
        if kind in {"project", "group_cables", None}:
            add_action("Добавить кабель", self.add_cable)
        if kind in {"project", "group_ferrules", None}:
            add_action("Добавить наконечник", self.add_ferrule)
        if kind in {"project", "group_connections", "connections", None}:
            add_action("Добавить строку соединения", self.add_connection_row)
            add_action("Открыть мастер шлейфа", self.open_daisy_chain_wizard)

        if kind in {"connector", "cable", "ferrule"}:
            menu.addSeparator()
            add_action("Дублировать", self.duplicate_selected_item)
            add_action("Удалить", self.delete_selected_item)

        if kind == "connections":
            menu.addSeparator()
            add_action("Дублировать все строки", self.duplicate_selected_item)
            add_action("Удалить все строки соединений", self.delete_selected_item)

        menu.addSeparator()
        add_action("Обновить предпросмотр", self.refresh_preview)
        menu.exec(self.project_tree.viewport().mapToGlobal(pos))

    def new_project(self) -> None:
        self._save_current_editor()
        self.project = ProjectModel(title="Новый жгут")
        self.current_path = None
        self.current_path_kind = "json"
        self._refresh_tree()
        self.refresh_preview()

    def open_project(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Открыть проект или YAML",
            "",
            "Файлы проекта (*.json *.wwg.json *.yml *.yaml);;Файлы JSON (*.json);;Файлы YAML (*.yml *.yaml)",
        )
        if not path:
            return
        try:
            self.project = ProjectService.load_project(path)
            self.current_path = path if Path(path).suffix.lower() == ".json" else None
            self.current_path_kind = "json"
            self._refresh_tree()
            self.refresh_preview()
            self.statusBar().showMessage(f"Открыт файл: {path}", 4000)
        except Exception as exc:
            QMessageBox.critical(self, "Открытие проекта", str(exc))

    def import_yaml(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Импорт YAML WireViz", "", "Файлы YAML (*.yml *.yaml)")
        if not path:
            return
        try:
            self.project = ProjectService.import_yaml(path)
            self.current_path = None
            self.current_path_kind = "json"
            self._refresh_tree()
            self.refresh_preview()
            self.statusBar().showMessage(f"Импортирован YAML: {path}", 4000)
        except Exception as exc:
            QMessageBox.critical(self, "Импорт YAML", str(exc))

    def save_project(self) -> None:
        self._save_current_editor()
        path = self.current_path
        if not path:
            self.save_project_as()
            return
        try:
            ProjectService.save_project(path, self.project)
            self.statusBar().showMessage(f"Проект сохранён: {path}", 4000)
            self._refresh_tree()
        except Exception as exc:
            QMessageBox.critical(self, "Сохранение проекта", str(exc))

    def save_project_as(self) -> None:
        self._save_current_editor()
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить проект как",
            self.current_path or "project.json",
            "Проект JSON (*.json)",
        )
        if not path:
            return
        try:
            ProjectService.save_project(path, self.project)
            self.current_path = path
            self.current_path_kind = "json"
            self.statusBar().showMessage(f"Проект сохранён: {path}", 4000)
            self._refresh_tree()
        except Exception as exc:
            QMessageBox.critical(self, "Сохранение проекта", str(exc))

    def export_yaml(self) -> None:
        self._save_current_editor()
        path, _ = QFileDialog.getSaveFileName(self, "Экспорт YAML", "project.yml", "Файлы YAML (*.yml *.yaml)")
        if not path:
            return
        try:
            ProjectService.export_yaml(path, self.project)
            self.statusBar().showMessage(f"YAML экспортирован: {path}", 4000)
        except Exception as exc:
            QMessageBox.critical(self, "Экспорт YAML", str(exc))

    def run_wireviz(self) -> None:
        self._save_current_editor()
        suggested = Path(self.current_path).stem if self.current_path else (self.project.title.strip() or "harness")
        safe_name = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in suggested).strip("_") or "harness"
        output_dir = QFileDialog.getExistingDirectory(self, "Выберите папку для результатов WireViz")
        if not output_dir:
            return
        ok, message, generated = WireVizService.run_full(self.project, output_dir, safe_name)
        if ok:
            self.statusBar().showMessage(message, 6000)
            QMessageBox.information(self, "Построение в WireViz", message)
        else:
            QMessageBox.critical(self, "Построение в WireViz", message)

    def add_connector(self) -> None:
        self._save_current_editor()
        new_name = self._next_name("X", [item.name for item in self.project.connectors])
        self.project.connectors.append(ConnectorModel(name=new_name))
        self._refresh_tree()
        self.refresh_preview()

    def add_cable(self) -> None:
        self._save_current_editor()
        new_name = self._next_name("W", [item.name for item in self.project.cables])
        self.project.cables.append(CableModel(name=new_name))
        self._refresh_tree()
        self.refresh_preview()

    def add_ferrule(self) -> None:
        self._save_current_editor()
        new_name = self._next_name("F", [item.name for item in self.project.ferrules])
        self.project.ferrules.append(FerruleModel(name=new_name))
        self._refresh_tree()
        self.refresh_preview()

    def add_connection_row(self) -> None:
        self._save_current_editor()
        seed = self._default_route_template()
        self.project.connections.append(ConnectionRowModel(route=seed))
        self._refresh_tree()
        self.refresh_preview()

    def _default_route_template(self) -> str:
        left = self.project.connectors[0].name if self.project.connectors else "X1"
        cable = self.project.cables[0].name if self.project.cables else "W1"
        right = self.project.connectors[1].name if len(self.project.connectors) > 1 else left
        return f"{left}:1 -> {cable}:1 -> {right}:1"

    def open_daisy_chain_wizard(self) -> None:
        self._save_current_editor()
        if len(self.project.connectors) < 2:
            QMessageBox.warning(self, "Шлейфовое соединение", "Сначала добавьте не менее двух разъёмов.")
            return
        if not self.project.cables:
            QMessageBox.warning(self, "Шлейфовое соединение", "Сначала добавьте хотя бы один кабель.")
            return
        dialog = DaisyChainWizard(
            connectors=self.project.connectors,
            cables=self.project.cables,
            parent=self,
        )
        if dialog.exec() != QDialog.Accepted:
            return
        plan = dialog.plan()
        generated: list[ConnectionRowModel] = []
        segment_count = len(plan.connectors) - 1
        if segment_count < 1:
            return

        template = next((cable for cable in self.project.cables if cable.name == plan.cable_template), None)
        if template is None:
            QMessageBox.warning(self, "Шлейфовое соединение", "Выбранный шаблон кабеля не найден.")
            return

        existing_cable_names = [item.name for item in self.project.cables]
        created_cables = []
        for segment_index in range(segment_count):
            segment_name = self._next_name("W", existing_cable_names)
            existing_cable_names.append(segment_name)
            segment_cable = deepcopy(template)
            segment_cable.name = segment_name
            created_cables.append(segment_cable)

            left = plan.connectors[segment_index]
            right = plan.connectors[segment_index + 1]
            reverse = plan.zig_zag and (segment_index % 2 == 1)
            for offset in range(plan.pin_count):
                connector_pin = plan.start_pin + offset
                target_pin = plan.start_pin + (plan.pin_count - 1 - offset if reverse else offset)
                wire_index = offset + 1
                generated.append(
                    ConnectionRowModel(route=f"{left}:{connector_pin} -> {segment_name}:{wire_index} -> {right}:{target_pin}")
                )

        self.project.cables.extend(created_cables)
        self.project.connections.extend(generated)
        self._refresh_tree()
        self.refresh_preview()
        self.statusBar().showMessage(
            f"Создано сегментов шлейфа: {len(created_cables)}; строк соединений: {len(generated)}.",
            5000,
        )

    def duplicate_selected_item(self) -> None:
        self._save_current_editor()
        payload = self._selected_payload()
        if not payload:
            return
        kind, obj = payload
        if kind == "connector":
            clone = deepcopy(obj)
            clone.name = self._next_name("X", [item.name for item in self.project.connectors])
            self.project.connectors.append(clone)
        elif kind == "cable":
            clone = deepcopy(obj)
            clone.name = self._next_name("W", [item.name for item in self.project.cables])
            self.project.cables.append(clone)
        elif kind == "ferrule":
            clone = deepcopy(obj)
            clone.name = self._next_name("F", [item.name for item in self.project.ferrules])
            self.project.ferrules.append(clone)
        elif kind == "connections":
            self.project.connections.extend(deepcopy(self.project.connections))
        else:
            return
        self._refresh_tree()
        self.refresh_preview()

    def delete_selected_item(self) -> None:
        payload = self._selected_payload()
        if not payload:
            return
        kind, obj = payload
        if kind == "connector":
            self.project.connectors = [x for x in self.project.connectors if x is not obj]
        elif kind == "cable":
            self.project.cables = [x for x in self.project.cables if x is not obj]
        elif kind == "ferrule":
            self.project.ferrules = [x for x in self.project.ferrules if x is not obj]
        elif kind == "connections":
            self.project.connections = []
        self._refresh_tree()
        self.refresh_preview()

    def refresh_preview(self) -> None:
        self._save_current_editor()
        self._refresh_tree()

        errors = ProjectValidator.validate(self.project)
        yaml_text = ProjectSerializer.to_wireviz_yaml(self.project)
        if errors:
            yaml_text += "\n\n# Предупреждения проверки:\n"
            yaml_text += "\n".join(f"# - {err}" for err in errors)
        self.yaml_preview.setPlainText(yaml_text)

        ok, message, svg_text = WireVizService.render_svg(self.project)
        if ok and svg_text:
            self.svg_preview.show_svg(svg_text)
            status = "Предпросмотр построен"
            if errors:
                status += f"; предупреждений: {len(errors)}"
            self.statusBar().showMessage(status, 5000)
        else:
            preview_message = message
            if errors:
                preview_message += "\n\nПредупреждения проверки:\n" + "\n".join(errors)
            self.svg_preview.show_message(preview_message)
            self.statusBar().showMessage(message, 5000)

    @staticmethod
    def _next_name(prefix: str, existing: list[str]) -> str:
        idx = 1
        while f"{prefix}{idx}" in existing:
            idx += 1
        return f"{prefix}{idx}"
