from __future__ import annotations

from copy import deepcopy
import os
from pathlib import Path
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    import PySide6  # noqa: F401
except ModuleNotFoundError:
    PYSIDE_AVAILABLE = False
else:
    PYSIDE_AVAILABLE = True


@unittest.skipUnless(PYSIDE_AVAILABLE, "PySide6 is not installed")
class MainWindowDocumentStateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.render_patch = patch(
            "wirewizard_gui.ui.main_window.WireVizService.render_svg",
            return_value=(False, "Предпросмотр недоступен", None),
        )
        self.render_patch.start()
        self.addCleanup(self.render_patch.stop)

    def _make_window(self):
        from wirewizard_gui.ui.main_window import MainWindow

        window = MainWindow()
        self.addCleanup(self._close_without_prompt, window)
        self._wait_for_wireviz(window)
        return window

    def _make_session_window(self, service):
        from wirewizard_gui.ui.main_window import MainWindow

        window = MainWindow(session_service=service)
        self.addCleanup(self._close_without_prompt, window)
        self._wait_for_wireviz(window)
        return window

    def test_recovery_is_offered_and_restored_as_unsaved_work(self) -> None:
        from PySide6.QtWidgets import QMessageBox

        from wirewizard_gui.domain.models import ProjectModel
        from wirewizard_gui.services.session_service import SessionService

        with tempfile.TemporaryDirectory() as tmp:
            service = SessionService(tmp)
            original_path = str(Path(tmp) / "original.json")
            service.save_recovery(ProjectModel(title="Восстановленный проект"), original_path)

            with patch.object(
                QMessageBox,
                "question",
                return_value=QMessageBox.StandardButton.Yes,
            ):
                window = self._make_session_window(service)

            self.assertEqual(window.project.title, "Восстановленный проект")
            self.assertEqual(window.current_path, original_path)
            self.assertTrue(window._dirty)
            self.assertTrue(window.windowTitle().endswith(" *"))

    def test_session_tracks_recent_json_and_saves_layout_on_close(self) -> None:
        from wirewizard_gui.domain.models import ProjectModel
        from wirewizard_gui.services.project_service import ProjectService
        from wirewizard_gui.services.session_service import SessionService

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project_path = root / "recent.json"
            ProjectService.save_project(project_path, ProjectModel(title="Недавний"))
            service = SessionService(root / "session")
            window = self._make_session_window(service)

            window._open_project_path(str(project_path))

            self.assertEqual(service.recent_projects(), [str(project_path.resolve())])
            self.assertEqual(window.recent_menu.actions()[0].text(), str(project_path.resolve()))
            window.resize(1111, 777)
            window.close()
            geometry, state = service.load_layout()
            self.assertTrue(geometry)
            self.assertTrue(state)

    def test_dirty_edit_automatically_writes_and_clean_save_removes_recovery(self) -> None:
        from wirewizard_gui.services.session_service import SessionService

        with tempfile.TemporaryDirectory() as tmp:
            service = SessionService(tmp)
            window = self._make_session_window(service)
            self._make_dirty(window)
            deadline = time.monotonic() + 2.0
            while not service.recovery_path.exists() and time.monotonic() < deadline:
                self.app.processEvents()
                time.sleep(0.01)

            self.assertTrue(service.recovery_path.exists())
            with patch(
                "wirewizard_gui.ui.main_window.QFileDialog.getSaveFileName",
                return_value=(str(Path(tmp) / "saved.json"), ""),
            ):
                self.assertTrue(window.save_project_as())
            self.assertFalse(service.recovery_path.exists())

    def _wait_for_wireviz(self, window, timeout: float = 3.0) -> None:
        deadline = time.monotonic() + timeout
        while window._wireviz_tasks and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(0.005)
        self.app.processEvents()
        self.assertFalse(window._wireviz_tasks, "Фоновая задача WireViz не завершилась")

    def _close_without_prompt(self, window) -> None:
        with patch.object(window, "_confirm_unsaved_changes", return_value=True):
            window.close()
        window.deleteLater()
        self.app.processEvents()

    @staticmethod
    def _select_project(window) -> None:
        window.project_tree.setCurrentItem(window.project_tree.topLevelItem(0))

    def _make_dirty(self, window) -> None:
        self._select_project(window)
        window.project_editor.title_edit.setText(f"{window.project.title} изменён")
        self.assertTrue(window._dirty)

    def test_field_edit_sets_dirty_marker_and_revert_clears_it(self) -> None:
        window = self._make_window()
        original_title = window.project.title

        self._select_project(window)
        window.project_editor.title_edit.setText("Изменённый проект")

        self.assertTrue(window._dirty)
        self.assertTrue(window.isWindowModified())
        self.assertEqual(window.project.title, "Изменённый проект")
        self.assertTrue(window.windowTitle().endswith(" *"), window.windowTitle())

        window.project_editor.title_edit.setText(original_title)

        self.assertFalse(window._dirty)
        self.assertFalse(window.isWindowModified())
        self.assertNotIn("*", window.windowTitle())

    def test_selection_refresh_and_presentation_changes_do_not_set_dirty(self) -> None:
        window = self._make_window()
        original = window.project.to_dict()
        root = window.project_tree.topLevelItem(0)
        nodes = [
            root,
            root.child(0),
            root.child(0).child(0),
            root.child(1).child(0),
            root.child(2).child(0),
            root.child(3).child(0),
        ]

        for node in nodes:
            window.project_tree.setCurrentItem(node)
            self.assertFalse(window._dirty, node.text(0))

        window.connections_editor.steps_spin.setValue(6)
        window.connections_editor.set_component_sources(
            window.project.connectors,
            window.project.cables,
            window.project.ferrules,
        )
        window.refresh_preview()

        self.assertFalse(window._dirty)
        self.assertEqual(window.project.to_dict(), original)

    def test_structural_add_operations_set_dirty(self) -> None:
        cases = [
            ("add_connector", "connectors"),
            ("add_cable", "cables"),
            ("add_ferrule", "ferrules"),
            ("add_connection_row", "connections"),
        ]

        for method_name, collection_name in cases:
            with self.subTest(method=method_name):
                window = self._make_window()
                before = len(getattr(window.project, collection_name))

                getattr(window, method_name)()

                self.assertEqual(len(getattr(window.project, collection_name)), before + 1)
                self.assertTrue(window._dirty)
                self.assertTrue(window.windowTitle().endswith(" *"))

    def test_duplicated_component_gets_a_new_internal_id(self) -> None:
        window = self._make_window()
        connector_node = window.project_tree.topLevelItem(0).child(0).child(0)
        window.project_tree.setCurrentItem(connector_node)
        original_id = window.project.connectors[0].id

        window.duplicate_selected_item()
        self._wait_for_wireviz(window)

        clone = window.project.connectors[-1]
        self.assertNotEqual(clone.id, original_id)
        self.assertEqual(len({item.id for item in window.project.connectors}), 4)

    def test_star_bulk_wiring_is_generated_and_reversible(self) -> None:
        from PySide6.QtWidgets import QDialog

        window = self._make_window()
        cable_count = len(window.project.cables)
        connection_count = len(window.project.connections)
        dialog = Mock()
        dialog.exec.return_value = QDialog.DialogCode.Accepted
        dialog.plan.return_value = SimpleNamespace(
            mode="star",
            connectors=["X1", "X2", "X3"],
            cable_template="W1",
            start_pin=1,
            pin_count=1,
            zig_zag=False,
        )

        with patch(
            "wirewizard_gui.ui.main_window.BulkWiringWizard", return_value=dialog
        ):
            window.open_bulk_wiring_wizard()
        self._wait_for_wireviz(window)

        self.assertEqual(len(window.project.cables), cable_count + 2)
        self.assertEqual(len(window.project.connections), connection_count + 2)
        generated = [row.route for row in window.project.connections[-2:]]
        self.assertTrue(generated[0].startswith("X1:1 -> W3:1 -> X2:1"))
        self.assertTrue(generated[1].startswith("X1:1 -> W4:1 -> X3:1"))

        window.undo_stack.undo()
        self._wait_for_wireviz(window)
        self.assertEqual(len(window.project.cables), cable_count)
        self.assertEqual(len(window.project.connections), connection_count)

    def test_component_editor_signals_immediately_update_right_model(self) -> None:
        window = self._make_window()

        for case in ("connector_combo", "cable_spin", "cable_check", "ferrule_plain_text"):
            with self.subTest(case=case):
                window._install_project(window._create_demo_project(), None, dirty=False)
                root = window.project_tree.topLevelItem(0)

                if case == "connector_combo":
                    window.project_tree.setCurrentItem(root.child(0).child(0))
                    window.connector_editor.type_combo.setEditText("Тестовый разъём")
                    self.assertEqual(window.project.connectors[0].type, "Тестовый разъём")
                elif case == "cable_spin":
                    window.project_tree.setCurrentItem(root.child(1).child(0))
                    new_count = window.project.cables[0].wirecount + 1
                    window.cable_editor.wirecount_spin.setValue(new_count)
                    self.assertEqual(window.project.cables[0].wirecount, new_count)
                elif case == "cable_check":
                    window.project_tree.setCurrentItem(root.child(1).child(0))
                    new_shield = not window.project.cables[0].shield
                    window.cable_editor.shield_check.setChecked(new_shield)
                    self.assertEqual(window.project.cables[0].shield, new_shield)
                else:
                    window.project_tree.setCurrentItem(root.child(2).child(0))
                    window.ferrule_editor.notes_edit.setPlainText("Проверка наконечника")
                    self.assertEqual(window.project.ferrules[0].notes, "Проверка наконечника")

                self.assertTrue(window._dirty)
                self.assertTrue(window.windowTitle().endswith(" *"))

    def test_bom_editor_fields_update_models_and_support_undo(self) -> None:
        window = self._make_window()

        cases = [
            (0, window.connector_editor.mpn_edit, "connectors", "mpn", "MPN-1"),
            (1, window.cable_editor.pn_edit, "cables", "pn", "WIRE-1"),
            (2, window.ferrule_editor.spn_edit, "ferrules", "spn", "SPN-1"),
        ]
        for tree_group, editor, collection, attribute, value in cases:
            with self.subTest(attribute=attribute):
                window._install_project(window._create_demo_project(), None, dirty=False)
                node = window.project_tree.topLevelItem(0).child(tree_group).child(0)
                window.project_tree.setCurrentItem(node)

                editor.setText(value)

                item = getattr(window.project, collection)[0]
                self.assertEqual(getattr(item, attribute), value)
                window.undo_stack.undo()
                self._wait_for_wireviz(window)
                item = getattr(window.project, collection)[0]
                self.assertEqual(getattr(item, attribute), "")

        window._install_project(window._create_demo_project(), None, dirty=False)
        node = window.project_tree.topLevelItem(0).child(1).child(0)
        window.project_tree.setCurrentItem(node)
        window.cable_editor.ignore_in_bom_check.setChecked(True)
        self.assertTrue(window.project.cables[0].ignore_in_bom)

    def test_connection_cell_and_row_changes_set_dirty(self) -> None:
        window = self._make_window()
        connections_node = window.project_tree.topLevelItem(0).child(3).child(0)
        window.project_tree.setCurrentItem(connections_node)
        cell = window.connections_editor.table.cellWidget(0, 0)

        cell.component_combo.setCurrentIndex(cell.component_combo.findData("X2"))

        self.assertTrue(window._dirty)
        self.assertTrue(window.project.connections[0].route.startswith("X2:"))

        window._install_project(window._create_demo_project(), None, dirty=False)
        connections_node = window.project_tree.topLevelItem(0).child(3).child(0)
        window.project_tree.setCurrentItem(connections_node)
        before = len(window.project.connections)

        window.connections_editor.add_row()

        self.assertEqual(len(window.project.connections), before + 1)
        self.assertTrue(window._dirty)

    def test_connections_editor_suppresses_load_signals_but_emits_user_changes(self) -> None:
        from unittest.mock import Mock

        from wirewizard_gui.domain.models import CableModel, ConnectionRowModel, ConnectorModel
        from wirewizard_gui.ui.editors.connections_editor import ConnectionsEditor

        editor = ConnectionsEditor()
        self.addCleanup(editor.close)
        editor.set_component_sources(
            [ConnectorModel(name="X1"), ConnectorModel(name="X2")],
            [CableModel(name="W1")],
            [],
        )
        changed = Mock()
        editor.content_changed.connect(changed)

        editor.load_items([ConnectionRowModel(route="X1:1 -> W1:1 -> X2:1")])
        changed.assert_not_called()

        editor.add_row()
        self.assertGreaterEqual(changed.call_count, 1)

        changed.reset_mock()
        editor.remove_selected()
        self.assertGreaterEqual(changed.call_count, 1)

        changed.reset_mock()
        cell = editor.table.cellWidget(0, 0)
        cell.component_combo.setCurrentIndex(cell.component_combo.findData("X2"))
        self.assertGreaterEqual(changed.call_count, 1)

    def test_successful_save_clears_dirty_and_marker(self) -> None:
        window = self._make_window()
        window.current_path = "saved-project.json"
        self._make_dirty(window)

        with patch("wirewizard_gui.ui.main_window.ProjectService.save_project") as save:
            result = window.save_project()

        self.assertTrue(result)
        save.assert_called_once_with("saved-project.json", window.project)
        self.assertFalse(window._dirty)
        self.assertFalse(window.isWindowModified())
        self.assertNotIn("*", window.windowTitle())

    def test_save_as_cancel_and_save_error_keep_dirty_state(self) -> None:
        window = self._make_window()
        self._make_dirty(window)

        with (
            patch(
                "wirewizard_gui.ui.main_window.QFileDialog.getSaveFileName",
                return_value=("", ""),
            ),
            patch("wirewizard_gui.ui.main_window.ProjectService.save_project") as save,
        ):
            result = window.save_project()

        self.assertFalse(result)
        self.assertIsNone(window.current_path)
        self.assertTrue(window._dirty)
        save.assert_not_called()

        window.current_path = "existing.json"
        with (
            patch(
                "wirewizard_gui.ui.main_window.ProjectService.save_project",
                side_effect=OSError("disk full"),
            ),
            patch("wirewizard_gui.ui.main_window.QMessageBox.critical") as critical,
        ):
            result = window.save_project()

        self.assertFalse(result)
        self.assertEqual(window.current_path, "existing.json")
        self.assertTrue(window._dirty)
        critical.assert_called_once()

    def test_confirmation_maps_save_discard_and_cancel(self) -> None:
        from PySide6.QtWidgets import QMessageBox

        window = self._make_window()
        self._make_dirty(window)

        with (
            patch.object(
                window,
                "_ask_unsaved_changes",
                return_value=QMessageBox.StandardButton.Save,
            ),
            patch.object(window, "save_project", return_value=False) as save,
        ):
            self.assertFalse(window._confirm_unsaved_changes("продолжить"))
            save.assert_called_once_with()

        with patch.object(
            window,
            "_ask_unsaved_changes",
            return_value=QMessageBox.StandardButton.Discard,
        ):
            self.assertTrue(window._confirm_unsaved_changes("продолжить"))

        with patch.object(
            window,
            "_ask_unsaved_changes",
            return_value=QMessageBox.StandardButton.Cancel,
        ):
            self.assertFalse(window._confirm_unsaved_changes("продолжить"))

    def test_new_project_cancel_preserves_and_discard_replaces_document(self) -> None:
        from PySide6.QtWidgets import QMessageBox

        window = self._make_window()
        self._make_dirty(window)
        old_project = window.project
        old_state = window.project.to_dict()

        with patch.object(
            window,
            "_ask_unsaved_changes",
            return_value=QMessageBox.StandardButton.Cancel,
        ):
            window.new_project()

        self.assertIs(window.project, old_project)
        self.assertEqual(window.project.to_dict(), old_state)
        self.assertTrue(window._dirty)

        with patch.object(
            window,
            "_ask_unsaved_changes",
            return_value=QMessageBox.StandardButton.Discard,
        ):
            window.new_project()

        self.assertIsNot(window.project, old_project)
        self.assertEqual(window.project.title, "Новый жгут")
        self.assertFalse(window._dirty)
        self.assertIsNone(window.current_path)

    def test_open_dialog_cancel_and_unsaved_guard_preserve_document(self) -> None:
        from PySide6.QtWidgets import QMessageBox

        window = self._make_window()
        self._make_dirty(window)
        old_project = window.project

        with (
            patch(
                "wirewizard_gui.ui.main_window.QFileDialog.getOpenFileName",
                return_value=("", ""),
            ),
            patch.object(window, "_confirm_unsaved_changes") as confirm,
        ):
            window.open_project()
            confirm.assert_not_called()

        with (
            patch(
                "wirewizard_gui.ui.main_window.QFileDialog.getOpenFileName",
                return_value=("opened.json", ""),
            ),
            patch.object(
                window,
                "_ask_unsaved_changes",
                return_value=QMessageBox.StandardButton.Cancel,
            ),
            patch("wirewizard_gui.ui.main_window.ProjectService.load_project") as load,
        ):
            window.open_project()
            load.assert_not_called()

        self.assertIs(window.project, old_project)
        self.assertTrue(window._dirty)

    def test_open_discard_installs_clean_json_document(self) -> None:
        from PySide6.QtWidgets import QMessageBox

        from wirewizard_gui.domain.models import ProjectModel

        window = self._make_window()
        self._make_dirty(window)
        opened = ProjectModel(title="Открытый проект")

        with (
            patch(
                "wirewizard_gui.ui.main_window.QFileDialog.getOpenFileName",
                return_value=("opened.json", ""),
            ),
            patch.object(
                window,
                "_ask_unsaved_changes",
                return_value=QMessageBox.StandardButton.Discard,
            ),
            patch(
                "wirewizard_gui.ui.main_window.ProjectService.load_project",
                return_value=opened,
            ) as load,
        ):
            window.open_project()

        load.assert_called_once_with("opened.json")
        self.assertIs(window.project, opened)
        self.assertEqual(window.current_path, "opened.json")
        self.assertFalse(window._dirty)

    def test_open_yaml_installs_dirty_document_without_native_path(self) -> None:
        from wirewizard_gui.domain.models import ProjectModel

        window = self._make_window()
        opened = ProjectModel(title="Проект из YAML")

        with (
            patch(
                "wirewizard_gui.ui.main_window.QFileDialog.getOpenFileName",
                return_value=("harness.yml", ""),
            ),
            patch.object(window, "_ask_unsaved_changes") as ask,
            patch(
                "wirewizard_gui.ui.main_window.ProjectService.load_project",
                return_value=opened,
            ),
        ):
            window.open_project()

        ask.assert_not_called()
        self.assertIs(window.project, opened)
        self.assertIsNone(window.current_path)
        self.assertTrue(window._dirty)
        self.assertTrue(window.windowTitle().endswith(" *"))

    def test_failed_project_install_rolls_back_dirty_document(self) -> None:
        from PySide6.QtWidgets import QMessageBox

        from wirewizard_gui.domain.models import ProjectModel

        window = self._make_window()
        window.current_path = "old-project.json"
        self._make_dirty(window)
        old_project = window.project
        old_data = window.project.to_dict()
        old_path = window.current_path
        old_clean_state = deepcopy(window._clean_state)
        old_dirty = window._dirty
        replacement = ProjectModel(title="Новый проект")

        with (
            patch(
                "wirewizard_gui.ui.main_window.QFileDialog.getOpenFileName",
                return_value=("new-project.json", ""),
            ),
            patch.object(
                window,
                "_ask_unsaved_changes",
                return_value=QMessageBox.StandardButton.Discard,
            ),
            patch(
                "wirewizard_gui.ui.main_window.ProjectService.load_project",
                return_value=replacement,
            ),
            patch.object(window, "refresh_preview", side_effect=RuntimeError("preview failed")),
            patch("wirewizard_gui.ui.main_window.QMessageBox.critical") as critical,
        ):
            window.open_project()

        critical.assert_called_once()
        self.assertIs(window.project, old_project)
        self.assertEqual(window.project.to_dict(), old_data)
        self.assertEqual(window.current_path, old_path)
        self.assertEqual(window._clean_state, old_clean_state)
        self.assertEqual(window._dirty, old_dirty)

    def test_import_save_failure_blocks_replacement_and_success_proceeds(self) -> None:
        from PySide6.QtWidgets import QMessageBox

        from wirewizard_gui.domain.models import ProjectModel

        window = self._make_window()
        self._make_dirty(window)
        old_project = window.project
        imported = ProjectModel(title="Импортированный проект")
        dialog_patch = patch(
            "wirewizard_gui.ui.main_window.QFileDialog.getOpenFileName",
            return_value=("import.yml", ""),
        )
        warning_patch = patch.object(
            window,
            "_ask_unsaved_changes",
            return_value=QMessageBox.StandardButton.Save,
        )

        with (
            dialog_patch,
            warning_patch,
            patch.object(window, "save_project", return_value=False),
            patch("wirewizard_gui.ui.main_window.ProjectService.import_yaml") as load,
        ):
            window.import_yaml()
            load.assert_not_called()

        self.assertIs(window.project, old_project)
        self.assertTrue(window._dirty)

        with (
            patch(
                "wirewizard_gui.ui.main_window.QFileDialog.getOpenFileName",
                return_value=("import.yml", ""),
            ),
            patch.object(
                window,
                "_ask_unsaved_changes",
                return_value=QMessageBox.StandardButton.Save,
            ),
            patch.object(window, "save_project", return_value=True),
            patch(
                "wirewizard_gui.ui.main_window.ProjectService.import_yaml",
                return_value=imported,
            ) as load,
        ):
            window.import_yaml()

        load.assert_called_once_with("import.yml")
        self.assertIs(window.project, imported)
        self.assertIsNone(window.current_path)
        self.assertTrue(window._dirty)

    def test_close_event_honours_save_discard_and_cancel(self) -> None:
        from PySide6.QtGui import QCloseEvent
        from PySide6.QtWidgets import QMessageBox

        window = self._make_window()
        self._make_dirty(window)

        cases = [
            (QMessageBox.StandardButton.Cancel, None, False),
            (QMessageBox.StandardButton.Discard, None, True),
            (QMessageBox.StandardButton.Save, False, False),
            (QMessageBox.StandardButton.Save, True, True),
        ]
        for answer, save_result, accepted in cases:
            with self.subTest(answer=answer, save_result=save_result):
                event = QCloseEvent()
                save_patch = patch.object(window, "save_project", return_value=save_result)
                with (
                    patch.object(
                        window,
                        "_ask_unsaved_changes",
                        return_value=answer,
                    ),
                    save_patch as save,
                ):
                    window.closeEvent(event)

                self.assertEqual(event.isAccepted(), accepted)
                if answer == QMessageBox.StandardButton.Save:
                    save.assert_called_once_with()
                else:
                    save.assert_not_called()

    def test_clean_close_does_not_prompt(self) -> None:
        from PySide6.QtGui import QCloseEvent

        window = self._make_window()
        event = QCloseEvent()

        with patch.object(window, "_ask_unsaved_changes") as ask:
            window.closeEvent(event)

        self.assertTrue(event.isAccepted())
        ask.assert_not_called()

    def test_component_rename_updates_exact_route_references(self) -> None:
        from wirewizard_gui.domain.models import (
            CableModel,
            ConnectionRowModel,
            ConnectorModel,
            ProjectModel,
        )
        from wirewizard_gui.domain.validation import ProjectValidator

        window = self._make_window()
        project = ProjectModel(
            connectors=[
                ConnectorModel(name="X1"),
                ConnectorModel(name="X10"),
            ],
            cables=[CableModel(name="W1")],
            connections=[
                ConnectionRowModel(route="X1:1 -> W1:1 -> X10:1"),
                ConnectionRowModel(route="X10:2 -> W1:2 -> X10:1"),
            ],
        )
        window._install_project(project, None, dirty=False)
        connector_node = window.project_tree.topLevelItem(0).child(0).child(0)
        window.project_tree.setCurrentItem(connector_node)

        window.connector_editor.name_edit.setText("X2")
        window.connector_editor.name_edit.editingFinished.emit()

        self.assertEqual(project.connectors[0].name, "X2")
        self.assertEqual(
            [row.route for row in project.connections],
            ["X2:1 -> W1:1 -> X10:1", "X10:2 -> W1:2 -> X10:1"],
        )
        self.assertEqual(connector_node.text(0), "X2")
        self.assertTrue(window._dirty)
        self.assertFalse(
            any("неизвестный компонент" in error for error in ProjectValidator.validate(project))
        )

    def test_duplicate_component_name_is_rejected_without_touching_routes(self) -> None:
        window = self._make_window()
        connector_node = window.project_tree.topLevelItem(0).child(0).child(0)
        window.project_tree.setCurrentItem(connector_node)
        original_routes = [row.route for row in window.project.connections]

        with patch("wirewizard_gui.ui.main_window.QMessageBox.warning") as warning:
            window.connector_editor.name_edit.setText("X2")
            window.connector_editor.name_edit.editingFinished.emit()

        warning.assert_called_once()
        self.assertEqual(window.project.connectors[0].name, "X1")
        self.assertEqual(window.connector_editor.name_edit.text(), "X1")
        self.assertEqual([row.route for row in window.project.connections], original_routes)
        self.assertFalse(window._dirty)

    def test_component_delete_removes_only_confirmed_dependent_rows(self) -> None:
        from wirewizard_gui.domain.models import (
            CableModel,
            ConnectionRowModel,
            ConnectorModel,
            ProjectModel,
        )
        from wirewizard_gui.domain.validation import ProjectValidator

        window = self._make_window()
        project = ProjectModel(
            connectors=[ConnectorModel(name="X1"), ConnectorModel(name="X10")],
            cables=[CableModel(name="W1")],
            connections=[
                ConnectionRowModel(route="X1:1 -> W1:1 -> X10:1"),
                ConnectionRowModel(route="X10:1 -> W1:1 -> X10:2"),
            ],
        )
        window._install_project(project, None, dirty=False)
        connector_node = window.project_tree.topLevelItem(0).child(0).child(0)
        window.project_tree.setCurrentItem(connector_node)

        with patch.object(
            window, "_confirm_component_deletion", return_value=True
        ) as confirm:
            window.delete_selected_item()

        confirm.assert_called_once_with("X1", [0])
        self.assertEqual([item.name for item in project.connectors], ["X10"])
        self.assertEqual(
            [row.route for row in project.connections],
            ["X10:1 -> W1:1 -> X10:2"],
        )
        self.assertTrue(window._dirty)
        self.assertFalse(
            any("неизвестный компонент" in error for error in ProjectValidator.validate(project))
        )

    def test_component_delete_cancel_preserves_project(self) -> None:
        window = self._make_window()
        connector_node = window.project_tree.topLevelItem(0).child(0).child(0)
        window.project_tree.setCurrentItem(connector_node)
        original = window.project.to_dict()

        with patch.object(window, "_confirm_component_deletion", return_value=False):
            window.delete_selected_item()

        self.assertEqual(window.project.to_dict(), original)
        self.assertFalse(window._dirty)

    def test_problems_panel_separates_issues_and_navigates_to_source(self) -> None:
        from PySide6.QtCore import Qt

        from wirewizard_gui.domain.models import (
            CableModel,
            ConnectionRowModel,
            ConnectorModel,
            ProjectModel,
        )
        from wirewizard_gui.domain.validation import IssueSeverity

        window = self._make_window()
        project = ProjectModel(
            connectors=[
                ConnectorModel(name="X1", pincount=1),
                ConnectorModel(name="X2", pincount=1),
                ConnectorModel(name="X3", pincount=1),
            ],
            cables=[CableModel(name="W1", wirecount=1)],
            connections=[ConnectionRowModel(route="X1:2 -> W1:1 -> X2:1")],
        )
        window._install_project(project, None, dirty=False)

        panel = window.problems_panel
        issues = [
            panel.topLevelItem(index).data(0, Qt.ItemDataRole.UserRole)
            for index in range(panel.topLevelItemCount())
        ]
        error = next(issue for issue in issues if issue.severity == IssueSeverity.ERROR)
        warning = next(issue for issue in issues if issue.severity == IssueSeverity.WARNING)
        self.assertEqual(error.row_index, 0)
        self.assertEqual(error.component_name, "X1")
        self.assertEqual(warning.component_name, "X3")

        error_item = next(
            panel.topLevelItem(index)
            for index in range(panel.topLevelItemCount())
            if panel.topLevelItem(index).data(0, Qt.ItemDataRole.UserRole) == error
        )
        panel.itemDoubleClicked.emit(error_item, 0)
        self.assertEqual(window.editor_stack.currentWidget(), window.connections_editor)
        self.assertEqual(window.connections_editor.table.currentRow(), 0)

        window._navigate_to_issue(warning)
        payload = window.project_tree.currentItem().data(0, Qt.ItemDataRole.UserRole)
        self.assertEqual(payload[1].name, "X3")

    def test_wireviz_is_blocked_by_errors_but_not_warnings(self) -> None:
        from wirewizard_gui.domain.models import (
            CableModel,
            ConnectionRowModel,
            ConnectorModel,
            ProjectModel,
        )

        window = self._make_window()
        invalid = ProjectModel(
            connectors=[ConnectorModel(name="X1"), ConnectorModel(name="X2")],
            cables=[CableModel(name="W1", wirecount=1)],
            connections=[ConnectionRowModel(route="X1:1 -> W1:2 -> X2:1")],
        )
        with patch(
            "wirewizard_gui.ui.main_window.WireVizService.render_svg"
        ) as render:
            window._install_project(invalid, None, dirty=False)
        render.assert_not_called()

        with (
            patch("wirewizard_gui.ui.main_window.QFileDialog.getExistingDirectory") as choose,
            patch("wirewizard_gui.ui.main_window.WireVizService.run_full") as run,
            patch("wirewizard_gui.ui.main_window.QMessageBox.critical") as critical,
        ):
            window.run_wireviz()

        choose.assert_not_called()
        run.assert_not_called()
        critical.assert_called_once()

        valid_with_warning = ProjectModel(
            connectors=[
                ConnectorModel(name="X1"),
                ConnectorModel(name="X2"),
                ConnectorModel(name="X3"),
            ],
            cables=[CableModel(name="W1", wirecount=1)],
            connections=[ConnectionRowModel(route="X1:1 -> W1:1 -> X2:1")],
        )
        with patch(
            "wirewizard_gui.ui.main_window.WireVizService.render_svg",
            return_value=(False, "Предпросмотр недоступен", None),
        ) as render:
            window._install_project(valid_with_warning, None, dirty=False)
            self._wait_for_wireviz(window)
        render.assert_called_once()
        with (
            patch(
                "wirewizard_gui.ui.main_window.QFileDialog.getExistingDirectory",
                return_value="output",
            ),
            patch(
                "wirewizard_gui.ui.main_window.WireVizService.run_full",
                return_value=(True, "Готово", []),
            ) as run,
            patch("wirewizard_gui.ui.main_window.QMessageBox.information"),
        ):
            window.run_wireviz()
            self._wait_for_wireviz(window)

        run.assert_called_once()

    def test_preview_runs_in_background_and_reports_progress(self) -> None:
        window = self._make_window()
        started = threading.Event()
        release = threading.Event()

        def slow_render(project):
            started.set()
            release.wait(2.0)
            return False, "Предпросмотр недоступен", None

        with patch(
            "wirewizard_gui.ui.main_window.WireVizService.render_svg",
            side_effect=slow_render,
        ):
            window.refresh_preview()
            self.assertTrue(started.wait(1.0))
            self.assertTrue(window._wireviz_tasks)
            self.assertFalse(window.render_progress.isHidden())
            release.set()
            self._wait_for_wireviz(window)

        self.assertTrue(window.render_progress.isHidden())

    def test_preview_queue_is_sequential_and_only_latest_result_is_shown(self) -> None:
        window = self._make_window()
        self._select_project(window)
        state_lock = threading.Lock()
        active = 0
        max_active = 0
        rendered_titles: list[str] = []

        def tracked_render(project):
            nonlocal active, max_active
            with state_lock:
                active += 1
                max_active = max(max_active, active)
                rendered_titles.append(project.title)
            time.sleep(0.03)
            with state_lock:
                active -= 1
            svg = (
                '<svg xmlns="http://www.w3.org/2000/svg">'
                f"<text>{project.title}</text></svg>"
            )
            return True, "Готово", svg

        with patch(
            "wirewizard_gui.ui.main_window.WireVizService.render_svg",
            side_effect=tracked_render,
        ):
            window.project_editor.title_edit.setText("Первый запрос")
            window.refresh_preview()
            window.project.title = "Последний запрос"
            window.refresh_preview()
            self._wait_for_wireviz(window)

        self.assertEqual(max_active, 1)
        self.assertEqual(rendered_titles, ["Первый запрос", "Последний запрос"])
        self.assertIn("Последний запрос", window.svg_preview._svg_text)
        self.assertNotIn("Первый запрос", window.svg_preview._svg_text)

    def test_undo_redo_field_edit_restores_clean_checkpoint(self) -> None:
        window = self._make_window()
        original_title = window.project.title
        self._select_project(window)

        window.project_editor.title_edit.setText("Новое название")

        self.assertTrue(window.undo_stack.canUndo())
        self.assertTrue(window._dirty)
        window.undo_stack.undo()
        self._wait_for_wireviz(window)
        self.assertEqual(window.project.title, original_title)
        self.assertFalse(window._dirty)

        window.undo_stack.redo()
        self._wait_for_wireviz(window)
        self.assertEqual(window.project.title, "Новое название")
        self.assertTrue(window._dirty)

    def test_undo_redo_connection_edit_and_addition(self) -> None:
        window = self._make_window()
        connections_node = window.project_tree.topLevelItem(0).child(3).child(0)
        window.project_tree.setCurrentItem(connections_node)
        original_route = window.project.connections[0].route
        cell = window.connections_editor.table.cellWidget(0, 0)

        cell.component_combo.setCurrentIndex(cell.component_combo.findData("X2"))
        changed_route = window.project.connections[0].route
        self.assertNotEqual(changed_route, original_route)

        window.undo_stack.undo()
        self._wait_for_wireviz(window)
        self.assertEqual(window.project.connections[0].route, original_route)
        window.undo_stack.redo()
        self._wait_for_wireviz(window)
        self.assertEqual(window.project.connections[0].route, changed_route)

        count = len(window.project.connectors)
        window.add_connector()
        self.assertEqual(len(window.project.connectors), count + 1)
        window.undo_stack.undo()
        self._wait_for_wireviz(window)
        self.assertEqual(len(window.project.connectors), count)
        window.undo_stack.redo()
        self._wait_for_wireviz(window)
        self.assertEqual(len(window.project.connectors), count + 1)

    def test_component_rename_and_delete_are_single_reversible_commands(self) -> None:
        window = self._make_window()
        connector_node = window.project_tree.topLevelItem(0).child(0).child(0)
        window.project_tree.setCurrentItem(connector_node)
        original_routes = [row.route for row in window.project.connections]

        window.connector_editor.name_edit.setText("X9")
        window.connector_editor.name_edit.editingFinished.emit()

        self.assertEqual(window.undo_stack.count(), 1)
        self.assertEqual(window.project.connectors[0].name, "X9")
        self.assertTrue(window.project.connections[0].route.startswith("X9:"))
        window.undo_stack.undo()
        self._wait_for_wireviz(window)
        self.assertEqual(window.project.connectors[0].name, "X1")
        self.assertEqual([row.route for row in window.project.connections], original_routes)
        window.undo_stack.redo()
        self._wait_for_wireviz(window)
        self.assertEqual(window.project.connectors[0].name, "X9")

        connector_node = window.project_tree.topLevelItem(0).child(0).child(0)
        window.project_tree.setCurrentItem(connector_node)
        with patch.object(window, "_confirm_component_deletion", return_value=True):
            window.delete_selected_item()
        self.assertNotIn("X9", [item.name for item in window.project.connectors])
        window.undo_stack.undo()
        self._wait_for_wireviz(window)
        self.assertIn("X9", [item.name for item in window.project.connectors])
        self.assertTrue(window.project.connections[0].route.startswith("X9:"))

    def test_installing_another_document_clears_undo_history(self) -> None:
        from wirewizard_gui.domain.models import ProjectModel

        window = self._make_window()
        window.add_connector()
        self.assertTrue(window.undo_stack.canUndo())

        window._install_project(ProjectModel(title="Другой проект"), None, dirty=False)
        self._wait_for_wireviz(window)

        self.assertFalse(window.undo_stack.canUndo())
        self.assertFalse(window.undo_stack.canRedo())

    def test_document_shortcuts_are_registered(self) -> None:
        from PySide6.QtGui import QKeySequence

        window = self._make_window()
        expected = {
            "undo_action": "Ctrl+Z",
            "redo_action": "Ctrl+Y",
            "new_project_action": "Ctrl+N",
            "open_project_action": "Ctrl+O",
            "save_project_action": "Ctrl+S",
            "save_project_as_action": "Ctrl+Shift+S",
        }

        for attribute, shortcut in expected.items():
            with self.subTest(action=attribute):
                action = getattr(window, attribute)
                self.assertIn(action, window.actions())
                self.assertEqual(
                    action.shortcut().toString(QKeySequence.SequenceFormat.PortableText),
                    shortcut,
                )


if __name__ == "__main__":
    unittest.main()
