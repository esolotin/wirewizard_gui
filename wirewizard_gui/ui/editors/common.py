from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QToolButton,
    QWidget,
)


WIRE_COLOR_HELP = """Коды цветов WireViz:
BK — чёрный
BN — коричневый
BU — синий
GN — зелёный
GY — серый
OG — оранжевый
PK — розовый
RD — красный
VT — фиолетовый
WH — белый
YE — жёлтый
GNYE — зелёно-жёлтый"""


def build_help_field(
    field: QWidget, title: str, help_text: str
) -> tuple[QWidget, QToolButton]:
    container = QWidget()
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.addWidget(field, 1)

    button = QToolButton()
    button.setText("?")
    button.setToolTip(f"Открыть справку: {title.lower()}")
    button.setAccessibleName(f"Справка: {title}")
    button.clicked.connect(
        lambda _checked=False: QMessageBox.information(
            container, title, help_text
        )
    )
    layout.addWidget(button)
    return container, button


def set_text_hint(
    editor: QLineEdit | QPlainTextEdit, placeholder: str, tooltip: str | None = None
) -> None:
    editor.setPlaceholderText(placeholder)
    editor.setToolTip(tooltip or placeholder)


def set_combo_hint(combo: QComboBox, placeholder: str, tooltip: str | None = None) -> None:
    combo.setToolTip(tooltip or placeholder)
    line_edit = combo.lineEdit()
    if line_edit is not None:
        line_edit.setPlaceholderText(placeholder)
        line_edit.setToolTip(tooltip or placeholder)


def build_combo(values: list[str], editable: bool = True) -> QComboBox:
    combo = QComboBox()
    combo.addItems(values)
    combo.setEditable(editable)
    combo.setInsertPolicy(QComboBox.NoInsert)
    return combo


def set_combo_text(combo: QComboBox, value: str) -> None:
    idx = combo.findText(value)
    if idx >= 0:
        combo.setCurrentIndex(idx)
    else:
        combo.setEditText(value)
