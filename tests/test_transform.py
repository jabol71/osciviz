import math

import numpy as np

from osciviz.scene.transform import Transform, apply_point, corners, hit_test


def test_identity_matrix():
    assert np.allclose(Transform().matrix(), np.eye(3))


def test_composition_translate_rotate_scale():
    t = Transform(x=1.0, y=2.0, sx=2.0, sy=3.0, rotation=90.0)
    # Punkt (1, 0): skala → (2, 0), obrót o 90° → (0, 2), przesunięcie → (1, 4).
    x, y = apply_point(t.matrix(), 1.0, 0.0)
    assert math.isclose(x, 1.0, abs_tol=1e-9)
    assert math.isclose(y, 4.0, abs_tol=1e-9)


def test_inverse_is_inverse():
    t = Transform(x=-0.3, y=0.7, sx=1.7, sy=0.4, rotation=33.0)
    assert np.allclose(t.matrix() @ t.inverse(), np.eye(3))
    assert np.allclose(t.inverse(), np.linalg.inv(t.matrix()))


def test_hit_test_after_rotation_and_scale():
    t = Transform(x=1.0, y=0.0, sx=2.0, sy=0.5, rotation=90.0)
    half = (1.0, 1.0)
    # Po obrocie o 90° prostokąt 4 × 1 stoi pionowo: X ∈ [0.5, 1.5], Y ∈ [-2, 2].
    assert hit_test(t, half, 1.0, 1.9)
    assert hit_test(t, half, 1.4, -1.5)
    assert not hit_test(t, half, 1.9, 0.0)
    assert not hit_test(t, half, 1.0, 2.2)


def test_corners_order_and_position():
    pts = corners(Transform(x=1, y=1), (0.5, 0.25))
    assert np.allclose(pts, [[0.5, 0.75], [1.5, 0.75], [1.5, 1.25], [0.5, 1.25]])
