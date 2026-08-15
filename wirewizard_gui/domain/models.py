from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any
from uuid import uuid4

from wirewizard_gui.domain.connections import ConnectionRowModel, iter_component_steps
from wirewizard_gui.domain.project_format import CURRENT_SCHEMA_VERSION


@dataclass
class ConnectorModel:
    name: str
    id: str = field(default_factory=lambda: uuid4().hex)
    type: str = "Универсальный разъём"
    subtype: str = ""
    pincount: int = 2
    pins: list[str] = field(default_factory=list)
    pinlabels: list[str] = field(default_factory=list)
    notes: str = ""
    color: str = ""
    simple: bool = False
    pn: str = ""
    manufacturer: str = ""
    mpn: str = ""
    supplier: str = ""
    spn: str = ""
    ignore_in_bom: bool = False
    wireviz_extras: dict[str, Any] = field(default_factory=dict)


@dataclass
class CableModel:
    name: str
    id: str = field(default_factory=lambda: uuid4().hex)
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
    pn: str = ""
    manufacturer: str = ""
    mpn: str = ""
    supplier: str = ""
    spn: str = ""
    ignore_in_bom: bool = False
    wireviz_extras: dict[str, Any] = field(default_factory=dict)


@dataclass
class FerruleModel:
    name: str
    id: str = field(default_factory=lambda: uuid4().hex)
    type: str = "Обжимной наконечник"
    subtype: str = "0.5 mm²"
    color: str = ""
    notes: str = ""
    pn: str = ""
    manufacturer: str = ""
    mpn: str = ""
    supplier: str = ""
    spn: str = ""
    ignore_in_bom: bool = False
    wireviz_extras: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProjectModel:
    schema_version: int = CURRENT_SCHEMA_VERSION
    title: str = "Новый жгут"
    description: str = ""
    connectors: list[ConnectorModel] = field(default_factory=list)
    cables: list[CableModel] = field(default_factory=list)
    ferrules: list[FerruleModel] = field(default_factory=list)
    connections: list[ConnectionRowModel] = field(default_factory=list)
    wireviz_extras: dict[str, Any] = field(default_factory=dict)
    wireviz_metadata_extras: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        self.resolve_connection_ids()
        return asdict(self)

    def resolve_connection_ids(self) -> None:
        components = {
            item.name: item.id
            for item in [*self.connectors, *self.cables, *self.ferrules]
        }
        for row in self.connections:
            for step in iter_component_steps(row.steps):
                base_name = step.component.split(".", 1)[0]
                if base_name in components:
                    step.component_id = components[base_name]

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
            wireviz_extras=data.get("wireviz_extras", {}),
            wireviz_metadata_extras=data.get("wireviz_metadata_extras", {}),
        )
