"""Opis parametrów warstw (schemat), z którego inspektor buduje formularz.

Każda klasa warstwy deklaruje listę ``ParamSpec``. Inspektor nie zna
konkretnych warstw — tworzy suwak, pole wyboru koloru itp. na podstawie
rodzaju parametru (``kind``). Dodanie nowego parametru to jedna linijka.

Etykiety są oznaczone ``QT_TRANSLATE_NOOP("Params", ...)``, żeby narzędzie
``pyside6-lupdate`` dodało je do plików tłumaczeń; tłumaczenie następuje
dopiero w GUI (``QCoreApplication.translate("Params", label)``).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from PySide6.QtCore import QT_TRANSLATE_NOOP


@dataclass(frozen=True)
class ParamSpec:
    key: str
    kind: str  # "float" | "int" | "bool" | "color" | "enum" | "image"
    default: object
    label: str
    minimum: float = 0.0
    maximum: float = 1.0
    step: float = 0.01
    options: tuple = field(default_factory=tuple)  # dla "enum": krotki (wartość, etykieta)
    group: str = QT_TRANSLATE_NOOP("Params", "Appearance")
    suffix: str = ""


GROUP_LOOK = QT_TRANSLATE_NOOP("Params", "Appearance")
GROUP_SIGNAL = QT_TRANSLATE_NOOP("Params", "Signal")
GROUP_GLOW = QT_TRANSLATE_NOOP("Params", "Glow")
GROUP_PHYSICS = QT_TRANSLATE_NOOP("Params", "Physics")
GROUP_SOURCE = QT_TRANSLATE_NOOP("Params", "Source image")
GROUP_REACT = QT_TRANSLATE_NOOP("Params", "Reaction")
