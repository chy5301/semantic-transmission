from unittest.mock import MagicMock, patch
import queue as _q
import numpy as np
from semantic_transmission.common.config import ProjectConfig
from semantic_transmission.gui.video_panel import (
    unload_video_receiver,
    build_video_prompt_fn,
    start_video,
    poll_video,
)


class TestUnloadVideoReceiver:
    def test_none_returns_message(self):
        result, status = unload_video_receiver(None)
        assert result is None and "无已加载" in status

    def test_calls_unload_and_clears(self):
        receiver = MagicMock()
        result, status = unload_video_receiver(receiver)
        receiver.unload.assert_called_once()
        assert result is None and "已卸载" in status

    def test_swallows_unload_exception(self):
        receiver = MagicMock()
        receiver.unload.side_effect = RuntimeError("boom")
        result, status = unload_video_receiver(receiver)
        assert result is None and "boom" in status


class TestBuildVideoPromptFn:
    def test_manual_returns_same_prompt(self):
        fn = build_video_prompt_fn("manual", "a cat", None)
        z = np.zeros((4, 4, 3), dtype=np.uint8)
        assert fn(0, z) == "a cat" and fn(5, z) == "a cat"

    def test_manual_none_prompt_returns_empty(self):
        fn = build_video_prompt_fn("manual", None, None)
        assert fn(0, np.zeros((4, 4, 3), dtype=np.uint8)) == ""

    def test_auto_calls_vlm_describe(self):
        vlm = MagicMock()
        vlm.describe.return_value = MagicMock(text="auto desc")
        fn = build_video_prompt_fn("auto", None, vlm)
        assert fn(2, np.zeros((4, 4, 3), dtype=np.uint8)) == "auto desc"
        vlm.describe.assert_called_once()


def test_start_video_empty_path_no_thread():
    with patch("semantic_transmission.gui.video_panel.threading.Thread") as T:
        state, status = start_video(
            {}, None, "klein", "manual", "x", "prev", 12, True, None, None, MagicMock()
        )
        assert "请先上传" in status
        T.assert_not_called()


def test_start_video_rejects_when_running():
    alive = MagicMock()
    alive.is_alive.return_value = True
    state, status = start_video(
        {"thread": alive},
        "in.mp4",
        "klein",
        "manual",
        "x",
        "prev",
        12,
        True,
        None,
        None,
        MagicMock(),
    )
    assert "已在运行" in status


class TestStartVideoTemporalPolicyResolution:
    """回归测试：start_video 的 resolve_reference_mode 调用不应反转 None/"none" 语义。

    finding: klein + ref_mode="none" 曾经被三元表达式转换为 Python None 再传入
    resolve_reference_mode，而该函数把 None 解释为"未显式指定"→按 backend 默认值解析
    （klein → "prev"），导致用户显式关闭的时序补偿被静默重新启用。
    """

    def _run_and_capture_policy(self, ref_mode):
        captured = {}

        def _fake_run(*args, **kwargs):
            captured["temporal_policy"] = kwargs.get("temporal_policy")
            stats = MagicMock()
            stats.to_dict.return_value = {
                "total": 1,
                "success": 1,
                "keyframe_count": 0,
                "generated_frames": 0,
            }
            return stats

        with (
            patch(
                "semantic_transmission.gui.video_panel.VideoPipeline"
            ) as MockPipeline,
            patch(
                "semantic_transmission.gui.video_panel.create_receiver"
            ) as mock_create_receiver,
            patch("semantic_transmission.gui.video_panel.LocalCannyExtractor"),
        ):
            MockPipeline.return_value.run.side_effect = _fake_run
            mock_create_receiver.return_value = MagicMock()
            state, status = start_video(
                {},
                "in.mp4",
                "klein",
                "manual",
                "x",
                ref_mode,
                12,
                True,
                None,
                None,
                ProjectConfig(),
            )
            state["thread"].join(timeout=5)

        assert state["done"] is True
        assert state.get("error") is None, f"worker 出错：{state.get('error')}"
        return captured.get("temporal_policy")

    def test_klein_explicit_none_disables_temporal_policy(self):
        """klein + ref_mode="none" 显式关闭时序 → temporal_policy 必须为 None（修复点）。"""
        policy = self._run_and_capture_policy("none")
        assert policy is None

    def test_klein_prev_still_enables_temporal_policy(self):
        """klein + ref_mode="prev" → temporal_policy 非 None 且 reference_mode == "prev"（未被误伤）。"""
        policy = self._run_and_capture_policy("prev")
        assert policy is not None
        assert policy.reference_mode == "prev"


def test_poll_video_progress_then_done():
    q = _q.Queue()
    q.put((0, 3, {}))
    q.put((1, 3, {}))
    state = {"progress_q": q, "done": False, "error": None, "result": None}
    text, out, rows, log = poll_video(state)
    assert "2/3" in text and out is None

    state2 = {
        "progress_q": _q.Queue(),
        "done": True,
        "error": None,
        "result": {
            "out_path": "o.mp4",
            "stats": {
                "total": 3,
                "success": 3,
                "keyframe_count": 1,
                "generated_frames": 2,
            },
        },
    }
    text2, out2, rows2, log2 = poll_video(state2)
    assert out2 == "o.mp4"
    assert ["总帧数", "3"] in rows2


def test_poll_video_error():
    state = {"progress_q": _q.Queue(), "done": True, "error": "boom", "result": None}
    text, out, rows, log = poll_video(state)
    assert "boom" in text and out is None
