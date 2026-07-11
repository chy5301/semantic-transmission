from unittest.mock import MagicMock, patch
import queue as _q
import numpy as np
from semantic_transmission.common.config import ProjectConfig
from semantic_transmission.gui.video_panel import (
    unload_video_receiver,
    build_video_prompt_fn,
    start_video,
    poll_video,
    run_video_evaluation,
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


def test_start_video_blank_kf_interval_defaults_not_crash():
    """finding: klein 默认配置下清空 kf_interval（""）曾在主线程 int("") 崩溃。

    修复后应回退默认 12 且 start_video 不抛异常（守卫与 seed/fps 一致）。
    """
    captured = {}

    def _fake_run(*args, **kwargs):
        captured["temporal_policy"] = kwargs.get("temporal_policy")
        stats = MagicMock()
        stats.to_dict.return_value = {"total": 1, "success": 1}
        return stats

    with (
        patch("semantic_transmission.gui.video_panel.VideoPipeline") as MockPipeline,
        patch("semantic_transmission.gui.video_panel.create_receiver") as mock_cr,
        patch("semantic_transmission.gui.video_panel.LocalCannyExtractor"),
    ):
        MockPipeline.return_value.run.side_effect = _fake_run
        mock_cr.return_value = MagicMock()
        # kf_interval="" 若无守卫会在此调用（主线程）抛 ValueError
        state, _ = start_video(
            {},
            "in.mp4",
            "klein",
            "manual",
            "x",
            "prev",
            "",
            True,
            None,
            None,
            ProjectConfig(),
        )
        state["thread"].join(timeout=5)

    assert state.get("error") is None, f"worker 出错：{state.get('error')}"
    policy = captured.get("temporal_policy")
    assert policy is not None
    assert policy.keyframe_interval == 12


def test_start_video_recreates_receiver_on_backend_switch():
    """finding: 复用缓存 receiver 时不校验 backend，切换后端会静默沿用旧模型。"""
    kfake = MagicMock(name="klein_receiver")
    dfake = MagicMock(name="diffusers_receiver")

    def _fake_run(*args, **kwargs):
        stats = MagicMock()
        stats.to_dict.return_value = {"total": 1, "success": 1}
        return stats

    with (
        patch("semantic_transmission.gui.video_panel.VideoPipeline") as MockPipeline,
        patch("semantic_transmission.gui.video_panel.create_receiver") as mock_cr,
        patch("semantic_transmission.gui.video_panel.LocalCannyExtractor"),
    ):
        MockPipeline.return_value.run.side_effect = _fake_run
        mock_cr.side_effect = lambda backend: kfake if backend == "klein" else dfake

        s1, _ = start_video(
            {},
            "in.mp4",
            "klein",
            "manual",
            "x",
            "none",
            12,
            True,
            None,
            None,
            ProjectConfig(),
        )
        s1["thread"].join(timeout=5)
        assert s1.get("error") is None
        assert s1["receiver"] is kfake and s1["backend"] == "klein"

        # 同后端第二次运行：复用缓存，不重建
        mock_cr.reset_mock()
        s2, _ = start_video(
            s1,
            "in.mp4",
            "klein",
            "manual",
            "x",
            "none",
            12,
            True,
            None,
            None,
            ProjectConfig(),
        )
        s2["thread"].join(timeout=5)
        assert s2.get("error") is None
        mock_cr.assert_not_called()
        assert s2["receiver"] is kfake

        # 切到 diffusers：必须卸载旧 klein receiver 并按新 backend 重建（修复点）
        mock_cr.reset_mock()
        s3, _ = start_video(
            s2,
            "in.mp4",
            "diffusers",
            "manual",
            "x",
            "none",
            12,
            True,
            None,
            None,
            ProjectConfig(),
        )
        s3["thread"].join(timeout=5)
        assert s3.get("error") is None
        mock_cr.assert_called_once_with(backend="diffusers")
        assert s3["receiver"] is dfake and s3["backend"] == "diffusers"
        kfake.unload.assert_called_once()


def test_poll_video_done_stops_reemitting_after_first():
    """finding: gr.Timer 完成后不停用会每 tick 重复 re-fetch 视频。

    修复后首次 done 返回真实 out_path，之后返回 gr.update() 无变更（不再推路径）。
    """
    state = {
        "progress_q": _q.Queue(),
        "done": True,
        "error": None,
        "result": {
            "out_path": "o.mp4",
            "stats": {"total": 1, "success": 1},
        },
    }
    _, out1, _, _ = poll_video(state)
    assert out1 == "o.mp4"  # 首次推送真实路径
    assert state.get("_emitted") is True
    _, out2, _, _ = poll_video(state)
    assert out2 != "o.mp4"  # 二次不再重复推送同一视频路径


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


class TestRunVideoEvaluation:
    def test_missing_inputs_returns_error(self):
        rows, log = run_video_evaluation(None, None)
        assert rows == [] and "需要" in log

    def test_summary_rows_no_clip_column(self):
        fake_report = {
            "summary": {
                "psnr": {"mean": 15.0, "count": 2},
                "ssim": {"mean": 0.75, "count": 2},
                "lpips": {"mean": 0.45, "count": 2},
            }
        }
        with (
            patch(
                "semantic_transmission.gui.video_panel.read_frames",
                return_value=([1, 2], MagicMock()),
            ),
            patch(
                "semantic_transmission.gui.video_panel.evaluate_video",
                return_value=fake_report,
            ) as ev,
        ):
            rows, log = run_video_evaluation("in.mp4", "out.mp4")
        # with_clip 默认 False，不列 CLIP
        assert ev.call_args.kwargs.get("with_clip") is False
        assert ["PSNR", "15.0000"] in rows
        assert all(r[0] != "CLIP" for r in rows)
        assert "评估完成" in log
