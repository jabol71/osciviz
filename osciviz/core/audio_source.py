"""Abstrakcja źródła dźwięku: plik albo przechwytywanie na żywo.

Analiza i warstwy korzystają tylko z interfejsu ``AudioSource``:
``get_window(n_samples)`` zwraca ostatnie ``n`` próbek przed bieżącą chwilą
jako ``np.ndarray`` o kształcie ``(n, 2)`` i typie float32. Dzięki temu kod
wizualizacji nie wie (i nie musi wiedzieć), skąd pochodzi dźwięk.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from osciviz.core.ring_buffer import RingBuffer
from osciviz.core.sd import get_sounddevice


def load_audio_file(path: str | Path) -> tuple[np.ndarray, int]:
    """Wczytuje plik audio do tablicy ``(n, 2)`` float32.

    Obsługiwane formaty to te, które zna libsndfile (WAV, FLAC, OGG, MP3, AIFF).
    Mono jest duplikowane na dwa kanały, a więcej niż 2 kanały — obcinane.
    """
    import soundfile as sf  # noqa: PLC0415  (import tylko, gdy naprawdę potrzebny)

    data, sample_rate = sf.read(str(path), dtype="float32", always_2d=True)
    if data.shape[1] == 1:
        data = np.repeat(data, 2, axis=1)
    elif data.shape[1] > 2:
        data = data[:, :2]
    return np.ascontiguousarray(data), int(sample_rate)


class AudioSource:
    """Interfejs źródła audio."""

    sample_rate: int = 48000
    is_live: bool = False

    def get_window(self, n_samples: int) -> np.ndarray:  # pragma: no cover - interfejs
        raise NotImplementedError

    def close(self) -> None:
        """Zwalnia zasoby (strumienie audio)."""


class SilentSource(AudioSource):
    """Źródło zastępcze, gdy nic nie wczytano — zwraca ciszę."""

    def get_window(self, n_samples: int) -> np.ndarray:
        return np.zeros((n_samples, 2), dtype=np.float32)


class FileSource(AudioSource):
    """Dźwięk z pliku; pozycję (zegar) ustawia ``AudioPlayer`` lub eksporter."""

    def __init__(self, path: str | Path | None = None, data: np.ndarray | None = None,
                 sample_rate: int = 48000) -> None:
        if path is not None:
            data, sample_rate = load_audio_file(path)
        if data is None:
            raise ValueError("Podaj ścieżkę pliku albo dane")
        self.path = str(path) if path is not None else None
        self.data = data
        self.sample_rate = int(sample_rate)
        self.position = 0  # indeks próbki „teraz”

    @property
    def n_samples(self) -> int:
        return len(self.data)

    @property
    def duration(self) -> float:
        return self.n_samples / self.sample_rate

    def window_at(self, end_sample: int, n_samples: int) -> np.ndarray:
        """Zwraca ``n`` próbek kończących się na ``end_sample`` (z zerami poza plikiem)."""
        start = end_sample - n_samples
        out = np.zeros((n_samples, 2), dtype=np.float32)
        a = max(start, 0)
        b = min(end_sample, self.n_samples)
        if b > a:
            out[a - start: b - start] = self.data[a:b]
        return out

    def get_window(self, n_samples: int) -> np.ndarray:
        return self.window_at(self.position, n_samples)

    def peaks(self, n_columns: int) -> np.ndarray:
        """Min/max sygnału mono w ``n_columns`` kolumnach — do miniatury na osi czasu."""
        n_columns = max(1, int(n_columns))
        mono = self.data.mean(axis=1)
        usable = (len(mono) // n_columns) * n_columns
        if usable == 0:
            return np.zeros((n_columns, 2), dtype=np.float32)
        blocks = mono[:usable].reshape(n_columns, -1)
        return np.stack((blocks.min(axis=1), blocks.max(axis=1)), axis=1)


class LiveSource(AudioSource):
    """Przechwytywanie na żywo przez ``sounddevice.InputStream`` (np. BlackHole 2ch).

    Callback strumienia robi tylko jedno: kopiuje blok do bufora kołowego
    (i opcjonalnie podaje go nagrywarce przez kolejkę). Żadnej analizy,
    alokacji ani logowania — to wymóg pracy w wątku czasu rzeczywistego.
    """

    is_live = True

    def __init__(self, device=None, sample_rate: int | None = None,
                 blocksize: int = 512, buffer_seconds: float = 2.0) -> None:
        sd = get_sounddevice()
        if sd is None:
            raise RuntimeError("Biblioteka sounddevice/PortAudio jest niedostępna")
        if sample_rate is None:
            info = sd.query_devices(device, "input")
            sample_rate = int(info["default_samplerate"]) or 48000
        self.sample_rate = int(sample_rate)
        self.device = device
        self.buffer = RingBuffer(int(self.sample_rate * buffer_seconds), channels=2)
        self.recorder = None  # ustawiane z zewnątrz (core.recorder.Recorder)
        self._stream = sd.InputStream(
            device=device, channels=2, samplerate=self.sample_rate,
            blocksize=blocksize, dtype="float32", callback=self._callback,
        )
        self._stream.start()

    def _callback(self, indata, frames, time_info, status) -> None:  # wątek audio
        self.buffer.write(indata)
        recorder = self.recorder
        if recorder is not None:
            recorder.push(indata)

    def get_window(self, n_samples: int) -> np.ndarray:
        return self.buffer.latest(n_samples)

    def close(self) -> None:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None


def list_input_devices() -> list[dict]:
    """Lista urządzeń wejściowych: ``[{index, name, channels, samplerate, is_blackhole}]``."""
    sd = get_sounddevice()
    if sd is None:
        return []
    result = []
    try:
        devices = sd.query_devices()
    except Exception:
        return []
    for index, dev in enumerate(devices):
        if dev.get("max_input_channels", 0) > 0:
            result.append({
                "index": index,
                "name": dev["name"],
                "channels": dev["max_input_channels"],
                "samplerate": dev.get("default_samplerate", 48000),
                "is_blackhole": "blackhole" in dev["name"].lower(),
            })
    return result
