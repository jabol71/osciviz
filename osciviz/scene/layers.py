"""Klasy warstw — czyste dane: nazwa, transformacja, parametry.

Warstwa nie wie nic o OpenGL ani o widżetach. Renderer czyta jej parametry,
a GUI zmienia je wyłącznie przez komendy undo (``scene/commands.py``).

Każda warstwa ma lokalny prostokąt ograniczający ``half_extent()``
(połowa szerokości i wysokości w jednostkach lokalnych). Na nim działają
hit test, ramka zaznaczenia i uchwyty.
"""

from __future__ import annotations

import copy
import uuid

from PySide6.QtCore import QT_TRANSLATE_NOOP

from osciviz.scene.params import (
    GROUP_GLOW,
    GROUP_PHYSICS,
    GROUP_REACT,
    GROUP_SIGNAL,
    GROUP_SOURCE,
    ParamSpec,
)
from osciviz.scene.transform import Transform

BLEND_MODES = ("normal", "additive")

# Parametry poświaty wspólne dla warstw liniowych.
GLOW_PARAMS = [
    ParamSpec("glow", "float", 0.6, QT_TRANSLATE_NOOP("Params", "Glow strength"), 0.0, 3.0, 0.05, group=GROUP_GLOW),
    ParamSpec("glow_radius", "float", 14.0, QT_TRANSLATE_NOOP("Params", "Glow radius"), 1.0, 60.0, 0.5,
              group=GROUP_GLOW, suffix=" px"),
]


def new_id() -> str:
    return uuid.uuid4().hex[:10]


class Layer:
    """Wspólna baza wszystkich warstw."""

    TYPE = "layer"
    DISPLAY_NAME = QT_TRANSLATE_NOOP("LayerTypes", "Layer")
    PARAMS: list[ParamSpec] = []

    def __init__(self, name: str | None = None, transform: Transform | None = None) -> None:
        self.id = new_id()
        self.name = name or self.DISPLAY_NAME
        self.transform = transform or Transform()
        self.opacity = 1.0
        self.blend_mode = "additive"
        self.visible = True
        self.locked = False
        self.params: dict = {p.key: copy.deepcopy(p.default) for p in self.PARAMS}

    # --- geometria -----------------------------------------------------------
    def half_extent(self) -> tuple[float, float]:
        return (1.0, 1.0)

    # --- parametry -----------------------------------------------------------
    @classmethod
    def spec(cls, key: str) -> ParamSpec | None:
        for p in cls.PARAMS:
            if p.key == key:
                return p
        return None

    def get(self, key: str):
        return self.params.get(key, self.spec(key).default if self.spec(key) else None)

    # --- serializacja --------------------------------------------------------
    def to_dict(self) -> dict:
        return {
            "type": self.TYPE,
            "id": self.id,
            "name": self.name,
            "transform": self.transform.to_dict(),
            "opacity": self.opacity,
            "blend_mode": self.blend_mode,
            "visible": self.visible,
            "locked": self.locked,
            "params": copy.deepcopy(self.params),
        }

    def preset_dict(self) -> dict:
        """Dane do presetu: typ i parametry, bez transformacji i bez identyfikatora."""
        return {"type": self.TYPE, "name": self.name, "opacity": self.opacity,
                "blend_mode": self.blend_mode, "params": copy.deepcopy(self.params)}

    def apply_params(self, params: dict) -> None:
        """Ustawia znane parametry, ignorując nieznane i rzutując typy."""
        for spec in self.PARAMS:
            if spec.key in params:
                self.params[spec.key] = coerce(spec, params[spec.key])

    def clone(self) -> Layer:
        data = self.to_dict()
        layer = layer_from_dict(data)
        layer.id = new_id()
        return layer


def coerce(spec: ParamSpec, value):
    """Rzutuje wartość z pliku/GUI na typ parametru i przycina do zakresu."""
    if spec.kind == "float":
        return float(min(max(float(value), spec.minimum), spec.maximum))
    if spec.kind == "int":
        return int(min(max(int(round(float(value))), spec.minimum), spec.maximum))
    if spec.kind == "bool":
        return bool(value)
    if spec.kind == "enum":
        values = [o[0] for o in spec.options]
        return value if value in values else spec.default
    return value if value is not None else spec.default


class WaveformLayer(Layer):
    """Oscyloskop czasowy: fragment sygnału narysowany jako linia."""

    TYPE = "waveform"
    DISPLAY_NAME = QT_TRANSLATE_NOOP("LayerTypes", "Waveform")
    PARAMS = [
        ParamSpec("color", "color", "#7C5CFF", QT_TRANSLATE_NOOP("Params", "Color")),
        ParamSpec("use_gradient", "bool", True, QT_TRANSLATE_NOOP("Params", "Gradient")),
        ParamSpec("color2", "color", "#22D3EE", QT_TRANSLATE_NOOP("Params", "Gradient end")),
        ParamSpec("thickness", "float", 4.0, QT_TRANSLATE_NOOP("Params", "Thickness"), 0.5, 40.0, 0.5, suffix=" px"),
        ParamSpec("copies", "int", 1, QT_TRANSLATE_NOOP("Params", "Copies"), 1, 8, 1),
        ParamSpec("copy_offset", "float", 0.12, QT_TRANSLATE_NOOP("Params", "Copy offset"), -1.0, 1.0, 0.01),
        ParamSpec("channel", "enum", "mono", QT_TRANSLATE_NOOP("Params", "Channel"),
                  options=(("mono", QT_TRANSLATE_NOOP("Params", "Mono")), ("left", QT_TRANSLATE_NOOP("Params", "Left")),
                           ("right", QT_TRANSLATE_NOOP("Params", "Right"))), group=GROUP_SIGNAL),
        ParamSpec("window_ms", "float", 40.0, QT_TRANSLATE_NOOP("Params", "Window"), 2.0, 250.0, 1.0,
                  group=GROUP_SIGNAL, suffix=" ms"),
        ParamSpec("gain", "float", 1.5, QT_TRANSLATE_NOOP("Params", "Gain"), 0.1, 10.0, 0.1, group=GROUP_SIGNAL),
        ParamSpec("stabilize", "bool", True, QT_TRANSLATE_NOOP("Params", "Trigger (stabilize)"), group=GROUP_SIGNAL),
        *GLOW_PARAMS,
    ]

    def half_extent(self):
        return (1.0, 0.4)


class XYLayer(Layer):
    """Oscyloskop XY: kanał lewy → oś X, prawy → oś Y (figury Lissajous)."""

    TYPE = "xy"
    DISPLAY_NAME = QT_TRANSLATE_NOOP("LayerTypes", "XY scope")
    PARAMS = [
        ParamSpec("color", "color", "#3DFFA2", QT_TRANSLATE_NOOP("Params", "Color")),
        ParamSpec("thickness", "float", 2.0, QT_TRANSLATE_NOOP("Params", "Thickness"), 0.5, 30.0, 0.5, suffix=" px"),
        ParamSpec("persistence", "float", 0.85, QT_TRANSLATE_NOOP("Params", "Persistence"), 0.0, 0.98, 0.01),
        ParamSpec("trail_ms", "float", 25.0, QT_TRANSLATE_NOOP("Params", "Trail length"), 2.0, 200.0, 1.0,
                  group=GROUP_SIGNAL, suffix=" ms"),
        ParamSpec("gain", "float", 1.2, QT_TRANSLATE_NOOP("Params", "Gain"), 0.1, 10.0, 0.1, group=GROUP_SIGNAL),
        ParamSpec("rotate45", "bool", False, QT_TRANSLATE_NOOP("Params", "Mid/side (rotate 45°)"), group=GROUP_SIGNAL),
        *GLOW_PARAMS,
    ]

    def half_extent(self):
        return (0.6, 0.6)


class SpectrumLayer(Layer):
    """Widmo FFT jako słupki albo koło."""

    TYPE = "spectrum"
    DISPLAY_NAME = QT_TRANSLATE_NOOP("LayerTypes", "Spectrum")
    PARAMS = [
        ParamSpec("mode", "enum", "bars", QT_TRANSLATE_NOOP("Params", "Mode"),
                  options=(("bars", QT_TRANSLATE_NOOP("Params", "Bars")), ("circle", QT_TRANSLATE_NOOP("Params", "Circle")),
                           ("mirror", QT_TRANSLATE_NOOP("Params", "Mirrored bars")))),
        ParamSpec("color", "color", "#FF4FD8", QT_TRANSLATE_NOOP("Params", "Color")),
        ParamSpec("use_gradient", "bool", True, QT_TRANSLATE_NOOP("Params", "Gradient")),
        ParamSpec("color2", "color", "#7C5CFF", QT_TRANSLATE_NOOP("Params", "Gradient end")),
        ParamSpec("bar_gap", "float", 0.3, QT_TRANSLATE_NOOP("Params", "Bar gap"), 0.0, 0.9, 0.01),
        ParamSpec("inner_radius", "float", 0.45, QT_TRANSLATE_NOOP("Params", "Inner radius"), 0.05, 0.95, 0.01),
        ParamSpec("bands", "int", 64, QT_TRANSLATE_NOOP("Params", "Bands"), 8, 256, 1, group=GROUP_SIGNAL),
        ParamSpec("f_min", "float", 30.0, QT_TRANSLATE_NOOP("Params", "Min frequency"), 20.0, 2000.0, 1.0,
                  group=GROUP_SIGNAL, suffix=" Hz"),
        ParamSpec("f_max", "float", 14000.0, QT_TRANSLATE_NOOP("Params", "Max frequency"), 500.0, 22000.0, 10.0,
                  group=GROUP_SIGNAL, suffix=" Hz"),
        ParamSpec("log_scale", "bool", True, QT_TRANSLATE_NOOP("Params", "Logarithmic scale"), group=GROUP_SIGNAL),
        ParamSpec("smoothing", "float", 0.6, QT_TRANSLATE_NOOP("Params", "Smoothing"), 0.0, 0.97, 0.01,
                  group=GROUP_SIGNAL),
        ParamSpec("gain", "float", 1.2, QT_TRANSLATE_NOOP("Params", "Gain"), 0.1, 5.0, 0.05, group=GROUP_SIGNAL),
        ParamSpec("floor", "float", 0.35, QT_TRANSLATE_NOOP("Params", "Noise floor"), 0.0, 0.9, 0.01,
                  group=GROUP_SIGNAL),
        *GLOW_PARAMS,
    ]

    def half_extent(self):
        if self.params.get("mode") == "circle":
            return (1.0, 1.0)
        return (1.0, 0.4)


class ParticleLayer(Layer):
    """Obraz rozbity na cząsteczki, które wypycha bas i przyciąga sprężyna."""

    TYPE = "particles"
    DISPLAY_NAME = QT_TRANSLATE_NOOP("LayerTypes", "Particles")
    PARAMS = [
        ParamSpec("image", "image", "", QT_TRANSLATE_NOOP("Params", "Image"), group=GROUP_SOURCE),
        ParamSpec("method", "enum", "brightness", QT_TRANSLATE_NOOP("Params", "Sampling"),
                  options=(("brightness", QT_TRANSLATE_NOOP("Params", "Brightness")), ("edges", QT_TRANSLATE_NOOP("Params", "Edges")),
                           ("alpha", QT_TRANSLATE_NOOP("Params", "Alpha channel"))), group=GROUP_SOURCE),
        ParamSpec("invert", "bool", False, QT_TRANSLATE_NOOP("Params", "Invert"), group=GROUP_SOURCE),
        ParamSpec("threshold", "float", 0.5, QT_TRANSLATE_NOOP("Params", "Threshold"), 0.0, 1.0, 0.01, group=GROUP_SOURCE),
        ParamSpec("count", "int", 20000, QT_TRANSLATE_NOOP("Params", "Particle count"), 1000, 100000, 1000,
                  group=GROUP_SOURCE),
        ParamSpec("size", "float", 2.5, QT_TRANSLATE_NOOP("Params", "Point size"), 0.5, 12.0, 0.1, suffix=" px"),
        ParamSpec("brightness", "float", 1.0, QT_TRANSLATE_NOOP("Params", "Brightness"), 0.1, 3.0, 0.05),
        ParamSpec("bass_lo", "float", 20.0, QT_TRANSLATE_NOOP("Params", "Bass from"), 20.0, 500.0, 1.0,
                  group=GROUP_REACT, suffix=" Hz"),
        ParamSpec("bass_hi", "float", 150.0, QT_TRANSLATE_NOOP("Params", "Bass to"), 40.0, 1000.0, 1.0,
                  group=GROUP_REACT, suffix=" Hz"),
        ParamSpec("gate", "float", 0.55, QT_TRANSLATE_NOOP("Params", "Sensitivity gate"), 0.0, 0.95, 0.01,
                  group=GROUP_REACT),
        ParamSpec("push_mode", "enum", "radial", QT_TRANSLATE_NOOP("Params", "Push direction"),
                  options=(("radial", QT_TRANSLATE_NOOP("Params", "Radial")), ("noise", QT_TRANSLATE_NOOP("Params", "Noise field")),
                           ("jitter", QT_TRANSLATE_NOOP("Params", "Random jitter"))), group=GROUP_REACT),
        ParamSpec("mid_brightness", "bool", True, QT_TRANSLATE_NOOP("Params", "Mids → brightness"), group=GROUP_REACT),
        ParamSpec("high_size", "bool", False, QT_TRANSLATE_NOOP("Params", "Highs → size"), group=GROUP_REACT),
        ParamSpec("strength", "float", 6.0, QT_TRANSLATE_NOOP("Params", "Push strength"), 0.0, 40.0, 0.1,
                  group=GROUP_PHYSICS),
        ParamSpec("stiffness", "float", 40.0, QT_TRANSLATE_NOOP("Params", "Spring stiffness"), 1.0, 200.0, 0.5,
                  group=GROUP_PHYSICS),
        ParamSpec("damping", "float", 6.0, QT_TRANSLATE_NOOP("Params", "Damping"), 0.0, 40.0, 0.1, group=GROUP_PHYSICS),
        ParamSpec("glow", "float", 0.0, QT_TRANSLATE_NOOP("Params", "Glow strength"), 0.0, 3.0, 0.05, group=GROUP_GLOW),
        ParamSpec("glow_radius", "float", 10.0, QT_TRANSLATE_NOOP("Params", "Glow radius"), 1.0, 60.0, 0.5,
                  group=GROUP_GLOW, suffix=" px"),
    ]

    def __init__(self, name=None, transform=None) -> None:
        super().__init__(name, transform)
        self._extent = (0.7, 0.35)  # aktualizowane po wczytaniu obrazu (proporcje)

    def set_image_extent(self, half_extent: tuple[float, float]) -> None:
        self._extent = (0.7 * half_extent[0], 0.7 * half_extent[1])

    def half_extent(self):
        return self._extent


LAYER_TYPES: dict[str, type[Layer]] = {
    cls.TYPE: cls for cls in (WaveformLayer, XYLayer, SpectrumLayer, ParticleLayer)
}


def create_layer(type_name: str) -> Layer:
    return LAYER_TYPES[type_name]()


def layer_from_dict(data: dict) -> Layer:
    """Tworzy warstwę z danych słownika (projekt lub preset), z walidacją pól."""
    type_name = data.get("type")
    if type_name not in LAYER_TYPES:
        raise ValueError(f"Nieznany typ warstwy: {type_name!r}")
    layer = LAYER_TYPES[type_name]()
    if "id" in data:
        layer.id = str(data["id"])
    layer.name = str(data.get("name", layer.name))
    if "transform" in data:
        layer.transform = Transform.from_dict(data["transform"])
    layer.opacity = float(min(max(float(data.get("opacity", 1.0)), 0.0), 1.0))
    blend = data.get("blend_mode", layer.blend_mode)
    layer.blend_mode = blend if blend in BLEND_MODES else "normal"
    layer.visible = bool(data.get("visible", True))
    layer.locked = bool(data.get("locked", False))
    layer.apply_params(data.get("params", {}))
    return layer
