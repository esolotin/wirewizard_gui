from __future__ import annotations

import unittest

from wirewizard_gui.domain.models import (
    CableModel,
    ConnectionRowModel,
    ConnectorModel,
    FerruleModel,
    ProjectModel,
)
from wirewizard_gui.domain.serializer import ProjectSerializer
from wirewizard_gui.domain.validation import ProjectValidator


class RussianDomainTests(unittest.TestCase):
    def test_new_models_use_russian_names(self) -> None:
        self.assertEqual(ProjectModel().title, "Новый жгут")
        self.assertEqual(ConnectorModel(name="X1").type, "Универсальный разъём")
        self.assertEqual(CableModel(name="W1").type, "Универсальный кабель")
        self.assertEqual(FerruleModel(name="F1").type, "Обжимной наконечник")

    def test_russian_ferrule_type_survives_yaml_round_trip(self) -> None:
        project = ProjectModel(
            ferrules=[FerruleModel(name="J1", type="Обжимной наконечник")],
        )

        restored = ProjectSerializer.from_wireviz_yaml(
            ProjectSerializer.to_wireviz_yaml(project),
        )

        self.assertEqual(len(restored.ferrules), 1)
        self.assertEqual(restored.ferrules[0].name, "J1")
        self.assertEqual(restored.ferrules[0].type, "Обжимной наконечник")

    def test_validation_messages_are_russian(self) -> None:
        project = ProjectModel(
            connectors=[ConnectorModel(name="X1")],
            connections=[ConnectionRowModel(route="UNKNOWN:1 -> X1:1")],
        )

        errors = ProjectValidator.validate(project)

        self.assertTrue(errors)
        self.assertTrue(all("Connection row" not in error for error in errors))
        self.assertTrue(any("Строка соединения" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
