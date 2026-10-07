"""Leniwy import biblioteki ``sounddevice``.

``sounddevice`` wymaga systemowej biblioteki PortAudio. Na macOS jest ona
dołączona do paczki, ale w środowiskach bez karty dźwiękowej (CI, serwer)
import może się nie udać. Wtedy aplikacja działa dalej: odtwarzanie używa
zegara systemowego (bez dźwięku), a tryb „na żywo” jest niedostępny.
"""

from __future__ import annotations

_sd = None
_error: str | None = None


def get_sounddevice():
    """Zwraca moduł ``sounddevice`` albo ``None``, jeśli jest niedostępny."""
    global _sd, _error
    if _sd is None and _error is None:
        try:
            import sounddevice  # noqa: PLC0415

            _sd = sounddevice
        except Exception as exc:  # OSError, gdy brak PortAudio
            _error = str(exc)
    return _sd


def import_error() -> str | None:
    get_sounddevice()
    return _error
