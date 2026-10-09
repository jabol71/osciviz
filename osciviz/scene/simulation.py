"""Stan zależny od historii, liczony klatka po klatce.

Część wizualizacji zależy nie tylko od bieżącej klatki, ale też od
poprzednich: wygładzone słupki widma, obwiednie basu, fizyka cząsteczek.
Ten stan trzymamy w ``Simulation`` — osobno od sceny (scena to dane
projektu) i osobno od renderera (który tylko rysuje).

Podgląd i eksport mają *osobne* obiekty ``Simulation``. Eksport startuje
od zera i stosuje stały krok ``dt = 1/fps``, więc wynik jest powtarzalny.
"""

from __future__ import annotations

import numpy as np

from osciviz.core.analysis import Envelope, band_energy, log_bands
from osciviz.core.frame import FrameContext
from osciviz.core.image_to_points import image_to_points
from osciviz.scene.layers import ParticleLayer, SpectrumLayer
from osciviz.scene.particles import ParticleSystem
from osciviz.scene.scene import Scene


class ParticleState:
    def __init__(self, key: tuple, system: ParticleSystem) -> None:
        self.key = key  # (obraz, metoda, liczba, odwrócenie, próg) — zmiana = przebudowa
        self.system = system
        self.bass = Envelope(attack=0.008, release=0.12)
        self.mid = Envelope(attack=0.05, release=0.3)
        self.high = Envelope(attack=0.02, release=0.2)
        self.drive = 0.0
        self.mid_value = 0.0
        self.high_value = 0.0


class Simulation:
    def __init__(self, max_particles: int | None = None) -> None:
        self.max_particles = max_particles  # niższy limit w podglądzie (wydajność)
        self.spectrum: dict[str, np.ndarray] = {}
        self.particles: dict[str, ParticleState] = {}
        self.errors: dict[str, str] = {}

    def reset(self) -> None:
        self.spectrum.clear()
        for state in self.particles.values():
            state.system.reset()
            for env in (state.bass, state.mid, state.high):
                env.reset()

    def update(self, scene: Scene, frame: FrameContext, default_image: str | None = None) -> None:
        alive = set()
        for layer in scene.layers:
            alive.add(layer.id)
            if isinstance(layer, SpectrumLayer):
                self._update_spectrum(layer, frame)
            elif isinstance(layer, ParticleLayer):
                self._update_particles(layer, frame, scene.seed, default_image)
        # Sprzątanie stanu po usuniętych warstwach.
        for store in (self.spectrum, self.particles):
            for key in list(store):
                if key not in alive:
                    del store[key]

    # --- widmo -------------------------------------------------------------------
    def _update_spectrum(self, layer: SpectrumLayer, frame: FrameContext) -> None:
        p = layer.params
        a = frame.analysis
        values = log_bands(a.mags, a.freqs, int(p["bands"]), p["f_min"], p["f_max"], p["log_scale"])
        # Odcięcie szumu i wzmocnienie: (v − floor) / (1 − floor) · gain, przycięte do [0, 1].
        values = np.clip((values - p["floor"]) / max(1e-3, 1 - p["floor"]) * p["gain"], 0, 1)
        prev = self.spectrum.get(layer.id)
        if prev is None or len(prev) != len(values):
            prev = np.zeros_like(values)
        # Wygładzanie: szybki wzrost, wolny spadek (jak wskaźnik szczytowy).
        s = float(p["smoothing"])
        smoothed = np.where(values > prev, values, prev * s + values * (1 - s))
        self.spectrum[layer.id] = smoothed.astype(np.float32)

    # --- cząsteczki --------------------------------------------------------------
    def _update_particles(self, layer: ParticleLayer, frame: FrameContext, seed: int,
                          default_image: str | None) -> None:
        p = layer.params
        image = p["image"] or default_image
        if not image:
            return
        count = int(p["count"])
        if self.max_particles:
            count = min(count, self.max_particles)
        key = (image, p["method"], count, p["invert"], round(p["threshold"], 3))
        state = self.particles.get(layer.id)
        if state is None or state.key != key:
            try:
                cloud = image_to_points(image, p["method"], count, p["invert"], p["threshold"], seed)
            except Exception as exc:  # brak pliku, uszkodzony obraz
                self.errors[layer.id] = str(exc)
                self.particles.pop(layer.id, None)
                return
            self.errors.pop(layer.id, None)
            layer.set_image_extent(cloud.half_extent)
            state = ParticleState(key, ParticleSystem(cloud.rest_pos, cloud.colors, seed))
            self.particles[layer.id] = state

        a = frame.analysis
        bass = band_energy(a.mags, a.freqs, p["bass_lo"], p["bass_hi"])
        # Bramka czułości: poziom bazowy basu (np. 0.55) nie porusza cząsteczek,
        # dopiero nadwyżka ponad bramkę, rozciągnięta do [0, 1] i podniesiona do
        # kwadratu — wyraźne uderzenia stopy, spokój między nimi.
        gate = p["gate"]
        drive = max(0.0, bass - gate) / max(1e-3, 1.0 - gate)
        state.drive = state.bass.process(drive * drive, frame.dt)
        state.mid_value = state.mid.process(a.bands.get("mid", 0.0), frame.dt)
        state.high_value = state.high.process(a.bands.get("high", 0.0), frame.dt)
        state.system.step(frame.dt, state.drive, p["strength"], p["stiffness"], p["damping"],
                          p["push_mode"])
