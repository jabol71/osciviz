"""Geometria warstw: z parametrów i próbek audio → wierzchołki do narysowania.

Funkcje są czyste (bez OpenGL), więc można je testować bez karty grafiki.
Wynik jest od razu w układzie sceny (transformacja warstwy zastosowana na
CPU). Dzięki temu grubość linii nie zniekształca się przy nierównym
skalowaniu ani obrocie warstwy.

Grubości podajemy w „pikselach przy wysokości 1080”: wysokość kadru to
2 jednostki sceny, więc 1 px = 2/1080 jednostki, a połowa grubości
``t`` px to ``t / 1080`` jednostki.
"""

from __future__ import annotations

import math

import numpy as np

from osciviz.core.frame import FrameContext
from osciviz.render.line_mesh import VERTEX_FLOATS, polyline_mesh, quads_mesh
from osciviz.scene.layers import SpectrumLayer, WaveformLayer, XYLayer
from osciviz.scene.transform import apply

PX = 2.0 / 1080.0  # jednostki sceny na „piksel referencyjny”
MAX_POINTS = 1600  # więcej punktów niż pikseli szerokości nic nie daje


def _channel(samples: np.ndarray, channel: str) -> np.ndarray:
    if channel == "left":
        return samples[:, 0]
    if channel == "right":
        return samples[:, 1]
    return samples.mean(axis=1)


def find_trigger(signal: np.ndarray, n: int, search: int) -> int:
    """Indeks początku okna wyrównany do zbocza narastającego (jak trigger oscyloskopu).

    Szukamy przejść przez zero „z dołu do góry” w obszarze ``search`` próbek
    przed ostatnim możliwym początkiem okna i bierzemy najpóźniejsze.
    Dzięki temu okresowy sygnał stoi w miejscu, zamiast „pływać”.
    """
    latest_start = len(signal) - n
    first = max(1, latest_start - search)
    if latest_start <= first:
        return max(0, latest_start)
    seg = signal[first - 1: latest_start + 1]
    rising = np.nonzero((seg[:-1] < 0) & (seg[1:] >= 0))[0]
    if len(rising) == 0:
        return latest_start
    return first + int(rising[-1])


def waveform_mesh(layer: WaveformLayer, frame: FrameContext) -> np.ndarray:
    p = layer.params
    sr = frame.sample_rate
    n = max(8, int(p["window_ms"] / 1000.0 * sr))
    signal = _channel(frame.samples, p["channel"])
    n = min(n, len(signal))
    if p["stabilize"]:
        start = find_trigger(signal, n, search=min(len(signal) - n, int(sr / 25)))
    else:
        start = len(signal) - n
    window = signal[start:start + n]
    if len(window) > MAX_POINTS:
        idx = np.linspace(0, len(window) - 1, MAX_POINTS).astype(np.int64)
        window = window[idx]
    hx, hy = layer.half_extent()
    xs = np.linspace(-hx, hx, len(window), dtype=np.float32)
    ys = window * p["gain"] * hy
    matrix = layer.transform.matrix()
    meshes = []
    copies = int(p["copies"])
    for k in range(copies):
        local = np.stack((xs, ys + k * p["copy_offset"]), axis=1)
        alpha = 1.0 - 0.75 * (k / copies)
        meshes.append(polyline_mesh(apply(matrix, local), p["thickness"] * PX / 2, alpha))
    return np.concatenate(meshes) if meshes else np.zeros((0, VERTEX_FLOATS), np.float32)


def xy_mesh(layer: XYLayer, frame: FrameContext) -> np.ndarray:
    p = layer.params
    n = max(8, int(p["trail_ms"] / 1000.0 * frame.sample_rate))
    s = frame.samples[-n:]
    left, right = s[:, 0], s[:, 1]
    if p["rotate45"]:
        # Obrót o 45°: sygnał mono (L = R) staje się pionową kreską (goniometr).
        x = (left - right) * math.sqrt(0.5)
        y = (left + right) * math.sqrt(0.5)
    else:
        x, y = left, right
    if len(x) > MAX_POINTS * 2:
        idx = np.linspace(0, len(x) - 1, MAX_POINTS * 2).astype(np.int64)
        x, y = x[idx], y[idx]
    hx, hy = layer.half_extent()
    local = np.stack((x * p["gain"] * hx, y * p["gain"] * hy), axis=1)
    # Starsza część śladu jest bledsza (alfa rośnie od 0.15 do 1).
    alpha = np.linspace(0.15, 1.0, len(local), dtype=np.float32)
    return polyline_mesh(apply(layer.transform.matrix(), local), p["thickness"] * PX / 2, alpha)


def spectrum_mesh(layer: SpectrumLayer, values: np.ndarray) -> np.ndarray:
    p = layer.params
    k = len(values)
    if k == 0:
        return np.zeros((0, VERTEX_FLOATS), np.float32)
    hx, hy = layer.half_extent()
    gap = p["bar_gap"]
    u = np.linspace(0.0, 1.0, k, dtype=np.float32)
    v = np.maximum(values, 0.004)
    if p["mode"] == "circle":
        # Słupki promieniowo: kąt środka słupka, szerokość kątowa pomniejszona o przerwę.
        r0 = p["inner_radius"] * hx
        r1 = r0 + (hx - r0) * v
        step = 2 * math.pi / k
        a_mid = math.pi / 2 - np.arange(k) * step  # start na górze, zgodnie z zegarem
        half = step * (1 - gap) / 2
        a0, a1 = a_mid - half, a_mid + half
        corners = np.stack((
            np.stack((r0 * np.cos(a0), r0 * np.sin(a0)), axis=1),
            np.stack((r1 * np.cos(a0), r1 * np.sin(a0)), axis=1),
            np.stack((r1 * np.cos(a1), r1 * np.sin(a1)), axis=1),
            np.stack((r0 * np.cos(a1), r0 * np.sin(a1)), axis=1),
        ), axis=1)
    else:
        width = 2 * hx / k
        x0 = -hx + np.arange(k) * width + width * gap / 2
        x1 = x0 + width * (1 - gap)
        if p["mode"] == "mirror":
            y0 = -hy * v
            y1 = hy * v
        else:
            y0 = np.full(k, -hy)
            y1 = -hy + 2 * hy * v
        corners = np.stack((
            np.stack((x0, y0), axis=1), np.stack((x1, y0), axis=1),
            np.stack((x1, y1), axis=1), np.stack((x0, y1), axis=1),
        ), axis=1)
    flat = apply(layer.transform.matrix(), corners.reshape(-1, 2)).reshape(k, 4, 2)
    return quads_mesh(flat, u)


def rect_mesh(hx: float, hy: float) -> np.ndarray:
    """Prostokąt tła kadru."""
    corners = np.array([[[-hx, -hy], [hx, -hy], [hx, hy], [-hx, hy]]], dtype=np.float32)
    return quads_mesh(corners, np.zeros(1, np.float32))
