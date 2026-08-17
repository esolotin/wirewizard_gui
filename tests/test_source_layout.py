from __future__ import annotations

import ast
import importlib.util
from pathlib import Path
import unittest

from wirewizard_gui import app as canonical_app


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LEGACY_ROOTS = ("domain", "services", "ui")


class SourceLayoutTests(unittest.TestCase):
    def test_legacy_source_mirrors_are_absent(self) -> None:
        for directory in LEGACY_ROOTS:
            with self.subTest(directory=directory):
                self.assertFalse(
                    (PROJECT_ROOT / directory).exists(),
                    f"Legacy source mirror must be removed: {directory}",
                )

    def test_source_code_does_not_import_legacy_namespaces(self) -> None:
        source_files = [PROJECT_ROOT / "app.py"]
        for directory in ("wirewizard_gui", "tests", "packaging/common"):
            source_files.extend(sorted((PROJECT_ROOT / directory).rglob("*.py")))

        offenders: list[str] = []
        for path in source_files:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif (
                    isinstance(node, ast.ImportFrom)
                    and node.level == 0
                    and node.module is not None
                ):
                    names = [node.module]
                else:
                    continue
                for name in names:
                    if name.split(".", 1)[0] in LEGACY_ROOTS:
                        relative = path.relative_to(PROJECT_ROOT)
                        offenders.append(f"{relative}:{node.lineno}: {name}")

        self.assertEqual(offenders, [])

    def test_root_launcher_delegates_to_canonical_entry_point(self) -> None:
        launcher_path = PROJECT_ROOT / "app.py"
        spec = importlib.util.spec_from_file_location(
            "wirewizard_compat_launcher",
            launcher_path,
        )
        self.assertIsNotNone(spec)
        assert spec is not None
        self.assertIsNotNone(spec.loader)
        assert spec.loader is not None

        launcher = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(launcher)

        self.assertIs(launcher.main, canonical_app.main)


if __name__ == "__main__":
    unittest.main()
