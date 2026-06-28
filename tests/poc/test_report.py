import numpy as np

from scripts.poc.h1_h2.report import comparison_grid, consecutive_strip, write_iou_table


def test_consecutive_strip_concatenates_width():
    imgs = [np.zeros((32, 32, 3), np.uint8) for _ in range(4)]
    strip = consecutive_strip(imgs)
    assert strip.shape == (32, 128, 3)


def test_comparison_grid_runs_and_shapes():
    f = np.zeros((64, 64, 3), np.uint8)
    c = np.zeros((64, 64), np.uint8)
    grid = comparison_grid(f, c, f, c, f, c, 0.31, 0.55)
    assert grid.ndim == 3 and grid.shape[2] == 3


def test_write_iou_table_means(tmp_path):
    klein = [{"index": 0, "iou": 0.2}, {"index": 1, "iou": 0.4}]
    qwen = [{"index": 0, "iou": 0.5}, {"index": 1, "iou": 0.7}]
    summary = write_iou_table(klein, qwen, tmp_path)
    assert abs(summary["klein_mean"] - 0.3) < 1e-9
    assert abs(summary["qwen_mean"] - 0.6) < 1e-9
    assert (tmp_path / "iou_table.json").exists()
    assert (tmp_path / "iou_table.md").exists()
