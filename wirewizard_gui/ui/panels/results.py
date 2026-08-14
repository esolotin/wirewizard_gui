from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QBuffer, QIODevice, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtPdf import QPdfDocument
from PySide6.QtPdfWidgets import QPdfView
from PySide6.QtWidgets import (
    QLabel,
    QListWidget,
    QListWidgetItem,
    QScrollArea,
    QSplitter,
    QStackedWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from wirewizard_gui.ui.panels.svg_preview import SvgPreviewPanel


class ResultsPanel(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.files = QListWidget()
        self.files.currentItemChanged.connect(self._show_item)

        self.message = QLabel("Запустите WireViz, чтобы увидеть результаты.")
        self.message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.text = QTextBrowser()
        self.image = QLabel()
        self.image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        image_scroll = QScrollArea()
        image_scroll.setWidgetResizable(True)
        image_scroll.setWidget(self.image)
        self.svg = SvgPreviewPanel()
        self.pdf_document = QPdfDocument(self)
        self._pdf_buffer: QBuffer | None = None
        self.pdf = QPdfView()
        self.pdf.setDocument(self.pdf_document)

        self.preview = QStackedWidget()
        for widget in (self.message, self.text, image_scroll, self.svg, self.pdf):
            self.preview.addWidget(widget)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.files)
        splitter.addWidget(self.preview)
        splitter.setSizes([220, 780])
        layout = QVBoxLayout(self)
        layout.addWidget(splitter)

    def show_results(self, output_dir: str | Path, filenames: list[str]) -> None:
        self.release_files()
        root = Path(output_dir)
        for filename in filenames:
            path = root / filename
            if not path.is_file():
                continue
            item = QListWidgetItem(filename)
            item.setData(Qt.ItemDataRole.UserRole, str(path))
            self.files.addItem(item)
        if self.files.count():
            self.files.setCurrentRow(0)
        else:
            self.message.setText("WireViz не создал доступных для просмотра файлов.")
            self.preview.setCurrentWidget(self.message)

    def release_files(self) -> None:
        self.pdf_document.close()
        if self._pdf_buffer is not None:
            self._pdf_buffer.close()
            self._pdf_buffer = None
        self.image.clear()
        self.files.clear()

    def _show_item(self, item: QListWidgetItem | None) -> None:
        if item is None:
            return
        path = Path(str(item.data(Qt.ItemDataRole.UserRole)))
        try:
            suffix = path.suffix.lower()
            self.pdf_document.close()
            if self._pdf_buffer is not None:
                self._pdf_buffer.close()
                self._pdf_buffer = None
            if suffix == ".svg":
                self.svg.show_svg(path.read_text(encoding="utf-8"))
                self.preview.setCurrentWidget(self.svg)
            elif suffix == ".png":
                self.image.setPixmap(QPixmap(str(path)))
                self.preview.setCurrentIndex(2)
            elif suffix == ".pdf":
                self._pdf_buffer = QBuffer(self)
                self._pdf_buffer.setData(path.read_bytes())
                self._pdf_buffer.open(QIODevice.OpenModeFlag.ReadOnly)
                self.pdf_document.load(self._pdf_buffer)
                self.preview.setCurrentWidget(self.pdf)
            elif suffix == ".html":
                self.text.setHtml(path.read_text(encoding="utf-8"))
                self.preview.setCurrentWidget(self.text)
            else:
                self.text.setPlainText(path.read_text(encoding="utf-8"))
                self.preview.setCurrentWidget(self.text)
        except Exception as exc:
            self.message.setText(f"Не удалось открыть {path.name}: {exc}")
            self.preview.setCurrentWidget(self.message)
