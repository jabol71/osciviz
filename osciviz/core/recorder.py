"""Nagrywanie sesji na żywo do pliku WAV.

Callback audio nie może czekać na dysk, dlatego tylko wrzuca kopię bloku do
``queue.Queue``. Osobny wątek zapisujący wyjmuje bloki z kolejki i dopisuje je
przez ``soundfile.SoundFile``. Nagranie można potem wczytać jak zwykły plik
i wyeksportować do MP4 offline — w pełnej jakości i bez gubienia klatek.
"""

from __future__ import annotations

import queue
import threading
import time
from pathlib import Path

import numpy as np


class Recorder:
    def __init__(self, path: str | Path, sample_rate: int, channels: int = 2) -> None:
        self.path = str(path)
        self.sample_rate = int(sample_rate)
        self.channels = channels
        self._queue: queue.Queue = queue.Queue()
        self._thread: threading.Thread | None = None
        self._running = False
        self.frames_written = 0
        self.started_at = 0.0

    @property
    def is_recording(self) -> bool:
        return self._running

    @property
    def elapsed(self) -> float:
        return self.frames_written / self.sample_rate

    def start(self) -> None:
        self._running = True
        self.started_at = time.monotonic()
        self._thread = threading.Thread(target=self._writer, name="osciviz-recorder", daemon=True)
        self._thread.start()

    def push(self, block: np.ndarray) -> None:
        """Wywoływane z callbacku audio — tylko kopia i wrzucenie do kolejki."""
        if self._running:
            self._queue.put(block.copy())

    def stop(self) -> str:
        """Kończy nagrywanie, czeka na zapis reszty kolejki i zwraca ścieżkę pliku."""
        self._running = False
        self._queue.put(None)  # znacznik końca
        if self._thread is not None:
            self._thread.join(timeout=5.0)
        return self.path

    def _writer(self) -> None:
        import soundfile as sf  # noqa: PLC0415

        with sf.SoundFile(self.path, mode="w", samplerate=self.sample_rate,
                          channels=self.channels, subtype="PCM_24") as f:
            while True:
                block = self._queue.get()
                if block is None:
                    break
                f.write(block)
                self.frames_written += len(block)
