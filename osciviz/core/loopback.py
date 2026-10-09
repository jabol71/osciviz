"""Przechwytywanie dźwięku systemu na Windows (WASAPI loopback).

Windows potrafi „nagrywać” to, co gra na wybranym urządzeniu wyjściowym
(głośnikach, słuchawkach) — to tzw. loopback interfejsu WASAPI. Dzięki temu
dźwięk z FL Studio można wizualizować bez instalowania wirtualnego kabla.
Minus: nagrywa się wszystko, co gra w systemie, nie tylko FL Studio.

``sounddevice`` (PortAudio z PyPI) nie udostępnia loopbacku, dlatego używamy
biblioteki ``PyAudioWPatch`` — wersji PyAudio z poprawką WASAPI, która dla
każdego wyjścia dodaje urządzenie „[Loopback]”. Biblioteka istnieje tylko na
Windows; na innych systemach ``available()`` zwraca ``False``.

Ważna różnica względem zwykłego wejścia: gdy nic nie gra, WASAPI nie wysyła
żadnych bloków. Bufor kołowy zatrzymałby się na ostatniej klatce, więc po
krótkiej przerwie ``get_window`` zwraca ciszę (zera).
"""

from __future__ import annotations

import sys
import time

import numpy as np

from osciviz.core.audio_source import BufferedSource

# Po takiej przerwie bez danych uznajemy, że w systemie panuje cisza.
SILENCE_AFTER = 0.15  # s

_pyaudio = None
_import_failed = False


def _get_pyaudio():
    """Leniwy import ``pyaudiowpatch``; ``None``, gdy biblioteki nie ma."""
    global _pyaudio, _import_failed
    if _pyaudio is None and not _import_failed and sys.platform == "win32":
        try:
            import pyaudiowpatch  # noqa: PLC0415

            _pyaudio = pyaudiowpatch
        except Exception:
            _import_failed = True
    return _pyaudio


def available() -> bool:
    return _get_pyaudio() is not None


def clean_name(name: str) -> str:
    """„Głośniki (Realtek) [Loopback]” → „Głośniki (Realtek)”."""
    return name.replace("[Loopback]", "").strip()


def list_loopback_devices() -> list[dict]:
    """Urządzenia loopback: ``[{index, name, channels, samplerate, is_default}]``.

    ``is_default`` oznacza loopback domyślnego wyjścia systemu — to właśnie
    przez nie zwykle gra FL Studio, więc wybieramy je automatycznie.
    """
    pa_mod = _get_pyaudio()
    if pa_mod is None:
        return []
    pa = pa_mod.PyAudio()
    try:
        default_name = ""
        try:
            wasapi = pa.get_host_api_info_by_type(pa_mod.paWASAPI)
            default_name = pa.get_device_info_by_index(wasapi["defaultOutputDevice"])["name"]
        except Exception:
            pass
        result = []
        for dev in pa.get_loopback_device_info_generator():
            result.append({
                "index": dev["index"],
                "name": clean_name(dev["name"]),
                "channels": int(dev["maxInputChannels"]),
                "samplerate": int(dev["defaultSampleRate"]),
                "is_default": bool(default_name) and clean_name(dev["name"]) == default_name,
            })
        result.sort(key=lambda d: not d["is_default"])  # domyślne wyjście na początek
        return result
    except Exception:
        return []
    finally:
        pa.terminate()


class LoopbackSource(BufferedSource):
    """Źródło na żywo z loopbacku WASAPI. Interfejs taki sam jak ``LiveSource``."""

    def __init__(self, device_index: int, blocksize: int = 512, buffer_seconds: float = 2.0) -> None:
        pa_mod = _get_pyaudio()
        if pa_mod is None:
            raise RuntimeError("Biblioteka PyAudioWPatch jest niedostępna")
        self._pa = pa_mod.PyAudio()
        try:
            info = self._pa.get_device_info_by_index(device_index)
            self.sample_rate = int(info["defaultSampleRate"])
            # Wyjście 5.1/7.1 ma więcej kanałów — bierzemy dwa pierwsze (lewy, prawy).
            self._channels = max(1, int(info["maxInputChannels"]))
            self.device = device_index
            self._init_buffer(buffer_seconds)
            self._last_block = 0.0
            self._stream = self._pa.open(
                format=pa_mod.paFloat32, channels=self._channels, rate=self.sample_rate,
                input=True, input_device_index=device_index,
                frames_per_buffer=blocksize, stream_callback=self._callback,
            )
            self._continue = pa_mod.paContinue
            self._stream.start_stream()
        except Exception:
            self._pa.terminate()
            raise

    def _callback(self, in_data, frame_count, time_info, status):  # wątek audio
        # Bajty → widok (n, kanały) bez kopiowania; zapis do bufora robi jedyną kopię.
        block = np.frombuffer(in_data, dtype=np.float32).reshape(-1, self._channels)[:, :2]
        self._push(block)
        self._last_block = time.perf_counter()
        return None, self._continue

    def get_window(self, n_samples: int) -> np.ndarray:
        if time.perf_counter() - self._last_block > SILENCE_AFTER:
            return np.zeros((n_samples, 2), dtype=np.float32)
        return super().get_window(n_samples)

    def close(self) -> None:
        if self._stream is not None:
            self._stream.stop_stream()
            self._stream.close()
            self._stream = None
            self._pa.terminate()
