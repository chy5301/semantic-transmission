import queue as _q
from unittest.mock import MagicMock, patch

from semantic_transmission.gui.video_relay_panel import (
    poll_listening,
    run_video_sender,
    start_listening,
    stop_listening,
)


def test_sender_empty_path_yields_error():
    gen = run_video_sender(
        None, "127.0.0.1", 9000, "manual", "x", 12, None, None, MagicMock()
    )
    progress, rows, log = next(gen)
    assert "请先上传" in log


def test_sender_runs_and_reports_stats():
    fake_stats = MagicMock()
    fake_stats.to_dict.return_value = {
        "total_frames": 3,
        "keyframe_count": 1,
        "generated_count": 2,
        "keyframe_bytes": 300,
        "generated_bytes": 60,
    }
    with (
        patch("semantic_transmission.gui.video_relay_panel.VideoRelaySender") as MS,
        patch("semantic_transmission.gui.video_relay_panel.LocalCannyExtractor"),
    ):
        MS.return_value.run.return_value = fake_stats
        gen = run_video_sender(
            "in.mp4", "127.0.0.1", 9000, "manual", "x", 12, None, None, MagicMock()
        )
        outputs = list(gen)
    progress, rows, log = outputs[-1]
    assert any(r[0] == "总帧数" for r in rows)
    assert any(r[0] == "关键帧∶生成帧倍率" for r in rows)
    assert "完成" in log


def test_sender_unloads_vlm_on_exception_after_creation():
    """回归测试：VLM 加载后、VideoRelaySender.run 抛异常时，VLM 必须被 unload（不泄漏显存）。

    finding: build_video_prompt_fn / kf_interval 解析 / TemporalPolicyConfig 构造均在
    try/finally 之外执行，一旦其中任意一步抛异常，已加载的 VLM 永远不会被 unload。
    这里用 VideoRelaySender.run 抛异常来验证 try/finally 已覆盖到 run 调用本身。
    """
    mock_vlm = MagicMock()
    with (
        patch(
            "semantic_transmission.sender.qwen_vl_sender.QwenVLSender",
            return_value=mock_vlm,
        ),
        patch("semantic_transmission.gui.video_relay_panel.VideoRelaySender") as MS,
        patch("semantic_transmission.gui.video_relay_panel.LocalCannyExtractor"),
    ):
        MS.return_value.run.side_effect = RuntimeError("boom")
        gen = run_video_sender(
            "in.mp4", "127.0.0.1", 9000, "auto", "x", 12, None, None, MagicMock()
        )
        outputs = list(gen)
    progress, rows, log = outputs[-1]
    assert "失败" in progress
    assert "boom" in log
    mock_vlm.unload.assert_called_once()


def test_sender_blank_kf_interval_does_not_raise():
    """回归测试：kf_interval="" （Gradio 数字输入框留空的真实场景）不应触发 int("") 崩溃。

    与 seed/fps 一样应被兜底为"未设置"（此处等价于 0，即不启用时序策略）。
    """
    fake_stats = MagicMock()
    fake_stats.to_dict.return_value = {
        "total_frames": 3,
        "keyframe_count": 1,
        "generated_count": 2,
        "keyframe_bytes": 300,
        "generated_bytes": 60,
    }
    with (
        patch("semantic_transmission.gui.video_relay_panel.VideoRelaySender") as MS,
        patch("semantic_transmission.gui.video_relay_panel.LocalCannyExtractor"),
    ):
        MS.return_value.run.return_value = fake_stats
        gen = run_video_sender(
            "in.mp4", "127.0.0.1", 9000, "manual", "x", "", None, None, MagicMock()
        )
        outputs = list(gen)
    progress, rows, log = outputs[-1]
    assert "完成" in log
    assert any(r[0] == "总帧数" for r in rows)


def test_start_listening_rejects_double_start():
    alive = MagicMock()
    alive.is_alive.return_value = True
    state = {"thread": alive}
    new_state, status = start_listening(
        state, "0.0.0.0", 9000, "klein", "prev", "o.mp4", None
    )
    assert "已在监听" in status and new_state is state


def test_stop_listening_calls_receiver_stop():
    rcv = MagicMock()
    new_state, status = stop_listening({"receiver": rcv})
    rcv.stop.assert_called_once()
    assert "停止" in status


def test_poll_listening_drains_queue():
    q = _q.Queue()
    q.put((1, 3, {}))
    q.put((2, 3, {}))
    text, out = poll_listening(
        {"progress_q": q, "done": False, "result": None, "error": None}
    )
    assert "3/3" in text and out is None


def test_poll_listening_done_returns_output():
    result = MagicMock()
    result.output_path = "out.mp4"
    text, out = poll_listening(
        {"progress_q": _q.Queue(), "done": True, "result": result, "error": None}
    )
    assert out == "out.mp4"
