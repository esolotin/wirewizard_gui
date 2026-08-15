from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from wirewizard_gui.domain.component_library import ComponentPreset, presets_for


class ComponentLibraryDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Библиотека компонентов")
        self.resize(620, 430)
        self._presets: dict[str, ComponentPreset] = {}
        self._lists: list[QListWidget] = []
        self.description = QLabel()
        self.description.setWordWrap(True)
        self.description.setMinimumHeight(48)

        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        for kind, title in (
            ("connector", "Разъёмы"),
            ("cable", "Кабели"),
            ("ferrule", "Наконечники"),
        ):
            page = QWidget()
            page_layout = QVBoxLayout(page)
            component_list = QListWidget()
            component_list.currentItemChanged.connect(self._show_description)
            component_list.itemDoubleClicked.connect(lambda _item: self.accept())
            page_layout.addWidget(component_list)
            for preset in presets_for(kind):
                self._presets[preset.key] = preset
                item = QListWidgetItem(preset.title)
                item.setData(Qt.ItemDataRole.UserRole, preset.key)
                component_list.addItem(item)
            if component_list.count():
                component_list.setCurrentRow(0)
            self._lists.append(component_list)
            self.tabs.addTab(page, title)

        layout.addWidget(self.description)
        self.tabs.currentChanged.connect(self._sync_description)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Добавить")
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Отмена")
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        self._sync_description()

    def selected_preset(self) -> ComponentPreset | None:
        current_list = self._lists[self.tabs.currentIndex()]
        item = current_list.currentItem()
        if item is None:
            return None
        return self._presets.get(str(item.data(Qt.ItemDataRole.UserRole)))

    def _show_description(self, item: QListWidgetItem | None, _previous=None) -> None:
        key = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        preset = self._presets.get(str(key))
        self.description.setText(preset.description if preset is not None else "")

    def _sync_description(self, _index: int | None = None) -> None:
        preset = self.selected_preset()
        self.description.setText(preset.description if preset is not None else "")
