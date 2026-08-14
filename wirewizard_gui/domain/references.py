from __future__ import annotations

from wirewizard_gui.domain.models import ProjectModel
from wirewizard_gui.domain.serializer import ProjectSerializer


class ProjectReferences:
    @staticmethod
    def dependent_rows(project: ProjectModel, component_name: str) -> list[int]:
        return [
            index
            for index, row in enumerate(project.connections)
            if ProjectReferences._route_references(row.route, component_name)
        ]

    @staticmethod
    def rename_component(project: ProjectModel, old_name: str, new_name: str) -> list[int]:
        changed_rows: list[int] = []
        for index, row in enumerate(project.connections):
            rewritten, changed = ProjectReferences._rewrite_route(row.route, old_name, new_name)
            if changed:
                row.route = rewritten
                changed_rows.append(index)
        return changed_rows

    @staticmethod
    def remove_dependent_rows(project: ProjectModel, component_name: str) -> list[int]:
        dependent = ProjectReferences.dependent_rows(project, component_name)
        dependent_set = set(dependent)
        project.connections = [
            row for index, row in enumerate(project.connections) if index not in dependent_set
        ]
        return dependent

    @staticmethod
    def _route_references(route: str, component_name: str) -> bool:
        for part in ProjectSerializer._split_route(route):
            parsed = ProjectSerializer._parse_connection_part(part)
            if isinstance(parsed, dict) and parsed:
                name = str(next(iter(parsed)))
                if ProjectReferences._matches_component(name, component_name):
                    return True
            elif isinstance(parsed, list):
                if any(
                    isinstance(item, str)
                    and not ProjectSerializer._is_arrow(item)
                    and ProjectReferences._matches_component(item, component_name)
                    for item in parsed
                ):
                    return True
            elif (
                isinstance(parsed, str)
                and not ProjectSerializer._is_arrow(parsed)
                and ProjectReferences._matches_component(parsed, component_name)
            ):
                return True
        return False

    @staticmethod
    def _rewrite_route(route: str, old_name: str, new_name: str) -> tuple[str, bool]:
        rewritten_parts: list[str] = []
        changed = False

        for part in ProjectSerializer._split_route(route):
            parsed = ProjectSerializer._parse_connection_part(part)
            if isinstance(parsed, dict) and parsed:
                name, value = next(iter(parsed.items()))
                rewritten_name, token_changed = ProjectReferences._rewrite_component_name(
                    str(name), old_name, new_name
                )
                parsed = {rewritten_name: value}
                changed = changed or token_changed
            elif isinstance(parsed, list):
                rewritten_items = []
                for item in parsed:
                    if isinstance(item, str) and not ProjectSerializer._is_arrow(item):
                        item, token_changed = ProjectReferences._rewrite_component_name(
                            item, old_name, new_name
                        )
                        changed = changed or token_changed
                    rewritten_items.append(item)
                parsed = rewritten_items
            elif isinstance(parsed, str) and not ProjectSerializer._is_arrow(parsed):
                parsed, token_changed = ProjectReferences._rewrite_component_name(
                    parsed, old_name, new_name
                )
                changed = changed or token_changed

            rewritten_parts.append(ProjectSerializer._format_connection_part(parsed))

        return " -> ".join(rewritten_parts), changed

    @staticmethod
    def _matches_component(token: str, component_name: str) -> bool:
        token = str(token).strip()
        component_name = component_name.strip()
        return token == component_name or token.startswith(f"{component_name}.")

    @staticmethod
    def _rewrite_component_name(token: str, old_name: str, new_name: str) -> tuple[str, bool]:
        token = str(token).strip()
        if token == old_name:
            return new_name, True
        prefix = f"{old_name}."
        if token.startswith(prefix):
            return f"{new_name}{token[len(old_name):]}", True
        return token, False
