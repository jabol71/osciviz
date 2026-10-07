"""Analiza sygnału: okna, FFT, energie pasm i obwiednie.

Wszystkie funkcje poza klasą ``Envelope`` są *czyste* (bez stanu), dzięki czemu
łatwo je testować na sygnałach syntetycznych (np. sinus o znanej częstotliwości).

Przepływ dla jednej klatki:

1. bierzemy ostatnie ``fft_size`` próbek (mono = średnia kanałów),
2. mnożymy przez okno Hanna — wygasza krawędzie fragmentu, dzięki czemu
   FFT nie „widzi” sztucznego skoku na brzegach (mniejszy przeciek widma),
3. ``np.fft.rfft`` daje widmo dla częstotliwości 0 … fs/2,
4. amplitudy zamieniamy na decybele i normalizujemy do ``[0, 1]``
   (``-80 dB`` → 0, ``0 dB`` → 1), co nadaje się wprost do animacji.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

DB_FLOOR = -80.0  # poziom, poniżej którego traktujemy sygnał jako ciszę

DEFAULT_BANDS = {
    "bass": (20.0, 150.0),
    "mid": (150.0, 2000.0),
    "high": (2000.0, 16000.0),
}


def to_mono(samples: np.ndarray) -> np.ndarray:
    """Zamienia próbki ``(n, 2)`` na mono ``(n,)`` jako średnią kanałów."""
    if samples.ndim == 1:
        return samples.astype(np.float32, copy=False)
    return samples.mean(axis=1).astype(np.float32)


def hann_window(n: int) -> np.ndarray:
    """Okno Hanna długości ``n``: w[k] = 0.5 − 0.5·cos(2πk/(n−1))."""
    return np.hanning(n).astype(np.float32)


def magnitude_spectrum(mono: np.ndarray, fft_size: int = 2048) -> np.ndarray:
    """Zwraca amplitudy widma (liniowe) dla ostatnich ``fft_size`` próbek.

    Amplituda jest skalowana tak, by sinus o amplitudzie 1 dał wartość ≈ 1
    w swoim prążku: dzielimy przez sumę okna i mnożymy przez 2 (bo rfft
    pokazuje tylko połowę widma — druga połowa jest lustrzana).
    """
    if len(mono) < fft_size:
        mono = np.pad(mono, (fft_size - len(mono), 0))
    frame = mono[-fft_size:]
    window = hann_window(fft_size)
    spectrum = np.fft.rfft(frame * window)
    return (np.abs(spectrum) * 2.0 / window.sum()).astype(np.float32)


def fft_frequencies(fft_size: int, sample_rate: float) -> np.ndarray:
    """Częstotliwości (Hz) odpowiadające kolejnym prążkom ``rfft``."""
    return np.fft.rfftfreq(fft_size, d=1.0 / sample_rate).astype(np.float32)


def amplitude_to_norm_db(amplitude: np.ndarray | float, floor_db: float = DB_FLOOR):
    """Amplituda liniowa → dB → wartość w ``[0, 1]`` (``floor_db`` → 0, 0 dB → 1)."""
    db = 20.0 * np.log10(np.maximum(amplitude, 1e-9))
    return np.clip((db - floor_db) / -floor_db, 0.0, 1.0)


def band_energy(mags: np.ndarray, freqs: np.ndarray, lo: float, hi: float) -> float:
    """Energia pasma ``[lo, hi]`` Hz znormalizowana do ``[0, 1]``.

    Liczymy pierwiastek z sumy kwadratów amplitud w paśmie (energia sygnału
    w tym paśmie, niezależna od tego, ile prążków pasmo obejmuje), a potem
    przeliczamy na skalę dB.
    """
    mask = (freqs >= lo) & (freqs <= hi)
    if not np.any(mask):
        return 0.0
    rms = float(np.sqrt(np.sum(mags[mask] ** 2)))
    return float(amplitude_to_norm_db(rms))


def log_bands(
    mags: np.ndarray, freqs: np.ndarray, n_bands: int, f_min: float, f_max: float,
    log_scale: bool = True,
) -> np.ndarray:
    """Dzieli widmo na ``n_bands`` pasm i zwraca ich poziomy w ``[0, 1]``.

    Przy skali logarytmicznej granice pasm rozkładają się równomiernie
    w log(f) — tak słyszy człowiek (oktawa 50–100 Hz „waży” tyle co 5–10 kHz).
    Pasmo, w które nie wpada żaden prążek (wąskie pasma przy niskich f),
    bierze wartość z najbliższego prążka.
    """
    f_min = max(f_min, freqs[1] if len(freqs) > 1 else 1.0)
    f_max = max(f_max, f_min * 1.01)
    if log_scale:
        edges = np.geomspace(f_min, f_max, n_bands + 1)
    else:
        edges = np.linspace(f_min, f_max, n_bands + 1)
    # Dla każdej krawędzi znajdujemy indeks prążka (wektorowo, bez pętli po prążkach).
    idx = np.searchsorted(freqs, edges)
    idx = np.clip(idx, 0, len(mags) - 1)
    lo_idx = idx[:-1]
    hi_idx = np.maximum(idx[1:], lo_idx + 1)
    # Suma kwadratów w przedziałach przez sumy skumulowane: S[hi] − S[lo].
    cumsum = np.concatenate(([0.0], np.cumsum(mags.astype(np.float64) ** 2)))
    energy = np.sqrt(cumsum[hi_idx] - cumsum[lo_idx])
    return amplitude_to_norm_db(energy).astype(np.float32)


@dataclass
class Envelope:
    """Obwiednia (follower) z osobnymi czasami narastania i opadania.

    To wygładzanie wykładnicze: ``y += (x − y) · (1 − e^(−dt/τ))``.
    Gdy sygnał rośnie, używamy krótkiego ``attack`` (szybka reakcja na
    uderzenie stopy), gdy maleje — dłuższego ``release`` (płynne wygasanie).
    """

    attack: float = 0.01  # sekundy
    release: float = 0.15  # sekundy
    value: float = 0.0

    def process(self, x: float, dt: float) -> float:
        tau = self.attack if x > self.value else self.release
        coeff = 1.0 - math.exp(-dt / max(tau, 1e-6))
        self.value += (x - self.value) * coeff
        return self.value

    def reset(self) -> None:
        self.value = 0.0


@dataclass
class AnalysisResult:
    """Wynik analizy jednej klatki (to, co dostają warstwy przez FrameContext)."""

    mags: np.ndarray
    freqs: np.ndarray
    bands: dict[str, float] = field(default_factory=dict)  # wartości surowe [0,1]
    envelopes: dict[str, float] = field(default_factory=dict)  # wygładzone [0,1]


class Analyzer:
    """Liczy FFT i obwiednie pasm klatka po klatce (ma stan — obwiednie)."""

    def __init__(self, fft_size: int = 2048, bands: dict | None = None) -> None:
        self.fft_size = fft_size
        self.bands = dict(bands or DEFAULT_BANDS)
        self.envelopes = {name: Envelope() for name in self.bands}

    def reset(self) -> None:
        for env in self.envelopes.values():
            env.reset()

    def analyze(self, samples: np.ndarray, sample_rate: float, dt: float) -> AnalysisResult:
        mono = to_mono(samples)
        mags = magnitude_spectrum(mono, self.fft_size)
        freqs = fft_frequencies(self.fft_size, sample_rate)
        raw = {name: band_energy(mags, freqs, lo, hi) for name, (lo, hi) in self.bands.items()}
        smooth = {name: self.envelopes[name].process(raw[name], dt) for name in raw}
        return AnalysisResult(mags=mags, freqs=freqs, bands=raw, envelopes=smooth)
