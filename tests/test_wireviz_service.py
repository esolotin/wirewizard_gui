from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

from wirewizard_gui.domain.models import ProjectModel
from wirewizard_gui.services import wireviz_service
from wirewizard_gui.services.wireviz_service import (
    DEFAULT_OUTPUT_FORMATS,
    WireVizDependencyError,
    WireVizService,
)


class WireVizServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.project = ProjectModel(title="Test harness")

    @patch.object(wireviz_service, "configure_bundled_graphviz")
    @patch.object(wireviz_service, "graphviz_subprocess_environment")
    @patch.object(wireviz_service, "_load_wireviz_parse")
    @patch.object(
        wireviz_service.ProjectSerializer,
        "to_wireviz_yaml",
        return_value="metadata:\n  title: Test harness\n",
    )
    def test_render_svg_uses_in_process_api(
        self,
        serialize: Mock,
        load_parse: Mock,
        graphviz_environment: Mock,
        configure_graphviz: Mock,
    ) -> None:
        parse = Mock(return_value="<svg>ok</svg>")
        load_parse.return_value = parse

        ok, message, svg = WireVizService.render_svg(self.project)

        self.assertTrue(ok)
        self.assertEqual(message, "OK")
        self.assertEqual(svg, "<svg>ok</svg>")
        configure_graphviz.assert_called_once_with()
        graphviz_environment.assert_called_once_with(configure_graphviz.return_value)
        serialize.assert_called_once_with(self.project)
        parse.assert_called_once_with(
            "metadata:\n  title: Test harness\n",
            return_types="svg",
            output_name="preview",
        )

    @patch.object(wireviz_service, "configure_bundled_graphviz")
    @patch.object(wireviz_service, "_load_wireviz_parse")
    def test_render_svg_accepts_utf8_bytes(
        self,
        load_parse: Mock,
        configure_graphviz: Mock,
    ) -> None:
        load_parse.return_value = Mock(return_value="<svg>тест</svg>".encode())

        ok, _, svg = WireVizService.render_svg(self.project)

        self.assertTrue(ok)
        self.assertEqual(svg, "<svg>тест</svg>")
        configure_graphviz.assert_called_once_with()

    @patch.object(wireviz_service, "configure_bundled_graphviz")
    @patch.object(wireviz_service, "_load_wireviz_parse")
    def test_render_svg_captures_wireviz_console_output(
        self,
        load_parse: Mock,
        _configure_graphviz: Mock,
    ) -> None:
        def fake_parse(*_args: object, **_kwargs: object) -> str:
            print("unused component warning")
            return "<svg>ok</svg>"

        load_parse.return_value = fake_parse

        with (
            self.assertLogs(wireviz_service.logger, level="WARNING") as captured,
            patch.object(sys, "stdout", None),
            patch.object(sys, "stderr", None),
        ):
            ok, _, _ = WireVizService.render_svg(self.project)

        self.assertTrue(ok)
        self.assertIn("unused component warning", "\n".join(captured.output))

    @patch.object(wireviz_service, "configure_bundled_graphviz")
    @patch.object(wireviz_service, "_load_wireviz_parse")
    def test_missing_wireviz_returns_clear_error(
        self,
        load_parse: Mock,
        configure_graphviz: Mock,
    ) -> None:
        load_parse.side_effect = WireVizDependencyError(
            "WireViz 0.4.1 не удалось загрузить."
        )

        with self.assertLogs(wireviz_service.logger, level="ERROR"):
            ok, message, svg = WireVizService.render_svg(self.project)

        self.assertFalse(ok)
        self.assertIn("WireViz 0.4.1", message)
        self.assertIsNone(svg)
        configure_graphviz.assert_called_once_with()

    @patch.object(wireviz_service, "configure_bundled_graphviz")
    @patch.object(wireviz_service, "_load_wireviz_parse")
    def test_missing_dot_returns_graphviz_specific_error(
        self,
        load_parse: Mock,
        _configure_graphviz: Mock,
    ) -> None:
        executable_not_found = type("ExecutableNotFound", (RuntimeError,), {})
        load_parse.return_value = Mock(
            side_effect=executable_not_found("failed to execute PosixPath('dot')")
        )

        with self.assertLogs(wireviz_service.logger, level="ERROR"):
            ok, message, _ = WireVizService.render_svg(self.project)

        self.assertFalse(ok)
        self.assertIn("Graphviz (dot)", message)

    @patch.object(wireviz_service, "configure_bundled_graphviz")
    @patch.object(wireviz_service, "_load_wireviz_parse")
    @patch.object(
        wireviz_service.ProjectSerializer,
        "to_wireviz_yaml",
        return_value="metadata:\n  title: Export\n",
    )
    def test_run_full_generates_standard_outputs(
        self,
        _serialize: Mock,
        load_parse: Mock,
        configure_graphviz: Mock,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)

            def fake_parse(input_path: Path, **kwargs: object) -> None:
                self.assertEqual(input_path, output_dir / "harness.yml")
                for suffix in (".html", ".png", ".svg", ".bom.tsv"):
                    (output_dir / f"harness{suffix}").write_bytes(b"output")

            parse = Mock(side_effect=fake_parse)
            load_parse.return_value = parse

            ok, message, generated = WireVizService.run_full(
                self.project,
                output_dir,
                "harness",
            )

            self.assertTrue(ok)
            self.assertIn("harness.svg", message)
            self.assertEqual(
                generated,
                ["harness.bom.tsv", "harness.html", "harness.png", "harness.svg"],
            )
            self.assertEqual(
                (output_dir / "harness.yml").read_text(encoding="utf-8"),
                "metadata:\n  title: Export\n",
            )
            parse.assert_called_once_with(
                output_dir / "harness.yml",
                output_formats=DEFAULT_OUTPUT_FORMATS,
                output_dir=output_dir,
                output_name="harness",
            )
            configure_graphviz.assert_called_once_with()

    @patch.object(wireviz_service, "_load_wireviz_parse")
    def test_run_full_rejects_path_as_base_name(self, load_parse: Mock) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertLogs(wireviz_service.logger, level="ERROR"):
                ok, message, generated = WireVizService.run_full(
                    self.project,
                    tmp,
                    "../escape",
                )

        self.assertFalse(ok)
        self.assertIn("без пути", message)
        self.assertEqual(generated, [])
        load_parse.assert_not_called()

    def test_load_parse_reports_missing_python_dependency(self) -> None:
        missing = ModuleNotFoundError("No module named wireviz", name="wireviz")
        with patch.object(
            wireviz_service,
            "_import_wireviz_modules",
            side_effect=missing,
        ):
            with self.assertRaisesRegex(WireVizDependencyError, "wireviz"):
                wireviz_service._load_wireviz_parse()

    def test_load_parse_accepts_expected_api(self) -> None:
        parse = Mock()
        package = SimpleNamespace(__version__="0.4.1")
        api = SimpleNamespace(parse=parse)
        with patch.object(
            wireviz_service,
            "_import_wireviz_modules",
            return_value=(package, api),
        ):
            result = wireviz_service._load_wireviz_parse()
        self.assertIs(result, parse)


if __name__ == "__main__":
    unittest.main()
