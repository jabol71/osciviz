"""Zamiana łamanej na pasek trójkątów o zadanej grubości.

Na macOS (OpenGL 4.1 Core) ``glLineWidth`` obsługuje tylko szerokość 1,
dlatego grubą linię budujemy sami z trójkątów:

1. dla każdego odcinka liczymy wektor kierunku ``d`` i normalną
   ``n = (−d.y, d.x)`` (obrót o 90°),
2. w każdym wierzchołku łamanej bierzemy uśrednioną styczną sąsiednich
   odcinków; normalna do niej to kierunek „miter” (ścięcia narożnika),
3. długość miter = połowa grubości / cos(połowy kąta zgięcia), czyli
   ``hw / dot(miter, n_odcinka)``; przy bardzo ostrych kątach rośnie do
   nieskończoności, więc ograniczamy ją (``miter_limit``),
4. wierzchołki po obu stronach: ``P ± miter · długość``, a każdy odcinek to
   dwa trójkąty łączące lewą i prawą krawędź.

Każdy wierzchołek wyjściowy ma 5 liczb: ``x, y, u, v, alpha`` — ``u`` to
położenie wzdłuż linii (do gradientu), ``v = ±1`` to strona paska (do
wygładzania krawędzi w shaderze).
"""

from __future__ import annotations

import numpy as np

VERTEX_FLOATS = 5


def polyline_mesh(points: np.ndarray, half_width: float, alpha: np.ndarray | float = 1.0,
                  u: np.ndarray | None = None, miter_limit: float = 3.0) -> np.ndarray:
    """Zwraca tablicę ``(6·(n−1), 5)`` float32: trójkąty pokrywające łamaną."""
    p = np.asarray(points, dtype=np.float32)
    n = len(p)
    if n < 2:
        return np.zeros((0, VERTEX_FLOATS), dtype=np.float32)
    if u is None:
        u = np.linspace(0.0, 1.0, n, dtype=np.float32)
    alpha = np.broadcast_to(np.asarray(alpha, dtype=np.float32), (n,))

    # 1. Kierunki odcinków (znormalizowane) i ich normalne.
    d = np.diff(p, axis=0)
    length = np.linalg.norm(d, axis=1, keepdims=True)
    d = d / np.maximum(length, 1e-9)
    seg_normal = np.stack((-d[:, 1], d[:, 0]), axis=1)

    # 2. Styczna w wierzchołku = suma kierunków odcinka przed i po.
    tangent = np.empty_like(p)
    tangent[0] = d[0]
    tangent[-1] = d[-1]
    tangent[1:-1] = d[:-1] + d[1:]
    t_len = np.linalg.norm(tangent, axis=1, keepdims=True)
    # Gdy linia zawraca o 180°, suma = 0 — wtedy bierzemy kierunek odcinka.
    degenerate = t_len[:, 0] < 1e-6
    tangent[degenerate] = np.vstack((d, d[-1:]))[degenerate]
    tangent = tangent / np.maximum(np.linalg.norm(tangent, axis=1, keepdims=True), 1e-9)
    miter = np.stack((-tangent[:, 1], tangent[:, 0]), axis=1)

    # 3. Długość miter: hw / cos(α), gdzie cos(α) = dot(miter, normalna odcinka).
    ref_normal = np.vstack((seg_normal, seg_normal[-1:]))
    cos_a = np.abs(np.sum(miter * ref_normal, axis=1))
    miter_len = half_width / np.maximum(cos_a, 1.0 / miter_limit)

    left = p + miter * miter_len[:, None]
    right = p - miter * miter_len[:, None]

    # 4. Dwa trójkąty na odcinek: (L_i, R_i, L_i+1) i (R_i, R_i+1, L_i+1).
    def verts(pos, side):
        out = np.empty((n, VERTEX_FLOATS), dtype=np.float32)
        out[:, 0:2] = pos
        out[:, 2] = u
        out[:, 3] = side
        out[:, 4] = alpha
        return out

    lv = verts(left, 1.0)
    rv = verts(right, -1.0)
    i = np.arange(n - 1)
    tris = np.stack((lv[i], rv[i], lv[i + 1], rv[i], rv[i + 1], lv[i + 1]), axis=1)
    return tris.reshape(-1, VERTEX_FLOATS)


def quads_mesh(corners: np.ndarray, u: np.ndarray, alpha: float = 1.0) -> np.ndarray:
    """Prostokąty (np. słupki widma) jako trójkąty.

    ``corners`` ma kształt ``(k, 4, 2)``: dla każdego słupka 4 narożniki
    w kolejności LD, PD, PG, LG. Zwraca ``(6k, 5)``.
    """
    k = len(corners)
    if k == 0:
        return np.zeros((0, VERTEX_FLOATS), dtype=np.float32)
    order = [0, 1, 2, 0, 2, 3]
    pos = corners[:, order, :]  # (k, 6, 2)
    out = np.empty((k, 6, VERTEX_FLOATS), dtype=np.float32)
    out[:, :, 0:2] = pos
    out[:, :, 2] = u[:, None]
    out[:, :, 3] = 0.0
    out[:, :, 4] = alpha
    return out.reshape(-1, VERTEX_FLOATS)
