"""Bufor kołowy na próbki audio w trybie „na żywo”.

Callback karty dźwiękowej (wątek audio) dopisuje bloki próbek, a wątek GUI
co klatkę czyta *najnowsze* N próbek. Bufor ma stały rozmiar, więc nie
alokuje pamięci w trakcie pracy — to ważne, bo w callbacku audio nie wolno
robić nic kosztownego.

Dostęp z dwóch wątków chroni ``threading.Lock``. Sekcja krytyczna to tylko
kopiowanie tablic numpy, więc blokada trwa mikrosekundy.
"""

from __future__ import annotations

import threading

import numpy as np


class RingBuffer:
    """Bufor kołowy próbek stereo o kształcie ``(capacity, channels)``."""

    def __init__(self, capacity: int, channels: int = 2) -> None:
        if capacity <= 0:
            raise ValueError("capacity musi być dodatnie")
        self.capacity = int(capacity)
        self.channels = int(channels)
        self._data = np.zeros((self.capacity, self.channels), dtype=np.float32)
        self._write_pos = 0  # indeks, pod który trafi następna próbka
        self._total_written = 0  # ile próbek łącznie zapisano (licznik monotoniczny)
        self._lock = threading.Lock()

    @property
    def total_written(self) -> int:
        """Łączna liczba zapisanych próbek (przydatne jako zegar trybu na żywo)."""
        with self._lock:
            return self._total_written

    def write(self, block: np.ndarray) -> None:
        """Dopisuje blok próbek ``(n, channels)``; najstarsze dane są nadpisywane."""
        n = len(block)
        if n == 0:
            return
        with self._lock:
            if n >= self.capacity:
                # Blok większy niż bufor: zostaje tylko jego końcówka.
                self._data[:] = block[-self.capacity:]
                self._write_pos = 0
            else:
                end = self._write_pos + n
                if end <= self.capacity:
                    self._data[self._write_pos:end] = block
                else:
                    # Zawijanie: część na koniec bufora, reszta na początek.
                    first = self.capacity - self._write_pos
                    self._data[self._write_pos:] = block[:first]
                    self._data[: n - first] = block[first:]
                self._write_pos = end % self.capacity
            self._total_written += n

    def latest(self, n: int) -> np.ndarray:
        """Zwraca kopię ``n`` najnowszych próbek (najstarsza pierwsza).

        Jeśli zapisano mniej niż ``n`` próbek, początek jest wypełniony zerami.
        """
        n = int(n)
        out = np.zeros((n, self.channels), dtype=np.float32)
        with self._lock:
            available = min(n, self.capacity, self._total_written)
            if available == 0:
                return out
            start = (self._write_pos - available) % self.capacity
            if start + available <= self.capacity:
                chunk = self._data[start:start + available]
            else:
                chunk = np.concatenate(
                    (self._data[start:], self._data[: (start + available) - self.capacity])
                )
            out[n - available:] = chunk
        return out

    def clear(self) -> None:
        with self._lock:
            self._data[:] = 0
            self._write_pos = 0
            self._total_written = 0
