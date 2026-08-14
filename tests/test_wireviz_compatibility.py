from __future__ import annotations

import unittest

try:
    from wireviz import wireviz
except ModuleNotFoundError:
    wireviz = None

from wirewizard_gui.domain.models import (
    CableModel,
    ConnectionRowModel,
    ConnectorModel,
    ProjectModel,
)
from wirewizard_gui.domain.serializer import ProjectSerializer


class WireVizCompatibilityTests(unittest.TestCase):
    @unittest.skipIf(wireviz is None, "WireViz runtime dependency is not installed")
    def test_serialized_project_is_accepted_by_pinned_wireviz(self) -> None:
        project = ProjectModel(
            title="Compatibility smoke",
            connectors=[
                ConnectorModel(name="X1", pincount=1),
                ConnectorModel(name="X2", pincount=1),
            ],
            cables=[CableModel(name="W1", wirecount=1)],
            connections=[ConnectionRowModel(route="X1:1 -> W1:1 -> X2:1")],
        )

        assert wireviz is not None
        harness = wireviz.parse(
            ProjectSerializer.to_wireviz_yaml(project),
            return_types="harness",
            output_name="compatibility-smoke",
        )

        self.assertEqual(set(harness.connectors), {"X1", "X2"})
        self.assertEqual(set(harness.cables), {"W1"})


if __name__ == "__main__":
    unittest.main()
