import numpy as np

from osciviz.core.analysis import (
    DEFAULT_BANDS,
    Analyzer,
    Envelope,
    band_energy,
    fft_frequencies,
    log_bands,
    magnitude_spectrum,
)

SR = 48000


def sine(freq, seconds=0.2, amp=0.8):
    t = np.arange(int(SR * seconds)) / SR
    return (amp * np.sin(2 * np.pi * freq * t)).astype(np.float32)


def energies(signal):
    mags = magnitude_spectrum(signal, 2048)
    freqs = fft_frequencies(2048, SR)
    return {name: band_energy(mags, freqs, lo, hi) for name, (lo, hi) in DEFAULT_BANDS.items()}


def test_60hz_sine_peaks_in_bass():
    e = energies(sine(60))
    assert e["bass"] > e["mid"] and e["bass"] > e["high"]


def test_5khz_sine_peaks_in_high_band():
    e = energies(sine(5000))
    assert e["high"] > e["mid"] and e["high"] > e["bass"]


def test_amplitude_scaling_of_spectrum_peak():
    mags = magnitude_spectrum(sine(1000, amp=1.0), 2048)
    assert 0.8 < mags.max() < 1.05  # sinus o amplitudzie 1 → szczyt ≈ 1


def test_silence_is_zero():
    e = energies(np.zeros(4096, np.float32))
    assert all(v == 0.0 for v in e.values())


def test_log_bands_shape_and_range():
    mags = magnitude_spectrum(sine(440), 2048)
    bands = log_bands(mags, fft_frequencies(2048, SR), 32, 30, 16000)
    assert bands.shape == (32,)
    assert bands.min() >= 0 and bands.max() <= 1


def test_envelope_attack_faster_than_release():
    env = Envelope(attack=0.01, release=0.3)
    for _ in range(10):
        env.process(1.0, 1 / 60)
    up = env.value
    for _ in range(10):
        env.process(0.0, 1 / 60)
    assert up > 0.99
    assert env.value > 0.5  # długi release — wartość opada powoli


def test_analyzer_stereo_input():
    stereo = np.stack((sine(60), sine(60)), axis=1)
    result = Analyzer().analyze(stereo, SR, 1 / 60)
    assert result.bands["bass"] > result.bands["high"]
