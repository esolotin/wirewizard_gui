from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
from typing import Any, Callable
from uuid import NAMESPACE_URL, uuid5


CURRENT_SCHEMA_VERSION = 4


class ProjectFormatError(ValueError):
    """Raised when a native project uses an unsupported JSON schema."""


def _migrate_v0_to_v1(data: dict[str, Any]) -> dict[str, Any]:
    data["schema_version"] = 1
    return data


def _migrate_v1_to_v2(data: dict[str, Any]) -> dict[str, Any]:
    from wirewizard_gui.domain.connections import ConnectionRowModel

    component_ids: dict[str, str] = {}
    for group in ("connectors", "cables", "ferrules"):
        entries = data.get(group, [])
        if not isinstance(entries, list):
            continue
        for index, item in enumerate(entries):
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", ""))
            component_id = uuid5(
                NAMESPACE_URL, f"wirewizard-gui:{group}:{index}:{name}"
            ).hex
            item["id"] = component_id
            component_ids.setdefault(name, component_id)

    migrated_connections: list[dict[str, Any]] = []
    for item in data.get("connections", []) or []:
        if not isinstance(item, dict):
            continue
        row = ConnectionRowModel(route=str(item.get("route", "")))
        for step in row.steps:
            _assign_step_ids(step, component_ids)
        migrated_connections.append(asdict(row))
    data["connections"] = migrated_connections
    data["schema_version"] = 2
    return data


def _migrate_v2_to_v3(data: dict[str, Any]) -> dict[str, Any]:
    data["schema_version"] = 3
    return data


def _migrate_v3_to_v4(data: dict[str, Any]) -> dict[str, Any]:
    data.setdefault("wireviz_extras", {})
    data.setdefault("wireviz_metadata_extras", {})
    for group in ("connectors", "cables", "ferrules"):
        for item in data.get(group, []) or []:
            if isinstance(item, dict):
                item.setdefault("wireviz_extras", {})
    data["schema_version"] = 4
    return data


def _assign_step_ids(step, component_ids: dict[str, str]) -> None:
    if step.kind == "component":
        step.component_id = component_ids.get(step.component.split(".", 1)[0])
    for item in step.items:
        _assign_step_ids(item, component_ids)


_MIGRATIONS: dict[int, Callable[[dict[str, Any]], dict[str, Any]]] = {
    0: _migrate_v0_to_v1,
    1: _migrate_v1_to_v2,
    2: _migrate_v2_to_v3,
    3: _migrate_v3_to_v4,
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
