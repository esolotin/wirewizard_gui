from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from typing import Iterator

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QCloseEvent, QKeySequence
from PySide6.QtWidgets import (
    QDockWidget,
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
from wirewizard_gui.domain.references import ProjectReferences
from wirewizard_gui.domain.serializer import ProjectSerializer
from wirewizard_gui.domain.validation import IssueSeverity, ProjectValidator, ValidationIssue
from wirewizard_gui.services.project_service import ProjectService
from wirewizard_gui.services.wireviz_service import WireVizService
from wirewizard_gui.ui.dialogs.daisy_chain_wizard import DaisyChainWizard
from wirewizard_gui.ui.editors.cable_editor import CableEditor
from wirewizard_gui.ui.editors.connections_editor import ConnectionsEditor
from wirewizard_gui.ui.editors.connector_editor import ConnectorEditor
from wirewizard_gui.ui.editors.ferrule_editor import FerruleEditor
from wirewizard_gui.ui.editors.project_editor import ProjectEditor
from wirewizard_gui.ui.panels.svg_preview import SvgPreviewPanel
from wirewizard_gui.ui.panels.problems import ProblemsPanel
from wirewizard_gui.ui.panels.yaml_preview import YamlPreviewPanel


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.resize(1450, 850)

        self.project = self._create_demo_project()
        self.current_path: str | None = None
        self.current_path_kind: str = "json"
        self._change_tracking_depth = 1
        self._editor_pending = False
        self._dirty = False
        self._clean_state: dict | None = None
        self._current_reference_item: tuple[object, str] | None = None

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

        self.problems_panel = ProblemsPanel()
        self.problems_panel.issue_activated.connect(self._navigate_to_issue)
        self.problems_dock = QDockWidget("Проблемы", self)
        self.problems_dock.setObjectName("problems_dock")
        self.problems_dock.setWidget(self.problems_panel)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.problems_dock)

        self._connect_editor_change_signals()
        self._build_toolbar()
        self._build_shortcuts()
        self._refresh_tree()
        self.refresh_preview()
        self._clean_state = self.project.to_dict()
        self._change_tracking_depth = 0
        self._update_dirty_state()

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

    def _build_shortcuts(self) -> None:
        shortcuts = [
            ("new_project_action", "Новый проект", "Ctrl+N", self.new_project),
            ("open_project_action", "Открыть проект", "Ctrl+O", self.open_project),
            ("save_project_action", "Сохранить проект", "Ctrl+S", self.save_project),
            ("save_project_as_action", "Сохранить проект как", "Ctrl+Shift+S", self.save_project_as),
        ]
        for attribute, text, shortcut, callback in shortcuts:
            action = QAction(text, self)
            action.setShortcut(QKeySequence(shortcut))
            action.triggered.connect(callback)
            self.addAction(action)
            setattr(self, attribute, action)

    def _connect_editor_change_signals(self) -> None:
        line_edits = [
            self.project_editor.title_edit,
            self.connector_editor.name_edit,
            self.connector_editor.pins_edit,
            self.connector_editor.pinlabels_edit,
            self.cable_editor.name_edit,
            self.cable_editor.colors_edit,
            self.cable_editor.wirelabels_edit,
            self.ferrule_editor.name_edit,
        ]
        for editor in line_edits:
            editor.textChanged.connect(self._on_editor_content_changed)

        plain_text_edits = [
            self.project_editor.description_edit,
            self.connector_editor.notes_edit,
            self.cable_editor.notes_edit,
            self.ferrule_editor.notes_edit,
        ]
        for editor in plain_text_edits:
            editor.textChanged.connect(self._on_editor_content_changed)

        combo_boxes = [
            self.connector_editor.type_combo,
            self.connector_editor.subtype_combo,
            self.connector_editor.color_combo,
            self.cable_editor.type_combo,
            self.cable_editor.gauge_combo,
            self.cable_editor.length_combo,
            self.cable_editor.color_code_combo,
            self.ferrule_editor.type_combo,
            self.ferrule_editor.subtype_combo,
            self.ferrule_editor.color_combo,
        ]
        for combo_box in combo_boxes:
            combo_box.currentTextChanged.connect(self._on_editor_content_changed)

        self.connector_editor.pincount_spin.valueChanged.connect(self._on_editor_content_changed)
        self.cable_editor.wirecount_spin.valueChanged.connect(self._on_editor_content_changed)
        self.connector_editor.simple_check.toggled.connect(self._on_editor_content_changed)
        self.cable_editor.shield_check.toggled.connect(self._on_editor_content_changed)
        self.cable_editor.bundle_check.toggled.connect(self._on_editor_content_changed)
        self.connections_editor.content_changed.connect(self._on_editor_content_changed)
        self.connector_editor.name_edit.editingFinished.connect(self._commit_current_component_rename)
        self.cable_editor.name_edit.editingFinished.connect(self._commit_current_component_rename)
        self.ferrule_editor.name_edit.editingFinished.connect(self._commit_current_component_rename)

    def _create_demo_project(self) -> ProjectModel:
        return ProjectModel(
            title="Демонстрационный жгут",
            description="Простой начальный проект WireWizardGUI",
            connectors=[
                ConnectorModel(name="X1", type="Molex KK 254", subtype="female", pincount=2, pinlabels=["A", "B"]),
                ConnectorModel(name="X2", type="Molex KK 254", subtype="female", pincount=2, pinlabels=["A", "B"]),
                ConnectorModel(name="X3", type="Клеммная колодка", subtype="plug", pincount=2, pinlabels=["1", "2"]),
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

    @contextmanager
    def _suspend_change_tracking(self) -> Iterator[None]:
        self._change_tracking_depth += 1
        try:
            yield
        finally:
            self._change_tracking_depth -= 1

    def _on_editor_content_changed(self, *_args) -> None:
        if self._change_tracking_depth:
            return
        self._editor_pending = True
        self._save_current_editor(finalize_name=False)

    def _save_current_editor(self, *, finalize_name: bool = True) -> None:
        if self._editor_pending:
            idx = self.editor_stack.currentIndex()
            try:
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
            finally:
                self._editor_pending = False
            self._update_dirty_state()
        if finalize_name:
            self._commit_current_component_rename()

    def _commit_current_component_rename(self) -> None:
        if self._change_tracking_depth or self._current_reference_item is None:
            return
        item, previous_name = self._current_reference_item
        current_name = str(getattr(item, "name", "")).strip()
        if current_name == previous_name:
            return

        all_items = [*self.project.connectors, *self.project.cables, *self.project.ferrules]
        if any(other is not item and other.name == current_name for other in all_items):
            with self._suspend_change_tracking():
                item.name = previous_name
                name_edit = self._current_component_name_edit()
                if name_edit is not None:
                    name_edit.setText(previous_name)
            QMessageBox.warning(
                self,
                "Переименование компонента",
                f"Обозначение {current_name!r} уже используется. Переименование отменено.",
            )
            self._update_dirty_state()
            return

        changed_rows = ProjectReferences.rename_component(
            self.project, previous_name, current_name
        )
        self._current_reference_item = (item, current_name)
        current_tree_item = self.project_tree.currentItem()
        if current_tree_item is not None:
            payload = current_tree_item.data(0, Qt.UserRole)
            if payload and payload[1] is item:
                current_tree_item.setText(0, current_name)
        self.connections_editor.set_component_sources(
            self.project.connectors, self.project.cables, self.project.ferrules
        )
        self._update_dirty_state()
        if changed_rows:
            rows = ", ".join(str(index + 1) for index in changed_rows)
            self.statusBar().showMessage(f"Ссылки обновлены в строках: {rows}", 5000)

    def _current_component_name_edit(self):
        index = self.editor_stack.currentIndex()
        if index == 2:
            return self.connector_editor.name_edit
        if index == 3:
            return self.cable_editor.name_edit
        if index == 4:
            return self.ferrule_editor.name_edit
        return None

    def _update_dirty_state(self) -> None:
        dirty = self._clean_state is None or self.project.to_dict() != self._clean_state
        if dirty != self._dirty:
            self._dirty = dirty
            self.setWindowModified(dirty)
        self._update_window_title()

    def _update_window_title(self) -> None:
        document_name = Path(self.current_path).name if self.current_path else self.project.title.strip()
        document_name = document_name or "Без имени"
        marker = " *" if self._dirty else ""
        self.setWindowTitle(f"WireWizardGUI — {document_name}{marker}")

    def _mark_clean(self) -> None:
        self._clean_state = self.project.to_dict()
        self._update_dirty_state()

    def _install_project(self, project: ProjectModel, path: str | None, *, dirty: bool) -> None:
        previous_project = self.project
        previous_path = self.current_path
        previous_path_kind = self.current_path_kind
        previous_clean_state = self._clean_state

        try:
            with self._suspend_change_tracking():
                self._editor_pending = False
                self._current_reference_item = None
                self.editor_stack.setCurrentIndex(0)
                self.project = project
                self.current_path = path
                self.current_path_kind = "json"
                self._refresh_tree()
                self.refresh_preview()
            self._clean_state = None if dirty else self.project.to_dict()
            self._update_dirty_state()
        except BaseException:
            with self._suspend_change_tracking():
                self._editor_pending = False
                self._current_reference_item = None
                self.editor_stack.setCurrentIndex(0)
                self.project = previous_project
                self.current_path = previous_path
                self.current_path_kind = previous_path_kind
                try:
                    self._refresh_tree()
                    self.refresh_preview()
                except BaseException:
                    pass
            self._clean_state = previous_clean_state
            self._update_dirty_state()
            raise

    def _confirm_unsaved_changes(self, action: str) -> bool:
        self._save_current_editor()
        if not self._dirty:
            return True

        answer = self._ask_unsaved_changes(action)
        if answer == QMessageBox.StandardButton.Save:
            return self.save_project()
        return answer == QMessageBox.StandardButton.Discard

    def _ask_unsaved_changes(self, action: str) -> QMessageBox.StandardButton:
        dialog = QMessageBox(self)
        dialog.setIcon(QMessageBox.Icon.Warning)
        dialog.setWindowTitle("Несохранённые изменения")
        dialog.setText(f"В проекте есть несохранённые изменения. Сохранить их перед тем, как {action}?")
        dialog.setStandardButtons(
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel
        )
        labels = {
            QMessageBox.StandardButton.Save: "Сохранить",
            QMessageBox.StandardButton.Discard: "Не сохранять",
            QMessageBox.StandardButton.Cancel: "Отмена",
        }
        for standard_button, label in labels.items():
            button = dialog.button(standard_button)
            if button is not None:
                button.setText(label)
        dialog.setDefaultButton(QMessageBox.StandardButton.Save)
        dialog.exec()
        clicked_button = dialog.clickedButton()
        if clicked_button is None:
            return QMessageBox.StandardButton.Cancel
        return dialog.standardButton(clicked_button)

    def _on_tree_selection_changed(self) -> None:
        self._save_current_editor()
        self.svg_preview.set_highlight(None)
        with self._suspend_change_tracking():
            self._current_reference_item = None
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
                self._current_reference_item = (obj, obj.name)
                self.editor_stack.setCurrentIndex(2)
                self.svg_preview.set_highlight(obj.name)
            elif kind == "cable":
                self.cable_editor.load_item(obj)
                self._current_reference_item = (obj, obj.name)
                self.editor_stack.setCurrentIndex(3)
                self.svg_preview.set_highlight(obj.name)
            elif kind == "ferrule":
                self.ferrule_editor.load_item(obj)
                self._current_reference_item = (obj, obj.name)
                self.editor_stack.setCurrentIndex(4)
                self.svg_preview.set_highlight(obj.name)
            elif kind == "connections":
                self.connections_editor.load_items(obj)
                self.editor_stack.setCurrentIndex(5)
            else:
                self.editor_stack.setCurrentIndex(0)
        self._editor_pending = False

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
        if not self._confirm_unsaved_changes("создать новый проект"):
            return
        try:
            self._install_project(ProjectModel(title="Новый жгут"), None, dirty=False)
        except Exception as exc:
            QMessageBox.critical(self, "Новый проект", str(exc))

    def open_project(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Открыть проект или YAML",
            "",
            "Файлы проекта (*.json *.wwg.json *.yml *.yaml);;Файлы JSON (*.json);;Файлы YAML (*.yml *.yaml)",
        )
        if not path:
            return
        if not self._confirm_unsaved_changes("открыть другой проект"):
            return
        try:
            project = ProjectService.load_project(path)
            is_json = Path(path).suffix.lower() == ".json"
            self._install_project(project, path if is_json else None, dirty=not is_json)
            self.statusBar().showMessage(f"Открыт файл: {path}", 4000)
        except Exception as exc:
            QMessageBox.critical(self, "Открытие проекта", str(exc))

    def import_yaml(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Импорт YAML WireViz", "", "Файлы YAML (*.yml *.yaml)")
        if not path:
            return
        if not self._confirm_unsaved_changes("импортировать YAML"):
            return
        try:
            project = ProjectService.import_yaml(path)
            self._install_project(project, None, dirty=True)
            self.statusBar().showMessage(f"Импортирован YAML: {path}", 4000)
        except Exception as exc:
            QMessageBox.critical(self, "Импорт YAML", str(exc))

    def save_project(self) -> bool:
        self._save_current_editor()
        path = self.current_path
        if not path:
            return self.save_project_as()
        try:
            ProjectService.save_project(path, self.project)
        except Exception as exc:
            QMessageBox.critical(self, "Сохранение проекта", str(exc))
            return False
        self._mark_clean()
        self.statusBar().showMessage(f"Проект сохранён: {path}", 4000)
        self._refresh_tree()
        return True

    def save_project_as(self) -> bool:
        self._save_current_editor()
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить проект как",
            self.current_path or "project.json",
            "Проект JSON (*.json)",
        )
        if not path:
            return False
        try:
            ProjectService.save_project(path, self.project)
        except Exception as exc:
            QMessageBox.critical(self, "Сохранение проекта", str(exc))
            return False
        self.current_path = path
        self.current_path_kind = "json"
        self._mark_clean()
        self.statusBar().showMessage(f"Проект сохранён: {path}", 4000)
        self._refresh_tree()
        return True

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
        issues = self._validate_project()
        errors = [issue for issue in issues if issue.severity == IssueSeverity.ERROR]
        if errors:
            QMessageBox.critical(
                self,
                "Построение в WireViz",
                "Исправьте ошибки перед запуском WireViz:\n\n"
                + "\n".join(f"• {issue.message}" for issue in errors),
            )
            self.problems_dock.show()
            return
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
        self._update_dirty_state()
        self._refresh_tree()
        self.refresh_preview()

    def add_cable(self) -> None:
        self._save_current_editor()
        new_name = self._next_name("W", [item.name for item in self.project.cables])
        self.project.cables.append(CableModel(name=new_name))
        self._update_dirty_state()
        self._refresh_tree()
        self.refresh_preview()

    def add_ferrule(self) -> None:
        self._save_current_editor()
        new_name = self._next_name("F", [item.name for item in self.project.ferrules])
        self.project.ferrules.append(FerruleModel(name=new_name))
        self._update_dirty_state()
        self._refresh_tree()
        self.refresh_preview()

    def add_connection_row(self) -> None:
        self._save_current_editor()
        seed = self._default_route_template()
        self.project.connections.append(ConnectionRowModel(route=seed))
        self._update_dirty_state()
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
        self._update_dirty_state()
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
        self._update_dirty_state()
        self._refresh_tree()
        self.refresh_preview()

    def delete_selected_item(self) -> None:
        self._save_current_editor()
        payload = self._selected_payload()
        if not payload:
            return
        kind, obj = payload
        if kind in {"connector", "cable", "ferrule"}:
            dependent_rows = ProjectReferences.dependent_rows(self.project, obj.name)
            if not self._confirm_component_deletion(obj.name, dependent_rows):
                return
            ProjectReferences.remove_dependent_rows(self.project, obj.name)
            self._current_reference_item = None

        if kind == "connector":
            self.project.connectors = [x for x in self.project.connectors if x is not obj]
        elif kind == "cable":
            self.project.cables = [x for x in self.project.cables if x is not obj]
        elif kind == "ferrule":
            self.project.ferrules = [x for x in self.project.ferrules if x is not obj]
        elif kind == "connections":
            self.project.connections = []
        else:
            return
        self._update_dirty_state()
        self._refresh_tree()
        self.refresh_preview()

    def _confirm_component_deletion(self, component_name: str, dependent_rows: list[int]) -> bool:
        dialog = QMessageBox(self)
        dialog.setIcon(QMessageBox.Icon.Warning)
        dialog.setWindowTitle("Удаление компонента")
        if dependent_rows:
            row_numbers = ", ".join(str(index + 1) for index in dependent_rows)
            dialog.setText(
                f"Компонент {component_name} используется в строках {row_numbers}. "
                "Удалить компонент вместе с этими строками?"
            )
            dialog.setDetailedText(
                "\n".join(
                    f"{index + 1}: {self.project.connections[index].route}"
                    for index in dependent_rows
                )
            )
            delete_label = "Удалить вместе со строками"
        else:
            dialog.setText(f"Удалить компонент {component_name}?")
            delete_label = "Удалить"

        delete_button = dialog.addButton(delete_label, QMessageBox.ButtonRole.DestructiveRole)
        cancel_button = dialog.addButton("Отмена", QMessageBox.ButtonRole.RejectRole)
        dialog.setDefaultButton(cancel_button)
        dialog.exec()
        return dialog.clickedButton() is delete_button

    def refresh_preview(self) -> None:
        self._save_current_editor()
        self._refresh_tree()

        issues = self._validate_project()
        errors = [issue for issue in issues if issue.severity == IssueSeverity.ERROR]
        warnings = [issue for issue in issues if issue.severity == IssueSeverity.WARNING]
        yaml_text = ProjectSerializer.to_wireviz_yaml(self.project)
        if errors:
            yaml_text += "\n\n# Ошибки проверки:\n"
            yaml_text += "\n".join(f"# - {issue.message}" for issue in errors)
        if warnings:
            yaml_text += "\n\n# Предупреждения проверки:\n"
            yaml_text += "\n".join(f"# - {issue.message}" for issue in warnings)
        self.yaml_preview.setPlainText(yaml_text)

        if errors:
            self.svg_preview.show_message(
                "Исправьте ошибки в панели проблем перед построением предпросмотра."
            )
            self.statusBar().showMessage(
                f"Ошибок: {len(errors)}; предупреждений: {len(warnings)}", 5000
            )
            return

        ok, message, svg_text = WireVizService.render_svg(self.project)
        if ok and svg_text:
            self.svg_preview.show_svg(svg_text)
            status = "Предпросмотр построен"
            if warnings:
                status += f"; предупреждений: {len(warnings)}"
            self.statusBar().showMessage(status, 5000)
        else:
            preview_message = message
            if warnings:
                preview_message += "\n\nПредупреждения проверки:\n" + "\n".join(
                    issue.message for issue in warnings
                )
            self.svg_preview.show_message(preview_message)
            self.statusBar().showMessage(message, 5000)

    def _validate_project(self) -> list[ValidationIssue]:
        issues = ProjectValidator.validate_issues(self.project)
        self.problems_panel.set_issues(issues)
        return issues

    def _navigate_to_issue(self, issue: ValidationIssue) -> None:
        root = self.project_tree.topLevelItem(0)
        if root is None:
            return

        if issue.row_index is not None:
            connections_group = root.child(3)
            if connections_group is not None and connections_group.childCount():
                self.project_tree.setCurrentItem(connections_group.child(0))
                row = min(issue.row_index, self.connections_editor.table.rowCount() - 1)
                if row >= 0:
                    self.connections_editor.table.setCurrentCell(row, 0)
                    self.connections_editor.table.scrollTo(
                        self.connections_editor.table.model().index(row, 0)
                    )
                return

        if issue.component_name:
            for group_index in range(3):
                group = root.child(group_index)
                if group is None:
                    continue
                for child_index in range(group.childCount()):
                    child = group.child(child_index)
                    payload = child.data(0, Qt.UserRole)
                    if payload and payload[1].name == issue.component_name:
                        self.project_tree.setCurrentItem(child)
                        return

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._confirm_unsaved_changes("закрыть приложение"):
            event.accept()
        else:
            event.ignore()

    @staticmethod
    def _next_name(prefix: str, existing: list[str]) -> str:
        idx = 1
        while f"{prefix}{idx}" in existing:
            idx += 1
        return f"{prefix}{idx}"
