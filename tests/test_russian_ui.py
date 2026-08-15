from __future__ import annotations

import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    import PySide6  # noqa: F401
except ModuleNotFoundError:
    PYSIDE_AVAILABLE = False
else:
    PYSIDE_AVAILABLE = True


@unittest.skipUnless(PYSIDE_AVAILABLE, "PySide6 is not installed")
class RussianUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def _wait_for_wireviz(self, window, timeout: float = 3.0) -> None:
        deadline = time.monotonic() + timeout
        while window._wireviz_tasks and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(0.005)
        self.app.processEvents()
        self.assertFalse(window._wireviz_tasks, "Фоновая задача WireViz не завершилась")

    def test_main_window_uses_russian_labels(self) -> None:
        from PySide6.QtWidgets import QAbstractButton

        from wirewizard_gui.ui.main_window import MainWindow

        with patch(
            "wirewizard_gui.ui.main_window.WireVizService.render_svg",
            return_value=(False, "Предпросмотр недоступен", None),
        ):
            window = MainWindow()
            self._wait_for_wireviz(window)
        self.addCleanup(window.close)

        button_texts = {button.text() for button in window.findChildren(QAbstractButton)}
        expected = {
            "Новый проект",
            "Открыть проект",
            "Сохранить",
            "Построить в WireViz",
            "Массовая разводка",
            "Обновить предпросмотр",
        }

        self.assertTrue(expected.issubset(button_texts), expected - button_texts)
        self.assertEqual(window.project_tree.headerItem().text(0), "Состав проекта")
        self.assertEqual(window.project.title, "Демонстрационный жгут")

    def test_workspace_panels_are_movable_and_resettable(self) -> None:
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QDockWidget, QMenu

        from wirewizard_gui.ui.main_window import MainWindow

        with patch(
            "wirewizard_gui.ui.main_window.WireVizService.render_svg",
            return_value=(False, "Предпросмотр недоступен", None),
        ):
            window = MainWindow()
            self._wait_for_wireviz(window)
        self.addCleanup(window.close)
        window.show()
        self.app.processEvents()
        window.resize(820, 560)
        self.app.processEvents()

        self.assertLessEqual(window.minimumSizeHint().width(), 400)
        self.assertEqual(window.size().width(), 820)
        self.assertEqual(window.size().height(), 560)

        docks = (
            window.project_dock,
            window.yaml_dock,
            window.svg_dock,
            window.problems_dock,
            window.results_dock,
        )
        for dock in docks:
            features = dock.features()
            self.assertTrue(features & QDockWidget.DockWidgetFeature.DockWidgetMovable)
            self.assertTrue(features & QDockWidget.DockWidgetFeature.DockWidgetFloatable)
            self.assertTrue(features & QDockWidget.DockWidgetFeature.DockWidgetClosable)

        window.yaml_dock.setFloating(True)
        window.project_dock.hide()
        window.results_dock.show()
        window.reset_workspace_layout()
        self.app.processEvents()

        self.assertFalse(window.yaml_dock.isFloating())
        self.assertTrue(window.project_dock.isVisible())
        self.assertTrue(window.problems_dock.isVisible())
        self.assertFalse(window.results_dock.isVisible())
        self.assertEqual(
            window.dockWidgetArea(window.project_dock),
            Qt.DockWidgetArea.LeftDockWidgetArea,
        )
        self.assertEqual(
            window.dockWidgetArea(window.yaml_dock),
            Qt.DockWidgetArea.RightDockWidgetArea,
        )
        view_menu = next(
            menu
            for menu in window.menuBar().findChildren(QMenu)
            if menu.title() == "Вид"
        )
        self.assertIn(
            "Сбросить расположение панелей",
            {action.text() for action in view_menu.actions()},
        )

    def test_daisy_chain_wizard_uses_russian_labels(self) -> None:
        from PySide6.QtWidgets import QAbstractButton

        from wirewizard_gui.domain.models import CableModel, ConnectorModel
        from wirewizard_gui.ui.dialogs.daisy_chain_wizard import DaisyChainWizard

        dialog = DaisyChainWizard(
            [ConnectorModel(name="X1"), ConnectorModel(name="X2")],
            [CableModel(name="W1")],
        )
        self.addCleanup(dialog.close)

        button_texts = {button.text() for button in dialog.findChildren(QAbstractButton)}
        self.assertEqual(dialog.windowTitle(), "Мастер массовой разводки")
        self.assertEqual(dialog.plan().mode, "daisy_chain")
        dialog.mode_combo.setCurrentIndex(1)
        self.assertEqual(dialog.plan().mode, "star")
        self.assertTrue({"Создать", "Отмена"}.issubset(button_texts))

    def test_component_library_has_russian_tabs_and_presets(self) -> None:
        from wirewizard_gui.ui.dialogs.component_library import ComponentLibraryDialog

        dialog = ComponentLibraryDialog()
        self.addCleanup(dialog.close)

        self.assertEqual(dialog.windowTitle(), "Библиотека компонентов")
        self.assertEqual(
            [dialog.tabs.tabText(index) for index in range(dialog.tabs.count())],
            ["Разъёмы", "Кабели", "Наконечники"],
        )
        self.assertIsNotNone(dialog.selected_preset())
        self.assertTrue(dialog.description.text())

    def test_editors_show_examples_and_wireviz_code_hints(self) -> None:
        from wirewizard_gui.ui.editors import common
        from wirewizard_gui.ui.editors.cable_editor import CableEditor
        from wirewizard_gui.ui.editors.connector_editor import ConnectorEditor
        from wirewizard_gui.ui.editors.ferrule_editor import FerruleEditor

        connector = ConnectorEditor()
        cable = CableEditor()
        ferrule = FerruleEditor()
        self.addCleanup(connector.close)
        self.addCleanup(cable.close)
        self.addCleanup(ferrule.close)

        self.assertIn("A, B", connector.pins_edit.placeholderText())
        self.assertIn("GND", connector.pinlabels_edit.placeholderText())
        self.assertIn("RD, BK", cable.colors_edit.placeholderText())
        self.assertIn("Нажмите ?", cable.colors_edit.toolTip())
        self.assertIn("CAN_H", cable.wirelabels_edit.placeholderText())
        self.assertIn("жиле 1", cable.wirelabels_edit.toolTip())
        self.assertIn("DIN", cable.color_code_combo.toolTip())
        self.assertIn("OG", ferrule.color_combo.lineEdit().placeholderText())
        self.assertGreaterEqual(common.WIRE_COLOR_HELP.count("\n"), 12)
        with patch.object(common.QMessageBox, "information") as information:
            cable.colors_help_btn.click()
        information.assert_called_once()
        title, message = information.call_args.args[1:]
        self.assertEqual(title, "Коды цветов жил WireViz")
        self.assertIn("BK — чёрный\n", message)
        self.assertIn("GNYE — зелёно-жёлтый", message)

    def test_connections_editor_preserves_arrows_and_parallel_groups(self) -> None:
        from wirewizard_gui.domain.models import (
            CableModel,
            ConnectionRowModel,
            ConnectorModel,
        )
        from wirewizard_gui.ui.editors.connections_editor import ConnectionsEditor

        long_route = " -> ".join(
            [part for idx in range(1, 7) for part in (f"X{idx}:1", f"W{idx}:1")]
            + ["X7:1"]
        )
        routes = [
            "X1:1 -> -> -> X2:1",
            "X1:1 -> --> -> X2:1",
            "X1:1 -> <=> -> X2:1",
            "X1:[1, 2] -> [->, -->] -> X2:[1, 2]",
            "[X1, X2] -> W1:[1, 2] -> X3:[1, 2]",
            long_route,
        ]
        connectors = [
            ConnectorModel(name=f"X{idx}", pincount=2) for idx in range(1, 8)
        ]
        cables = [
            CableModel(name=f"W{idx}", wirecount=2) for idx in range(1, 7)
        ]
        editor = ConnectionsEditor()
        self.addCleanup(editor.close)
        editor.set_component_sources(connectors, cables, [])
        editor.load_items([ConnectionRowModel(route=route) for route in routes])

        # Обновление вариантов combo box не должно сбрасывать сырые элементы WireViz.
        editor.set_component_sources(connectors, cables, [])
        saved = editor.save_to_items()

        self.assertGreaterEqual(editor.table.columnCount(), 13)
        self.assertEqual([item.route for item in saved], routes)

    def test_connections_editor_filters_next_step_by_previous_kind(self) -> None:
        from wirewizard_gui.domain.models import CableModel, ConnectorModel, FerruleModel
        from wirewizard_gui.ui.editors.connections_editor import ConnectionsEditor

        editor = ConnectionsEditor()
        self.addCleanup(editor.close)
        editor.set_component_sources(
            [ConnectorModel(name="X1"), ConnectorModel(name="X2")],
            [CableModel(name="W1")],
            [FerruleModel(name="F1")],
        )
        editor.add_row()

        def options(col: int) -> set[str]:
            combo = editor.table.cellWidget(0, col).component_combo
            return {
                str(combo.itemData(index))
                for index in range(combo.count())
                if combo.itemData(index) is not None
            }

        self.assertEqual(options(0), {"X1", "X2", "W1", "F1"})
        self.assertEqual(options(1), {"W1", "->", "-->", "<=>"})
        self.assertEqual(options(2), {"X1", "X2", "F1"})

        first_combo = editor.table.cellWidget(0, 0).component_combo
        first_combo.setCurrentIndex(first_combo.findData("W1"))
        self.assertEqual(options(1), {"X1", "X2", "F1"})

        first_combo.setCurrentIndex(first_combo.findData("X1"))
        second_combo = editor.table.cellWidget(0, 1).component_combo
        second_combo.setCurrentIndex(second_combo.findData("-->"))
        self.assertEqual(options(2), {"X1", "X2", "F1"})

    def test_svg_preview_zoom_highlight_and_export(self) -> None:
        from wirewizard_gui.ui.panels.svg_preview import SvgPreviewPanel

        svg = """<svg xmlns="http://www.w3.org/2000/svg" width="120" height="80">
        <g id="node1"><polygon points="1,1 119,1 119,79 1,79" stroke="black"/>
        <text x="10" y="30">X1</text></g></svg>"""
        panel = SvgPreviewPanel()
        self.addCleanup(panel.close)
        panel.resize(400, 300)
        panel.show_svg(svg)
        initial_scale = panel.view.transform().m11()
        panel.view.scale(1.2, 1.2)
        self.assertGreater(panel.view.transform().m11(), initial_scale)
        panel.fit_to_view()

        panel.set_highlight("X1")
        self.assertIn("#e53935", panel._display_svg)

        with tempfile.TemporaryDirectory() as tmp:
            svg_path = Path(tmp) / "preview.svg"
            png_path = Path(tmp) / "preview.png"
            with patch(
                "wirewizard_gui.ui.panels.svg_preview.QFileDialog.getSaveFileName",
                return_value=(str(svg_path), ""),
            ):
                panel.save_svg()
            with patch(
                "wirewizard_gui.ui.panels.svg_preview.QFileDialog.getSaveFileName",
                return_value=(str(png_path), ""),
            ):
                panel.save_png()

            self.assertIn("#e53935", svg_path.read_text(encoding="utf-8"))
            self.assertGreater(png_path.stat().st_size, 0)

    def test_results_panel_opens_wireviz_output_formats(self) -> None:
        from PySide6.QtGui import QPainter, QPdfWriter, QPixmap

        from wirewizard_gui.ui.panels.results import ResultsPanel

        panel = ResultsPanel()
        self.addCleanup(panel.close)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "harness.bom.tsv").write_text("id\tdescription\n1\tTest", encoding="utf-8")
            (root / "harness.bom.csv").write_text("id,description\n1,Test", encoding="utf-8")
            (root / "harness.html").write_text("<h1>Harness</h1>", encoding="utf-8")
            (root / "harness.svg").write_text(
                '<svg xmlns="http://www.w3.org/2000/svg"><text>Harness</text></svg>',
                encoding="utf-8",
            )
            pixmap = QPixmap(20, 20)
            pixmap.fill()
            pixmap.save(str(root / "harness.png"))
            writer = QPdfWriter(str(root / "harness.pdf"))
            painter = QPainter(writer)
            painter.drawText(20, 20, "Harness")
            painter.end()
            filenames = [path.name for path in root.iterdir()]

            panel.show_results(root, filenames)

            try:
                self.assertEqual(panel.files.count(), 6)
                for row in range(panel.files.count()):
                    panel.files.setCurrentRow(row)
                    self.app.processEvents()
                pdf_row = next(
                    row
                    for row in range(panel.files.count())
                    if panel.files.item(row).text().endswith(".pdf")
                )
                panel.files.setCurrentRow(pdf_row)
                self.app.processEvents()
                self.assertIs(panel.preview.currentWidget(), panel.pdf)
            finally:
                panel.release_files()

    def test_main_window_selection_highlights_rendered_component(self) -> None:
        from wirewizard_gui.ui.main_window import MainWindow

        svg = """<svg xmlns="http://www.w3.org/2000/svg" width="120" height="80">
        <g><rect width="120" height="80"/><text x="10" y="30">X1</text></g></svg>"""
        with patch(
            "wirewizard_gui.ui.main_window.WireVizService.render_svg",
            return_value=(True, "Готово", svg),
        ):
            window = MainWindow()
            self._wait_for_wireviz(window)
        self.addCleanup(window.close)
        connector = window.project_tree.topLevelItem(0).child(0).child(0)

        window.project_tree.setCurrentItem(connector)

        self.assertIn("#e53935", window.svg_preview._display_svg)

    def test_daisy_chain_limit_signal_is_connected_once(self) -> None:
        from wirewizard_gui.domain.models import CableModel, ConnectorModel
        from wirewizard_gui.ui.dialogs.daisy_chain_wizard import DaisyChainWizard

        class CountingWizard(DaisyChainWizard):
            def __init__(self, *args, **kwargs) -> None:
                self.limit_update_calls = 0
                super().__init__(*args, **kwargs)

            def _update_limits_start_only(self, value=None) -> None:
                self.limit_update_calls += 1
                super()._update_limits_start_only(value)

        dialog = CountingWizard(
            [
                ConnectorModel(name="X1", pincount=4),
                ConnectorModel(name="X2", pincount=4),
            ],
            [CableModel(name="W1", wirecount=4)],
        )
        self.addCleanup(dialog.close)

        dialog.connectors_list.selectAll()
        dialog._update_limits()
        dialog._update_limits()
        dialog._update_limits()
        dialog.pin_count_spin.setValue(3)

        self.assertEqual(dialog.limit_update_calls, 1)


if __name__ == "__main__":
    unittest.main()
