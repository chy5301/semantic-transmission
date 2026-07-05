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


def test_run_respects_explicit_fps(tmp_path):
    """显式传入的 fps 必须被写入输出视频，不得被 meta.fps 覆盖。"""
    src = tmp_path / "in.mp4"
    _make_input_video(src, 4)  # 以 8.0 fps 写入
    pipe = VideoPipeline(_FakeReceiver(), LocalCannyExtractor())

    pipe.run(src, tmp_path / "out.mp4", prompt_fn=lambda i, f: "t", fps=5.0)

    _, meta = read_frames(tmp_path / "out.mp4")
    assert abs(meta.fps - 5.0) < 1.0, f"期望输出 fps≈5.0，实际 {meta.fps}"


def test_run_calls_on_prompts_ready_between_describe_and_generate(tmp_path):
    """on_prompts_ready 必须在所有帧 describe 之后、任何帧生成之前触发。

    这是显存生命周期的契约：auto-prompt 时调用方传入 vlm_sender.unload，
    确保 VLM 在接收端加载生成模型前被释放，两模型不同驻 GPU。
    """
    src = tmp_path / "in.mp4"
    _make_input_video(src, 3)
    events: list[str] = []

    class _RecordingReceiver(BaseReceiver):
        def process(self, edge_image, prompt_text, seed=None):
            events.append("generate")
            return Image.new("RGB", (64, 48), color=(0, 255, 0))

    def prompt_fn(i, frame):
        events.append(f"describe_{i}")
        return "t"

    def on_ready():
        events.append("unload")

    pipe = VideoPipeline(_RecordingReceiver(), LocalCannyExtractor())
    pipe.run(src, tmp_path / "out.mp4", prompt_fn=prompt_fn, on_prompts_ready=on_ready)

    unload_at = events.index("unload")
    last_describe = max(i for i, e in enumerate(events) if e.startswith("describe"))
    first_generate = min(i for i, e in enumerate(events) if e == "generate")
    assert last_describe < unload_at < first_generate, events


def test_run_without_on_prompts_ready_still_works(tmp_path):
    """不传 on_prompts_ready 时（如 --prompt 固定文本）行为不变。"""
    src = tmp_path / "in.mp4"
    _make_input_video(src, 2)
    pipe = VideoPipeline(_FakeReceiver(), LocalCannyExtractor())

    stats = pipe.run(src, tmp_path / "out.mp4", prompt_fn=lambda i, f: "t")

    assert stats.total == 2
    assert stats.success == 2


def test_run_survives_prompt_fn_failure(tmp_path):
    """prompt_fn 对某帧抛异常时，该帧回退空 prompt，整段正常完成。"""
    src = tmp_path / "in.mp4"
    _make_input_video(src, 3)

    def flaky_prompt(i, frame):
        if i == 1:
            raise RuntimeError("模拟 VLM 单帧失败")
        return f"ok_{i}"

    pipe = VideoPipeline(_FakeReceiver(), LocalCannyExtractor())
    stats = pipe.run(src, tmp_path / "out.mp4", prompt_fn=flaky_prompt)

    read, _ = read_frames(tmp_path / "out.mp4")
    assert len(read) == 3, "输出帧数应等于输入帧数"
    assert stats.total == 3


def test_run_saves_artifacts(tmp_path):
    """save_artifacts_to 提供时，保存 prompts.json（逐帧描述+码率）与 edges/。"""
    import json

    src = tmp_path / "in.mp4"
    _make_input_video(src, 3)
    artifacts = tmp_path / "artifacts"
    pipe = VideoPipeline(_FakeReceiver(), LocalCannyExtractor())

    pipe.run(
        src,
        tmp_path / "out.mp4",
        prompt_fn=lambda i, f: f"描述 {i}",
        save_artifacts_to=artifacts,
    )

    data = json.loads((artifacts / "prompts.json").read_text(encoding="utf-8"))
    assert data["total_frames"] == 3
    assert [f["prompt"] for f in data["frames"]] == ["描述 0", "描述 1", "描述 2"]
    # byte_count 用 UTF-8 字节数（中文 != 字符数），是码率统计的基础
    assert data["frames"][0]["byte_count"] == len("描述 0".encode("utf-8"))
    assert data["frames"][0]["char_count"] == 4
    assert data["semantic_bitrate"]["total_bytes"] > 0
    assert data["semantic_bitrate"]["avg_bytes_per_second"] > 0
    # 每帧一张边缘图
    assert len(list((artifacts / "edges").glob("*.png"))) == 3


def test_run_without_artifacts_dir_skips_saving(tmp_path):
    """不传 save_artifacts_to 时不产出 artifacts（行为不变）。"""
    src = tmp_path / "in.mp4"
    _make_input_video(src, 2)
    pipe = VideoPipeline(_FakeReceiver(), LocalCannyExtractor())

    pipe.run(src, tmp_path / "out.mp4", prompt_fn=lambda i, f: "t")

    assert not (tmp_path / "prompts.json").exists()
    assert not (tmp_path / "edges").exists()


def test_batch_result_to_dict_omits_keyframe_fields_by_default():
    """无状态路径：keyframe_indices 未赋值时 to_dict 不含时序字段（逐字节向后兼容）。"""
    from semantic_transmission.pipeline.batch_processor import BatchResult

    d = BatchResult(total=3, success=3).to_dict()
    assert "keyframe_count" not in d
    assert "generated_frames" not in d
    assert "keyframe_indices" not in d


def test_batch_result_to_dict_includes_keyframe_fields_when_set():
    """时序路径：赋值后 to_dict 输出三个关键帧统计字段。"""
    from semantic_transmission.pipeline.batch_processor import BatchResult

    b = BatchResult(total=5, success=5)
    b.keyframe_count = 1
    b.generated_frames = 4
    b.keyframe_indices = [0]
    d = b.to_dict()
    assert d["keyframe_count"] == 1
    assert d["generated_frames"] == 4
    assert d["keyframe_indices"] == [0]
