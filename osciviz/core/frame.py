"""Kontekst klatki: wszystko, czego renderer i symulacja potrzebują o dźwięku.

Ten sam ``FrameContext`` powstaje w podglądzie (z zegara odtwarzacza albo
bufora na żywo) i w eksporcie (z czasu ``start + i / fps``), dzięki czemu
podgląd i plik MP4 są liczone tym samym kodem.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from osciviz.core.analysis import AnalysisResult, Analyzer

WINDOW_SECONDS = 0.30  # ile ostatnich próbek trzymamy (najdłuższe okno warstw + zapas)


@dataclass
class FrameContext:
    time: float  # sekundy od początku utworu (w trybie na żywo: czas sesji)
    dt: float  # krok czasu od poprzedniej klatki
    sample_rate: int
    samples: np.ndarray  # (n, 2) float32 — najnowsze próbki, ostatnia = „teraz”
    analysis: AnalysisResult
    playing: bool = True


def window_length(sample_rate: int, fft_size: int) -> int:
    return max(fft_size, int(sample_rate * WINDOW_SECONDS))


def build_frame(samples: np.ndarray, sample_rate: int, analyzer: Analyzer,
                time: float, dt: float, playing: bool = True) -> FrameContext:
    analysis = analyzer.analyze(samples, sample_rate, dt)
    return FrameContext(time=time, dt=dt, sample_rate=sample_rate, samples=samples,
                        analysis=analysis, playing=playing)


def silent_frame(sample_rate: int = 48000, fft_size: int = 2048) -> FrameContext:
    analyzer = Analyzer(fft_size)
    samples = np.zeros((window_length(sample_rate, fft_size), 2), dtype=np.float32)
    return build_frame(samples, sample_rate, analyzer, 0.0, 1 / 60)
