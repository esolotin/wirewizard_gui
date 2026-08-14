from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from wirewizard_gui.domain.models import ProjectModel
from wirewizard_gui.domain.project_format import (
    CURRENT_SCHEMA_VERSION,
    ProjectFormatError,
)
from wirewizard_gui.services import project_service
from wirewizard_gui.services.project_service import ProjectService


class ProjectServiceTests(unittest.TestCase):
    def test_supported_schema_examples_open_and_save_as_current_version(self) -> None:
        examples = Path(__file__).resolve().parents[1] / "examples" / "projects"

        for filename in ("v0-unversioned.json", "v1.json"):
            with self.subTest(filename=filename), tempfile.TemporaryDirectory() as tmp:
                project = ProjectService.load_project(examples / filename)
                self.assertEqual(project.schema_version, CURRENT_SCHEMA_VERSION)

                saved = Path(tmp) / "saved.json"
                ProjectService.save_project(saved, project)
                payload = json.loads(saved.read_text(encoding="utf-8"))

                self.assertEqual(payload["schema_version"], CURRENT_SCHEMA_VERSION)
                self.assertEqual(ProjectService.load_project(saved), project)

    def test_unsupported_or_invalid_schema_version_is_rejected(self) -> None:
        invalid_versions = [True, "1", -1, CURRENT_SCHEMA_VERSION + 1]

        for version in invalid_versions:
            with self.subTest(version=version), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "project.json"
                path.write_text(
                    json.dumps({"schema_version": version}), encoding="utf-8"
                )

                with self.assertRaises(ProjectFormatError):
                    ProjectService.load_project(path)

    def test_save_project_writes_exact_utf8_json_and_loads_it(self) -> None:
        project = ProjectModel(title="Жгут № 1", description="Проверка UTF-8")
        expected = json.dumps(
            project.to_dict(), indent=2, ensure_ascii=False
        ).encode("utf-8")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "project.json"

            ProjectService.save_project(target, project)

            self.assertEqual(target.read_bytes(), expected)
            self.assertEqual(ProjectService.load_project(target), project)
            self.assertEqual({item.name for item in root.iterdir()}, {target.name})

    def test_save_project_fsyncs_complete_sibling_before_replace(self) -> None:
        project = ProjectModel(title="Новая версия")
        expected = json.dumps(
            project.to_dict(), indent=2, ensure_ascii=False
        ).encode("utf-8")
        real_fsync = os.fsync
        real_replace = os.replace
        events: list[str] = []

        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "project.json"
            target.write_bytes(b"old project")

            def record_fsync(fd: int) -> None:
                events.append("fsync")
                real_fsync(fd)

            def record_replace(source: str | Path, destination: str | Path) -> None:
                events.append("replace")
                source_path = Path(source)
                self.assertEqual(source_path.parent, target.parent)
                self.assertEqual(Path(destination), target)
                self.assertEqual(target.read_bytes(), b"old project")
                self.assertEqual(source_path.read_bytes(), expected)
                real_replace(source, destination)

            with (
                patch.object(
                    project_service.os,
                    "fsync",
                    side_effect=record_fsync,
                ),
                patch.object(
                    project_service.os,
                    "replace",
                    side_effect=record_replace,
                ),
            ):
                ProjectService.save_project(target, project)

            self.assertEqual(events[:2], ["fsync", "replace"])
            self.assertEqual(target.read_bytes(), expected)
            self.assertEqual(
                {item.name for item in target.parent.iterdir()},
                {target.name},
            )

    def test_fsync_error_keeps_existing_project_and_cleans_temp(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "project.json"
            target.write_bytes(b"known good")

            with (
                patch.object(
                    project_service.os,
                    "fsync",
                    side_effect=OSError("disk full"),
                ),
                patch.object(project_service.os, "replace") as replace,
                self.assertRaisesRegex(OSError, "disk full"),
            ):
                ProjectService.save_project(target, ProjectModel(title="Новый"))

            replace.assert_not_called()
            self.assertEqual(target.read_bytes(), b"known good")
            self.assertEqual(
                {item.name for item in target.parent.iterdir()},
                {target.name},
            )

    def test_partial_write_error_keeps_existing_project_and_cleans_temp(self) -> None:
        real_named_temporary_file = tempfile.NamedTemporaryFile
        partial_write_sizes: list[int] = []

        class PartialWriteFile:
            def __init__(self, temporary) -> None:
                self._temporary = temporary
                self.name = temporary.name

            def __enter__(self) -> "PartialWriteFile":
                return self

            def __exit__(self, exc_type, exc_value, traceback) -> None:
                self._temporary.close()

            def write(self, data: bytes) -> int:
                fragment = data[:8]
                written = self._temporary.write(fragment)
                self._temporary.flush()
                partial_write_sizes.append(written)
                raise OSError("disk full during write")

        def make_partial_write_file(*args, **kwargs) -> PartialWriteFile:
            return PartialWriteFile(real_named_temporary_file(*args, **kwargs))

        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "project.json"
            target.write_bytes(b"known good")

            with (
                patch.object(
                    project_service.tempfile,
                    "NamedTemporaryFile",
                    side_effect=make_partial_write_file,
                ),
                patch.object(project_service.os, "replace") as replace,
                self.assertRaisesRegex(OSError, "disk full during write"),
            ):
                ProjectService.save_project(target, ProjectModel(title="Новый"))

            replace.assert_not_called()
            self.assertEqual(partial_write_sizes, [8])
            self.assertEqual(target.read_bytes(), b"known good")
            self.assertEqual(
                {item.name for item in target.parent.iterdir()},
                {target.name},
            )

    def test_serialization_error_keeps_existing_project_without_temp(self) -> None:
        project = ProjectModel(title="Новый")

        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "project.json"
            target.write_bytes(b"known good")

            with (
                patch.object(
                    project,
                    "to_dict",
                    return_value={"invalid": object()},
                ),
                patch.object(
                    project_service.tempfile,
                    "NamedTemporaryFile",
                ) as named_temporary_file,
                self.assertRaisesRegex(TypeError, "not JSON serializable"),
            ):
                ProjectService.save_project(target, project)

            named_temporary_file.assert_not_called()
            self.assertEqual(target.read_bytes(), b"known good")
            self.assertEqual(
                {item.name for item in target.parent.iterdir()},
                {target.name},
            )

    def test_replace_error_keeps_existing_project_and_cleans_temp(self) -> None:
        error = PermissionError("project is locked")

        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "project.json"
            target.write_bytes(b"known good")

            with (
                patch.object(project_service.os, "replace", side_effect=error),
                self.assertRaises(PermissionError) as raised,
            ):
                ProjectService.save_project(target, ProjectModel(title="Новый"))

            self.assertIs(raised.exception, error)
            self.assertEqual(target.read_bytes(), b"known good")
            self.assertEqual(
                {item.name for item in target.parent.iterdir()},
                {target.name},
            )


if __name__ == "__main__":
    unittest.main()
