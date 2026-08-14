from __future__ import annotations

from pathlib import Path
import xml.etree.ElementTree as ET

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtSvgWidgets import QGraphicsSvgItem
from PySide6.QtWidgets import (
    QFileDialog,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QStackedLayout,
    QVBoxLayout,
    QWidget,
)


class _SvgView(QGraphicsView):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

    def wheelEvent(self, event) -> None:
        factor = 1.2 if event.angleDelta().y() > 0 else 1 / 1.2
        self.scale(factor, factor)
        event.accept()


class SvgPreviewPanel(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._svg_text = ""
        self._display_svg = ""
        self._highlight_name: str | None = None
        self._renderer: QSvgRenderer | None = None

        self.info_label = QLabel("Предпросмотр SVG пока не построен.")
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.info_label.setWordWrap(True)

        self.view = _SvgView()
        self.scene = QGraphicsScene(self)
        self.view.setScene(self.scene)

        zoom_out = QPushButton("−")
        zoom_out.setToolTip("Уменьшить")
        zoom_in = QPushButton("+")
        zoom_in.setToolTip("Увеличить")
        fit = QPushButton("Вписать")
        save_svg = QPushButton("Сохранить SVG")
        save_png = QPushButton("Сохранить PNG")
        zoom_out.clicked.connect(lambda: self.view.scale(1 / 1.2, 1 / 1.2))
        zoom_in.clicked.connect(lambda: self.view.scale(1.2, 1.2))
        fit.clicked.connect(self.fit_to_view)
        save_svg.clicked.connect(self.save_svg)
        save_png.clicked.connect(self.save_png)

        controls = QHBoxLayout()
        for widget in (zoom_out, zoom_in, fit, save_svg, save_png):
            controls.addWidget(widget)
        controls.addStretch(1)

        self.stack = QStackedLayout()
        info_page = QWidget()
        info_layout = QVBoxLayout(info_page)
        info_layout.addWidget(self.info_label)

        svg_page = QWidget()
        svg_layout = QVBoxLayout(svg_page)
        svg_layout.addLayout(controls)
        svg_layout.addWidget(self.view)

        self.stack.addWidget(info_page)
        self.stack.addWidget(svg_page)
        self.setLayout(self.stack)

    def show_message(self, message: str) -> None:
        self.info_label.setText(message)
        self.stack.setCurrentIndex(0)

    def show_svg(self, svg_text: str) -> None:
        self._svg_text = svg_text
        self._render_svg()
        self.stack.setCurrentIndex(1)
        self.fit_to_view()

    def set_highlight(self, component_name: str | None) -> None:
        self._highlight_name = component_name
        if self._svg_text:
            self._render_svg()

    def fit_to_view(self) -> None:
        if not self.scene.items():
            return
        self.view.resetTransform()
        self.view.fitInView(
            self.scene.itemsBoundingRect(), Qt.AspectRatioMode.KeepAspectRatio
        )

    def save_svg(self) -> None:
        if not self._display_svg:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Сохранить SVG", "harness.svg", "SVG (*.svg)"
        )
        if path:
            try:
                Path(path).write_text(self._display_svg, encoding="utf-8")
            except OSError as exc:
                QMessageBox.critical(self, "Сохранение SVG", str(exc))

    def save_png(self) -> None:
        if self._renderer is None or not self._renderer.isValid():
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Сохранить PNG", "harness.png", "PNG (*.png)"
        )
        if not path:
            return
        size = self._renderer.defaultSize()
        if size.isEmpty():
            return
        image = QImage(size, QImage.Format.Format_ARGB32)
        image.fill(QColor(Qt.GlobalColor.transparent))
        painter = QPainter(image)
        self._renderer.render(painter)
        painter.end()
        if not image.save(path, "PNG"):
            QMessageBox.critical(self, "Сохранение PNG", "Не удалось записать PNG.")

    def _render_svg(self) -> None:
        self._display_svg = self._highlight_svg(self._svg_text, self._highlight_name)
        renderer = QSvgRenderer(QByteArray(self._display_svg.encode("utf-8")), self)
        self.scene.clear()
        item = QGraphicsSvgItem()
        item.setSharedRenderer(renderer)
        self.scene.addItem(item)
        self.scene.setSceneRect(item.boundingRect())
        self._renderer = renderer

    @staticmethod
    def _highlight_svg(svg_text: str, component_name: str | None) -> str:
        if not component_name:
            return svg_text
        try:
            root = ET.fromstring(svg_text)
        except ET.ParseError:
            return svg_text
        parents = {child: parent for parent in root.iter() for child in parent}
        text_node = next(
            (
                element
                for element in root.iter()
                if element.tag.rsplit("}", 1)[-1] == "text"
                and "".join(element.itertext()).strip() == component_name
            ),
            None,
        )
        if text_node is None:
            return svg_text
        group = text_node
        while group in parents and group.tag.rsplit("}", 1)[-1] != "g":
            group = parents[group]
        for element in group.iter():
            tag = element.tag.rsplit("}", 1)[-1]
            if tag in {"ellipse", "path", "polygon", "polyline", "rect"}:
                element.set("stroke", "#e53935")
                element.set("stroke-width", "4")
            elif tag == "text":
                element.set("fill", "#e53935")
                element.set("font-weight", "bold")
        return ET.tostring(root, encoding="unicode")
