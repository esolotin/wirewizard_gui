from __future__ import annotations

import unittest

from wirewizard_gui.domain.component_library import COMPONENT_PRESETS, presets_for
from wirewizard_gui.domain.models import CableModel, ConnectorModel, FerruleModel


class ComponentLibraryTests(unittest.TestCase):
    def test_library_contains_each_component_kind(self) -> None:
        self.assertGreaterEqual(len(presets_for("connector")), 3)
        self.assertGreaterEqual(len(presets_for("cable")), 3)
        self.assertGreaterEqual(len(presets_for("ferrule")), 3)

    def test_presets_create_independent_models_with_new_ids(self) -> None:
        expected_types = {
            "connector": ConnectorModel,
            "cable": CableModel,
            "ferrule": FerruleModel,
        }
        for preset in COMPONENT_PRESETS:
            with self.subTest(preset=preset.key):
                first = preset.create("A1")
                second = preset.create("A2")
                self.assertIsInstance(first, expected_types[preset.kind])
                self.assertNotEqual(first.id, second.id)
                self.assertEqual(first.name, "A1")
                self.assertEqual(second.name, "A2")


if __name__ == "__main__":
    unittest.main()
