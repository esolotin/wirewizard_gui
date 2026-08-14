from __future__ import annotations

import os
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

    def test_main_window_uses_russian_labels(self) -> None:
        from PySide6.QtWidgets import QAbstractButton

        from wirewizard_gui.ui.main_window import MainWindow

        with patch(
            "wirewizard_gui.ui.main_window.WireVizService.render_svg",
            return_value=(False, "Предпросмотр недоступен", None),
        ):
            window = MainWindow()
        self.addCleanup(window.close)

        button_texts = {button.text() for button in window.findChildren(QAbstractButton)}
        expected = {
            "Новый проект",
            "Открыть проект",
            "Сохранить",
            "Построить в WireViz",
            "Создать шлейф",
            "Обновить предпросмотр",
        }

        self.assertTrue(expected.issubset(button_texts), expected - button_texts)
        self.assertEqual(window.project_tree.headerItem().text(0), "Состав проекта")
        self.assertEqual(window.project.title, "Демонстрационный жгут")

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
        self.assertEqual(dialog.windowTitle(), "Мастер шлейфового соединения")
        self.assertTrue({"Создать", "Отмена"}.issubset(button_texts))

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
