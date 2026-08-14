from __future__ import annotations

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtWidgets import QLabel, QStackedLayout, QVBoxLayout, QWidget


class SvgPreviewPanel(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.info_label = QLabel("Предпросмотр SVG пока не построен.")
        self.info_label.setAlignment(Qt.AlignCenter)
        self.info_label.setWordWrap(True)

        self.svg_widget = QSvgWidget()

        self.stack = QStackedLayout()
        info_page = QWidget()
        info_layout = QVBoxLayout(info_page)
        info_layout.addWidget(self.info_label)

        svg_page = QWidget()
        svg_layout = QVBoxLayout(svg_page)
        svg_layout.addWidget(self.svg_widget)

        self.stack.addWidget(info_page)
        self.stack.addWidget(svg_page)
        self.setLayout(self.stack)

    def show_message(self, message: str) -> None:
        self.info_label.setText(message)
        self.stack.setCurrentIndex(0)

    def show_svg(self, svg_text: str) -> None:
        self.svg_widget.load(QByteArray(svg_text.encode("utf-8")))
        self.stack.setCurrentIndex(1)
