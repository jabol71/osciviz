"""Loopback WASAPI: logika niezależna od sprzętu (nazwy, cisza po przerwie)."""

import time

import numpy as np

from osciviz.core import loopback
from osciviz.core.ring_buffer import RingBuffer


def test_clean_name():
    assert loopback.clean_name("Speakers (Realtek(R) Audio) [Loopback]") == "Speakers (Realtek(R) Audio)"


def _fake_source(channels: int) -> loopback.LoopbackSource:
    # Obiekt bez otwierania strumienia: sprawdzamy tylko callback i get_window.
    src = loopback.LoopbackSource.__new__(loopback.LoopbackSource)
    src._channels = channels
    src.buffer = RingBuffer(4800, channels=2)
    src.recorder = None
    src._last_block = 0.0
    src._continue = 0
    return src


def test_callback_takes_first_two_channels_of_surround():
    src = _fake_source(6)
    frames = np.tile(np.arange(6, dtype=np.float32), (256, 1))  # kanał k ma wartość k
    src._callback(frames.tobytes(), 256, None, 0)
    window = src.get_window(256)
    assert window.shape == (256, 2)
    assert np.allclose(window[:, 0], 0.0) and np.allclose(window[:, 1], 1.0)


def test_mono_is_duplicated():
    src = _fake_source(1)
    src._callback(np.full(128, 0.5, dtype=np.float32).tobytes(), 128, None, 0)
    assert np.allclose(src.get_window(128), 0.5)


def test_silence_after_gap():
    src = _fake_source(2)
    src._callback(np.ones((128, 2), dtype=np.float32).tobytes(), 128, None, 0)
    src._last_block = time.perf_counter() - 1.0  # od sekundy nic nie przyszło
    assert not src.get_window(128).any()


def test_unavailable_off_windows(monkeypatch):
    monkeypatch.setattr(loopback, "_pyaudio", None)
    monkeypatch.setattr(loopback, "_import_failed", False)
    monkeypatch.setattr(loopback.sys, "platform", "darwin")
    assert loopback.list_loopback_devices() == []
