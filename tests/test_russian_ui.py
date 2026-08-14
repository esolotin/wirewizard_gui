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


if __name__ == "__main__":
    unittest.main()
