import zipfile

import numpy as np
import pytest
import soundfile as sf

from osciviz.io.project_io import ProjectError, load_project, save_project
from osciviz.scene.layers import ParticleLayer, SpectrumLayer, WaveformLayer, XYLayer
from osciviz.scene.scene import Scene


@pytest.fixture
def scene(qapp, tmp_path):
    s = Scene()
    s.aspect = "9:16"
    s.background = "#112233"
    s.seed = 42
    w = WaveformLayer("Fala")
    w.transform.x = 0.3
    w.transform.rotation = 15
    w.params["thickness"] = 7.5
    w.opacity = 0.5
    sp = SpectrumLayer()
    sp.params["mode"] = "circle"
    xy = XYLayer()
    xy.locked = True
    xy.visible = False
    s.layers += [w, sp, xy]
    audio = tmp_path / "a.wav"
    sf.write(str(audio), np.zeros((4800, 2), np.float32), 48000)
    s.audio_path = str(audio)
    return s


def dump(scene):
    return [(lay.to_dict()) for lay in scene.layers], scene.aspect, scene.background, scene.seed


def test_roundtrip_gives_identical_scene(scene, tmp_path):
    path = tmp_path / "p.osv"
    save_project(scene, path)
    loaded = Scene()
    load_project(path, loaded, tmp_path / "extract")
    assert dump(loaded) == dump(scene)
    assert loaded.audio_path and loaded.audio_path.endswith(".wav")


def test_particle_image_is_embedded(qapp, tmp_path):
    import cv2

    img = tmp_path / "logo.png"
    cv2.imwrite(str(img), np.full((10, 10, 3), 255, np.uint8))
    s = Scene()
    p = ParticleLayer()
    p.params["image"] = str(img)
    s.layers.append(p)
    path = tmp_path / "p.osv"
    save_project(s, path)
    img.unlink()  # projekt musi działać bez oryginalnego pliku
    loaded = Scene()
    load_project(path, loaded, tmp_path / "x")
    assert loaded.layers[0].params["image"].endswith(".png")
    assert (tmp_path / "x" / "images").exists()


def test_corrupted_file_raises_readable_error(qapp, tmp_path):
    bad = tmp_path / "bad.osv"
    bad.write_bytes(b"not a zip")
    with pytest.raises(ProjectError):
        load_project(bad, Scene(), tmp_path / "x")


def test_invalid_json_raises_readable_error(qapp, tmp_path):
    bad = tmp_path / "bad.osv"
    with zipfile.ZipFile(bad, "w") as zf:
        zf.writestr("project.json", "{oops")
    with pytest.raises(ProjectError):
        load_project(bad, Scene(), tmp_path / "x")


def test_unknown_layer_type_raises_readable_error(qapp, tmp_path):
    bad = tmp_path / "bad.osv"
    with zipfile.ZipFile(bad, "w") as zf:
        zf.writestr("project.json", '{"format_version": 2, "layers": [{"type": "hologram"}]}')
    with pytest.raises(ProjectError):
        load_project(bad, Scene(), tmp_path / "x")


def test_migration_from_v1(qapp, tmp_path):
    old = tmp_path / "old.osv"
    with zipfile.ZipFile(old, "w") as zf:
        zf.writestr("project.json", '{"format_version": 1, "aspect": "4:3", "layers": []}')
    s = Scene()
    load_project(old, s, tmp_path / "x")
    assert s.aspect == "4:3"
