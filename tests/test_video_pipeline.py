"""video_pipeline 纯函数与编排测试。"""

import pytest
from PIL import Image
from types import SimpleNamespace
from unittest.mock import MagicMock
import numpy as np

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


def test_save_temporal_artifacts_marks_passthrough_and_counts_generated(tmp_path):
    """透传关键帧标 passthrough、无 edge；码率只计生成帧。"""
    import json
    from types import SimpleNamespace

    from semantic_transmission.pipeline.video_pipeline import _save_temporal_artifacts
    from semantic_transmission.receiver.base import FrameInput

    def _edge():
        return Image.new("RGB", (16, 12), color=(255, 255, 255))

    # 4 帧：0 为透传关键帧，1/2/3 为生成帧
    generated = [
        FrameInput(
            edge_image=_edge(),
            prompt_text=f"描述 {i}",
            metadata={"index": i, "name": f"frame_{i:04d}"},
        )
        for i in (1, 2, 3)
    ]
    artifacts = tmp_path / "art"
    _save_temporal_artifacts(
        artifacts,
        generated_inputs=generated,
        passthrough_indices=[0],
        total_frames=4,
        meta=SimpleNamespace(fps=25.0),
    )

    data = json.loads((artifacts / "prompts.json").read_text(encoding="utf-8"))
    assert data["total_frames"] == 4
    assert data["generated_frames"] == 3
    assert data["keyframe_indices"] == [0]
    # frames 覆盖全部下标；透传帧标记、无 prompt
    assert data["frames"][0] == {"index": 0, "passthrough": True}
    assert data["frames"][1]["prompt"] == "描述 1"
    assert data["frames"][1]["byte_count"] == len("描述 1".encode("utf-8"))
    # 码率仅计 3 个生成帧
    expected_total = sum(len(f"描述 {i}".encode("utf-8")) for i in (1, 2, 3))
    assert data["semantic_bitrate"]["total_bytes"] == expected_total
    assert data["semantic_bitrate"]["avg_bytes_per_generated_frame"] == round(
        expected_total / 3, 2
    )
    # edges 只有 3 张（生成帧），透传帧 frame_0000 无 edge
    pngs = sorted(p.name for p in (artifacts / "edges").glob("*.png"))
    assert pngs == ["frame_0001.png", "frame_0002.png", "frame_0003.png"]


class _FakeReferenceReceiver(BaseReceiver):
    """无 GPU 多参考接收端：记录每帧收到的 reference_images / prompt；
    可指定某些「生成帧序号」抛异常。带 config.max_side 供透传帧缩放。"""

    def __init__(self, fail_gen_calls=(), max_side=64):
        from types import SimpleNamespace

        self.config = SimpleNamespace(max_side=max_side)
        self.calls = []  # 每次 process 调用：{"prompt":..., "refs":[...]}
        self.returns = []  # 每次 process 调用实际返回的图像对象（用于 is 身份断言）
        self._fail = set(fail_gen_calls)
        self._n = -1

    def process(self, edge_image, prompt_text, seed=None, reference_images=None):
        self._n += 1
        self.calls.append({"prompt": prompt_text, "refs": list(reference_images or [])})
        if self._n in self._fail:
            raise RuntimeError("fake gen failure")
        # 返回工作分辨率大小的图（与透传帧尺寸一致：64 长边 → 64x48 源缩不变）
        result = Image.new("RGB", (64, 48), color=(0, 255, 0))
        self.returns.append(result)
        return result


def _temporal_cfg(**kw):
    from semantic_transmission.pipeline.temporal_policy import TemporalPolicyConfig

    return TemporalPolicyConfig(**kw)


def test_temporal_none_is_backward_compatible(tmp_path):
    """temporal_policy=None 时输出与旧无状态路径一致（帧数/成功数不变）。"""
    src = tmp_path / "in.mp4"
    _make_input_video(src, 4)
    pipe = VideoPipeline(_FakeReceiver(), LocalCannyExtractor())

    stats = pipe.run(
        src, tmp_path / "out.mp4", prompt_fn=lambda i, f: "t", temporal_policy=None
    )
    read, _ = read_frames(tmp_path / "out.mp4")
    assert len(read) == 4
    assert stats.total == 4 and stats.success == 4
    assert stats.keyframe_indices is None  # 无状态路径不带时序字段


def test_temporal_prev_chain_refs(tmp_path):
    """prev 模式：第 i 生成帧收到的 refs == [上一帧输出]。"""
    src = tmp_path / "in.mp4"
    _make_input_video(src, 4)
    rec = _FakeReferenceReceiver()
    pipe = VideoPipeline(rec, LocalCannyExtractor())

    # interval=12 → 仅帧 0 是关键帧（透传）；帧 1/2/3 生成
    pipe.run(
        src,
        tmp_path / "out.mp4",
        prompt_fn=lambda i, f: f"p{i}",
        temporal_policy=_temporal_cfg(keyframe_interval=12, reference_mode="prev"),
    )
    # 3 次生成调用（帧 1/2/3）
    assert len(rec.calls) == 3
    # 帧 1 的 refs = [帧 0 透传图]；帧 2 的 refs = [帧 1 输出]；帧 3 = [帧 2 输出]
    assert len(rec.calls[0]["refs"]) == 1
    assert len(rec.calls[1]["refs"]) == 1
    assert len(rec.calls[2]["refs"]) == 1
    # 身份断言：帧 2 的 ref 就是帧 1 的输出对象本身（非同值不同对象），
    # 帧 3 的 ref 就是帧 2 的输出对象本身——证明 prev 链真的串接了输出，
    # 而不只是凑巧长度都为 1。
    assert rec.calls[1]["refs"][0] is rec.returns[0]
    assert rec.calls[2]["refs"][0] is rec.returns[1]


def test_temporal_passthrough_keyframe_not_generated(tmp_path):
    """关键帧透传：is_keyframe 下标不调用 process，输出为原图（缩放后）。"""
    src = tmp_path / "in.mp4"
    _make_input_video(src, 3)
    rec = _FakeReferenceReceiver()
    pipe = VideoPipeline(rec, LocalCannyExtractor())

    pipe.run(
        src,
        tmp_path / "out.mp4",
        prompt_fn=lambda i, f: "p",
        temporal_policy=_temporal_cfg(keyframe_interval=2),  # 关键帧 {0, 2}
    )
    # 帧 0、2 透传，仅帧 1 生成 → 1 次 process 调用
    assert len(rec.calls) == 1


def test_temporal_all_passthrough_zero_generated(tmp_path):
    """边界：keyframe_interval=1 → 全部下标都是关键帧、全部透传、0 生成帧。

    覆盖零生成帧场景：receiver.process 一次都不应被调用；统计字段与
    avg_bytes_per_generated_frame 的除零保护需在此场景下正确。
    """
    import json

    src = tmp_path / "in.mp4"
    _make_input_video(src, 4)
    rec = _FakeReferenceReceiver()
    pipe = VideoPipeline(rec, LocalCannyExtractor())
    artifacts = tmp_path / "artifacts"

    stats = pipe.run(
        src,
        tmp_path / "out.mp4",
        prompt_fn=lambda i, f: "p",
        temporal_policy=_temporal_cfg(keyframe_interval=1),  # 全部下标为关键帧
        save_artifacts_to=artifacts,
    )

    # 全部透传 → receiver.process 零次调用
    assert len(rec.calls) == 0
    assert stats.generated_frames == 0
    assert stats.keyframe_count == 4
    assert stats.keyframe_indices == list(range(4))
    # 帧数守恒
    read, _ = read_frames(tmp_path / "out.mp4")
    assert len(read) == 4

    data = json.loads((artifacts / "prompts.json").read_text(encoding="utf-8"))
    assert data["semantic_bitrate"]["avg_bytes_per_generated_frame"] == 0.0


def test_temporal_passthrough_skips_prompt_fn(tmp_path):
    """透传关键帧下标不调用 prompt_fn（§5 VLM 跳过优化）。"""
    src = tmp_path / "in.mp4"
    _make_input_video(src, 4)
    described = []
    pipe = VideoPipeline(_FakeReferenceReceiver(), LocalCannyExtractor())

    pipe.run(
        src,
        tmp_path / "out.mp4",
        prompt_fn=lambda i, f: described.append(i) or "p",
        temporal_policy=_temporal_cfg(keyframe_interval=2),  # 关键帧 {0, 2} 透传
    )
    # 只有生成帧 1、3 被描述
    assert described == [1, 3]


def test_temporal_failed_frame_does_not_poison_prev_chain(tmp_path):
    """某生成帧失败 → 下一帧 refs 仍指向上一成功帧、非 None。"""
    src = tmp_path / "in.mp4"
    _make_input_video(src, 4)
    # 关键帧 {0}；生成帧调用序 0->帧1, 1->帧2, 2->帧3；令第 1 次（帧2）失败
    rec = _FakeReferenceReceiver(fail_gen_calls=[1])
    pipe = VideoPipeline(rec, LocalCannyExtractor())

    stats = pipe.run(
        src,
        tmp_path / "out.mp4",
        prompt_fn=lambda i, f: "p",
        temporal_policy=_temporal_cfg(keyframe_interval=12, reference_mode="prev"),
    )
    # 帧3（第 2 次调用）的 refs 必须非空（用帧1 的成功输出，而非帧2 的 None）
    assert len(rec.calls[2]["refs"]) == 1
    assert rec.calls[2]["refs"][0] is not None
    assert stats.failed == 1


def test_temporal_stats_and_size_consistency(tmp_path):
    """时序统计字段正确 + 透传帧与生成帧输出尺寸一致（帧数守恒）。"""
    src = tmp_path / "in.mp4"
    _make_input_video(src, 4)
    pipe = VideoPipeline(_FakeReferenceReceiver(), LocalCannyExtractor())

    stats = pipe.run(
        src,
        tmp_path / "out.mp4",
        prompt_fn=lambda i, f: "p",
        temporal_policy=_temporal_cfg(keyframe_interval=2),  # 关键帧 {0,2} 透传
    )
    read, _ = read_frames(tmp_path / "out.mp4")
    assert len(read) == 4  # 帧数守恒
    assert stats.keyframe_count == 2
    assert stats.generated_frames == 2
    assert stats.keyframe_indices == [0, 2]


def test_temporal_requires_reference_capable_receiver(tmp_path):
    """能力门控：receiver.process 不接受 reference_images 时抛明确错误、不静默降级。"""
    src = tmp_path / "in.mp4"
    _make_input_video(src, 2)
    pipe = VideoPipeline(_FakeReceiver(), LocalCannyExtractor())  # 无 reference_images

    with pytest.raises(TypeError, match="reference_images"):
        pipe.run(
            src,
            tmp_path / "out.mp4",
            prompt_fn=lambda i, f: "p",
            temporal_policy=_temporal_cfg(),
        )


def test_temporal_non_passthrough_keyframe_updates_anchor(tmp_path):
    """passthrough=False：关键帧不透传但仍更新 last_kf 锚点，全部帧都生成。

    覆盖 `if i in kf_set` 非透传关键帧分支（其余测试均 passthrough=True，从不触发它）。
    """
    src = tmp_path / "in.mp4"
    _make_input_video(src, 4)
    rec = _FakeReferenceReceiver()
    pipe = VideoPipeline(rec, LocalCannyExtractor())

    # 关键帧 {0,2}，passthrough 关，reference_mode=keyframe → refs=[last_kf 锚点]
    stats = pipe.run(
        src,
        tmp_path / "out.mp4",
        prompt_fn=lambda i, f: "p",
        temporal_policy=_temporal_cfg(
            keyframe_interval=2, keyframe_passthrough=False, reference_mode="keyframe"
        ),
    )
    # 无透传 → 4 帧全部走 process（触发锚点更新分支）
    assert len(rec.calls) == 4
    # 锚点在 i=0（帧0）与 i=2（帧2）各更新一次 → 帧1、帧3 的参考锚点是不同对象
    assert rec.calls[1]["refs"][0] is not rec.calls[3]["refs"][0]
    # 非透传：无透传关键帧 → keyframe_count=0、全部帧计入 generated（与 total 对账）
    assert stats.keyframe_count == 0
    assert stats.generated_frames == 4
    assert stats.keyframe_indices == []


def _patch_io(monkeypatch, n):
    frames = [np.zeros((8, 8, 3), dtype=np.uint8) for _ in range(n)]
    meta = SimpleNamespace(fps=30.0)
    monkeypatch.setattr(
        "semantic_transmission.pipeline.video_pipeline.read_frames",
        lambda p: (frames, meta),
    )
    monkeypatch.setattr(
        "semantic_transmission.pipeline.video_pipeline.write_frames",
        lambda *a, **k: None,
    )
    return frames


def test_run_stateless_progress_callback_per_frame(monkeypatch, tmp_path):
    from semantic_transmission.pipeline.video_pipeline import VideoPipeline
    from semantic_transmission.pipeline.batch_processor import BatchResult

    _patch_io(monkeypatch, 3)
    receiver = MagicMock()
    out = MagicMock()
    out.images = [Image.new("RGB", (8, 8)) for _ in range(3)]
    out.stats = BatchResult(total=3, success=3)
    receiver.process_batch.return_value = out
    extractor = MagicMock()
    extractor.extract.return_value = np.zeros((8, 8, 3), dtype=np.uint8)

    calls = []
    VideoPipeline(receiver, extractor).run(
        "in.mp4",
        str(tmp_path / "o.mp4"),
        lambda i, f: "p",
        progress_callback=lambda i, t, info: calls.append((i, t)),
    )
    assert [c[0] for c in calls] == [0, 1, 2]
    assert all(c[1] == 3 for c in calls)


def test_run_passes_callback_to_temporal(monkeypatch, tmp_path):
    from semantic_transmission.pipeline.video_pipeline import VideoPipeline
    from semantic_transmission.pipeline.temporal_policy import TemporalPolicyConfig

    pipe = VideoPipeline(MagicMock(), MagicMock())
    captured = {}
    monkeypatch.setattr(
        pipe,
        "_run_temporal",
        lambda *a, **k: captured.update(k) or MagicMock(),
    )
    cb = lambda i, t, info: None  # noqa: E731
    pipe.run(
        "in.mp4",
        str(tmp_path / "o.mp4"),
        lambda i, f: "p",
        temporal_policy=TemporalPolicyConfig(
            keyframe_interval=12, reference_mode="prev"
        ),
        progress_callback=cb,
    )
    assert captured.get("progress_callback") is cb
