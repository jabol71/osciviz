import numpy as np

from osciviz.scene.particles import ParticleSystem


def make_system(n=500):
    rng = np.random.default_rng(0)
    rest = rng.uniform(-1, 1, (n, 2)).astype(np.float32)
    colors = np.ones((n, 4), np.float32)
    return ParticleSystem(rest, colors, seed=0)


def test_without_bass_particles_return_to_rest():
    system = make_system()
    for _ in range(30):  # pół sekundy uderzeń basu
        system.step(1 / 60, drive=1.0, strength=10, stiffness=40, damping=6)
    assert np.abs(system.pos - system.rest).max() > 0.05
    for _ in range(600):  # 10 s ciszy
        system.step(1 / 60, drive=0.0, strength=10, stiffness=40, damping=6)
    assert np.abs(system.pos - system.rest).max() < 1e-3


def test_radial_push_moves_outwards():
    system = make_system()
    r0 = np.linalg.norm(system.rest, axis=1)
    for _ in range(10):
        system.step(1 / 60, drive=1.0, strength=10, stiffness=40, damping=6, mode="radial")
    assert np.mean(np.linalg.norm(system.pos, axis=1) - r0) > 0


def test_stable_with_large_step_and_stiffness():
    system = make_system()
    for _ in range(100):
        system.step(1 / 15, drive=1.0, strength=20, stiffness=200, damping=1, mode="jitter")
    assert np.all(np.isfinite(system.pos))
    assert np.abs(system.pos).max() < 10
