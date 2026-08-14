from __future__ import annotations

from collections.abc import Callable
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import logging
from pathlib import Path
from typing import Any

from wirewizard_gui.domain.models import ProjectModel
from wirewizard_gui.domain.serializer import ProjectSerializer
from wirewizard_gui.metadata import WIREVIZ_VERSION
from wirewizard_gui.runtime import (
    configure_bundled_graphviz,
    graphviz_subprocess_environment,
)


logger = logging.getLogger(__name__)

WireVizParse = Callable[..., Any]
DEFAULT_OUTPUT_FORMATS = ("html", "png", "svg", "tsv")


class WireVizDependencyError(RuntimeError):
    """Raised when the bundled WireViz runtime cannot be loaded."""


def _import_wireviz_modules() -> tuple[Any, Any]:
    # Imports stay inside this function so Graphviz can be configured first,
    # while remaining visible to static bundlers such as PyInstaller.
    import wireviz
    from wireviz import wireviz as wireviz_api

    return wireviz, wireviz_api


def _load_wireviz_parse() -> WireVizParse:
    """Load the pinned WireViz API lazily, after Graphviz setup."""

    try:
        package, module = _import_wireviz_modules()
    except ModuleNotFoundError as exc:
        missing = exc.name or "unknown"
        raise WireVizDependencyError(
            f"WireViz {WIREVIZ_VERSION} не удалось загрузить: "
            f"отсутствует Python-модуль '{missing}'."
        ) from exc
    except Exception as exc:
        raise WireVizDependencyError(
            f"WireViz {WIREVIZ_VERSION} не удалось загрузить: {exc}"
        ) from exc

    installed_version = getattr(package, "__version__", None)
    if installed_version and installed_version != WIREVIZ_VERSION:
        logger.warning(
            "WireViz version %s is installed; the application was tested with %s",
            installed_version,
            WIREVIZ_VERSION,
        )

    parse = getattr(module, "parse", None)
    if not callable(parse):
        raise WireVizDependencyError(
            f"WireViz {WIREVIZ_VERSION} не содержит ожидаемый Python API parse()."
        )
    return parse


def _call_wireviz(parse: WireVizParse, *args: Any, **kwargs: Any) -> Any:
    """Call WireViz safely when a windowed executable has no stdio streams."""

    stdout = StringIO()
    stderr = StringIO()
    try:
        with redirect_stdout(stdout), redirect_stderr(stderr):
            return parse(*args, **kwargs)
    finally:
        stdout_text = stdout.getvalue().strip()
        stderr_text = stderr.getvalue().strip()
        if stdout_text:
            logger.warning("WireViz output: %s", stdout_text)
        if stderr_text:
            logger.warning("WireViz error output: %s", stderr_text)


def _format_wireviz_error(exc: Exception) -> str:
    if isinstance(exc, WireVizDependencyError):
        return str(exc)

    class_name = type(exc).__name__
    details = str(exc).strip() or class_name
    details_lower = details.lower()
    if class_name == "ExecutableNotFound" or (
        "failed to execute" in details_lower and "dot" in details_lower
    ):
        return (
            "Graphviz (dot) не найден или не запускается. "
            "Проверь комплект поставки приложения."
        )
    return f"WireViz не смог построить схему: {details}"


def _validate_base_name(base_name: str) -> str:
    value = str(base_name).strip()
    if not value or value in {".", ".."} or Path(value).name != value:
        raise ValueError("Имя выходного файла должно быть простым именем без пути.")
    return value


class WireVizService:
    @staticmethod
    def render_svg(project: ProjectModel) -> tuple[bool, str, str | None]:
        try:
            graphviz_bin = configure_bundled_graphviz()
            parse = _load_wireviz_parse()
            yaml_text = ProjectSerializer.to_wireviz_yaml(project)
            with graphviz_subprocess_environment(graphviz_bin):
                svg = _call_wireviz(
                    parse,
                    yaml_text,
                    return_types="svg",
                    output_name="preview",
                )
            if isinstance(svg, bytes):
                svg = svg.decode("utf-8")
            if not isinstance(svg, str) or not svg.strip():
                raise RuntimeError("WireViz вернул пустой или некорректный SVG.")
            return True, "OK", svg
        except Exception as exc:
            logger.exception("WireViz preview rendering failed")
            return False, _format_wireviz_error(exc), None

    @staticmethod
    def run_full(
        project: ProjectModel,
        output_dir: str | Path,
        base_name: str = "harness",
    ) -> tuple[bool, str, list[str]]:
        try:
            output_name = _validate_base_name(base_name)
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            yaml_path = output_path / f"{output_name}.yml"
            yaml_path.write_text(
                ProjectSerializer.to_wireviz_yaml(project),
                encoding="utf-8",
            )

            graphviz_bin = configure_bundled_graphviz()
            parse = _load_wireviz_parse()
            with graphviz_subprocess_environment(graphviz_bin):
                _call_wireviz(
                    parse,
                    yaml_path,
                    output_formats=DEFAULT_OUTPUT_FORMATS,
                    output_dir=output_path,
                    output_name=output_name,
                )

            generated = sorted(
                path.name
                for path in output_path.iterdir()
                if path.is_file()
                and path.name.startswith(f"{output_name}.")
                and path.name != yaml_path.name
            )
            message = (
                "WireViz выполнен успешно. Созданы файлы: " + ", ".join(generated)
                if generated
                else "WireViz выполнен успешно."
            )
            return True, message, generated
        except Exception as exc:
            logger.exception("WireViz full export failed")
            return False, _format_wireviz_error(exc), []


__all__ = ["WireVizService"]
