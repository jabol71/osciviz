"""Komendy undo/redo (``QUndoCommand``) — jedyna droga zmiany sceny z GUI.

Każda komenda pamięta stan „przed” i „po”, więc ``undo()`` i ``redo()`` to
proste przypisania. Komendy z tym samym identyfikatorem gestu (``gesture``) (np. kolejne ruchy
myszy w jednym przeciąganiu albo przesuwanie suwaka) łączą się w jeden
krok historii przez ``mergeWith`` — cofnięcie przywraca stan sprzed
całego gestu, a nie sprzed ostatniego piksela.
"""

from __future__ import annotations

import copy

from PySide6.QtCore import QCoreApplication
from PySide6.QtGui import QUndoCommand

from osciviz.scene.layers import Layer, coerce
from osciviz.scene.scene import Scene
from osciviz.scene.transform import Transform

MERGE_TRANSFORM = 1001
MERGE_PARAM = 1002
MERGE_PROP = 1003


class ValueCommand(QUndoCommand):
    """Baza komend „stan przed → stan po”.

    Podklasa ustawia ``self.old`` i ``self.new`` i definiuje ``_set(value)``;
    ``redo``/``undo`` to wtedy ``_set(new)``/``_set(old)``. Komendy z tym
    samym ``MERGE_ID``, gestem i ``merge_key()`` łączą się w jeden krok.
    """

    MERGE_ID = -1  # -1: bez łączenia (wartość domyślna Qt)

    def __init__(self, scene: Scene, text: str, gesture: object = None) -> None:
        super().__init__(text)
        self.scene = scene
        self.gesture = gesture  # identyfikator gestu; ten sam = łączenie w jeden krok

    def id(self) -> int:
        return self.MERGE_ID

    def merge_key(self):
        """Co musi się zgadzać, żeby dwie komendy jednego gestu się połączyły."""
        return None

    def mergeWith(self, other: QUndoCommand) -> bool:
        if (type(other) is not type(self) or self.gesture is None
                or other.gesture != self.gesture or other.merge_key() != self.merge_key()):
            return False
        self.new = other.new
        return True

    def _set(self, value) -> None:
        raise NotImplementedError

    def redo(self) -> None:
        self._set(self.new)

    def undo(self) -> None:
        self._set(self.old)


class AddLayersCommand(QUndoCommand):
    def __init__(self, scene: Scene, layers: list[Layer], index: int | None = None,
                 text: str | None = None) -> None:
        super().__init__(text or QCoreApplication.translate("Commands", "Add layer"))
        self.scene = scene
        self.layers = layers
        self.index = index
        self.prev_selection = list(scene.selection)

    def redo(self) -> None:
        index = self.index if self.index is not None else len(self.scene.layers)
        for offset, layer in enumerate(self.layers):
            self.scene.insert_layer(layer, index + offset)
        self.scene.set_selection([lay.id for lay in self.layers])

    def undo(self) -> None:
        for layer in self.layers:
            self.scene.remove_layer(layer.id)
        self.scene.set_selection(self.prev_selection)


class RemoveLayersCommand(QUndoCommand):
    def __init__(self, scene: Scene, layer_ids: list[str]) -> None:
        super().__init__(QCoreApplication.translate("Commands", "Delete layers"))
        self.scene = scene
        # Zapamiętujemy warstwy razem z indeksami, żeby undo wstawiło je na miejsce.
        self.removed = sorted(
            ((scene.index_of(i), scene.layer(i)) for i in layer_ids if scene.layer(i)),
            key=lambda t: t[0],
        )
        self.prev_selection = list(scene.selection)

    def redo(self) -> None:
        for _, layer in reversed(self.removed):
            self.scene.remove_layer(layer.id)

    def undo(self) -> None:
        for index, layer in self.removed:
            self.scene.insert_layer(layer, index)
        self.scene.set_selection(self.prev_selection)


class MoveLayerCommand(ValueCommand):
    """Zmiana kolejności rysowania (w górę/w dół, przeciąganie w panelu)."""

    def __init__(self, scene: Scene, layer_id: str, new_index: int) -> None:
        super().__init__(scene, QCoreApplication.translate("Commands", "Reorder layers"))
        self.layer_id = layer_id
        self.old = scene.index_of(layer_id)
        self.new = new_index

    def _set(self, index: int) -> None:
        self.scene.move_layer(self.layer_id, index)


def restack_command(scene: Scene, direction: int) -> MoveLayerCommand | None:
    """Komenda przesunięcia jedynej zaznaczonej warstwy o ``direction`` (+1 w górę, −1 w dół)."""
    if len(scene.selection) != 1:
        return None
    layer_id = scene.selection[0]
    i = scene.index_of(layer_id)
    j = max(0, min(len(scene.layers) - 1, i + direction))
    return MoveLayerCommand(scene, layer_id, j) if i != j else None


class SetTransformsCommand(ValueCommand):
    """Nowe transformacje dla wielu warstw naraz (przesuwanie, skalowanie, obrót)."""

    MERGE_ID = MERGE_TRANSFORM

    def __init__(self, scene: Scene, new: dict[str, Transform], gesture: object = None,
                 text: str | None = None) -> None:
        super().__init__(scene, text or QCoreApplication.translate("Commands", "Transform"), gesture)
        self.old = {i: scene.layer(i).transform.copy() for i in new if scene.layer(i)}
        self.new = {i: t.copy() for i, t in new.items() if i in self.old}

    def merge_key(self):
        return set(self.new)

    def _set(self, values: dict[str, Transform]) -> None:
        for layer_id, t in values.items():
            layer = self.scene.layer(layer_id)
            if layer is not None:
                layer.transform = t.copy()
        self.scene.notify_layer_changed()


class SetParamCommand(ValueCommand):
    """Zmiana jednego parametru warstwy z inspektora."""

    MERGE_ID = MERGE_PARAM

    def __init__(self, scene: Scene, layer_id: str, key: str, value, gesture: object = None) -> None:
        super().__init__(scene, QCoreApplication.translate("Commands", "Change parameter"), gesture)
        self.layer_id = layer_id
        self.key = key
        layer = scene.layer(layer_id)
        spec = layer.spec(key)
        self.old = copy.deepcopy(layer.params.get(key))
        self.new = coerce(spec, value) if spec else value

    def merge_key(self):
        return (self.layer_id, self.key)

    def _set(self, value) -> None:
        layer = self.scene.layer(self.layer_id)
        if layer is not None:
            layer.params[self.key] = copy.deepcopy(value)
            self.scene.notify_layer_changed(structural=self.key == "mode")


class SetLayerPropCommand(ValueCommand):
    """Zmiana właściwości warstwy: name, opacity, blend_mode, visible, locked."""

    MERGE_ID = MERGE_PROP
    STRUCTURAL = ("name", "visible", "locked")

    def __init__(self, scene: Scene, layer_ids: list[str], prop: str, value,
                 gesture: object = None) -> None:
        super().__init__(scene, QCoreApplication.translate("Commands", "Change layer"), gesture)
        self.prop = prop
        self.old = {i: getattr(scene.layer(i), prop) for i in layer_ids if scene.layer(i)}
        self.new = {i: value for i in self.old}

    def merge_key(self):
        return (self.prop, set(self.old))

    def _set(self, values: dict) -> None:
        for layer_id, v in values.items():
            layer = self.scene.layer(layer_id)
            if layer is not None:
                setattr(layer, self.prop, v)
        self.scene.notify_layer_changed(structural=self.prop in self.STRUCTURAL)


class SetSceneSettingCommand(ValueCommand):
    """Zmiana ustawienia sceny: proporcje płótna lub kolor tła."""

    def __init__(self, scene: Scene, attr: str, value) -> None:
        super().__init__(scene, QCoreApplication.translate("Commands", "Change canvas"))
        self.attr = attr
        self.old = getattr(scene, attr)
        self.new = value

    def _set(self, value) -> None:
        setattr(self.scene, self.attr, value)
        self.scene.settings_changed.emit()
        self.scene.changed.emit()


class ApplyPresetCommand(ValueCommand):
    """Nadpisanie parametrów warstwy presetem (transformacja zostaje)."""

    def __init__(self, scene: Scene, layer_id: str, params: dict) -> None:
        super().__init__(scene, QCoreApplication.translate("Commands", "Apply preset"))
        self.layer_id = layer_id
        layer = scene.layer(layer_id)
        self.old = copy.deepcopy(layer.params)
        preview = copy.deepcopy(layer)  # apply_params na kopii: rzutuje typy, pomija nieznane klucze
        preview.apply_params(params)
        self.new = preview.params

    def _set(self, params: dict) -> None:
        self.scene.layer(self.layer_id).params = copy.deepcopy(params)
        self.scene.notify_layer_changed(structural=True)
