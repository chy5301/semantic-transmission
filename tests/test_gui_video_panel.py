from unittest.mock import MagicMock, patch
import queue as _q
import numpy as np
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
