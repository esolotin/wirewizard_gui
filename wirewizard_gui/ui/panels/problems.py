from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QBrush
from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem

from wirewizard_gui.domain.validation import IssueSeverity, ValidationIssue


class ProblemsPanel(QTreeWidget):
    issue_activated = Signal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setHeaderLabels(["Тип", "Место", "Сообщение"])
        self.setRootIsDecorated(False)
        self.setAlternatingRowColors(True)
        self.itemDoubleClicked.connect(self._activate_item)

    def set_issues(self, issues: list[ValidationIssue]) -> None:
        self.clear()
        for issue in issues:
            severity_text = (
                "Ошибка" if issue.severity == IssueSeverity.ERROR else "Предупреждение"
            )
            locations: list[str] = []
            if issue.component_name:
                locations.append(issue.component_name)
            if issue.row_index is not None:
                locations.append(f"строка {issue.row_index + 1}")
            item = QTreeWidgetItem(
                [severity_text, ", ".join(locations) or "Проект", issue.message]
            )
            item.setData(0, Qt.ItemDataRole.UserRole, issue)
            color = QColor("#c62828" if issue.severity == IssueSeverity.ERROR else "#b26a00")
            item.setForeground(0, QBrush(color))
            self.addTopLevelItem(item)

        for column in range(3):
            self.resizeColumnToContents(column)

    def _activate_item(self, item: QTreeWidgetItem, _column: int) -> None:
        issue = item.data(0, Qt.ItemDataRole.UserRole)
        if isinstance(issue, ValidationIssue):
            self.issue_activated.emit(issue)
