"""Zamiana obrazu na chmurę punktów (dla warstwy cząsteczek).

Kroki (wykonywane raz po wczytaniu obrazu, wynik jest cache'owany):

1. wczytanie z kanałem alfa (``cv2.IMREAD_UNCHANGED``), zmniejszenie do
   maks. 1024 px na dłuższym boku, konwersja BGR(A) → RGBA,
2. wyznaczenie *wag* pikseli zależnie od metody próbkowania:
   - ``brightness`` — waga = jasność (opcjonalnie odwrócona),
   - ``edges``      — rozmycie Gaussa + detektor krawędzi Canny,
   - ``alpha``      — piksele z alfą powyżej progu (np. logo w PNG),
3. losowanie N pikseli bez pętli: ``rng.choice`` na spłaszczonych indeksach
   z prawdopodobieństwem proporcjonalnym do wag,
4. przeliczenie (wiersz, kolumna) → lokalne współrzędne warstwy:
   dłuższy bok obrazu ma zakres ``[-1, 1]``, oś Y w górę.

Do każdego punktu dodajemy losowe przesunięcie w obrębie piksela, żeby przy
dużej liczbie punktów nie było widać siatki pikseli.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import numpy as np

MAX_SIDE = 1024


@dataclass
class PointCloud:
    rest_pos: np.ndarray  # (N, 2) float32, lokalne współrzędne
    colors: np.ndarray  # (N, 4) float32, RGBA w [0, 1]
    half_extent: tuple[float, float]  # połowa szerokości/wysokości obrazu w jedn. lokalnych


def load_image_rgba(path: str) -> np.ndarray:
    """Wczytuje obraz jako RGBA uint8, zmniejszony do ``MAX_SIDE``."""
    import cv2  # noqa: PLC0415

    data = np.fromfile(path, dtype=np.uint8)  # obsługuje też ścieżki z polskimi znakami
    img = cv2.imdecode(data, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise ValueError(f"Nie można wczytać obrazu: {path}")
    if img.ndim == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGRA)
    elif img.shape[2] == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)
    h, w = img.shape[:2]
    scale = MAX_SIDE / max(h, w)
    if scale < 1.0:
        img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    return cv2.cvtColor(img, cv2.COLOR_BGRA2RGBA)


def compute_weights(rgba: np.ndarray, method: str, invert: bool = False,
                    threshold: float = 0.5) -> np.ndarray:
    """Zwraca wagi pikseli ``(h, w)`` float64 (nieujemne) dla danej metody."""
    import cv2  # noqa: PLC0415

    rgb = rgba[..., :3].astype(np.float32) / 255.0
    alpha = rgba[..., 3].astype(np.float32) / 255.0
    # Jasność percepcyjna (współczynniki Rec. 709).
    luma = 0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]
    if method == "brightness":
        weights = 1.0 - luma if invert else luma
        weights = weights * alpha
    elif method == "edges":
        gray = (luma * 255).astype(np.uint8)
        blurred = cv2.GaussianBlur(gray, (5, 5), 1.4)
        lo = int(40 + 80 * threshold)
        edges = cv2.Canny(blurred, lo, lo * 2)
        weights = (edges > 0).astype(np.float32) * np.maximum(alpha, 0.0)
    elif method == "alpha":
        weights = (alpha > threshold).astype(np.float32)
    else:
        raise ValueError(f"Nieznana metoda próbkowania: {method}")
    weights = weights.astype(np.float64)
    if weights.sum() <= 0:
        # Pusty wynik (np. czarny obraz przy metodzie jasności) — próbkuj równomiernie.
        weights = np.ones_like(weights)
    return weights


def sample_points(rgba: np.ndarray, weights: np.ndarray, count: int, seed: int = 0) -> PointCloud:
    """Losuje ``count`` punktów z wagami i zwraca chmurę w lokalnych współrzędnych."""
    rng = np.random.default_rng(seed)
    h, w = weights.shape
    flat = weights.ravel()
    probabilities = flat / flat.sum()
    idx = rng.choice(flat.size, size=int(count), replace=True, p=probabilities)
    rows, cols = np.divmod(idx, w)
    # Losowe przesunięcie w obrębie piksela (rozmywa siatkę pikseli).
    jitter = rng.random((len(idx), 2))
    px = cols + jitter[:, 0]
    py = rows + jitter[:, 1]
    longest = max(w, h)
    # Środek obrazu → (0, 0); dłuższy bok → [-1, 1]; oś Y odwrócona (w górę).
    x = (px - w / 2.0) / (longest / 2.0)
    y = -(py - h / 2.0) / (longest / 2.0)
    rest = np.stack((x, y), axis=1).astype(np.float32)
    colors = rgba[rows, cols].astype(np.float32) / 255.0
    colors[:, 3] = 1.0
    return PointCloud(rest, colors, (w / longest, h / longest))


@lru_cache(maxsize=8)
def image_to_points(path: str, method: str = "brightness", count: int = 20000,
                    invert: bool = False, threshold: float = 0.5, seed: int = 0) -> PointCloud:
    """Pełny potok: plik → wagi → chmura punktów. Wynik jest cache'owany."""
    rgba = load_image_rgba(path)
    weights = compute_weights(rgba, method, invert, threshold)
    return sample_points(rgba, weights, count, seed)


def make_default_image(path: str, text: str = "OSCIVIZ") -> str:
    """Tworzy domyślny obraz (napis z poświatą), gdy użytkownik nie wybrał własnego."""
    import cv2  # noqa: PLC0415

    w, h = 1024, 512
    img = np.zeros((h, w, 4), dtype=np.uint8)
    font = cv2.FONT_HERSHEY_DUPLEX
    scale, thick = 4.2, 14
    (tw, th), _ = cv2.getTextSize(text, font, scale, thick)
    org = ((w - tw) // 2, (h + th) // 2)
    cv2.putText(img, text, org, font, scale, (255, 255, 255, 255), thick, cv2.LINE_AA)
    # Gradient koloru po osi X: fiolet → cyjan (kanały BGR).
    gradient = np.linspace(0, 1, w, dtype=np.float32)[None, :]
    mask = img[..., 3] > 0
    b = (255 * (0.95 - 0.1 * gradient)).repeat(h, 0)
    g = (255 * (0.35 + 0.55 * gradient)).repeat(h, 0)
    r = (255 * (0.65 - 0.55 * gradient)).repeat(h, 0)
    img[..., 0] = np.where(mask, b, 0)
    img[..., 1] = np.where(mask, g, 0)
    img[..., 2] = np.where(mask, r, 0)
    cv2.imwrite(path, img)
    return path
