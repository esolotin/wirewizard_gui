from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile

from wirewizard_gui.domain.models import ProjectModel
from wirewizard_gui.domain.serializer import ProjectSerializer


def _atomic_write_text(path: str | Path, text: str) -> None:
    target = Path(path)
    data = text.encode("utf-8")
    temporary_path: Path | None = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=target.parent,
            prefix=".wirewizard-",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            temporary.write(data)
            temporary.flush()
            os.fsync(temporary.fileno())

        os.replace(temporary_path, target)
        temporary_path = None
    except BaseException:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass
        raise


class ProjectService:
    @staticmethod
    def save_project(path: str | Path, project: ProjectModel) -> None:
        text = json.dumps(project.to_dict(), indent=2, ensure_ascii=False)
        _atomic_write_text(path, text)

    @staticmethod
    def save_project_yaml(path: str | Path, project: ProjectModel) -> None:
        Path(path).write_text(ProjectSerializer.to_wireviz_yaml(project), encoding="utf-8")

    @staticmethod
    def load_project(path: str | Path) -> ProjectModel:
        path = Path(path)
        suffix = path.suffix.lower()
        text = path.read_text(encoding="utf-8")
        if suffix in {".yml", ".yaml"}:
            return ProjectSerializer.from_wireviz_yaml(text)
        data = json.loads(text)
        return ProjectModel.from_dict(data)

    @staticmethod
    def import_yaml(path: str | Path) -> ProjectModel:
        return ProjectSerializer.from_wireviz_yaml(Path(path).read_text(encoding="utf-8"))

    @staticmethod
    def export_yaml(path: str | Path, project: ProjectModel) -> None:
        Path(path).write_text(ProjectSerializer.to_wireviz_yaml(project), encoding="utf-8")
