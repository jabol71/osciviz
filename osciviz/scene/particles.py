"""Stan i fizyka cząsteczek (numpy, bez pętli po cząsteczkach).

Każda cząsteczka ma pozycję spoczynkową ``rest`` (piksel obrazu), bieżącą
pozycję ``pos`` i prędkość ``vel``. W każdym kroku działają trzy siły:

    F = push(kierunek, siła · bas)      # wypchnięcie przez uderzenie basu
      + k · (rest − pos)                # sprężyna ciągnąca do obrazu
      − c · vel                         # tłumienie (opór), gasi drgania

i całkujemy półjawną metodą Eulera (najpierw prędkość, potem pozycja):

    vel += F · dt
    pos += vel · dt

Ta kolejność jest stabilniejsza od zwykłego Eulera dla układów sprężyn.
Gdy krok jest duży względem sztywności (``dt·√k`` > 0.25), dzielimy go na
mniejsze podkroki, żeby symulacja nie „wybuchła”.
"""

from __future__ import annotations

import math

import numpy as np

PUSH_MODES = ("radial", "noise", "jitter")


class ParticleSystem:
    def __init__(self, rest_pos: np.ndarray, colors: np.ndarray, seed: int = 0) -> None:
        self.rest = rest_pos.astype(np.float32).copy()
        self.colors = colors.astype(np.float32).copy()
        self.pos = self.rest.copy()
        self.vel = np.zeros_like(self.rest)
        self.rng = np.random.default_rng(seed)
        self.time = 0.0
        # Kierunek promieniowy liczony raz: wektor jednostkowy od środka obrazu.
        norm = np.linalg.norm(self.rest, axis=1, keepdims=True)
        self._radial = self.rest / np.maximum(norm, 1e-4)
        # Indywidualna „czułość” cząsteczek (0.5…1.5) — ruch wygląda organicznie.
        self._weight = (0.5 + self.rng.random((len(self.rest), 1))).astype(np.float32)

    @property
    def count(self) -> int:
        return len(self.rest)

    def push_directions(self, mode: str) -> np.ndarray:
        if mode == "radial":
            return self._radial
        if mode == "noise":
            # Gładkie pole wektorowe z funkcji trygonometrycznych zależnych od
            # położenia i czasu: kąt θ(x, y, t), kierunek = (cos θ, sin θ).
            x, y = self.rest[:, 0], self.rest[:, 1]
            t = self.time
            angle = (np.sin(x * 3.1 + t * 0.9) + np.cos(y * 2.7 - t * 0.6)) * math.pi
            return np.stack((np.cos(angle), np.sin(angle)), axis=1).astype(np.float32)
        # "jitter": losowy kierunek jednostkowy dla każdej cząsteczki co klatkę
        angle = self.rng.random(len(self.rest)) * (2 * math.pi)
        return np.stack((np.cos(angle), np.sin(angle)), axis=1).astype(np.float32)

    def step(self, dt: float, drive: float, strength: float, stiffness: float,
             damping: float, mode: str = "radial") -> None:
        """Jeden krok symulacji; ``drive`` to znormalizowana energia basu ``[0, 1]``."""
        if dt <= 0:
            return
        n_sub = max(1, int(math.ceil(dt * math.sqrt(max(stiffness, 1e-6)) / 0.25)))
        h = dt / n_sub
        directions = self.push_directions(mode)
        push = directions * (strength * drive) * self._weight
        for _ in range(n_sub):  # pętla po podkrokach (zwykle 1–3), nie po cząsteczkach
            force = push + stiffness * (self.rest - self.pos) - damping * self.vel
            self.vel += force * h
            self.pos += self.vel * h
        self.time += dt

    def reset(self) -> None:
        self.pos[:] = self.rest
        self.vel[:] = 0
        self.time = 0.0
