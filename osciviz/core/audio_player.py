"""Odtwarzanie pliku audio i zegar nadrzędny.

Najważniejsza zasada synchronizacji: **licznik odtworzonych próbek jest
zegarem**. Callback ``sounddevice.OutputStream`` podaje kolejne bloki
z tablicy i przesuwa licznik. GUI co klatkę czyta ten licznik i rysuje
falę z tego miejsca, więc obraz nie „odjeżdża” od dźwięku.

Gdy PortAudio jest niedostępne (CI, brak karty), używamy zegara
``time.perf_counter`` — wizualizacja działa, tylko bez dźwięku.
"""

from __future__ import annotations

import threading
import time

import numpy as np

from osciviz.core.audio_source import FileSource
from osciviz.core.sd import get_sounddevice


class AudioPlayer:
    """Odtwarza ``FileSource``; udostępnia pozycję w próbkach i sekundach."""

    def __init__(self) -> None:
        self.source: FileSource | None = None
        self.volume = 1.0
        self._position = 0
        self._playing = False
        self._stream = None
        self._lock = threading.Lock()
        # Zegar zastępczy (bez karty dźwiękowej).
        self._fallback_t0 = 0.0
        self._fallback_pos0 = 0

    # --- właściwości -------------------------------------------------------
    @property
    def is_playing(self) -> bool:
        return self._playing

    @property
    def position(self) -> int:
        """Bieżąca pozycja w próbkach."""
        if self._playing and self._stream is None and self.source is not None:
            elapsed = time.perf_counter() - self._fallback_t0
            pos = self._fallback_pos0 + int(elapsed * self.source.sample_rate)
            if pos >= self.source.n_samples:
                self._playing = False
                pos = self.source.n_samples
                self._position = pos
            return pos
        with self._lock:
            return self._position

    @property
    def time(self) -> float:
        if self.source is None:
            return 0.0
        return self.position / self.source.sample_rate

    # --- sterowanie ----------------------------------------------------------
    def set_source(self, source: FileSource | None) -> None:
        self.stop()
        self.source = source
        self._position = 0

    def play(self) -> None:
        if self.source is None or self._playing:
            return
        if self._position >= self.source.n_samples:
            self._position = 0
        sd = get_sounddevice()
        self._playing = True
        if sd is None:
            self._start_fallback()
            return
        try:
            self._stream = sd.OutputStream(
                samplerate=self.source.sample_rate, channels=2, dtype="float32",
                callback=self._callback, finished_callback=self._on_finished,
            )
            self._stream.start()
        except Exception:
            # Brak urządzenia wyjściowego — gramy „po cichu” na zegarze systemowym.
            self._stream = None
            self._start_fallback()

    def pause(self) -> None:
        if not self._playing:
            return
        pos = self.position
        self._playing = False
        self._close_stream()
        with self._lock:
            self._position = pos

    def stop(self) -> None:
        self.pause()
        with self._lock:
            self._position = 0

    def toggle(self) -> None:
        if self._playing:
            self.pause()
        else:
            self.play()

    def seek(self, seconds: float) -> None:
        if self.source is None:
            return
        pos = int(np.clip(seconds * self.source.sample_rate, 0, self.source.n_samples))
        with self._lock:
            self._position = pos
        self._fallback_pos0 = pos
        self._fallback_t0 = time.perf_counter()

    # --- wnętrze -------------------------------------------------------------
    def _start_fallback(self) -> None:
        self._fallback_pos0 = self._position
        self._fallback_t0 = time.perf_counter()

    def _callback(self, outdata, frames, time_info, status) -> None:  # wątek audio
        src = self.source
        with self._lock:
            start = self._position
            end = min(start + frames, src.n_samples)
            n = end - start
            outdata[:n] = src.data[start:end] * self.volume
            if n < frames:
                outdata[n:] = 0
            self._position = end
        if n < frames:
            raise get_sounddevice().CallbackStop

    def _on_finished(self) -> None:
        if self.source is not None and self._position >= self.source.n_samples:
            self._playing = False

    def _close_stream(self) -> None:
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

    def close(self) -> None:
        self.pause()
