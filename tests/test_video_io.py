"""video_io 帧序列读写往返测试。"""

import numpy as np
import pytest
from PIL import Image

from semantic_transmission.common.video_io import read_frames, write_frames


def test_write_then_read_roundtrip(tmp_path):
    """写 3 帧再读回，帧数与尺寸一致。"""
    frames = [Image.new("RGB", (64, 48), color=(i * 60, 0, 0)) for i in range(3)]
    out = tmp_path / "clip.mp4"

    write_frames(out, frames, fps=10.0)
    read, meta = read_frames(out)

    assert len(read) == 3
    assert meta.width == 64
    assert meta.height == 48
    assert meta.frame_count == 3
    assert read[0].dtype == np.uint8
    assert read[0].shape == (48, 64, 3)


def test_write_empty_frames_raises(tmp_path):
    """空帧列表抛 ValueError。"""
    with pytest.raises(ValueError):
        write_frames(tmp_path / "x.mp4", [], fps=10.0)


def test_read_corrupt_file_raises(tmp_path):
    """损坏/非视频文件抛 ValueError。"""
    broken = tmp_path / "broken.mp4"
    broken.write_bytes(b"not a real video")
    with pytest.raises(ValueError):
        read_frames(broken)
