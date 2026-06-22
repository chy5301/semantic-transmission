"""video_pipeline 纯函数与编排测试。"""

import pytest
from PIL import Image

from semantic_transmission.pipeline.video_pipeline import (
    _fill_failed_frames,
    identity_postprocess,
)


def _img(color):
    return Image.new("RGB", (8, 8), color=color)


def test_identity_postprocess_returns_same_list():
    frames = [_img((1, 0, 0)), _img((2, 0, 0))]
    assert identity_postprocess(frames) is frames


def test_fill_middle_failed_uses_previous():
    a, b = _img((1, 0, 0)), _img((2, 0, 0))
    result = _fill_failed_frames([a, None, b])
    assert result == [a, a, b]


def test_fill_leading_failed_uses_first_valid():
    a = _img((1, 0, 0))
    result = _fill_failed_frames([None, a])
    assert result == [a, a]


def test_fill_all_failed_raises():
    with pytest.raises(ValueError):
        _fill_failed_frames([None, None])
