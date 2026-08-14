from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable


CURRENT_SCHEMA_VERSION = 1


class ProjectFormatError(ValueError):
    """Raised when a native project uses an unsupported JSON schema."""


def _migrate_v0_to_v1(data: dict[str, Any]) -> dict[str, Any]:
    data["schema_version"] = 1
    return data


_MIGRATIONS: dict[int, Callable[[dict[str, Any]], dict[str, Any]]] = {
    0: _migrate_v0_to_v1,
}


def migrate_project_data(data: object) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ProjectFormatError("JSON-проект должен быть объектом.")

    raw_version = data.get("schema_version", 0)
    if isinstance(raw_version, bool) or not isinstance(raw_version, int):
        raise ProjectFormatError("schema_version должен быть целым числом.")
    if raw_version < 0:
        raise ProjectFormatError("schema_version не может быть отрицательным.")
    if raw_version > CURRENT_SCHEMA_VERSION:
        raise ProjectFormatError(
            "Проект создан более новой версией WireWizardGUI "
            f"(schema_version={raw_version}, поддерживается до "
            f"{CURRENT_SCHEMA_VERSION})."
        )

    migrated = deepcopy(data)
    version = raw_version
    while version < CURRENT_SCHEMA_VERSION:
        migration = _MIGRATIONS.get(version)
        if migration is None:
            raise ProjectFormatError(
                f"Нет миграции JSON-проекта с версии {version}."
            )
        migrated = migration(migrated)
        version = migrated["schema_version"]
    return migrated
