"""Runtime helpers for installed and portable application builds.

This module intentionally has no Qt or WireViz imports. It can therefore set
up logging and the bundled Graphviz path before either dependency is loaded.
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import sys
import tempfile
import threading
from contextlib import contextmanager
from collections.abc import Iterator
from typing import Callable, MutableMapping

from wirewizard_gui.metadata import APP_ID, APP_NAME, APP_VERSION


GRAPHVIZ_DIR_ENV = "WIREWIZARD_GRAPHVIZ_DIR"
DATA_DIR_ENV = "WIREWIZARD_DATA_DIR"
PORTABLE_ENV = "WIREWIZARD_PORTABLE"
PORTABLE_MARKER = "portable.flag"

_LOGGER_NAME = "wirewizard_gui"
_HANDLER_MARKER = "_wirewizard_file_handler"
_ORIGINAL_SYS_EXCEPTHOOK = sys.excepthook
_ORIGINAL_THREADING_EXCEPTHOOK = threading.excepthook
_log_path: Path | None = None

ErrorReporter = Callable[[str, str], None]


def is_frozen() -> bool:
    """Return whether Python is running from a freezer such as PyInstaller."""

    return bool(getattr(sys, "frozen", False))


def application_dir() -> Path:
    """Return the directory containing the executable (or source checkout)."""

    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def _contains_dot(directory: Path) -> bool:
    return any((directory / executable).is_file() for executable in ("dot", "dot.exe"))


def _unique_paths(paths: list[Path]) -> list[Path]:
    result: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        key = os.path.normcase(str(path.resolve(strict=False)))
        if key not in seen:
            seen.add(key)
            result.append(path)
    return result


def _graphviz_dirs_for_root(root: Path) -> list[Path]:
    """Return supported portable/installer Graphviz layouts for one root."""

    return [
        root / "graphviz" / "bin",
        root / "Graphviz" / "bin",
        root / "_internal" / "graphviz" / "bin",
        root / "_internal" / "Graphviz" / "bin",
        root / "lib" / APP_ID / "graphviz" / "bin",
        root / "usr" / "lib" / APP_ID / "graphviz" / "bin",
        # AppImage and conventional Linux layouts commonly put the executable
        # in usr/bin and private application files in usr/lib/<app-id>.
        root.parent / "lib" / APP_ID / "graphviz" / "bin",
    ]


def find_bundled_graphviz(
    app_dir: str | Path | None = None,
    bundle_dir: str | Path | None = None,
    environ: MutableMapping[str, str] | None = None,
) -> Path | None:
    """Find a bundled Graphviz bin directory without changing the system.

    Automatic relative-path discovery is enabled for frozen applications. The
    optional directories are primarily useful to packaging probes and tests.
    WIREWIZARD_GRAPHVIZ_DIR may point either to Graphviz itself or its bin
    directory.
    """

    environment = os.environ if environ is None else environ
    override = environment.get(GRAPHVIZ_DIR_ENV)
    if override:
        hint = Path(override).expanduser()
        for directory in _unique_paths([hint, hint / "bin"]):
            if _contains_dot(directory):
                return directory.resolve(strict=False)

    explicit_roots = app_dir is not None or bundle_dir is not None
    if not explicit_roots and not is_frozen():
        return None

    roots: list[Path] = []
    if app_dir is not None:
        roots.append(Path(app_dir))
    else:
        roots.append(application_dir())

    if bundle_dir is not None:
        roots.append(Path(bundle_dir))
    elif is_frozen():
        pyinstaller_bundle = getattr(sys, "_MEIPASS", None)
        if pyinstaller_bundle:
            roots.append(Path(pyinstaller_bundle))

    candidates: list[Path] = []
    for root in _unique_paths(roots):
        candidates.extend(_graphviz_dirs_for_root(root))

    for directory in _unique_paths(candidates):
        if _contains_dot(directory):
            return directory.resolve(strict=False)
    return None


def _normalized_path_entry(value: str) -> str:
    return os.path.normcase(str(Path(value).resolve(strict=False)))


def _has_graphviz_config(directory: Path) -> bool:
    return directory.is_dir() and any(directory.glob("config[0-9]*"))


def _find_graphviz_plugin_dir(graphviz_bin: Path) -> Path | None:
    root = graphviz_bin.parent
    lib = root / "lib"
    lib64 = root / "lib64"
    candidates = [
        *sorted(lib.glob("*/graphviz")),
        *sorted(lib64.glob("*/graphviz")),
        lib / "graphviz",
        lib64 / "graphviz",
        graphviz_bin,
    ]
    for directory in _unique_paths(candidates):
        if _has_graphviz_config(directory):
            return directory.resolve(strict=False)
    return None


def _graphviz_linux_library_dirs(
    graphviz_bin: Path,
    plugin_dir: Path | None,
) -> list[Path]:
    root = graphviz_bin.parent
    lib = root / "lib"
    lib64 = root / "lib64"
    candidates = [
        lib,
        lib64,
        *sorted(path for path in lib.glob("*") if path.is_dir()),
        *sorted(path for path in lib64.glob("*") if path.is_dir()),
    ]
    if plugin_dir is not None:
        candidates.append(plugin_dir)
    return [
        directory.resolve(strict=False)
        for directory in _unique_paths(candidates)
        if directory.is_dir() and any(directory.glob("*.so*"))
    ]


def configure_bundled_graphviz(
    app_dir: str | Path | None = None,
    bundle_dir: str | Path | None = None,
    environ: MutableMapping[str, str] | None = None,
) -> Path | None:
    """Prepend bundled Graphviz to this process' PATH and return its path.

    No registry, shell profile, or machine/user environment settings are
    changed. Child processes (including Graphviz itself) inherit only this
    process-local environment.
    """

    environment = os.environ if environ is None else environ
    graphviz_bin = find_bundled_graphviz(app_dir, bundle_dir, environment)
    if graphviz_bin is None:
        return None

    current_path = environment.get("PATH", "")
    current_entries = [entry for entry in current_path.split(os.pathsep) if entry]
    normalized_graphviz = _normalized_path_entry(str(graphviz_bin))
    if normalized_graphviz not in {
        _normalized_path_entry(entry) for entry in current_entries
    }:
        environment["PATH"] = (
            str(graphviz_bin) + (os.pathsep + current_path if current_path else "")
        )

    plugin_dir = _find_graphviz_plugin_dir(graphviz_bin)
    if plugin_dir is not None and "GVBINDIR" not in environment:
        environment["GVBINDIR"] = str(plugin_dir)

    if sys.platform.startswith("linux") and "LD_LIBRARY_PATH" not in environment:
        library_dirs = _graphviz_linux_library_dirs(graphviz_bin, plugin_dir)
        if library_dirs:
            environment["LD_LIBRARY_PATH"] = os.pathsep.join(
                str(directory) for directory in library_dirs
            )

    logging.getLogger(_LOGGER_NAME).info("Using bundled Graphviz: %s", graphviz_bin)
    if plugin_dir is not None:
        logging.getLogger(_LOGGER_NAME).info(
            "Using bundled Graphviz plugins: %s",
            plugin_dir,
        )
    return graphviz_bin


@contextmanager
def graphviz_subprocess_environment(
    graphviz_bin: str | Path | None,
    environ: MutableMapping[str, str] | None = None,
) -> Iterator[None]:
    """Give Graphviz a clean Linux library path inside a frozen application.

    PyInstaller prepends its private directory to LD_LIBRARY_PATH. That is
    correct for Python extensions but can break a system ``dot`` subprocess.
    WireViz launches Graphviz synchronously, so temporarily restoring the
    bootloader's original value is safe here. A bundled Graphviz receives its
    own library directories before that original host path.
    """

    environment = os.environ if environ is None else environ
    if not (is_frozen() and sys.platform.startswith("linux")):
        yield
        return

    key = "LD_LIBRARY_PATH"
    previous_present = key in environment
    previous_value = environment.get(key, "")
    original_value = environment.get(f"{key}_ORIG")

    entries: list[str] = []
    if graphviz_bin is not None:
        graphviz_bin_path = Path(graphviz_bin)
        plugin_dir = _find_graphviz_plugin_dir(graphviz_bin_path)
        entries.extend(
            str(path)
            for path in _graphviz_linux_library_dirs(
                graphviz_bin_path,
                plugin_dir,
            )
        )
    if original_value:
        entries.extend(entry for entry in original_value.split(os.pathsep) if entry)

    unique_entries: list[str] = []
    seen: set[str] = set()
    for entry in entries:
        normalized = _normalized_path_entry(entry)
        if normalized not in seen:
            seen.add(normalized)
            unique_entries.append(entry)

    if unique_entries:
        environment[key] = os.pathsep.join(unique_entries)
    else:
        environment.pop(key, None)

    try:
        yield
    finally:
        if previous_present:
            environment[key] = previous_value
        else:
            environment.pop(key, None)


def _portable_requested(environment: MutableMapping[str, str], app_dir: Path) -> bool:
    value = environment.get(PORTABLE_ENV, "").strip().lower()
    return value in {"1", "true", "yes", "on"} or (
        is_frozen() and (app_dir / PORTABLE_MARKER).is_file()
    )


def application_data_dir(
    environ: MutableMapping[str, str] | None = None,
    app_dir: str | Path | None = None,
) -> Path:
    """Return a per-user data directory, or local data in portable mode."""

    environment = os.environ if environ is None else environ
    override = environment.get(DATA_DIR_ENV)
    if override:
        return Path(override).expanduser().resolve(strict=False)

    executable_dir = Path(app_dir) if app_dir is not None else application_dir()
    if _portable_requested(environment, executable_dir):
        return (executable_dir / "data").resolve(strict=False)

    if os.name == "nt":
        base = environment.get("LOCALAPPDATA")
        if base:
            return Path(base) / APP_NAME
        return Path.home() / "AppData" / "Local" / APP_NAME

    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME

    state_home = environment.get("XDG_STATE_HOME")
    if state_home:
        return Path(state_home) / APP_ID
    return Path.home() / ".local" / "state" / APP_ID


def configure_logging(log_dir: str | Path | None = None) -> Path:
    """Configure a bounded UTF-8 log file and return its absolute path."""

    global _log_path

    requested_dir = (
        Path(log_dir) if log_dir is not None else application_data_dir() / "logs"
    )
    try:
        requested_dir.mkdir(parents=True, exist_ok=True)
        target = requested_dir / f"{APP_ID}.log"
        handler = RotatingFileHandler(
            target,
            maxBytes=1_000_000,
            backupCount=3,
            encoding="utf-8",
        )
    except OSError:
        fallback_dir = Path(tempfile.gettempdir()) / APP_ID / "logs"
        fallback_dir.mkdir(parents=True, exist_ok=True)
        target = fallback_dir / f"{APP_ID}.log"
        handler = RotatingFileHandler(
            target,
            maxBytes=1_000_000,
            backupCount=3,
            encoding="utf-8",
        )

    setattr(handler, _HANDLER_MARKER, True)
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )

    logger = logging.getLogger(_LOGGER_NAME)
    for old_handler in list(logger.handlers):
        if getattr(old_handler, _HANDLER_MARKER, False):
            logger.removeHandler(old_handler)
            old_handler.close()
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    _log_path = target.resolve(strict=False)
    logger.info(
        "%s %s starting (Python %s, frozen=%s)",
        APP_NAME,
        APP_VERSION,
        sys.version.split()[0],
        is_frozen(),
    )
    return _log_path


def current_log_path() -> Path | None:
    """Return the active log path, if logging has been configured."""

    return _log_path


def _report_unhandled_exception(
    exc_type: type[BaseException],
    exc_value: BaseException,
    traceback: object,
    reporter: ErrorReporter | None,
) -> None:
    logger = logging.getLogger(_LOGGER_NAME)
    logger.critical(
        "Unhandled exception",
        exc_info=(exc_type, exc_value, traceback),
    )

    if reporter is None:
        return

    location = current_log_path()
    log_note = f"\n\nПодробности записаны в журнал:\n{location}" if location else ""
    message = f"Произошла необработанная ошибка:\n{exc_type.__name__}: {exc_value}{log_note}"
    try:
        reporter(f"{APP_NAME}: ошибка", message)
    except Exception:
        logger.exception("The GUI exception reporter failed")


def install_exception_handler(reporter: ErrorReporter | None = None) -> None:
    """Install process-wide hooks that log otherwise invisible exceptions."""

    def sys_hook(
        exc_type: type[BaseException],
        exc_value: BaseException,
        traceback: object,
    ) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            _ORIGINAL_SYS_EXCEPTHOOK(exc_type, exc_value, traceback)
            return
        _report_unhandled_exception(exc_type, exc_value, traceback, reporter)
        if not is_frozen() and sys.stderr is not None:
            _ORIGINAL_SYS_EXCEPTHOOK(exc_type, exc_value, traceback)

    def threading_hook(args: threading.ExceptHookArgs) -> None:
        _report_unhandled_exception(
            args.exc_type,
            args.exc_value,
            args.exc_traceback,
            None,
        )
        if not is_frozen() and sys.stderr is not None:
            _ORIGINAL_THREADING_EXCEPTHOOK(args)

    sys.excepthook = sys_hook
    threading.excepthook = threading_hook


__all__ = [
    "application_data_dir",
    "application_dir",
    "configure_bundled_graphviz",
    "configure_logging",
    "current_log_path",
    "find_bundled_graphviz",
    "graphviz_subprocess_environment",
    "install_exception_handler",
    "is_frozen",
]
