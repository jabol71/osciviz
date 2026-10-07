"""Scena: proporcje płótna, tło, ziarno losowości, lista warstw i zaznaczenie.

Scena jest modelem danych. Wysyła sygnały Qt o zmianach, ale nie rysuje
i nie wie o OpenGL. Zmiany robione przez GUI przechodzą przez komendy undo,
które wywołują metody sceny i emitują sygnały.

Układ współrzędnych: krótszy bok płótna ma zakres ``[-1, 1]``, dłuższy jest
wydłużony proporcjonalnie (16:9 → X w ``[-16/9, 16/9]``), oś Y w górę.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from osciviz.scene.layers import Layer

ASPECT_RATIOS = ("16:9", "1:1", "9:16", "4:3", "5:4", "21:9")


def parse_aspect(aspect: str) -> tuple[int, int]:
    w, h = aspect.split(":")
    return int(w), int(h)


def scene_extent(aspect: str) -> tuple[float, float]:
    """Połowa szerokości i wysokości kadru w jednostkach sceny."""
    w, h = parse_aspect(aspect)
    if w >= h:
        return (w / h, 1.0)
    return (1.0, h / w)


class Scene(QObject):
    changed = Signal()  # dowolna zmiana wpływająca na obraz
    layers_changed = Signal()  # dodanie/usunięcie/zmiana kolejności/nazwy warstw
    selection_changed = Signal()
    settings_changed = Signal()  # proporcje, tło

    def __init__(self) -> None:
        super().__init__()
        self.aspect = "16:9"
        self.background = "#07070B"
        self.seed = 1234
        self.layers: list[Layer] = []  # kolejność rysowania: indeks 0 = na spodzie
        self.selection: list[str] = []
        self.audio_path: str | None = None

    # --- dostęp --------------------------------------------------------------
    @property
    def extent(self) -> tuple[float, float]:
        return scene_extent(self.aspect)

    def layer(self, layer_id: str) -> Layer | None:
        for layer in self.layers:
            if layer.id == layer_id:
                return layer
        return None

    def index_of(self, layer_id: str) -> int:
        for i, layer in enumerate(self.layers):
            if layer.id == layer_id:
                return i
        return -1

    def selected_layers(self) -> list[Layer]:
        return [lay for lay in self.layers if lay.id in self.selection]

    # --- modyfikacje (wołane przez komendy undo) ----------------------------
    def insert_layer(self, layer: Layer, index: int | None = None) -> None:
        if index is None or index > len(self.layers):
            index = len(self.layers)
        self.layers.insert(index, layer)
        self.layers_changed.emit()
        self.changed.emit()

    def remove_layer(self, layer_id: str) -> tuple[Layer, int] | None:
        i = self.index_of(layer_id)
        if i < 0:
            return None
        layer = self.layers.pop(i)
        if layer_id in self.selection:
            self.selection.remove(layer_id)
            self.selection_changed.emit()
        self.layers_changed.emit()
        self.changed.emit()
        return layer, i

    def move_layer(self, layer_id: str, new_index: int) -> None:
        i = self.index_of(layer_id)
        if i < 0:
            return
        layer = self.layers.pop(i)
        new_index = max(0, min(new_index, len(self.layers)))
        self.layers.insert(new_index, layer)
        self.layers_changed.emit()
        self.changed.emit()

    def set_selection(self, ids: list[str]) -> None:
        ids = [i for i in ids if self.layer(i) is not None]
        if ids != self.selection:
            self.selection = ids
            self.selection_changed.emit()

    def notify_layer_changed(self, structural: bool = False) -> None:
        if structural:
            self.layers_changed.emit()
        self.changed.emit()

    def clear(self) -> None:
        self.layers = []
        self.selection = []
        self.aspect = "16:9"
        self.background = "#07070B"
        self.audio_path = None
        self.layers_changed.emit()
        self.selection_changed.emit()
        self.settings_changed.emit()
        self.changed.emit()
