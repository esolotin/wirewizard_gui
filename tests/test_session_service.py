from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from PySide6.QtCore import QByteArray

from wirewizard_gui.domain.models import ProjectModel
from wirewizard_gui.services.session_service import SessionService


class SessionServiceTests(unittest.TestCase):
    def test_recent_projects_are_deduplicated_bounded_and_skip_missing_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service = SessionService(root / "session")
            projects = []
            for index in range(12):
                path = root / f"project-{index}.json"
                path.write_text("{}", encoding="utf-8")
                projects.append(path)
                service.add_recent_project(path)

            service.add_recent_project(projects[5])
            projects[10].unlink()

            recent = service.recent_projects()
            self.assertEqual(recent[0], str(projects[5].resolve()))
            self.assertNotIn(str(projects[10].resolve()), recent)
            self.assertLessEqual(len(recent), service.MAX_RECENT_PROJECTS)

    def test_layout_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service = SessionService(tmp)
            geometry = QByteArray(b"geometry")
            state = QByteArray(b"state")

            service.save_layout(geometry, state)

            restored = SessionService(tmp).load_layout()
            self.assertEqual(restored, (geometry, state))

    def test_recovery_round_trip_keeps_original_path_and_can_be_cleared(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service = SessionService(tmp)
            project = ProjectModel(title="Аварийная копия")
            original_path = str(Path(tmp) / "working.json")

            service.save_recovery(project, original_path)

            restored, restored_path = SessionService(tmp).load_recovery()
            self.assertEqual(restored, project)
            self.assertEqual(restored_path, original_path)
            service.clear_recovery()
            self.assertFalse(service.recovery_path.exists())
            self.assertEqual(service.settings.value("recovery/original_path"), None)


if __name__ == "__main__":
    unittest.main()
