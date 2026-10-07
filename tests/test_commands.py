from PySide6.QtGui import QUndoStack

from osciviz.scene import commands as cmd
from osciviz.scene.layers import WaveformLayer
from osciviz.scene.scene import Scene
from osciviz.scene.transform import Transform


def test_add_remove_undo_redo(qapp):
    scene, stack = Scene(), QUndoStack()
    layer = WaveformLayer()
    stack.push(cmd.AddLayersCommand(scene, [layer]))
    assert scene.layers == [layer]
    stack.push(cmd.RemoveLayersCommand(scene, [layer.id]))
    assert scene.layers == []
    stack.undo()
    assert scene.layers == [layer]
    stack.undo()
    assert scene.layers == []
    stack.redo()
    assert scene.layers == [layer]


def test_drag_gesture_merges_into_one_step(qapp):
    scene, stack = Scene(), QUndoStack()
    layer = WaveformLayer()
    stack.push(cmd.AddLayersCommand(scene, [layer]))
    for i in range(1, 6):
        stack.push(cmd.SetTransformsCommand(scene, {layer.id: Transform(x=i * 0.1)}, gesture=7))
    assert stack.count() == 2
    assert abs(layer.transform.x - 0.5) < 1e-9
    stack.undo()
    assert layer.transform.x == 0.0


def test_param_change_and_coercion(qapp):
    scene, stack = Scene(), QUndoStack()
    layer = WaveformLayer()
    scene.layers.append(layer)
    stack.push(cmd.SetParamCommand(scene, layer.id, "thickness", 999))
    assert layer.params["thickness"] == 40.0  # przycięte do maksimum
    stack.undo()
    assert layer.params["thickness"] == 4.0


def test_reorder(qapp):
    scene, stack = Scene(), QUndoStack()
    a, b = WaveformLayer("a"), WaveformLayer("b")
    scene.layers += [a, b]
    stack.push(cmd.MoveLayerCommand(scene, a.id, 1))
    assert [lay.name for lay in scene.layers] == ["b", "a"]
    stack.undo()
    assert [lay.name for lay in scene.layers] == ["a", "b"]
