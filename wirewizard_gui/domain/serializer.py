from __future__ import annotations

from collections import OrderedDict
from typing import Any
import re

import yaml

from wirewizard_gui.domain.models import (
    CableModel,
    ConnectionRowModel,
    ConnectorModel,
    FerruleModel,
    ProjectModel,
)


class ProjectSerializer:
    @staticmethod
    def to_wireviz_dict(project: ProjectModel) -> dict:
        data: dict[str, Any] = OrderedDict()

        if project.title or project.description:
            metadata = OrderedDict()
            if project.title:
                metadata["title"] = project.title
            if project.description:
                metadata["description"] = project.description
            data["metadata"] = metadata

        connectors = OrderedDict()
        for item in project.connectors:
            entry = OrderedDict()
            entry["type"] = item.type
            if item.subtype:
                entry["subtype"] = item.subtype
            if item.simple:
                entry["style"] = "simple"
            else:
                entry["pincount"] = item.pincount
                if item.pins:
                    entry["pins"] = [ProjectSerializer._serialize_pin_token(v) for v in item.pins]
                if item.pinlabels:
                    entry["pinlabels"] = item.pinlabels
            if item.color:
                entry["color"] = item.color
            if item.notes:
                entry["notes"] = item.notes
            connectors[item.name] = entry

        for item in project.ferrules:
            entry = OrderedDict()
            entry["type"] = item.type
            if item.subtype:
                entry["subtype"] = item.subtype
            entry["style"] = "simple"
            if item.color:
                entry["color"] = item.color
            if item.notes:
                entry["notes"] = item.notes
            connectors[item.name] = entry

        if connectors:
            data["connectors"] = connectors

        cables = OrderedDict()
        for item in project.cables:
            entry = OrderedDict()
            entry["type"] = item.type
            entry["gauge"] = ProjectSerializer._serialize_gauge(item.gauge)
            entry["length"] = ProjectSerializer._serialize_length(item.length)
            entry["wirecount"] = item.wirecount
            if item.bundle:
                entry["category"] = "bundle"
            if item.color_code:
                entry["color_code"] = item.color_code
            if item.colors:
                entry["colors"] = item.colors
            if item.wirelabels:
                entry["wirelabels"] = item.wirelabels
            if item.shield:
                entry["shield"] = True
            if item.notes:
                entry["notes"] = item.notes
            cables[item.name] = entry

        if cables:
            data["cables"] = cables

        connection_sets: list[list[Any]] = []
        for row in project.connections:
            route = row.route.strip()
            if not route:
                continue
            parts = ProjectSerializer._split_route(route)
            items: list[Any] = []
            for part in parts:
                parsed = ProjectSerializer._parse_connection_part(part)
                if parsed is not None:
                    items.append(parsed)
            if items:
                connection_sets.append(items)

        if connection_sets:
            data["connections"] = connection_sets

        return data

    @staticmethod
    def to_wireviz_yaml(project: ProjectModel) -> str:
        data = ProjectSerializer.to_wireviz_dict(project)
        return yaml.safe_dump(ProjectSerializer._to_builtin(data), sort_keys=False, allow_unicode=True)

    @staticmethod
    def from_wireviz_yaml(text: str) -> ProjectModel:
        raw = yaml.safe_load(text) or {}
        if not isinstance(raw, dict):
            raise ValueError("Корневой элемент YAML должен быть объектом")
        return ProjectSerializer.from_wireviz_dict(raw)

    @staticmethod
    def from_wireviz_dict(data: dict[str, Any]) -> ProjectModel:
        metadata = data.get("metadata") or {}
        title = metadata.get("title", "Импортированный жгут") if isinstance(metadata, dict) else "Импортированный жгут"
        description = metadata.get("description", "") if isinstance(metadata, dict) else ""

        project = ProjectModel(title=title, description=description)

        connectors_data = data.get("connectors") or {}
        if not isinstance(connectors_data, dict):
            raise ValueError("Раздел 'connectors' должен быть объектом")

        for name, entry in connectors_data.items():
            entry = entry or {}
            if not isinstance(entry, dict):
                entry = {"type": str(entry)}
            is_simple = entry.get("style") == "simple"
            type_text = str(entry.get("type", "Универсальный разъём"))
            subtype = str(entry.get("subtype", "") or "")
            color = str(entry.get("color", "") or "")
            notes = str(entry.get("notes", "") or "")
            pins = ProjectSerializer._string_list(entry.get("pins"))
            pinlabels = ProjectSerializer._string_list(entry.get("pinlabels") or entry.get("pinout"))

            ferrule_type = type_text.lower()
            if is_simple and (
                str(name).upper().startswith("F")
                or "ferrule" in ferrule_type
                or "наконечник" in ferrule_type
            ):
                project.ferrules.append(
                    FerruleModel(
                        name=str(name),
                        type=type_text,
                        subtype=subtype or "0.5 mm²",
                        color=color,
                        notes=notes,
                    )
                )
            else:
                pincount = ProjectSerializer._guess_pincount(entry)
                project.connectors.append(
                    ConnectorModel(
                        name=str(name),
                        type=type_text,
                        subtype=subtype,
                        pincount=pincount,
                        pins=pins,
                        pinlabels=pinlabels,
                        notes=notes,
                        color=color,
                        simple=is_simple,
                    )
                )

        cables_data = data.get("cables") or {}
        if not isinstance(cables_data, dict):
            raise ValueError("Раздел 'cables' должен быть объектом")

        for name, entry in cables_data.items():
            entry = entry or {}
            if not isinstance(entry, dict):
                entry = {"type": str(entry)}
            colors = ProjectSerializer._string_list(entry.get("colors"))
            wirelabels = ProjectSerializer._string_list(entry.get("wirelabels"))
            wirecount = ProjectSerializer._guess_wirecount(entry, colors, wirelabels)
            project.cables.append(
                CableModel(
                    name=str(name),
                    type=str(entry.get("type", "Универсальный кабель")),
                    gauge=str(entry.get("gauge", "0.25 mm2")),
                    length=str(entry.get("length", "1 m")),
                    wirecount=wirecount,
                    colors=colors,
                    color_code=str(entry.get("color_code", "") or ""),
                    wirelabels=wirelabels,
                    shield=bool(entry.get("shield", False)),
                    bundle=str(entry.get("category", "")).lower() == "bundle",
                    notes=str(entry.get("notes", "") or ""),
                )
            )

        connections_data = data.get("connections") or []
        if not isinstance(connections_data, list):
            raise ValueError("Раздел 'connections' должен быть списком")
        for row in connections_data:
            if not isinstance(row, list):
                continue
            route_parts = [ProjectSerializer._format_connection_part(part) for part in row]
            route = " -> ".join(part for part in route_parts if part)
            if route:
                project.connections.append(ConnectionRowModel(route=route))

        return project

    @staticmethod
    def _format_connection_part(part: Any) -> str:
        if isinstance(part, dict) and part:
            name, value = next(iter(part.items()))
            return f"{name}:{ProjectSerializer._format_connection_value(value)}"
        if isinstance(part, list):
            return "[" + ", ".join(ProjectSerializer._format_connection_value(v) for v in part) + "]"
        return str(part)

    @staticmethod
    def _format_connection_value(value: Any) -> str:
        if isinstance(value, list):
            return "[" + ", ".join(ProjectSerializer._format_connection_value(v) for v in value) + "]"
        if isinstance(value, bool):
            return "true" if value else "false"
        return str(value)

    @staticmethod
    def _guess_pincount(entry: dict[str, Any]) -> int:
        explicit = ProjectSerializer._safe_int(entry.get("pincount"), None)
        if explicit is not None and explicit > 0:
            return explicit
        pins = entry.get("pins")
        if isinstance(pins, list) and pins:
            return len(pins)
        pinlabels = entry.get("pinlabels") or entry.get("pinout")
        if isinstance(pinlabels, list) and pinlabels:
            return len(pinlabels)
        return 1

    @staticmethod
    def _guess_wirecount(entry: dict[str, Any], colors: list[str], wirelabels: list[str]) -> int:
        explicit = ProjectSerializer._safe_int(entry.get("wirecount"), None)
        candidates = [1]
        if explicit is not None and explicit > 0:
            candidates.append(explicit)
        if colors:
            candidates.append(len(colors))
        if wirelabels:
            candidates.append(len(wirelabels))
        return max(candidates)

    @staticmethod
    def _string_list(value: Any) -> list[str]:
        if isinstance(value, list):
            return [str(v) for v in value if str(v).strip()]
        return []

    @staticmethod
    def _safe_int(value: Any, default: int | None = 0) -> int | None:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _expand_range_token(token: str) -> list[int] | None:
        token = token.strip()
        m = re.fullmatch(r"(\d+)\s*-\s*(\d+)", token)
        if not m:
            return None
        a, b = int(m.group(1)), int(m.group(2))
        step = 1 if b >= a else -1
        return list(range(a, b + step, step))

    @staticmethod
    def _parse_scalar_token(raw: str):
        raw = raw.strip()
        if raw == "s":
            return "s"
        rng = ProjectSerializer._expand_range_token(raw)
        if rng is not None:
            return raw.replace(" ", "")
        if raw.isdigit():
            return int(raw)
        return raw

    @staticmethod
    def _parse_value(raw: str):
        raw = raw.strip()
        if raw == "s":
            return "s"
        if raw.startswith("[") and raw.endswith("]"):
            inner = raw[1:-1].strip()
            if not inner:
                return []
            return [ProjectSerializer._parse_scalar_token(token) for token in ProjectSerializer._split_csv(inner)]
        return ProjectSerializer._parse_scalar_token(raw)

    @staticmethod
    def _parse_connection_part(part: str):
        text = part.strip()
        if not text:
            return None
        if text.startswith("[") and text.endswith("]"):
            inner = text[1:-1].strip()
            if not inner:
                return []
            return [ProjectSerializer._parse_scalar_token(token) for token in ProjectSerializer._split_csv(inner)]
        if ":" in text:
            name, value = text.split(":", 1)
            return {name.strip(): ProjectSerializer._parse_value(value.strip())}
        return text

    @staticmethod
    def _split_csv(text: str) -> list[str]:
        items: list[str] = []
        current: list[str] = []
        depth = 0
        for ch in text:
            if ch == "[":
                depth += 1
            elif ch == "]" and depth > 0:
                depth -= 1
            if ch == "," and depth == 0:
                token = "".join(current).strip()
                if token:
                    items.append(token)
                current = []
                continue
            current.append(ch)
        token = "".join(current).strip()
        if token:
            items.append(token)
        return items

    @staticmethod
    def _is_arrow(value: str) -> bool:
        return bool(re.fullmatch(r"<?(?:-+|=+)>?", str(value).strip()))

    @staticmethod
    def _split_route(route: str) -> list[str]:
        parts: list[str] = []
        current: list[str] = []
        depth = 0
        idx = 0
        arrow_with_separators = re.compile(
            r"->\s*(<?(?:-+|=+)>?)\s*->"
        )

        while idx < len(route):
            ch = route[idx]
            if ch == "[":
                depth += 1
            elif ch == "]" and depth > 0:
                depth -= 1

            if depth == 0:
                arrow_match = arrow_with_separators.match(route, idx)
                if arrow_match is not None:
                    token = "".join(current).strip()
                    if token:
                        parts.append(token)
                    parts.append(arrow_match.group(1))
                    current = []
                    idx = arrow_match.end()
                    continue

                is_separator = route.startswith("->", idx)
                belongs_to_longer_arrow = idx > 0 and route[idx - 1] in "-<"
                if is_separator and not belongs_to_longer_arrow:
                    token = "".join(current).strip()
                    if token:
                        parts.append(token)
                    current = []
                    idx += 2
                    continue

            current.append(ch)
            idx += 1

        token = "".join(current).strip()
        if token:
            parts.append(token)
        return parts

    @staticmethod
    def _serialize_length(length: str | int | float):
        if isinstance(length, (int, float)):
            return length
        text = str(length).strip()
        if re.fullmatch(r"\d+(\.\d+)?", text):
            return float(text) if "." in text else int(text)
        return text

    @staticmethod
    def _serialize_gauge(gauge: str | int | float):
        if isinstance(gauge, (int, float)):
            return f"{gauge} mm2"
        text = str(gauge).strip()
        if re.fullmatch(r"\d+(\.\d+)?", text):
            return f"{text} mm2"
        return text

    @staticmethod
    def _serialize_pin_token(value: Any):
        text = str(value).strip()
        if text.isdigit():
            return int(text)
        return text

    @staticmethod
    def _to_builtin(value):
        if isinstance(value, OrderedDict):
            return {k: ProjectSerializer._to_builtin(v) for k, v in value.items()}
        if isinstance(value, dict):
            return {k: ProjectSerializer._to_builtin(v) for k, v in value.items()}
        if isinstance(value, list):
            return [ProjectSerializer._to_builtin(v) for v in value]
        return value
