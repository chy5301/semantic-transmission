import numpy as np

from scripts.poc.h1_h2.iou import edge_iou, recanny_iou


def _mask(coords, shape=(10, 10)):
    m = np.zeros(shape, dtype=np.uint8)
    for y, x in coords:
        m[y, x] = 255
    return m


def test_identical_masks_iou_is_one():
    m = _mask([(1, 1), (2, 2), (3, 3)])
    assert edge_iou(m, m) == 1.0


def test_disjoint_masks_iou_is_zero():
    a = _mask([(1, 1)])
    b = _mask([(8, 8)])
    assert edge_iou(a, b) == 0.0


def test_partial_overlap_known_value():
    # 交集 1 像素，并集 3 像素 → 1/3
    a = _mask([(1, 1), (2, 2)])
    b = _mask([(2, 2), (5, 5)])
    assert abs(edge_iou(a, b) - 1 / 3) < 1e-9


def test_empty_union_returns_zero():
    z = np.zeros((10, 10), dtype=np.uint8)
    assert edge_iou(z, z) == 0.0


def test_dilation_recovers_one_pixel_offset():
    a = _mask([(5, 5)])
    b = _mask([(5, 6)])  # 错位 1px
    assert edge_iou(a, b) == 0.0
    assert edge_iou(a, b, dilation=3) > 0.0


def test_recanny_iou_of_solid_image_runs():
    img = np.zeros((32, 32, 3), dtype=np.uint8)
    img[8:24, 8:24] = 255  # 一个方块 → 有边缘
    canny_in = np.zeros((32, 32), dtype=np.uint8)
    val = recanny_iou(img, canny_in)
    assert 0.0 <= val <= 1.0
