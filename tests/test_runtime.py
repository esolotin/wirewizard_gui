from __future__ import annotations

import logging
import os
from pathlib import Path, PurePosixPath
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

from wirewizard_gui import runtime
from wirewizard_gui.metadata import APP_ID, APP_NAME, APP_VERSION


class RuntimeTests(unittest.TestCase):
    def tearDown(self) -> None:
        sys.excepthook = runtime._ORIGINAL_SYS_EXCEPTHOOK
        runtime.threading.excepthook = runtime._ORIGINAL_THREADING_EXCEPTHOOK
        logger = logging.getLogger("wirewizard_gui")
        for handler in list(logger.handlers):
            if getattr(handler, runtime._HANDLER_MARKER, False):
                logger.removeHandler(handler)
                handler.close()

    def test_metadata_is_stable(self) -> None:
        self.assertEqual(APP_NAME, "WireWizardGUI")
        self.assertEqual(APP_ID, "wirewizardgui")
        self.assertEqual(APP_VERSION, "0.1.0")

    def test_finds_graphviz_in_pyinstaller_internal_layout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app_dir = Path(tmp)
            graphviz_bin = app_dir / "_internal" / "graphviz" / "bin"
            graphviz_bin.mkdir(parents=True)
            (graphviz_bin / "dot.exe").write_bytes(b"")

            found = runtime.find_bundled_graphviz(app_dir=app_dir, environ={})

            self.assertEqual(found, graphviz_bin.resolve())

    def test_finds_graphviz_below_meipass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            executable = root / "app" / "WireWizardGUI"
            bundle = root / "bundle"
            graphviz_bin = bundle / "graphviz" / "bin"
            graphviz_bin.mkdir(parents=True)
            (graphviz_bin / "dot").write_bytes(b"")

            with (
                patch.object(runtime.sys, "frozen", True, create=True),
                patch.object(runtime.sys, "executable", str(executable)),
                patch.object(runtime.sys, "_MEIPASS", str(bundle), create=True),
            ):
                found = runtime.find_bundled_graphviz(environ={})

            self.assertEqual(found, graphviz_bin.resolve())

    def test_configure_graphviz_only_changes_given_process_environment(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app_dir = Path(tmp)
            graphviz_bin = app_dir / "graphviz" / "bin"
            graphviz_bin.mkdir(parents=True)
            (graphviz_bin / "dot").write_bytes(b"")
            environment = {"PATH": os.pathsep.join(("/system/bin", "/other/bin"))}

            first = runtime.configure_bundled_graphviz(
                app_dir=app_dir,
                environ=environment,
            )
            second = runtime.configure_bundled_graphviz(
                app_dir=app_dir,
                environ=environment,
            )

            self.assertEqual(first, graphviz_bin.resolve())
            self.assertEqual(second, graphviz_bin.resolve())
            self.assertEqual(
                environment["PATH"].split(os.pathsep).count(str(graphviz_bin.resolve())),
                1,
            )

    def test_configure_graphviz_sets_linux_plugin_and_library_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app_dir = Path(tmp)
            root = app_dir / "graphviz"
            graphviz_bin = root / "bin"
            graphviz_bin.mkdir(parents=True)
            (graphviz_bin / "dot").write_bytes(b"")
            library_dir = root / "lib" / "x86_64-linux-gnu"
            plugin_dir = library_dir / "graphviz"
            plugin_dir.mkdir(parents=True)
            (library_dir / "libgvc.so.6").write_bytes(b"")
            (plugin_dir / "config6a").write_text("plugins", encoding="utf-8")
            (plugin_dir / "libgvplugin_core.so.6").write_bytes(b"")
            environment = {"PATH": "/system/bin"}

            with patch.object(runtime.sys, "platform", "linux"):
                runtime.configure_bundled_graphviz(
                    app_dir=app_dir,
                    environ=environment,
                )

            self.assertEqual(environment["GVBINDIR"], str(plugin_dir.resolve()))
            self.assertIn(
                str(library_dir.resolve()),
                environment["LD_LIBRARY_PATH"].split(os.pathsep),
            )

    def test_configure_graphviz_keeps_explicit_plugin_environment(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app_dir = Path(tmp)
            graphviz_bin = app_dir / "graphviz" / "bin"
            graphviz_bin.mkdir(parents=True)
            (graphviz_bin / "dot").write_bytes(b"")
            (graphviz_bin / "config6").write_text("plugins", encoding="utf-8")
            environment = {
                "PATH": "/system/bin",
                "GVBINDIR": "/custom/plugins",
                "LD_LIBRARY_PATH": "/custom/libs",
            }

            with patch.object(runtime.sys, "platform", "linux"):
                runtime.configure_bundled_graphviz(
                    app_dir=app_dir,
                    environ=environment,
                )

            self.assertEqual(environment["GVBINDIR"], "/custom/plugins")
            self.assertEqual(environment["LD_LIBRARY_PATH"], "/custom/libs")

    def test_system_graphviz_restores_bootloader_library_path_temporarily(self) -> None:
        environment = {
            "LD_LIBRARY_PATH": "/app/_internal:/custom/current",
            "LD_LIBRARY_PATH_ORIG": "/host/original",
        }

        with (
            patch.object(runtime, "is_frozen", return_value=True),
            patch.object(runtime.sys, "platform", "linux"),
            runtime.graphviz_subprocess_environment(None, environment),
        ):
            self.assertEqual(environment["LD_LIBRARY_PATH"], "/host/original")

        self.assertEqual(
            environment["LD_LIBRARY_PATH"],
            "/app/_internal:/custom/current",
        )

    def test_system_graphviz_unsets_bootloader_path_without_original(self) -> None:
        environment = {"LD_LIBRARY_PATH": "/app/_internal"}

        with (
            patch.object(runtime, "is_frozen", return_value=True),
            patch.object(runtime.sys, "platform", "linux"),
            runtime.graphviz_subprocess_environment(None, environment),
        ):
            self.assertNotIn("LD_LIBRARY_PATH", environment)

        self.assertEqual(environment["LD_LIBRARY_PATH"], "/app/_internal")

    def test_bundled_graphviz_uses_own_libraries_without_meipass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "graphviz"
            graphviz_bin = root / "bin"
            graphviz_bin.mkdir(parents=True)
            (graphviz_bin / "dot").write_bytes(b"")
            library_dir = root / "lib"
            plugin_dir = library_dir / "graphviz"
            plugin_dir.mkdir(parents=True)
            (library_dir / "libgvc.so.8").write_bytes(b"")
            (plugin_dir / "config8").write_text("plugins", encoding="utf-8")
            (plugin_dir / "libgvplugin_core.so.8").write_bytes(b"")
            environment = {
                "LD_LIBRARY_PATH": "/app/_internal",
                "LD_LIBRARY_PATH_ORIG": "/host/original",
            }

            with (
                patch.object(runtime, "is_frozen", return_value=True),
                patch.object(runtime.sys, "platform", "linux"),
                runtime.graphviz_subprocess_environment(graphviz_bin, environment),
            ):
                entries = environment["LD_LIBRARY_PATH"].split(os.pathsep)
                self.assertIn(str(library_dir.resolve()), entries)
                self.assertIn(str(plugin_dir.resolve()), entries)
                self.assertIn("/host/original", entries)
                self.assertNotIn("/app/_internal", entries)

            self.assertEqual(environment["LD_LIBRARY_PATH"], "/app/_internal")

    def test_portable_environment_uses_local_data_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app_dir = Path(tmp)
            result = runtime.application_data_dir(
                environ={"WIREWIZARD_PORTABLE": "1"},
                app_dir=app_dir,
            )
            self.assertEqual(result, (app_dir / "data").resolve())

    def test_frozen_portable_marker_uses_local_data_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app_dir = Path(tmp)
            (app_dir / "portable.flag").write_text("", encoding="utf-8")
            with patch.object(runtime.sys, "frozen", True, create=True):
                result = runtime.application_data_dir(environ={}, app_dir=app_dir)
            self.assertEqual(result, (app_dir / "data").resolve())

    def test_nonportable_linux_uses_user_state_directory(self) -> None:
        with (
            patch.object(runtime.os, "name", "posix"),
            patch.object(runtime.sys, "platform", "linux"),
            patch.object(runtime, "Path", PurePosixPath),
        ):
            result = runtime.application_data_dir(
                environ={"XDG_STATE_HOME": "/state"},
                app_dir="/opt/wirewizardgui",
            )
        self.assertEqual(result, PurePosixPath("/state") / "wirewizardgui")

    def test_logging_and_exception_hook_work_without_console(self) -> None:
        logger = logging.getLogger("wirewizard_gui")
        with tempfile.TemporaryDirectory() as tmp:
            try:
                log_path = runtime.configure_logging(tmp)
                reporter = Mock()
                with patch.object(runtime, "is_frozen", return_value=True):
                    runtime.install_exception_handler(reporter)
                    try:
                        raise ValueError("boom")
                    except ValueError:
                        exc_type, exc_value, traceback = sys.exc_info()
                        assert exc_type is not None
                        assert exc_value is not None
                        sys.excepthook(exc_type, exc_value, traceback)

                for handler in logger.handlers:
                    handler.flush()
                log_text = log_path.read_text(encoding="utf-8")

                self.assertIn("Unhandled exception", log_text)
                self.assertIn("ValueError: boom", log_text)
                reporter.assert_called_once()
                self.assertIn(str(log_path), reporter.call_args.args[1])
            finally:
                # Windows does not allow TemporaryDirectory to remove an open
                # RotatingFileHandler target. Close it before leaving the
                # temporary directory instead of waiting for tearDown().
                for handler in list(logger.handlers):
                    if getattr(handler, runtime._HANDLER_MARKER, False):
                        logger.removeHandler(handler)
                        handler.close()

if __name__ == "__main__":
    unittest.main()
