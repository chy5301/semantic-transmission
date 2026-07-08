"""video_relay 时序路径（关键帧透传 + 参考帧补偿）单测，无 GPU。"""

import io
import threading
import time

from PIL import Image

from semantic_transmission.common.video_io import write_frames
from semantic_transmission.pipeline.relay import SocketRelayReceiver
from semantic_transmission.pipeline.temporal_policy import TemporalPolicyConfig
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


def _collect_packets(port, count, out):
    with SocketRelayReceiver("127.0.0.1", port) as r:
        for _ in range(count):
            out.append(r.receive(timeout=5.0))


def test_sender_temporal_tags_keyframe_and_generated(tmp_path):
    src = tmp_path / "in.mp4"
    _make_input_video(src, 5, fps=8.0)
    port = _find_free_port()
    received = []
    t = threading.Thread(target=_collect_packets, args=(port, 5, received))
    t.start()
    time.sleep(0.2)

    policy = TemporalPolicyConfig(keyframe_interval=2, reference_mode="prev")
    VideoRelaySender(LocalCannyExtractor()).run(
        src, "127.0.0.1", port, prompt_fn=lambda i, f: f"p{i}", temporal_policy=policy
    )
    t.join(timeout=5.0)

    # interval=2 → 关键帧 index 0,2,4；生成帧 1,3
    types = [p.metadata["frame_type"] for p in received]
    assert types == ["keyframe", "generated", "keyframe", "generated", "keyframe"]
    # 关键帧：空 prompt + 整帧 PNG（64x48）；生成帧：携 prompt
    kf = received[0]
    assert kf.prompt_text == ""
    assert Image.open(io.BytesIO(kf.edge_image)).size == (64, 48)
    assert received[1].prompt_text == "p1"


def test_sender_temporal_rate_ledger(tmp_path):
    src = tmp_path / "in.mp4"
    _make_input_video(src, 5, fps=8.0)
    port = _find_free_port()
    received = []
    t = threading.Thread(target=_collect_packets, args=(port, 5, received))
    t.start()
    time.sleep(0.2)

    policy = TemporalPolicyConfig(keyframe_interval=2, reference_mode="prev")
    stats = VideoRelaySender(LocalCannyExtractor()).run(
        src, "127.0.0.1", port, prompt_fn=lambda i, f: f"p{i}", temporal_policy=policy
    )
    t.join(timeout=5.0)

    assert stats.keyframe_count == 3  # index 0,2,4
    assert stats.generated_count == 2  # index 1,3
    assert stats.keyframe_bytes > 0
    assert stats.generated_bytes > 0
    d = stats.to_dict()
    assert d["keyframe_count"] == 3 and d["generated_count"] == 2


def test_sender_temporal_rejects_non_passthrough(tmp_path):
    """relay 时序守卫：keyframe_passthrough=False 直接 fail-fast（S3）。"""
    import pytest

    src = tmp_path / "in.mp4"
    _make_input_video(src, 2)
    policy = TemporalPolicyConfig(
        keyframe_interval=2, reference_mode="prev", keyframe_passthrough=False
    )
    with pytest.raises(ValueError, match="keyframe_passthrough"):
        VideoRelaySender(LocalCannyExtractor()).run(
            src, "127.0.0.1", 9999, prompt_fn=lambda i, f: "x", temporal_policy=policy
        )
