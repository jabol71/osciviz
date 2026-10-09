"""Syntetyczny utwór demonstracyjny (generowany w numpy, bez plików).

Dzięki niemu aplikację można pokazać od razu po uruchomieniu, bez szukania
pliku audio. Utwór ma stopę (do cząsteczek), linię basu, akordy i arpeggio
rozstawione w stereo (do oscyloskopu XY). Wszystko jest deterministyczne.
"""

from __future__ import annotations

import numpy as np

SR = 44100
BPM = 124


def _env(n: int, attack: float, decay: float, sr: int = SR) -> np.ndarray:
    t = np.arange(n) / sr
    return np.minimum(1.0, t / max(attack, 1e-4)) * np.exp(-t / decay)


def make_demo_track(seconds: float = 16.0, sr: int = SR) -> np.ndarray:
    n = int(seconds * sr)
    out = np.zeros((n, 2), dtype=np.float64)
    beat = 60.0 / BPM
    rng = np.random.default_rng(7)

    # Stopa: sinus z szybko opadającą częstotliwością (150 → 45 Hz).
    kick_len = int(0.45 * sr)
    tk = np.arange(kick_len) / sr
    freq = 45 + 105 * np.exp(-tk * 28)
    phase = 2 * np.pi * np.cumsum(freq) / sr
    kick = np.sin(phase) * np.exp(-tk * 7.5) * 0.95
    # Hi-hat: szum z wysokim filtrem (różnica sąsiednich próbek).
    hat_len = int(0.06 * sr)
    hat = np.diff(rng.standard_normal(hat_len + 1)) * _env(hat_len, 0.001, 0.015, sr) * 0.12

    # Progresja akordów (Am – F – C – G), częstotliwości w Hz.
    chords = [(220.0, 261.63, 329.63), (174.61, 220.0, 261.63), (261.63, 329.63, 392.0), (196.0, 246.94, 293.66)]
    bass_roots = [55.0, 43.65, 65.41, 49.0]
    bar = 4 * beat
    t_all = np.arange(n) / sr
    for b in range(int(seconds / bar) + 1):
        start = int(b * bar * sr)
        if start >= n:
            break
        idx = b % 4
        # Pad akordowy, lekko rozstrojony między kanałami (szeroka stereofonia).
        seg = slice(start, min(n, start + int(bar * sr)))
        ts = t_all[seg] - b * bar
        env = np.minimum(1, ts / 0.3) * np.minimum(1, (bar - ts) / 0.2)
        for k, f in enumerate(chords[idx]):
            out[seg, 0] += 0.05 * np.sin(2 * np.pi * f * 1.002 * ts + k) * env
            out[seg, 1] += 0.05 * np.sin(2 * np.pi * f * 0.998 * ts + 2 * k) * env
        # Prowadzący dźwięk z przesunięciem fazy o 90° między kanałami — na
        # oscyloskopie XY rysuje figury Lissajous (koło/elipsę) zamiast kreski.
        lead = chords[idx][0] / 2
        out[seg, 0] += 0.22 * np.sin(2 * np.pi * lead * ts) * env
        out[seg, 1] += 0.22 * np.sin(2 * np.pi * lead * 1.5 * ts + np.pi / 2) * env
        # Bas na ósemkach.
        for e in range(8):
            s = start + int(e * beat / 2 * sr)
            ln = int(beat / 2 * sr * 0.9)
            if s + ln > n:
                break
            tb = np.arange(ln) / sr
            f = bass_roots[idx] * (2 if e % 4 == 3 else 1)
            tone = np.tanh(2.2 * np.sin(2 * np.pi * f * tb)) * _env(ln, 0.005, 0.18) * 0.32
            out[s:s + ln, 0] += tone
            out[s:s + ln, 1] += tone
        # Arpeggio na szesnastkach, przesuwane między kanałami.
        for e in range(16):
            s = start + int(e * beat / 4 * sr)
            ln = int(beat / 4 * sr)
            if s + ln > n:
                break
            ta = np.arange(ln) / sr
            f = chords[idx][e % 3] * 2
            pan = 0.5 + 0.45 * np.sin(e * 0.8)
            tone = np.sin(2 * np.pi * f * ta) * _env(ln, 0.002, 0.07) * 0.1
            out[s:s + ln, 0] += tone * (1 - pan)
            out[s:s + ln, 1] += tone * pan

    for q in range(int(seconds / beat)):
        s = int(q * beat * sr)
        if s + kick_len <= n:
            out[s:s + kick_len] += kick[:, None]
        h = s + int(beat / 2 * sr)
        if h + hat_len <= n:
            out[h:h + hat_len] += hat[:, None]

    # Delikatne łagodne ograniczenie i fade in/out.
    out = np.tanh(out * 1.1) * 0.9
    fade = int(0.05 * sr)
    out[:fade] *= np.linspace(0, 1, fade)[:, None]
    out[-fade:] *= np.linspace(1, 0, fade)[:, None]
    return out.astype(np.float32)


def write_demo_wav(path: str, seconds: float = 16.0) -> str:
    import soundfile as sf  # noqa: PLC0415

    sf.write(path, make_demo_track(seconds), SR, subtype="PCM_16")
    return path
