"""Testy geometrii (bez GPU) i — jeśli dostępny — renderowania offscreen."""

import numpy as np
import pytest

from osciviz.core.frame import silent_frame
from osciviz.render.geometry import find_trigger, spectrum_mesh, waveform_mesh
from osciviz.render.line_mesh import polyline_mesh
from osciviz.scene.layers import SpectrumLayer, WaveformLayer


def test_polyline_mesh_thickness():
    pts = np.array([[0, 0], [1, 0], [2, 0]], np.float32)
    mesh = polyline_mesh(pts, 0.1)
    assert mesh.shape == (12, 5)  # 2 odcinki × 2 trójkąty × 3 wierzchołki
    assert np.allclose(np.abs(mesh[:, 1]), 0.1)  # pozioma linia: y = ±hw


def test_miter_is_limited_on_sharp_turn():
    pts = np.array([[0, 0], [1, 0], [0, 0.01]], np.float32)
    mesh = polyline_mesh(pts, 0.1, miter_limit=3)
    dist = np.linalg.norm(mesh[:, :2] - np.array([1, 0]), axis=1)
    assert dist.max() <= 1.1 + 0.3 + 1e-4


def test_trigger_aligns_to_rising_zero_crossing():
    t = np.arange(4000) / 48000
    sig = np.sin(2 * np.pi * 440 * t).astype(np.float32)
    start = find_trigger(sig, 1000, 500)
    assert sig[start - 1] < 0 <= sig[start]


def test_layer_meshes_have_geometry():
    frame = silent_frame()
    assert len(waveform_mesh(WaveformLayer(), frame)) > 0
    assert len(spectrum_mesh(SpectrumLayer(), np.full(64, 0.5, np.float32))) == 64 * 6


def test_offscreen_render_produces_image(qapp):
    moderngl = pytest.importorskip("moderngl")
    try:
        ctx = moderngl.create_standalone_context(require=410)
    except Exception:
        pytest.skip("Brak OpenGL 4.1 w tym środowisku")
    from osciviz.io.exporter import OffscreenRenderer
    from osciviz.scene.scene import Scene
    from osciviz.scene.simulation import Simulation

    scene = Scene()
    scene.background = "#FF0000"
    scene.layers.append(WaveformLayer())
    off = OffscreenRenderer((320, 180), ctx=ctx)
    image = off.render(scene, silent_frame(), Simulation())
    off.release()
    assert image.shape == (180, 320, 3)
    assert image[5, 5, 0] > 200 and image[5, 5, 1] < 30  # tło czerwone
