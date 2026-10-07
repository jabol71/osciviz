"""Presety warstw: wbudowane oraz zapisane przez użytkownika (pliki ``.json``).

Preset to typ warstwy + jej parametry (bez transformacji), np.::

    {"type": "waveform", "name": "Neon", "params": {"color": "#FF2BD6", ...}}

Wbudowane presety leżą w ``osciviz/resources/presets``. Presety użytkownika
zapisujemy w katalogu danych aplikacji (na macOS
``~/Library/Application Support/OsciViz/presets``).
"""

from __future__ import annotations

import json
import re
from importlib import resources
from pathlib import Path

from osciviz.scene.layers import LAYER_TYPES, Layer


class PresetError(Exception):
    pass


def read_preset(path: str | Path) -> dict:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PresetError(f"Nie można odczytać presetu: {exc}") from exc
    if not isinstance(data, dict) or data.get("type") not in LAYER_TYPES:
        raise PresetError("Plik nie jest presetem warstwy OsciViz.")
    data.setdefault("name", Path(path).stem)
    data.setdefault("params", {})
    return data


def write_preset(layer: Layer, path: str | Path, name: str | None = None) -> None:
    data = layer.preset_dict()
    if name:
        data["name"] = name
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def slug(text: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]+", "-", text).strip("-").lower() or "preset"


class PresetManager:
    def __init__(self, user_dir: str | Path | None = None) -> None:
        self.user_dir = Path(user_dir) if user_dir else None
        self.presets: dict[str, dict] = {}  # klucz "typ:nazwa" → dane
        self.reload()

    def reload(self) -> None:
        self.presets.clear()
        builtin = resources.files("osciviz.resources").joinpath("presets")
        for entry in sorted(builtin.iterdir(), key=lambda e: e.name):
            if entry.name.endswith(".json"):
                data = json.loads(entry.read_text(encoding="utf-8"))
                data["builtin"] = True
                self.presets[f"{data['type']}:{data['name']}"] = data
        if self.user_dir and self.user_dir.exists():
            for path in sorted(self.user_dir.glob("*.json")):
                try:
                    data = read_preset(path)
                except PresetError:
                    continue
                data["path"] = str(path)
                self.presets[f"{data['type']}:{data['name']}"] = data

    def list_for(self, type_name: str) -> list[tuple[str, str]]:
        return [(k, d["name"]) for k, d in self.presets.items() if d["type"] == type_name]

    def all(self) -> list[tuple[str, str]]:
        return [(k, d["name"]) for k, d in self.presets.items()]

    def get(self, key: str) -> dict | None:
        return self.presets.get(key)

    def save_user(self, layer: Layer, name: str) -> str:
        if self.user_dir is None:
            raise PresetError("Brak katalogu presetów użytkownika.")
        self.user_dir.mkdir(parents=True, exist_ok=True)
        path = self.user_dir / f"{layer.TYPE}-{slug(name)}.json"
        write_preset(layer, path, name)
        self.reload()
        return f"{layer.TYPE}:{name}"

    def import_file(self, path: str | Path) -> str:
        data = read_preset(path)
        if self.user_dir is None:
            raise PresetError("Brak katalogu presetów użytkownika.")
        self.user_dir.mkdir(parents=True, exist_ok=True)
        target = self.user_dir / f"{data['type']}-{slug(data['name'])}.json"
        target.write_text(json.dumps({k: v for k, v in data.items() if k != "path"}, indent=2,
                                     ensure_ascii=False), encoding="utf-8")
        self.reload()
        return f"{data['type']}:{data['name']}"
