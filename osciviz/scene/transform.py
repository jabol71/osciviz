"""Transformacje 2D warstw: macierze 3×3 we współrzędnych jednorodnych.

Punkt ``(x, y)`` zapisujemy jako wektor ``[x, y, 1]``. Dzięki trzeciej
współrzędnej przesunięcie też jest mnożeniem przez macierz, więc całą
transformację warstwy można złożyć w jedną macierz:

    M = T · R · S

Czytamy od prawej: najpierw skalowanie ``S`` (wokół środka warstwy),
potem obrót ``R`` (wokół środka), na końcu przesunięcie ``T`` na pozycję.

    S = [[sx, 0, 0], [0, sy, 0], [0, 0, 1]]
    R = [[cos θ, −sin θ, 0], [sin θ, cos θ, 0], [0, 0, 1]]
    T = [[1, 0, x], [0, 1, y], [0, 0, 1]]

Hit test robi drogę odwrotną: punkt sceny mnożymy przez ``M⁻¹`` i dostajemy
punkt w lokalnym układzie warstwy, gdzie wystarczy sprawdzić prostokąt
``|lx| ≤ hx`` i ``|ly| ≤ hy``.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass

import numpy as np


@dataclass
class Transform:
    x: float = 0.0
    y: float = 0.0
    sx: float = 1.0
    sy: float = 1.0
    rotation: float = 0.0  # stopnie, przeciwnie do ruchu wskazówek zegara

    def copy(self) -> Transform:
        return Transform(self.x, self.y, self.sx, self.sy, self.rotation)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> Transform:
        return cls(**{k: float(data.get(k, getattr(cls(), k))) for k in ("x", "y", "sx", "sy", "rotation")})

    def matrix(self) -> np.ndarray:
        """Macierz 3×3 przekształcająca lokalne współrzędne warstwy na scenę."""
        return translation(self.x, self.y) @ rotation(self.rotation) @ scale(self.sx, self.sy)

    def inverse(self) -> np.ndarray:
        """Macierz odwrotna, liczona analitycznie: M⁻¹ = S⁻¹ · R(−θ) · T(−x, −y)."""
        sx = self.sx if abs(self.sx) > 1e-9 else 1e-9
        sy = self.sy if abs(self.sy) > 1e-9 else 1e-9
        return scale(1.0 / sx, 1.0 / sy) @ rotation(-self.rotation) @ translation(-self.x, -self.y)


def translation(x: float, y: float) -> np.ndarray:
    return np.array([[1.0, 0.0, x], [0.0, 1.0, y], [0.0, 0.0, 1.0]])


def rotation(degrees: float) -> np.ndarray:
    a = math.radians(degrees)
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])


def scale(sx: float, sy: float) -> np.ndarray:
    return np.array([[sx, 0.0, 0.0], [0.0, sy, 0.0], [0.0, 0.0, 1.0]])


def apply(matrix: np.ndarray, points: np.ndarray) -> np.ndarray:
    """Przekształca tablicę punktów ``(n, 2)`` macierzą 3×3 (wektorowo)."""
    pts = np.asarray(points, dtype=np.float64)
    return (pts @ matrix[:2, :2].T + matrix[:2, 2]).astype(np.float32)


def apply_point(matrix: np.ndarray, x: float, y: float) -> tuple[float, float]:
    v = matrix @ np.array([x, y, 1.0])
    return float(v[0]), float(v[1])


def hit_test(transform: Transform, half_extent: tuple[float, float], x: float, y: float,
             margin: float = 0.0) -> bool:
    """Czy punkt sceny ``(x, y)`` leży w prostokącie warstwy (z marginesem w jedn. lokalnych)."""
    lx, ly = apply_point(transform.inverse(), x, y)
    hx, hy = half_extent
    return abs(lx) <= hx + margin and abs(ly) <= hy + margin


def corners(transform: Transform, half_extent: tuple[float, float]) -> np.ndarray:
    """Narożniki prostokąta warstwy w układzie sceny (kolejność: LD, PD, PG, LG)."""
    hx, hy = half_extent
    local = np.array([[-hx, -hy], [hx, -hy], [hx, hy], [-hx, hy]])
    return apply(transform.matrix(), local)
