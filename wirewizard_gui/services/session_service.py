from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QByteArray, QSettings

from wirewizard_gui.domain.models import ProjectModel
from wirewizard_gui.runtime import application_data_dir
from wirewizard_gui.services.project_service import ProjectService


class SessionService:
    """Persistent desktop session state, kept outside project files."""

    MAX_RECENT_PROJECTS = 10

    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root) if root is not None else application_data_dir() / "session"
        self.root.mkdir(parents=True, exist_ok=True)
        self.settings = QSettings(str(self.root / "settings.ini"), QSettings.Format.IniFormat)
        self.recovery_path = self.root / "recovery.json"

    def recent_projects(self) -> list[str]:
        value = self.settings.value("recent_projects", [])
        paths = [str(value)] if isinstance(value, str) else [str(item) for item in value]
        return [path for path in paths if Path(path).is_file()][: self.MAX_RECENT_PROJECTS]

    def add_recent_project(self, path: str | Path) -> None:
        normalized = str(Path(path).resolve())
        paths = [item for item in self.recent_projects() if item != normalized]
        self.settings.setValue(
            "recent_projects", [normalized, *paths][: self.MAX_RECENT_PROJECTS]
        )
        self.settings.sync()

    def remove_recent_project(self, path: str | Path) -> None:
        normalized = str(Path(path).resolve())
        self.settings.setValue(
            "recent_projects",
            [item for item in self.recent_projects() if item != normalized],
        )
        self.settings.sync()

    def save_layout(self, geometry: QByteArray, state: QByteArray) -> None:
        self.settings.setValue("window/geometry", geometry)
        self.settings.setValue("window/state", state)
        self.settings.sync()

    def load_layout(self) -> tuple[QByteArray | None, QByteArray | None]:
        geometry = self.settings.value("window/geometry")
        state = self.settings.value("window/state")
        return (
            geometry if isinstance(geometry, QByteArray) else None,
            state if isinstance(state, QByteArray) else None,
        )

    def save_recovery(self, project: ProjectModel, original_path: str | None) -> None:
        ProjectService.save_project(self.recovery_path, project)
        self.settings.setValue("recovery/original_path", original_path or "")
        self.settings.sync()

    def load_recovery(self) -> tuple[ProjectModel, str | None]:
        project = ProjectService.load_project(self.recovery_path)
        original_path = str(self.settings.value("recovery/original_path", "")).strip()
        return project, original_path or None

    def clear_recovery(self) -> None:
        try:
            self.recovery_path.unlink(missing_ok=True)
        except OSError:
            pass
        self.settings.remove("recovery/original_path")
        self.settings.sync()
