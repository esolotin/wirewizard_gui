from __future__ import annotations

from PySide6.QtWidgets import QFormLayout, QLineEdit, QPlainTextEdit, QWidget

from wirewizard_gui.domain.models import AnnotationModel
from wirewizard_gui.ui.editors.common import set_text_hint


class AnnotationEditor(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.current_item: AnnotationModel | None = None
        self.title_edit = QLineEdit()
        self.text_edit = QPlainTextEdit()
        set_text_hint(
            self.title_edit,
            "Например: Важно",
            "Короткий заголовок блока на схеме.",
        )
        set_text_hint(
            self.text_edit,
            "Например: Экран подключить только со стороны X1",
            "Многострочный текст. Graphviz выделит для блока отдельное место.",
        )

        layout = QFormLayout(self)
        layout.addRow("Заголовок", self.title_edit)
        layout.addRow("Текст примечания", self.text_edit)

    def load_item(self, item: AnnotationModel) -> None:
        self.current_item = item
        self.title_edit.setText(item.title)
        self.text_edit.setPlainText(item.text)

    def save_to_item(self) -> None:
        if self.current_item is None:
            return
        self.current_item.title = self.title_edit.text().strip() or "Примечание"
        self.current_item.text = self.text_edit.toPlainText().strip()
