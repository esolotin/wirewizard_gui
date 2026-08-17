from __future__ import annotations

import unittest

from wirewizard_gui.domain.models import (
    AnnotationModel,
    CableModel,
    ConnectionRowModel,
    ConnectorModel,
    FerruleModel,
    ProjectModel,
)
from wirewizard_gui.domain.options import CONNECTOR_SUBTYPES
from wirewizard_gui.domain.serializer import ProjectSerializer
from wirewizard_gui.domain.validation import IssueSeverity, ProjectValidator


class RussianDomainTests(unittest.TestCase):
    def test_annotations_round_trip_as_isolated_wireviz_nodes(self) -> None:
        project = ProjectModel(
            annotations=[
                AnnotationModel(
                    id="note-1",
                    title="Монтаж <важно>",
                    text="Экран подключить только со стороны X1.\nНе укорачивать.",
                )
            ]
        )

        exported = ProjectSerializer.to_wireviz_dict(project)
        note_name = "__WW_NOTE_note-1"
        note = exported["connectors"][note_name]

        self.assertEqual(note["style"], "simple")
        self.assertFalse(note["show_name"])
        self.assertFalse(note["show_pincount"])
        self.assertTrue(note["ignore_in_bom"])
        self.assertEqual(exported["connections"], [[note_name]])
        self.assertIn("&lt;важно&gt;", note["type"])

        restored = ProjectSerializer.from_wireviz_dict(exported)
        self.assertEqual(restored.annotations, project.annotations)
        self.assertEqual(restored.connections, [])

    def test_new_models_use_russian_names(self) -> None:
        self.assertEqual(ProjectModel().title, "Новый жгут")
        self.assertEqual(ConnectorModel(name="X1").type, "Универсальный разъём")
        self.assertEqual(CableModel(name="W1").type, "Универсальный кабель")
        self.assertEqual(FerruleModel(name="F1").type, "Обжимной наконечник")

    def test_connector_subtypes_keep_technical_wireviz_terms(self) -> None:
        self.assertEqual(CONNECTOR_SUBTYPES, ["", "male", "female", "plug", "socket"])

        project = ProjectModel(
            connectors=[ConnectorModel(name="X1", subtype="female")],
        )

        data = ProjectSerializer.to_wireviz_dict(project)

        self.assertEqual(data["connectors"]["X1"]["subtype"], "female")

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

    def test_structured_validation_separates_errors_and_warnings(self) -> None:
        project = ProjectModel(
            connectors=[
                ConnectorModel(name="X1", pincount=2),
                ConnectorModel(name="X2", pincount=2),
                ConnectorModel(name="X3", pincount=2),
            ],
            cables=[CableModel(name="W1", wirecount=1)],
            connections=[ConnectionRowModel(route="X1:3 -> W1:1 -> X2:1")],
        )

        issues = ProjectValidator.validate_issues(project)
        errors = [issue for issue in issues if issue.severity == IssueSeverity.ERROR]
        warnings = [issue for issue in issues if issue.severity == IssueSeverity.WARNING]

        self.assertTrue(errors)
        self.assertEqual(errors[0].component_name, "X1")
        self.assertEqual(errors[0].row_index, 0)
        self.assertEqual([issue.component_name for issue in warnings], ["X3"])

    def test_route_split_preserves_wireviz_arrows_and_groups(self) -> None:
        cases = {
            "X1:1 -> W1:1 -> X2:1": ["X1:1", "W1:1", "X2:1"],
            "X1:1 -> -> -> X2:1": ["X1:1", "->", "X2:1"],
            "X1:1->->->X2:1": ["X1:1", "->", "X2:1"],
            "X1:1 -> --> -> X2:1": ["X1:1", "-->", "X2:1"],
            "X1:1->-->->X2:1": ["X1:1", "-->", "X2:1"],
            "X1:1 -> -->->X2:1": ["X1:1", "-->", "X2:1"],
            "X1:1->--> -> X2:1": ["X1:1", "-->", "X2:1"],
            "X1:1 -> <=> -> X2:1": ["X1:1", "<=>", "X2:1"],
            "X1:1-><=>->X2:1": ["X1:1", "<=>", "X2:1"],
            "X1:[1, 2] -> [->, -->] -> X2:[1, 2]": [
                "X1:[1, 2]",
                "[->, -->]",
                "X2:[1, 2]",
            ],
            "X1:1->W1:1->X2:1": ["X1:1", "W1:1", "X2:1"],
            "X1:1 ->W1:1 -> X2:1": ["X1:1", "W1:1", "X2:1"],
            "X1:1->W1:1 -> X2:1": ["X1:1", "W1:1", "X2:1"],
            "X1:1 -> W1:1->X2:1": ["X1:1", "W1:1", "X2:1"],
        }

        for route, expected in cases.items():
            with self.subTest(route=route):
                self.assertEqual(ProjectSerializer._split_route(route), expected)

    def test_wireviz_connections_survive_import_and_export(self) -> None:
        connections = [
            [{"X1": 1}, "->", {"X2": 1}],
            [{"X1": 1}, "-->", {"X2": 1}],
            [{"X1": 1}, "<=>", {"X2": 1}],
            [{"X1": [1, 2]}, ["->", "-->"], {"X2": [1, 2]}],
            [["X1", "X2"], {"W1": [1, 2]}, {"X3": [1, 2]}],
        ]
        source = {
            "connectors": {
                "X1": {"pincount": 2},
                "X2": {"pincount": 2},
                "X3": {"pincount": 2},
            },
            "cables": {"W1": {"wirecount": 2}},
            "connections": connections,
        }

        project = ProjectSerializer.from_wireviz_dict(source)
        exported = ProjectSerializer.to_wireviz_dict(project)

        self.assertEqual(exported["connections"], connections)
        self.assertEqual(ProjectValidator.validate(project), [])

    def test_bom_fields_survive_wireviz_yaml_round_trip(self) -> None:
        project = ProjectModel(
            connectors=[
                ConnectorModel(
                    name="X1",
                    pn="CONN-1",
                    manufacturer="Molex",
                    mpn="22-01-2027",
                    supplier="Поставщик",
                    spn="A-42",
                )
            ],
            cables=[CableModel(name="W1", pn="WIRE-1", ignore_in_bom=True)],
            ferrules=[
                FerruleModel(name="F1", manufacturer="Phoenix Contact", mpn="AI 0,5-8")
            ],
        )

        exported = ProjectSerializer.to_wireviz_dict(project)
        restored = ProjectSerializer.from_wireviz_dict(exported)

        self.assertEqual(exported["connectors"]["X1"]["pn"], "CONN-1")
        self.assertEqual(exported["connectors"]["X1"]["mpn"], "22-01-2027")
        self.assertTrue(exported["cables"]["W1"]["ignore_in_bom"])
        self.assertEqual(restored.connectors[0].supplier, "Поставщик")
        self.assertEqual(restored.connectors[0].spn, "A-42")
        self.assertTrue(restored.cables[0].ignore_in_bom)
        self.assertEqual(restored.ferrules[0].manufacturer, "Phoenix Contact")

    def test_supported_edits_override_preserved_wireviz_extras(self) -> None:
        project = ConnectorModel(
            name="X1",
            type="Новый тип",
            wireviz_extras={"type": "Старый тип", "custom": {"nested": True}},
        )

        exported = ProjectSerializer.to_wireviz_dict(
            ProjectModel(connectors=[project])
        )

        self.assertEqual(exported["connectors"]["X1"]["type"], "Новый тип")
        self.assertEqual(
            exported["connectors"]["X1"]["custom"], {"nested": True}
        )


    def test_validator_rejects_invalid_arrows_and_group_sizes(self) -> None:
        project = ProjectModel(
            connectors=[
                ConnectorModel(name=f"X{idx}", pincount=3)
                for idx in range(1, 5)
            ],
            cables=[CableModel(name="W1", wirecount=3)],
            connections=[
                ConnectionRowModel(route="X1:1 -> --> -> W1:1 -> X2:1"),
                ConnectionRowModel(route="X1:1 -> -->"),
                ConnectionRowModel(
                    route="[X1, X2, X3] -> W1:[1, 2] -> X4:[1, 2]"
                ),
                ConnectionRowModel(route="X1:1-3 -> W1:1 -> X2:1"),
            ],
        )

        errors = ProjectValidator.validate(project)

        self.assertTrue(
            any("Строка соединения 1" in error and "чередоваться" in error for error in errors),
            errors,
        )
        self.assertTrue(
            any("Строка соединения 2" in error and "последним" in error for error in errors),
            errors,
        )
        self.assertTrue(
            any("Строка соединения 3" in error and "одинаковую длину" in error for error in errors),
            errors,
        )
        self.assertTrue(
            any("Строка соединения 4" in error and "одинаковую длину" in error for error in errors),
            errors,
        )


if __name__ == "__main__":
    unittest.main()
