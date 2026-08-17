from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from wirewizard_gui.domain.models import ProjectModel
from wirewizard_gui.domain.references import ProjectReferences
from wirewizard_gui.domain.serializer import ProjectSerializer


class IssueSeverity(str, Enum):
    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True)
class ValidationIssue:
    severity: IssueSeverity
    message: str
    component_name: str | None = None
    row_index: int | None = None


class ProjectValidator:
    @staticmethod
    def validate_issues(project: ProjectModel) -> list[ValidationIssue]:
        component_names = [
            item.name
            for item in [*project.connectors, *project.cables, *project.ferrules]
        ]
        issues = [
            ValidationIssue(
                severity=IssueSeverity.ERROR,
                message=message,
                component_name=ProjectValidator._message_component(
                    message, component_names
                ),
                row_index=ProjectValidator._message_row_index(message),
            )
            for message in ProjectValidator.validate(project)
        ]

        for name in component_names:
            if not ProjectReferences.dependent_rows(project, name):
                issues.append(
                    ValidationIssue(
                        severity=IssueSeverity.WARNING,
                        message=f"Компонент {name} не используется ни в одном соединении",
                        component_name=name,
                    )
                )
        return issues

    @staticmethod
    def validate(project: ProjectModel) -> list[str]:
        errors: list[str] = []
        names: list[str] = []
        names.extend(item.name for item in project.connectors)
        names.extend(item.name for item in project.cables)
        names.extend(item.name for item in project.ferrules)

        duplicates = {name for name in names if names.count(name) > 1}
        if duplicates:
            errors.append(f"Повторяющиеся обозначения: {', '.join(sorted(duplicates))}")

        component_names = set(names)
        connector_names = {item.name for item in project.connectors}
        connector_names.update(item.name for item in project.ferrules)
        cable_map = {item.name: item for item in project.cables}
        connector_map = {item.name: item for item in project.connectors}
        ferrule_names = {item.name for item in project.ferrules}
        simple_template_names = {item.name for item in project.connectors if item.simple} | ferrule_names
        pin_limits = {item.name: max(item.pincount, 1) for item in project.connectors}

        for item in project.connectors:
            if not item.simple and item.pincount < 1:
                errors.append(f"Разъём {item.name}: количество контактов должно быть не меньше 1")

        for item in project.cables:
            if item.wirecount < 1:
                errors.append(f"Кабель {item.name}: количество жил должно быть не меньше 1")

        for idx, row in enumerate(project.connections, start=1):
            route = row.route.strip()
            if not route:
                continue
            parts = [ProjectSerializer._parse_connection_part(part) for part in ProjectSerializer._split_route(route)]
            parts = [part for part in parts if part is not None]
            if not parts:
                continue

            parallel_sizes: list[int] = []
            previous_kind: str | None = None
            structure_error = (
                f"Строка соединения {idx}: в маршруте должны чередоваться "
                "разъёмы и кабели или стрелки"
            )
            arrow_boundary_error = (
                f"Строка соединения {idx}: стрелка не может быть первым "
                "или последним элементом маршрута"
            )

            for position, part in enumerate(parts):
                current_kinds: set[str] = set()
                contains_arrow = False

                if isinstance(part, dict):
                    name, value = next(iter(part.items()))
                    resolved = ProjectValidator._resolve_component_name(
                        str(name), component_names, simple_template_names
                    )
                    parallel_sizes.append(ProjectValidator._parallel_size(value))
                    if resolved is None:
                        errors.append(
                            f"Строка соединения {idx}: неизвестный компонент {name!r}"
                        )
                    else:
                        current_kinds.add(
                            "connector" if resolved in connector_names else "cable_or_arrow"
                        )
                        ProjectValidator._validate_index_value(
                            errors,
                            idx,
                            resolved,
                            value,
                            pin_limits,
                            cable_map,
                            connector_map,
                            ferrule_names,
                        )

                elif isinstance(part, list):
                    parallel_sizes.append(len(part))
                    for item in part:
                        if not isinstance(item, str):
                            errors.append(
                                f"Строка соединения {idx}: некорректный элемент {item!r}"
                            )
                            continue
                        if ProjectSerializer._is_arrow(item):
                            contains_arrow = True
                            current_kinds.add("cable_or_arrow")
                            continue
                        resolved = ProjectValidator._resolve_component_name(
                            item, component_names, simple_template_names
                        )
                        if resolved is None:
                            errors.append(
                                f"Строка соединения {idx}: неизвестный компонент {item!r}"
                            )
                            continue
                        current_kinds.add(
                            "connector" if resolved in connector_names else "cable_or_arrow"
                        )

                elif isinstance(part, str):
                    if ProjectSerializer._is_arrow(part):
                        contains_arrow = True
                        current_kinds.add("cable_or_arrow")
                    else:
                        resolved = ProjectValidator._resolve_component_name(
                            part, component_names, simple_template_names
                        )
                        if resolved is None:
                            errors.append(
                                f"Строка соединения {idx}: неизвестный компонент {part!r}"
                            )
                        else:
                            current_kinds.add(
                                "connector"
                                if resolved in connector_names
                                else "cable_or_arrow"
                            )

                if contains_arrow and position in {0, len(parts) - 1}:
                    if arrow_boundary_error not in errors:
                        errors.append(arrow_boundary_error)

                if len(current_kinds) != 1:
                    if len(current_kinds) > 1 and structure_error not in errors:
                        errors.append(structure_error)
                    previous_kind = None
                    continue

                current_kind = next(iter(current_kinds))
                if previous_kind == current_kind and structure_error not in errors:
                    errors.append(structure_error)
                previous_kind = current_kind

            if parallel_sizes and len(set(parallel_sizes)) > 1:
                errors.append(f"Строка соединения {idx}: параллельные группы контактов и жил должны иметь одинаковую длину")

        return errors

    @staticmethod
    def _message_row_index(message: str) -> int | None:
        import re

        match = re.search(r"Строка соединения (\d+)", message)
        return int(match.group(1)) - 1 if match else None

    @staticmethod
    def _message_component(message: str, component_names: list[str]) -> str | None:
        for name in sorted(component_names, key=len, reverse=True):
            if name and name in message:
                return name
        return None

    @staticmethod
    def _resolve_component_name(name: str, component_names: set[str], simple_template_names: set[str]) -> str | None:
        name = str(name).strip()
        if name in component_names:
            return name
        if "." in name:
            base = name.split(".", 1)[0]
            if base in component_names:
                return base
        if name.endswith("."):
            base = name[:-1]
            if base in component_names:
                return base
        m = __import__("re").match(r"([A-Za-z_]+)(\d+)$", name)
        if m and m.group(1) in component_names:
            return m.group(1)
        if name in simple_template_names:
            return name
        return None

    @staticmethod
    def _parallel_size(value) -> int:
        return len(ProjectValidator._flatten_value_list(value))

    @staticmethod
    def _flatten_value_list(value) -> list:
        if isinstance(value, list):
            flat: list = []
            for item in value:
                flat.extend(ProjectValidator._flatten_value_list(item))
            return flat
        if isinstance(value, str):
            expanded = ProjectSerializer._expand_range_token(value)
            if expanded is not None:
                return expanded
        return [value]

    @staticmethod
    def _validate_index_value(errors, row_index, name, value, pin_limits, cable_map, connector_map, ferrule_names) -> None:
        if isinstance(value, list):
            for item in value:
                ProjectValidator._validate_index_value(errors, row_index, name, item, pin_limits, cable_map, connector_map, ferrule_names)
            return

        if isinstance(value, str):
            expanded = ProjectSerializer._expand_range_token(value)
            if expanded is not None:
                for item in expanded:
                    ProjectValidator._validate_index_value(errors, row_index, name, item, pin_limits, cable_map, connector_map, ferrule_names)
                return

        if name in ferrule_names:
            return

        if name in connector_map:
            connector = connector_map[name]
            if isinstance(value, int):
                if connector.pins:
                    allowed_num = {ProjectSerializer._serialize_pin_token(v) for v in connector.pins}
                    if value not in allowed_num:
                        errors.append(f"Строка соединения {row_index}: контакт {value} не найден у {name}")
                elif value > pin_limits[name]:
                    errors.append(f"Строка соединения {row_index}: контакт {value} вне диапазона {name}")
            elif isinstance(value, str):
                allowed = {label.strip() for label in connector.pinlabels if label.strip()}
                allowed.update(str(pin).strip() for pin in connector.pins if str(pin).strip())
                if allowed and value not in allowed:
                    errors.append(f"Строка соединения {row_index}: контакт '{value}' не найден у {name}")
            return

        if name in cable_map:
            cable = cable_map[name]
            if value == "s":
                if not cable.shield:
                    errors.append(f"Строка соединения {row_index}: у кабеля {name} нет экрана")
                return
            if isinstance(value, int):
                if value > cable.wirecount:
                    errors.append(f"Строка соединения {row_index}: жила {value} вне диапазона {name}")
                return
            if isinstance(value, str):
                allowed = {v.strip() for v in (cable.colors + cable.wirelabels) if v.strip()}
                if allowed and value not in allowed:
                    errors.append(f"Строка соединения {row_index}: метка или цвет жилы '{value}' не найдены у {name}")
