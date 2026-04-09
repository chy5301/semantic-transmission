"""GUI 接收端 Tab 队列行为单元测试。

覆盖 M-13 引入的队列模式纯函数：add_to_queue / clear_queue / unload_model /
append_external_item / _format_queue_df / run_queue（mock receiver）。
"""

from unittest.mock import MagicMock, patch

from PIL import Image

from semantic_transmission.gui.receiver_panel import (
    _format_queue_df,
    add_to_queue,
    append_external_item,
    clear_queue,
    run_queue,
    unload_model,
)


def _make_edge_path(tmp_path) -> str:
    p = tmp_path / "edge.png"
    Image.new("L", (16, 16), color=128).save(p)
    return str(p)


class TestFormatQueueDf:
    def test_empty_queue(self):
        assert _format_queue_df([]) == []

    def test_single_item(self):
        rows = _format_queue_df(
            [{"edge_path": "/tmp/a.png", "prompt": "a cat", "seed": 42}]
        )
        assert rows == [["1", "a cat", "42"]]

    def test_seed_none_shows_random(self):
        rows = _format_queue_df(
            [{"edge_path": "/tmp/a.png", "prompt": "x", "seed": None}]
        )
        assert rows[0][2] == "(随机)"

    def test_long_prompt_truncated(self):
        long_prompt = "a" * 100
        rows = _format_queue_df(
            [{"edge_path": "/tmp/a.png", "prompt": long_prompt, "seed": 1}]
        )
        assert rows[0][1].endswith("...")
        assert len(rows[0][1]) == 60


class TestAddToQueue:
    def test_add_first_item(self, tmp_path):
        edge = _make_edge_path(tmp_path)
        queue, df, status = add_to_queue(edge, "a cat", 42, [])
        assert len(queue) == 1
        assert queue[0]["prompt"] == "a cat"
        assert queue[0]["seed"] == 42
        assert queue[0]["edge_path"] == edge
        assert df == [["1", "a cat", "42"]]
        assert "1 项" in status

    def test_add_to_existing_queue(self, tmp_path):
        edge = _make_edge_path(tmp_path)
        pre_queue = [{"edge_path": "/tmp/prev.png", "prompt": "prev", "seed": 1}]
        queue, df, _ = add_to_queue(edge, "next", None, pre_queue)
        assert len(queue) == 2
        assert queue[0]["prompt"] == "prev"
        assert queue[1]["prompt"] == "next"
        assert queue[1]["seed"] is None

    def test_reject_empty_edge(self):
        queue, _, status = add_to_queue(None, "x", None, [])
        assert queue == []
        assert "请先上传边缘图" in status

    def test_reject_empty_prompt(self, tmp_path):
        edge = _make_edge_path(tmp_path)
        queue, _, status = add_to_queue(edge, "  ", None, [])
        assert queue == []
        assert "请输入语义描述" in status

    def test_none_queue_treated_as_empty(self, tmp_path):
        edge = _make_edge_path(tmp_path)
        queue, _, _ = add_to_queue(edge, "x", 1, None)
        assert len(queue) == 1

    def test_pil_image_persisted_to_temp_file(self):
        img = Image.new("RGB", (8, 8), color=(255, 0, 0))
        queue, _, _ = add_to_queue(img, "x", None, [])
        assert len(queue) == 1
        from pathlib import Path

        assert Path(queue[0]["edge_path"]).exists()
        assert queue[0]["edge_path"].endswith(".png")


class TestAppendExternalItem:
    def test_append_with_path(self, tmp_path):
        edge = _make_edge_path(tmp_path)
        queue, df = append_external_item(edge, "from sender", [])
        assert len(queue) == 1
        assert queue[0]["prompt"] == "from sender"
        assert queue[0]["seed"] is None
        assert df == [["1", "from sender", "(随机)"]]

    def test_append_with_none_edge_noop(self):
        pre_queue = [{"edge_path": "/tmp/a.png", "prompt": "a", "seed": None}]
        queue, _ = append_external_item(None, "x", pre_queue)
        assert queue == pre_queue

    def test_append_empty_prompt_allowed(self, tmp_path):
        edge = _make_edge_path(tmp_path)
        queue, _ = append_external_item(edge, "", [])
        assert len(queue) == 1
        assert queue[0]["prompt"] == ""


class TestClearQueue:
    def test_returns_empty_state(self):
        queue, df, gallery, status = clear_queue()
        assert queue == []
        assert df == []
        assert gallery == []
        assert "清空" in status


class TestUnloadModel:
    def test_none_receiver(self):
        result, status = unload_model(None)
        assert result is None
        assert "无已加载" in status

    def test_calls_unload(self):
        receiver = MagicMock()
        result, status = unload_model(receiver)
        receiver.unload.assert_called_once()
        assert result is None
        assert "已卸载" in status

    def test_unload_exception_still_clears(self):
        receiver = MagicMock()
        receiver.unload.side_effect = RuntimeError("boom")
        result, status = unload_model(receiver)
        assert result is None
        assert "boom" in status


class TestRunQueue:
    def test_empty_queue_yields_error(self):
        gen = run_queue([], None)
        receiver, gallery, log = next(gen)
        assert receiver is None
        assert gallery == []
        assert "队列为空" in log

    def test_creates_receiver_when_none(self, tmp_path):
        edge = _make_edge_path(tmp_path)
        queue = [{"edge_path": edge, "prompt": "x", "seed": 1}]

        mock_receiver = MagicMock()
        mock_receiver.process.return_value = Image.new("RGB", (8, 8))

        with patch(
            "semantic_transmission.gui.receiver_panel.create_receiver",
            return_value=mock_receiver,
        ) as create_mock:
            gen = run_queue(queue, None)
            outputs = list(gen)

        create_mock.assert_called_once_with()
        # 最终 yield 应带回 receiver 和 1 张图
        final = outputs[-1]
        assert final[0] is mock_receiver
        assert len(final[1]) == 1
        assert "1/1 成功" in final[2]

    def test_reuses_existing_receiver(self, tmp_path):
        edge = _make_edge_path(tmp_path)
        queue = [{"edge_path": edge, "prompt": "y", "seed": None}]

        mock_receiver = MagicMock()
        mock_receiver.process.return_value = Image.new("RGB", (8, 8))

        with patch(
            "semantic_transmission.gui.receiver_panel.create_receiver"
        ) as create_mock:
            gen = run_queue(queue, mock_receiver)
            outputs = list(gen)

        create_mock.assert_not_called()
        assert "复用已加载的模型" in outputs[-1][2]

    def test_multi_item_queue_calls_process_for_each(self, tmp_path):
        edge = _make_edge_path(tmp_path)
        queue = [
            {"edge_path": edge, "prompt": "one", "seed": 1},
            {"edge_path": edge, "prompt": "two", "seed": 2},
            {"edge_path": edge, "prompt": "three", "seed": 3},
        ]

        mock_receiver = MagicMock()
        mock_receiver.process.return_value = Image.new("RGB", (8, 8))

        gen = run_queue(queue, mock_receiver)
        outputs = list(gen)

        assert mock_receiver.process.call_count == 3
        assert len(outputs[-1][1]) == 3
        assert "3/3 成功" in outputs[-1][2]

    def test_per_item_failure_continues(self, tmp_path):
        edge = _make_edge_path(tmp_path)
        queue = [
            {"edge_path": edge, "prompt": "ok", "seed": 1},
            {"edge_path": edge, "prompt": "bad", "seed": 2},
            {"edge_path": edge, "prompt": "ok2", "seed": 3},
        ]

        mock_receiver = MagicMock()
        mock_receiver.process.side_effect = [
            Image.new("RGB", (8, 8)),
            RuntimeError("inference failed"),
            Image.new("RGB", (8, 8)),
        ]

        gen = run_queue(queue, mock_receiver)
        outputs = list(gen)

        # 2 张成功 + 1 张失败
        final = outputs[-1]
        assert len(final[1]) == 2
        assert "2/3 成功" in final[2]
        assert "inference failed" in final[2]

    def test_create_receiver_failure(self, tmp_path):
        edge = _make_edge_path(tmp_path)
        queue = [{"edge_path": edge, "prompt": "x", "seed": None}]

        with patch(
            "semantic_transmission.gui.receiver_panel.create_receiver",
            side_effect=RuntimeError("no model"),
        ):
            gen = run_queue(queue, None)
            outputs = list(gen)

        final = outputs[-1]
        assert final[0] is None  # receiver state 被清空
        assert final[1] == []  # 无还原图
        assert "模型加载失败" in final[2]
