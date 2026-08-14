from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any


@dataclass
class ConnectionStepModel:
    kind: str = "component"
    component_id: str | None = None
    component: str = ""
    value: str = ""
    items: list[ConnectionStepModel] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ConnectionStepModel:
        return cls(
            kind=str(data.get("kind", "component")),
            component_id=data.get("component_id"),
            component=str(data.get("component", "")),
            value=str(data.get("value", "")),
            items=[cls.from_dict(item) for item in data.get("items", [])],
        )


@dataclass(init=False)
class ConnectionRowModel:
    steps: list[ConnectionStepModel]

    def __init__(
        self,
        route: str = "",
        steps: list[ConnectionStepModel | dict[str, Any]] | None = None,
    ) -> None:
        if steps is None:
            self.steps = parse_route(route)
        else:
            self.steps = [
                ConnectionStepModel.from_dict(step)
                if isinstance(step, dict)
                else step
                for step in steps
            ]

    @property
    def route(self) -> str:
        return format_route(self.steps)

    @route.setter
    def route(self, value: str) -> None:
        self.steps = parse_route(value)


def is_arrow(value: str) -> bool:
    return bool(re.fullmatch(r"<?(?:-+|=+)>?", str(value).strip()))


def split_route(route: str) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    depth = 0
    idx = 0
    arrow_with_separators = re.compile(r"->\s*(<?(?:-+|=+)>?)\s*->")

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

            separator = route.startswith("->", idx)
            longer_arrow = idx > 0 and route[idx - 1] in "-<"
            if separator and not longer_arrow:
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


def _split_csv(text: str) -> list[str]:
    items: list[str] = []
    current: list[str] = []
    depth = 0
    for char in text:
        if char == "[":
            depth += 1
        elif char == "]" and depth:
            depth -= 1
        if char == "," and depth == 0:
            token = "".join(current).strip()
            if token:
                items.append(token)
            current = []
        else:
            current.append(char)
    token = "".join(current).strip()
    if token:
        items.append(token)
    return items


def _parse_token(token: str) -> ConnectionStepModel:
    token = token.strip()
    if is_arrow(token):
        return ConnectionStepModel(kind="arrow", value=token)
    if token.startswith("[") and token.endswith("]"):
        return ConnectionStepModel(
            kind="parallel",
            items=[_parse_token(item) for item in _split_csv(token[1:-1])],
        )
    if ":" in token:
        component, value = token.split(":", 1)
        return ConnectionStepModel(
            kind="component", component=component.strip(), value=value.strip()
        )
    return ConnectionStepModel(kind="component", component=token)


def parse_route(route: str) -> list[ConnectionStepModel]:
    return [_parse_token(part) for part in split_route(route) if part.strip()]


def _format_step(step: ConnectionStepModel) -> str:
    if step.kind == "arrow":
        return step.value
    if step.kind == "parallel":
        return "[" + ", ".join(_format_step(item) for item in step.items) + "]"
    if step.value:
        return f"{step.component}:{step.value}"
    return step.component


def format_route(steps: list[ConnectionStepModel]) -> str:
    return " -> ".join(filter(None, (_format_step(step) for step in steps)))


def iter_component_steps(
    steps: list[ConnectionStepModel],
):
    for step in steps:
        if step.kind == "component":
            yield step
        elif step.kind == "parallel":
            yield from iter_component_steps(step.items)
