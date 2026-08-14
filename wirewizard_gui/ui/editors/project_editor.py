from __future__ import annotations

from PySide6.QtWidgets import QFormLayout, QLineEdit, QPlainTextEdit, QWidget

from wirewizard_gui.domain.models import ProjectModel


class ProjectEditor(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.current_item: ProjectModel | None = None

        self.title_edit = QLineEdit()
        self.description_edit = QPlainTextEdit()

        layout = QFormLayout(self)
        layout.addRow("Название", self.title_edit)
        layout.addRow("Описание", self.description_edit)

    def load_item(self, item: ProjectModel) -> None:
        self.current_item = item
        self.title_edit.setText(item.title)
        self.description_edit.setPlainText(item.description)

    def save_to_item(self) -> None:
        if not self.current_item:
            return
        self.current_item.title = self.title_edit.text().strip() or "Новый жгут"
        self.current_item.description = self.description_edit.toPlainText().strip()
