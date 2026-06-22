"""video_relay 发送端/接收端编排测试（无 GPU）。"""

import threading
import time

from PIL import Image

from semantic_transmission.common.video_io import write_frames
from semantic_transmission.pipeline.relay import SocketRelayReceiver
from semantic_transmission.pipeline.video_relay import VideoRelaySender
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
