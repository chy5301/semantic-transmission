"""video_pipeline 纯函数与编排测试。"""

import pytest
from PIL import Image

from semantic_transmission.common.video_io import read_frames, write_frames
from semantic_transmission.pipeline.video_pipeline import (
    VideoPipeline,
    _fill_failed_frames,
    identity_postprocess,
)
from semantic_transmission.receiver.base import BaseReceiver
from semantic_transmission.sender.local_condition_extractor import LocalCannyExtractor


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


class _FakeReceiver(BaseReceiver):
    """不碰 GPU 的接收端：按调用顺序返回固定绿图，可指定某些帧抛异常。"""

    def __init__(self, fail_indices=()):
        self.fail_indices = set(fail_indices)
        self._i = -1

    def process(self, edge_image, prompt_text, seed=None):
        self._i += 1
        if self._i in self.fail_indices:
            raise RuntimeError("fake failure")
        return Image.new("RGB", (64, 48), color=(0, 255, 0))


def _make_input_video(path, n):
    write_frames(
        path,
        [Image.new("RGB", (64, 48), color=(i * 30 % 256, 0, 0)) for i in range(n)],
        fps=8.0,
    )


def test_run_preserves_frame_count(tmp_path):
    src = tmp_path / "in.mp4"
    _make_input_video(src, 4)
    pipe = VideoPipeline(_FakeReceiver(), LocalCannyExtractor())

    stats = pipe.run(src, tmp_path / "out.mp4", prompt_fn=lambda i, f: "t", seed=0)

    read, _ = read_frames(tmp_path / "out.mp4")
    assert len(read) == 4
    assert stats.total == 4
    assert stats.success == 4


def test_run_invokes_postprocess(tmp_path):
    src = tmp_path / "in.mp4"
    _make_input_video(src, 3)
    calls = []

    def spy(frames):
        calls.append(len(frames))
        return frames

    pipe = VideoPipeline(_FakeReceiver(), LocalCannyExtractor(), frame_postprocess=spy)
    pipe.run(src, tmp_path / "out.mp4", prompt_fn=lambda i, f: "t")

    assert calls == [3]


def test_run_fills_failed_frames(tmp_path):
    src = tmp_path / "in.mp4"
    _make_input_video(src, 3)
    pipe = VideoPipeline(_FakeReceiver(fail_indices=[1]), LocalCannyExtractor())

    stats = pipe.run(src, tmp_path / "out.mp4", prompt_fn=lambda i, f: "t")

    read, _ = read_frames(tmp_path / "out.mp4")
    assert len(read) == 3
    assert stats.failed == 1
    assert stats.success == 2


def test_run_passes_frame_ndarray_to_prompt_fn(tmp_path):
    src = tmp_path / "in.mp4"
    _make_input_video(src, 2)
    seen = []

    def prompt_fn(i, frame):
        seen.append((i, type(frame).__name__, frame.shape))
        return f"p{i}"

    pipe = VideoPipeline(_FakeReceiver(), LocalCannyExtractor())
    pipe.run(src, tmp_path / "out.mp4", prompt_fn=prompt_fn)

    assert [s[0] for s in seen] == [0, 1]
    assert seen[0][1] == "ndarray"
    assert seen[0][2] == (48, 64, 3)
