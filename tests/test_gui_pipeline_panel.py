"""GUI 端到端 Tab 纯函数单元测试。

覆盖 R-10 引入的 unload_receiver：state 复用模式下的模型卸载行为。
与 receiver_panel.unload_model 测试模式对齐。
"""

from unittest.mock import MagicMock

from semantic_transmission.gui.pipeline_panel import unload_receiver


class TestUnloadReceiver:
    def test_unload_receiver_when_none_returns_message(self):
        """receiver=None 时应返回 (None, "无已加载" 提示)，不调用任何对象方法。"""
        result, status = unload_receiver(None)
        assert result is None
        assert "无已加载" in status

    def test_unload_receiver_releases_via_mock(self):
        """传入 mock receiver 时应调用 receiver.unload() 并清空 state。"""
        receiver = MagicMock()
        result, status = unload_receiver(receiver)
        receiver.unload.assert_called_once()
        assert result is None
        assert "已卸载" in status

    def test_unload_receiver_handles_unload_exception(self):
        """receiver.unload() 抛异常时函数不传播，返回 (None, 错误信息)。"""
        receiver = MagicMock()
        receiver.unload.side_effect = RuntimeError("boom")
        result, status = unload_receiver(receiver)
        assert result is None
        assert "boom" in status
