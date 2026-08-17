from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Literal

from wirewizard_gui.domain.models import CableModel, ConnectorModel, FerruleModel


ComponentKind = Literal["connector", "cable", "ferrule"]


@dataclass(frozen=True)
class ComponentPreset:
    key: str
    kind: ComponentKind
    title: str
    description: str
    values: dict[str, Any]

    def create(self, name: str) -> ConnectorModel | CableModel | FerruleModel:
        model_class = {
            "connector": ConnectorModel,
            "cable": CableModel,
            "ferrule": FerruleModel,
        }[self.kind]
        return model_class(name=name, **deepcopy(self.values))


COMPONENT_PRESETS = (
    ComponentPreset(
        "molex-kk-254-2",
        "connector",
        "Molex KK 254, 2 контакта",
        "Двухконтактный разъём с шагом 2,54 мм.",
        {"type": "Molex KK 254", "subtype": "female", "pincount": 2},
    ),
    ComponentPreset(
        "jst-xh-4",
        "connector",
        "JST XH, 4 контакта",
        "Четырёхконтактный разъём с шагом 2,50 мм.",
        {"type": "JST XH", "subtype": "female", "pincount": 4},
    ),
    ComponentPreset(
        "terminal-block-6",
        "connector",
        "Клеммная колодка, 6 контактов",
        "Универсальная шестипозиционная клеммная колодка.",
        {"type": "Клеммная колодка", "subtype": "plug", "pincount": 6},
    ),
    ComponentPreset(
        "hookup-025-rd",
        "cable",
        "Монтажный провод 0,25 мм²",
        "Красный одножильный монтажный провод длиной 1 м.",
        {
            "type": "Монтажный провод",
            "gauge": "0.25 mm2",
            "length": "1 m",
            "wirecount": 1,
            "colors": ["RD"],
        },
    ),
    ComponentPreset(
        "twisted-pair-034",
        "cable",
        "Витая пара 0,34 мм²",
        "Двухжильная витая пара длиной 1 м.",
        {
            "type": "Витая пара",
            "gauge": "0.34 mm2",
            "length": "1 m",
            "wirecount": 2,
            "colors": ["WH", "BU"],
        },
    ),
    ComponentPreset(
        "shielded-2x025",
        "cable",
        "Экранированный кабель 2×0,25 мм²",
        "Двухжильный кабель с общим экраном.",
        {
            "type": "Экранированный кабель",
            "gauge": "0.25 mm2",
            "length": "1 m",
            "wirecount": 2,
            "colors": ["WH", "BK"],
            "shield": True,
        },
    ),
    ComponentPreset(
        "ferrule-050",
        "ferrule",
        "Наконечник 0,5 мм²",
        "Одинарный втулочный наконечник оранжевого цвета.",
        {"type": "Обжимной наконечник", "subtype": "0.5 mm²", "color": "OG"},
    ),
    ComponentPreset(
        "ferrule-075",
        "ferrule",
        "Наконечник 0,75 мм²",
        "Одинарный втулочный наконечник синего цвета.",
        {"type": "Обжимной наконечник", "subtype": "0.75 mm²", "color": "BU"},
    ),
    ComponentPreset(
        "twin-ferrule-050",
        "ferrule",
        "Двойной наконечник 0,5 мм²",
        "Втулочный наконечник для двух проводов.",
        {"type": "Двойной наконечник", "subtype": "0.5 mm²", "color": "WH"},
    ),
)


def presets_for(kind: ComponentKind) -> tuple[ComponentPreset, ...]:
    return tuple(preset for preset in COMPONENT_PRESETS if preset.kind == kind)

