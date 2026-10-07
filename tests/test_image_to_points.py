import cv2
import numpy as np
import pytest

from osciviz.core.image_to_points import compute_weights, image_to_points, sample_points


@pytest.fixture
def red_square_png(tmp_path):
    img = np.zeros((100, 200, 4), dtype=np.uint8)
    img[25:75, 75:125] = (0, 0, 255, 255)  # BGRA: czerwony kwadrat na przezroczystym tle
    path = tmp_path / "square.png"
    cv2.imwrite(str(path), img)
    return str(path)


@pytest.mark.parametrize("method", ["brightness", "edges", "alpha"])
def test_point_count_and_range(red_square_png, method):
    cloud = image_to_points(red_square_png, method, 5000, seed=1)
    assert cloud.rest_pos.shape == (5000, 2)
    assert cloud.colors.shape == (5000, 4)
    # Dłuższy bok → [-1, 1], krótszy → [-0.5, 0.5] (proporcje 2:1).
    assert np.all(np.abs(cloud.rest_pos[:, 0]) <= 1.0)
    assert np.all(np.abs(cloud.rest_pos[:, 1]) <= 0.5)
    assert cloud.half_extent == (1.0, 0.5)


def test_alpha_sampling_stays_inside_square(red_square_png):
    cloud = image_to_points(red_square_png, "alpha", 3000, seed=2)
    # Kwadrat: kolumny 75–125 z 200 → x ∈ [-0.25, 0.25].
    assert np.all(np.abs(cloud.rest_pos[:, 0]) <= 0.26)
    assert np.all(np.abs(cloud.rest_pos[:, 1]) <= 0.26)


def test_colors_come_from_image(red_square_png):
    cloud = image_to_points(red_square_png, "alpha", 1000, seed=3)
    assert np.allclose(cloud.colors[:, 0], 1.0)  # R
    assert np.allclose(cloud.colors[:, 1:3], 0.0)  # G, B


def test_brightness_weights_prefer_bright_pixels():
    rgba = np.zeros((10, 10, 4), np.uint8)
    rgba[..., 3] = 255
    rgba[:, 5:, :3] = 255  # prawa połowa biała
    weights = compute_weights(rgba, "brightness")
    cloud = sample_points(rgba, weights, 2000, seed=0)
    assert np.all(cloud.rest_pos[:, 0] >= 0.0)
