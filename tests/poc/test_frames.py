import imageio.v3 as iio
import numpy as np
import pytest

from scripts.poc.h1_h2.frames import extract_frames, resize_frame


def _make_video(path, n=10, h=48, w=64):
    frames = []
    for i in range(n):
        f = np.full((h, w, 3), i * 20, dtype=np.uint8)  # 每帧亮度不同，便于辨认
        frames.append(f)
    iio.imwrite(path, np.stack(frames), fps=6, codec="libx264")


def test_extract_specific_indices(tmp_path):
    vid = tmp_path / "synthetic.mp4"
    _make_video(vid, n=10)
    out = extract_frames(vid, [0, 5, 9])
    assert len(out) == 3
    assert out[0].shape[2] == 3
    # 帧 5 应比帧 0 亮
    assert out[1].mean() > out[0].mean()


def test_out_of_range_raises(tmp_path):
    vid = tmp_path / "synthetic.mp4"
    _make_video(vid, n=5)
    with pytest.raises(IndexError):
        extract_frames(vid, [99])


def test_resize_to_square():
    f = np.zeros((48, 64, 3), dtype=np.uint8)
    r = resize_frame(f, 512)
    assert r.shape == (512, 512, 3)
