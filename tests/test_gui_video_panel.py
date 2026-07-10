from unittest.mock import MagicMock
import numpy as np
from semantic_transmission.gui.video_panel import (
    unload_video_receiver,
    build_video_prompt_fn,
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
