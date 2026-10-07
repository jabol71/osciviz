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


class MoveLayerCommand(QUndoCommand):
    """Zmiana kolejności rysowania (w górę/w dół, przeciąganie w panelu)."""

    def __init__(self, scene: Scene, layer_id: str, new_index: int) -> None:
        super().__init__(QCoreApplication.translate("Commands", "Reorder layers"))
        self.scene = scene
        self.layer_id = layer_id
        self.old_index = scene.index_of(layer_id)
        self.new_index = new_index

    def redo(self) -> None:
        self.scene.move_layer(self.layer_id, self.new_index)

    def undo(self) -> None:
        self.scene.move_layer(self.layer_id, self.old_index)


class SetTransformsCommand(QUndoCommand):
    """Nowe transformacje dla wielu warstw naraz (przesuwanie, skalowanie, obrót)."""

    def __init__(self, scene: Scene, new: dict[str, Transform], gesture: object = None,
                 text: str | None = None) -> None:
        super().__init__(text or QCoreApplication.translate("Commands", "Transform"))
        self.scene = scene
        self.old = {i: scene.layer(i).transform.copy() for i in new if scene.layer(i)}
        self.new = {i: t.copy() for i, t in new.items() if i in self.old}
        self.gesture = gesture  # identyfikator gestu; ten sam = łączenie w jeden krok

    def id(self) -> int:
        return MERGE_TRANSFORM

    def mergeWith(self, other: QUndoCommand) -> bool:
        if (not isinstance(other, SetTransformsCommand) or self.gesture is None
                or other.gesture != self.gesture or other.new.keys() != self.new.keys()):
            return False
        self.new = other.new
        return True

    def _apply(self, values: dict[str, Transform]) -> None:
        for layer_id, t in values.items():
            layer = self.scene.layer(layer_id)
            if layer is not None:
                layer.transform = t.copy()
        self.scene.notify_layer_changed()

    def redo(self) -> None:
        self._apply(self.new)

    def undo(self) -> None:
        self._apply(self.old)


class SetParamCommand(QUndoCommand):
    """Zmiana jednego parametru warstwy z inspektora."""

    def __init__(self, scene: Scene, layer_id: str, key: str, value, gesture: object = None) -> None:
        super().__init__(QCoreApplication.translate("Commands", "Change parameter"))
        self.scene = scene
        self.layer_id = layer_id
        self.key = key
        layer = scene.layer(layer_id)
        spec = layer.spec(key)
        self.old = copy.deepcopy(layer.params.get(key))
        self.new = coerce(spec, value) if spec else value
        self.gesture = gesture  # ten sam gest (np. jedno przeciągnięcie suwaka) = jeden krok

    def id(self) -> int:
        return MERGE_PARAM

    def mergeWith(self, other: QUndoCommand) -> bool:
        if (isinstance(other, SetParamCommand) and self.gesture is not None
                and other.gesture == self.gesture
                and other.layer_id == self.layer_id and other.key == self.key):
            self.new = other.new
            return True
        return False

    def _set(self, value) -> None:
        layer = self.scene.layer(self.layer_id)
        if layer is not None:
            layer.params[self.key] = copy.deepcopy(value)
            self.scene.notify_layer_changed(structural=self.key == "mode")

    def redo(self) -> None:
        self._set(self.new)

    def undo(self) -> None:
        self._set(self.old)


class SetLayerPropCommand(QUndoCommand):
    """Zmiana właściwości warstwy: name, opacity, blend_mode, visible, locked."""

    STRUCTURAL = ("name", "visible", "locked")

    def __init__(self, scene: Scene, layer_ids: list[str], prop: str, value,
                 gesture: object = None) -> None:
        super().__init__(QCoreApplication.translate("Commands", "Change layer"))
        self.scene = scene
        self.prop = prop
        self.old = {i: getattr(scene.layer(i), prop) for i in layer_ids if scene.layer(i)}
        self.value = value
        self.gesture = gesture

    def id(self) -> int:
        return MERGE_PROP

    def mergeWith(self, other: QUndoCommand) -> bool:
        if (isinstance(other, SetLayerPropCommand) and self.gesture is not None
                and other.gesture == self.gesture and other.prop == self.prop and other.old.keys() == self.old.keys()):
            self.value = other.value
            return True
        return False

    def _set(self, values: dict) -> None:
        for layer_id, v in values.items():
            layer = self.scene.layer(layer_id)
            if layer is not None:
                setattr(layer, self.prop, v)
        self.scene.notify_layer_changed(structural=self.prop in self.STRUCTURAL)

    def redo(self) -> None:
        self._set({i: self.value for i in self.old})

    def undo(self) -> None:
        self._set(self.old)


class SetSceneSettingCommand(QUndoCommand):
    """Zmiana ustawienia sceny: proporcje płótna lub kolor tła."""

    def __init__(self, scene: Scene, attr: str, value) -> None:
        super().__init__(QCoreApplication.translate("Commands", "Change canvas"))
        self.scene = scene
        self.attr = attr
        self.old = getattr(scene, attr)
        self.value = value

    def _set(self, value) -> None:
        setattr(self.scene, self.attr, value)
        self.scene.settings_changed.emit()
        self.scene.changed.emit()

    def redo(self) -> None:
        self._set(self.value)

    def undo(self) -> None:
        self._set(self.old)


class ApplyPresetCommand(QUndoCommand):
    """Nadpisanie parametrów warstwy presetem (transformacja zostaje)."""

    def __init__(self, scene: Scene, layer_id: str, params: dict) -> None:
        super().__init__(QCoreApplication.translate("Commands", "Apply preset"))
        self.scene = scene
        self.layer_id = layer_id
        layer = scene.layer(layer_id)
        self.old = copy.deepcopy(layer.params)
        self.new_params = params

    def redo(self) -> None:
        layer = self.scene.layer(self.layer_id)
        layer.apply_params(self.new_params)
        self.scene.notify_layer_changed(structural=True)

    def undo(self) -> None:
        layer = self.scene.layer(self.layer_id)
        layer.params = copy.deepcopy(self.old)
        self.scene.notify_layer_changed(structural=True)
