"""Zapis i odczyt projektu ``.osv`` (archiwum ZIP).

Struktura archiwum::

    project.json        # format_version, aspect_ratio, background, seed, layers[], audio_ref
    assets/
      audio.<ext>       # kopia pliku audio lub nagrania
      images/<id>.<ext> # obrazy warstw cząsteczek

- Zapis jest *atomowy*: piszemy do pliku tymczasowego obok docelowego,
  a potem podmieniamy go jednym ``os.replace`` — przerwany zapis nie
  zniszczy poprzedniej wersji projektu.
- Odczyt waliduje dane i w razie problemu rzuca ``ProjectError`` z czytelnym
  komunikatem (GUI pokazuje go w oknie dialogowym zamiast wyjątku).
- ``format_version`` + ``migrate()`` pozwalają czytać starsze wersje formatu.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import zipfile
from pathlib import Path

from osciviz.scene.layers import ParticleLayer, layer_from_dict
from osciviz.scene.scene import ASPECT_RATIOS, Scene

FORMAT_VERSION = 2


class ProjectError(Exception):
    """Błąd zapisu/odczytu projektu z komunikatem dla użytkownika."""


def scene_to_dict(scene: Scene, audio_ref: str | None, image_refs: dict[str, str]) -> dict:
    layers = []
    for layer in scene.layers:
        data = layer.to_dict()
        if isinstance(layer, ParticleLayer):
            data["params"]["image"] = image_refs.get(layer.id, "")
        layers.append(data)
    return {
        "format_version": FORMAT_VERSION,
        "app": "OsciViz",
        "aspect_ratio": scene.aspect,
        "background": scene.background,
        "seed": scene.seed,
        "audio_ref": audio_ref,
        "layers": layers,
    }


def save_project(scene: Scene, path: str | Path) -> None:
    path = Path(path)
    image_refs: dict[str, str] = {}
    audio_ref = None
    fd, tmp_name = tempfile.mkstemp(prefix=".osv-", suffix=".tmp", dir=str(path.parent))
    os.close(fd)
    try:
        with zipfile.ZipFile(tmp_name, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            if scene.audio_path and Path(scene.audio_path).exists():
                audio_ref = f"assets/audio{Path(scene.audio_path).suffix.lower()}"
                # Audio jest już skompresowane (lub duże) — zapis bez kompresji jest szybszy.
                zf.write(scene.audio_path, audio_ref, compress_type=zipfile.ZIP_STORED)
            for layer in scene.layers:
                if isinstance(layer, ParticleLayer):
                    img = layer.params.get("image")
                    if img and Path(img).exists():
                        ref = f"assets/images/{layer.id}{Path(img).suffix.lower()}"
                        zf.write(img, ref)
                        image_refs[layer.id] = ref
            data = scene_to_dict(scene, audio_ref, image_refs)
            zf.writestr("project.json", json.dumps(data, indent=2, ensure_ascii=False))
        os.replace(tmp_name, path)
    except OSError as exc:
        if os.path.exists(tmp_name):
            os.remove(tmp_name)
        raise ProjectError(f"Nie udało się zapisać projektu: {exc}") from exc


def migrate(data: dict) -> dict:
    """Aktualizuje słownik projektu ze starszej wersji formatu do bieżącej."""
    version = int(data.get("format_version", 1))
    if version < 2:
        # Wersja 1 przechowywała proporcje pod kluczem "aspect".
        if "aspect" in data and "aspect_ratio" not in data:
            data["aspect_ratio"] = data.pop("aspect")
        data.setdefault("seed", 1234)
        data["format_version"] = 2
    return data


def load_project(path: str | Path, scene: Scene, extract_dir: str | Path | None = None) -> None:
    """Wczytuje projekt do istniejącej sceny. Zasoby trafiają do ``extract_dir``."""
    path = Path(path)
    if extract_dir is None:
        extract_dir = tempfile.mkdtemp(prefix="osciviz-")
    extract_dir = Path(extract_dir)
    try:
        with zipfile.ZipFile(path) as zf:
            try:
                data = json.loads(zf.read("project.json").decode("utf-8"))
            except KeyError as exc:
                raise ProjectError("Plik nie zawiera project.json — to nie jest projekt OsciViz.") from exc
            data = migrate(data)
            if int(data["format_version"]) > FORMAT_VERSION:
                raise ProjectError("Projekt pochodzi z nowszej wersji OsciViz.")
            layers = []
            for raw in data.get("layers", []):
                layer = layer_from_dict(raw)
                if isinstance(layer, ParticleLayer):
                    ref = raw.get("params", {}).get("image", "")
                    layer.params["image"] = _extract(zf, ref, extract_dir) if ref else ""
                layers.append(layer)
            audio_ref = data.get("audio_ref")
            audio_path = _extract(zf, audio_ref, extract_dir) if audio_ref else None
    except zipfile.BadZipFile as exc:
        raise ProjectError("Plik projektu jest uszkodzony lub nie jest archiwum ZIP.") from exc
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ProjectError("project.json jest uszkodzony (niepoprawny JSON).") from exc
    except (ValueError, TypeError) as exc:
        raise ProjectError(f"Niepoprawne dane projektu: {exc}") from exc
    except OSError as exc:
        raise ProjectError(f"Nie udało się odczytać projektu: {exc}") from exc

    aspect = data.get("aspect_ratio", "16:9")
    scene.clear()
    scene.aspect = aspect if aspect in ASPECT_RATIOS else "16:9"
    scene.background = str(data.get("background", "#07070B"))
    scene.seed = int(data.get("seed", 1234))
    scene.audio_path = audio_path
    for layer in layers:
        scene.layers.append(layer)
    scene.layers_changed.emit()
    scene.settings_changed.emit()
    scene.changed.emit()


def _extract(zf: zipfile.ZipFile, ref: str, target: Path) -> str:
    # Ochrona przed ścieżkami typu "../../" w złośliwym archiwum.
    name = Path(ref).name
    sub = "images" if "/images/" in ref else ""
    out_dir = target / sub
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / name
    try:
        with zf.open(ref) as src, open(out, "wb") as dst:
            shutil.copyfileobj(src, dst)
    except KeyError as exc:
        raise ProjectError(f"Brak zasobu w archiwum: {ref}") from exc
    return str(out)
