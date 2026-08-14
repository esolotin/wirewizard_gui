from __future__ import annotations

import unittest

from wirewizard_gui.domain.models import (
    CableModel,
    ConnectionRowModel,
    ConnectorModel,
    ProjectModel,
)
from wirewizard_gui.domain.references import ProjectReferences
from wirewizard_gui.domain.validation import ProjectValidator


class ProjectReferencesTests(unittest.TestCase):
    def test_rename_updates_only_exact_component_references(self) -> None:
        project = ProjectModel(
            connectors=[
                ConnectorModel(name="X1"),
                ConnectorModel(name="X10"),
                ConnectorModel(name="X2"),
            ],
            cables=[CableModel(name="W1")],
            connections=[
                ConnectionRowModel(route="X1:1 -> W1:1 -> X10:1"),
                ConnectionRowModel(route="[X1, X10] -> W1:[1, 2] -> X2:[1, 2]"),
                ConnectionRowModel(route="X1.1:1 -> --> -> X2:1"),
            ],
        )

        changed = ProjectReferences.rename_component(project, "X1", "X3")
        project.connectors[0].name = "X3"

        self.assertEqual(changed, [0, 1, 2])
        self.assertEqual(
            [row.route for row in project.connections],
            [
                "X3:1 -> W1:1 -> X10:1",
                "[X3, X10] -> W1:[1, 2] -> X2:[1, 2]",
                "X3.1:1 -> --> -> X2:1",
            ],
        )
        self.assertFalse(
            any("неизвестный компонент 'X3'" in error for error in ProjectValidator.validate(project))
        )

    def test_dependencies_and_removal_use_exact_names(self) -> None:
        project = ProjectModel(
            connectors=[ConnectorModel(name="X1"), ConnectorModel(name="X10")],
            cables=[CableModel(name="W1")],
            connections=[
                ConnectionRowModel(route="X1:1 -> W1:1 -> X10:1"),
                ConnectionRowModel(route="X10:1 -> W1:1 -> X10:2"),
            ],
        )

        self.assertEqual(ProjectReferences.dependent_rows(project, "X1"), [0])
        removed = ProjectReferences.remove_dependent_rows(project, "X1")

        self.assertEqual(removed, [0])
        self.assertEqual(
            [row.route for row in project.connections],
            ["X10:1 -> W1:1 -> X10:2"],
        )


if __name__ == "__main__":
    unittest.main()
