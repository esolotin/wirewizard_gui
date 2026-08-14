from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from wirewizard_gui.domain.project_format import CURRENT_SCHEMA_VERSION


@dataclass
class ConnectorModel:
    name: str
    type: str = "Универсальный разъём"
    subtype: str = ""
    pincount: int = 2
    pins: list[str] = field(default_factory=list)
    pinlabels: list[str] = field(default_factory=list)
    notes: str = ""
    color: str = ""
    simple: bool = False


@dataclass
class CableModel:
    name: str
    type: str = "Универсальный кабель"
    gauge: str = "0.25 mm2"
    length: str = "1 m"
    wirecount: int = 2
    colors: list[str] = field(default_factory=list)
    color_code: str = ""
    wirelabels: list[str] = field(default_factory=list)
    shield: bool = False
    bundle: bool = False
    notes: str = ""


@dataclass
class FerruleModel:
    name: str
    type: str = "Обжимной наконечник"
    subtype: str = "0.5 mm²"
    color: str = ""
    notes: str = ""


@dataclass
class ConnectionRowModel:
    route: str = ""


@dataclass
class ProjectModel:
    schema_version: int = CURRENT_SCHEMA_VERSION
    title: str = "Новый жгут"
    description: str = ""
    connectors: list[ConnectorModel] = field(default_factory=list)
    cables: list[CableModel] = field(default_factory=list)
    ferrules: list[FerruleModel] = field(default_factory=list)
    connections: list[ConnectionRowModel] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProjectModel":
        return cls(
            schema_version=data.get("schema_version", CURRENT_SCHEMA_VERSION),
            title=data.get("title", "Новый жгут"),
            description=data.get("description", ""),
            connectors=[ConnectorModel(**item) for item in data.get("connectors", [])],
            cables=[CableModel(**item) for item in data.get("cables", [])],
            ferrules=[FerruleModel(**item) for item in data.get("ferrules", [])],
            connections=[ConnectionRowModel(**item) for item in data.get("connections", [])],
        )
