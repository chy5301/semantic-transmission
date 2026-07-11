"""video_relay 发送端/接收端编排测试（无 GPU）。"""

import io
import threading
import time
from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np
from PIL import Image

from semantic_transmission.common.video_io import read_frames, write_frames
from semantic_transmission.pipeline.relay import (
    SocketRelayReceiver,
    SocketRelaySender,
    TransmissionPacket,
)
from semantic_transmission.pipeline.video_relay import (
    VideoRelayReceiver,
    VideoRelaySender,
    _order_buffer,
)
from semantic_transmission.receiver.base import BaseReceiver
from semantic_transmission.sender.local_condition_extractor import LocalCannyExtractor


def _find_free_port() -> int:
    import socket as _socket

    with _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _make_input_video(path, n, fps=8.0):
    write_frames(
        path,
        [Image.new("RGB", (64, 48), color=(i * 30 % 256, 0, 0)) for i in range(n)],
        fps=fps,
    )


def test_sender_sends_all_frames_with_metadata(tmp_path):
    src = tmp_path / "in.mp4"
    _make_input_video(src, 3, fps=8.0)
    port = _find_free_port()
    received = []

    def recv_thread():
        with SocketRelayReceiver("127.0.0.1", port) as r:
            for _ in range(3):
                received.append(r.receive(timeout=5.0))

    t = threading.Thread(target=recv_thread)
    t.start()
    time.sleep(0.2)

    sender = VideoRelaySender(LocalCannyExtractor())
    stats = sender.run(src, "127.0.0.1", port, prompt_fn=lambda i, f: f"p{i}", seed=7)

    t.join(timeout=5.0)
    assert len(received) == 3
    assert [p.metadata["frame_index"] for p in received] == [0, 1, 2]
    assert all(p.metadata["total_frames"] == 3 for p in received)
    assert all(abs(p.metadata["fps"] - 8.0) < 0.01 for p in received)
    assert all(p.metadata["seed"] == 7 for p in received)
    assert received[1].prompt_text == "p1"
    assert received[0].edge_image[:8] == b"\x89PNG\r\n\x1a\n"  # PNG 魔数
    assert stats.total_frames == 3
    assert len(stats.frames) == 3


def test_sender_prompt_fn_failure_falls_back_empty(tmp_path):
    src = tmp_path / "in.mp4"
    _make_input_video(src, 2)
    port = _find_free_port()
    received = []

    def recv_thread():
        with SocketRelayReceiver("127.0.0.1", port) as r:
            for _ in range(2):
                received.append(r.receive(timeout=5.0))

    t = threading.Thread(target=recv_thread)
    t.start()
    time.sleep(0.2)

    def flaky(i, f):
        if i == 1:
            raise RuntimeError("VLM 单帧失败")
        return f"ok{i}"

    VideoRelaySender(LocalCannyExtractor()).run(src, "127.0.0.1", port, prompt_fn=flaky)
    t.join(timeout=5.0)
    assert received[0].prompt_text == "ok0"
    assert received[1].prompt_text == ""


def test_sender_explicit_fps_overrides_meta(tmp_path):
    src = tmp_path / "in.mp4"
    _make_input_video(src, 2, fps=8.0)
    port = _find_free_port()
    received = []

    def recv_thread():
        with SocketRelayReceiver("127.0.0.1", port) as r:
            for _ in range(2):
                received.append(r.receive(timeout=5.0))

    t = threading.Thread(target=recv_thread)
    t.start()
    time.sleep(0.2)

    VideoRelaySender(LocalCannyExtractor()).run(
        src, "127.0.0.1", port, prompt_fn=lambda i, f: "t", fps=5.0
    )
    t.join(timeout=5.0)
    assert all(abs(p.metadata["fps"] - 5.0) < 0.01 for p in received)


class _FakeReceiver(BaseReceiver):
    """不碰 GPU：返回固定绿图，可指定某些 frame_index 抛异常。"""

    def __init__(self, fail_indices=()):
        self.fail_indices = set(fail_indices)

    def process(self, edge_image, prompt_text, seed=None):
        idx = int(prompt_text.split("-")[-1]) if prompt_text else -1
        if idx in self.fail_indices:
            raise RuntimeError("fake failure")
        return Image.new("RGB", (64, 48), color=(0, 255, 0))


def _png_bytes():
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), color=(1, 1, 1)).save(buf, format="PNG")
    return buf.getvalue()


def _send_packets(host, port, n, fps=8.0, indices=None):
    indices = indices if indices is not None else list(range(n))
    with SocketRelaySender(host, port) as s:
        for i in indices:
            s.send(
                TransmissionPacket(
                    edge_image=_png_bytes(),
                    prompt_text=f"idx-{i}",
                    metadata={"frame_index": i, "total_frames": n, "fps": fps},
                )
            )


def test_order_buffer_sorts_by_index():
    a = Image.new("RGB", (4, 4), (1, 0, 0))
    b = Image.new("RGB", (4, 4), (2, 0, 0))
    c = Image.new("RGB", (4, 4), (3, 0, 0))
    ordered = _order_buffer({2: c, 0: a, 1: b}, 3)
    assert ordered == [a, b, c]


def test_order_buffer_missing_frame_is_none():
    a = Image.new("RGB", (4, 4), (1, 0, 0))
    ordered = _order_buffer({0: a}, 2)
    assert ordered == [a, None]


def test_receiver_assembles_video(tmp_path):
    port = _find_free_port()
    out = tmp_path / "out.mp4"
    box = []

    def recv_thread():
        box.append(
            VideoRelayReceiver(_FakeReceiver()).run("127.0.0.1", port, out, timeout=5.0)
        )

    t = threading.Thread(target=recv_thread)
    t.start()
    time.sleep(0.2)
    _send_packets("127.0.0.1", port, 3)
    t.join(timeout=10.0)
    assert not t.is_alive(), "receiver thread timed out"

    frames, meta = read_frames(out)
    assert len(frames) == 3
    result = box[0]
    assert result.stats.total == 3
    assert result.stats.success == 3
    assert result.prompts == ["idx-0", "idx-1", "idx-2"]
    assert abs(result.fps - 8.0) < 0.01
    assert result.output_path == out


def test_receiver_fills_failed_frames(tmp_path):
    port = _find_free_port()
    out = tmp_path / "out.mp4"
    box = []

    def recv_thread():
        box.append(
            VideoRelayReceiver(_FakeReceiver(fail_indices=[1])).run(
                "127.0.0.1", port, out, timeout=5.0
            )
        )

    t = threading.Thread(target=recv_thread)
    t.start()
    time.sleep(0.2)
    _send_packets("127.0.0.1", port, 3)
    t.join(timeout=10.0)
    assert not t.is_alive(), "receiver thread timed out"

    frames, _ = read_frames(out)
    assert len(frames) == 3  # 失败帧被填充，帧数守恒
    assert box[0].stats.failed == 1
    assert box[0].stats.success == 2


def test_receiver_failed_indices_in_result(tmp_path):
    """失败帧的索引应出现在 result.failed_indices 中。"""
    port = _find_free_port()
    out = tmp_path / "out.mp4"
    box = []

    def recv_thread():
        box.append(
            VideoRelayReceiver(_FakeReceiver(fail_indices=[0, 2])).run(
                "127.0.0.1", port, out, timeout=5.0
            )
        )

    t = threading.Thread(target=recv_thread)
    t.start()
    time.sleep(0.2)
    _send_packets("127.0.0.1", port, 3)
    t.join(timeout=10.0)
    assert not t.is_alive(), "receiver thread timed out"

    result = box[0]
    assert result.failed_indices == [0, 2]


def test_receiver_duplicate_frame_index_no_premature_exit(tmp_path):
    """重复 frame_index 不应导致提前退出——所有唯一帧仍需收齐。"""
    port = _find_free_port()
    out = tmp_path / "out.mp4"
    box = []

    def recv_thread():
        box.append(
            VideoRelayReceiver(_FakeReceiver()).run("127.0.0.1", port, out, timeout=5.0)
        )

    t = threading.Thread(target=recv_thread)
    t.start()
    time.sleep(0.2)
    # 发送索引序列：0, 0 (重复), 1, 2 —— 3 个唯一帧，total_frames=3
    _send_packets("127.0.0.1", port, 3, indices=[0, 0, 1, 2])
    t.join(timeout=10.0)
    assert not t.is_alive(), "receiver thread timed out"

    frames, _ = read_frames(out)
    assert len(frames) == 3  # 3 个唯一帧均已还原
    # 去重后重复包不应过计数：success 等于唯一帧数而非收到的包数
    assert box[0].stats.total == 3
    assert box[0].stats.success == 3


def test_sender_receiver_end_to_end(tmp_path):
    src = tmp_path / "in.mp4"
    write_frames(
        src,
        [Image.new("RGB", (64, 48), (i * 40 % 256, 0, 0)) for i in range(4)],
        fps=6.0,
    )
    out = tmp_path / "out.mp4"
    port = _find_free_port()
    box = []

    def recv_thread():
        box.append(
            VideoRelayReceiver(_FakeReceiver()).run(
                "127.0.0.1", port, out, timeout=10.0
            )
        )

    t = threading.Thread(target=recv_thread)
    t.start()
    time.sleep(0.2)
    VideoRelaySender(LocalCannyExtractor()).run(
        src, "127.0.0.1", port, prompt_fn=lambda i, f: f"idx-{i}"
    )
    t.join(timeout=15.0)
    assert not t.is_alive(), "receiver thread timed out"

    frames, _ = read_frames(out)
    assert len(frames) == 4
    assert box[0].stats.success == 4


class _FakeRelay:
    def __init__(self, *a, **k):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def send(self, packet):
        pass


def test_sender_progress_callback_per_frame(monkeypatch):
    from semantic_transmission.pipeline.video_relay import VideoRelaySender

    frames = [np.zeros((8, 8, 3), dtype=np.uint8) for _ in range(3)]
    monkeypatch.setattr(
        "semantic_transmission.pipeline.video_relay.read_frames",
        lambda p: (frames, SimpleNamespace(fps=30.0)),
    )
    monkeypatch.setattr(
        "semantic_transmission.pipeline.video_relay.SocketRelaySender", _FakeRelay
    )
    extractor = MagicMock()
    extractor.extract.return_value = np.zeros((8, 8, 3), dtype=np.uint8)

    calls = []
    VideoRelaySender(extractor).run(
        "in.mp4",
        "127.0.0.1",
        9000,
        lambda i, f: "p",
        progress_callback=lambda i, t, info: calls.append((i, t)),
    )
    assert [i for i, _ in calls] == [0, 1, 2]
    assert all(t == 3 for _, t in calls)


def test_receiver_stop_closes_relay():
    from unittest.mock import MagicMock

    from semantic_transmission.pipeline.video_relay import VideoRelayReceiver

    r = VideoRelayReceiver(MagicMock())
    fake = MagicMock()
    r._relay = fake
    r.stop()
    fake.close.assert_called_once()


def test_receiver_stop_noop_when_no_relay():
    from unittest.mock import MagicMock

    from semantic_transmission.pipeline.video_relay import VideoRelayReceiver

    VideoRelayReceiver(MagicMock()).stop()  # 不应抛错


def test_receiver_run_passes_callback_to_temporal(monkeypatch, tmp_path):
    from unittest.mock import MagicMock

    from semantic_transmission.pipeline.video_relay import VideoRelayReceiver

    r = VideoRelayReceiver(MagicMock())
    captured = {}
    monkeypatch.setattr(
        r,
        "_run_temporal",
        lambda *a, **k: captured.update(k) or MagicMock(),
    )
    cb = lambda i, t, info: None  # noqa: E731
    r.run(
        "0.0.0.0",
        9000,
        str(tmp_path / "o.mp4"),
        reference_mode="prev",
        progress_callback=cb,
    )
    assert captured.get("progress_callback") is cb
