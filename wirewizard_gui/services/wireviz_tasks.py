from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, Signal, Slot

from wirewizard_gui.domain.models import ProjectModel
from wirewizard_gui.services.wireviz_service import WireVizService


class WireVizTaskSignals(QObject):
    finished = Signal(str, int, bool, str, object)


class WireVizTask(QRunnable):
    def __init__(
        self,
        kind: str,
        request_id: int,
        project: ProjectModel,
        output_dir: str | Path | None = None,
        base_name: str = "harness",
    ) -> None:
        super().__init__()
        self.kind = kind
        self.request_id = request_id
        self.project = deepcopy(project)
        self.output_dir = output_dir
        self.base_name = base_name
        self.signals = WireVizTaskSignals()

    @Slot()
    def run(self) -> None:
        try:
            if self.kind == "preview":
                ok, message, svg = WireVizService.render_svg(self.project)
                self.signals.finished.emit(
                    self.kind, self.request_id, ok, message, svg
                )
                return
            if self.kind == "full" and self.output_dir is not None:
                ok, message, generated = WireVizService.run_full(
                    self.project, self.output_dir, self.base_name
                )
                self.signals.finished.emit(
                    self.kind, self.request_id, ok, message, generated
                )
                return
            self.signals.finished.emit(
                self.kind,
                self.request_id,
                False,
                "Некорректная задача WireViz.",
                None,
            )
        except Exception as exc:
            self.signals.finished.emit(
                self.kind,
                self.request_id,
                False,
                f"Ошибка фоновой задачи WireViz: {exc}",
                None,
            )
