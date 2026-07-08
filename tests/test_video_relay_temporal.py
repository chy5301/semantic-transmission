"""video_relay 时序路径（关键帧透传 + 参考帧补偿）单测，无 GPU。"""

import io
import threading
import time

from PIL import Image

from semantic_transmission.common.video_io import write_frames
from semantic_transmission.pipeline.relay import SocketRelayReceiver
from semantic_transmission.pipeline.temporal_policy import TemporalPolicyConfig
from semantic_transmission.pipeline.video_relay import (
    VideoRelayReceiver,
    VideoRelaySender,
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


class _ConfigStub:
    max_side = 512


class _RefRecordingReceiver(BaseReceiver):
    """记录每次 process 收到的 reference_images（数量 + 实际对象），返回可辨识纯色图。"""

    config = _ConfigStub()

    def __init__(self):
        self.calls = []  # list[(prompt_text, num_refs)]
        self.ref_images = []  # list[list[Image.Image]]，与 calls 逐条对应

    def process(self, edge_image, prompt_text, seed=None, reference_images=None):
        n_refs = len(reference_images) if reference_images else 0
        self.calls.append((prompt_text, n_refs))
        self.ref_images.append(list(reference_images) if reference_images else [])
        # 必须与关键帧透传尺寸一致（输入 64x48，fit_working_size(64x48,512)=64x48），
        # 否则 write_frames 混合尺寸抛 ValueError（B2）。
        return Image.new("RGB", (64, 48), color=(0, 0, 255))

    def process_batch(self, frames):  # 抽象方法占位，本测试不用
        raise NotImplementedError


def test_receiver_temporal_passthrough_and_refs(tmp_path):
    src = tmp_path / "in.mp4"
    _make_input_video(src, 5, fps=8.0)
    out = tmp_path / "out.mp4"
    port = _find_free_port()
    recv = _RefRecordingReceiver()
    box = []

    def recv_thread():
        box.append(
            VideoRelayReceiver(recv).run(
                "127.0.0.1", port, out, timeout=10.0, reference_mode="prev"
            )
        )

    t = threading.Thread(target=recv_thread)
    t.start()
    time.sleep(0.2)
    policy = TemporalPolicyConfig(keyframe_interval=2, reference_mode="prev")
    VideoRelaySender(LocalCannyExtractor()).run(
        src, "127.0.0.1", port, prompt_fn=lambda i, f: f"p{i}", temporal_policy=policy
    )
    t.join(timeout=15.0)
    assert not t.is_alive(), "receiver thread timed out"

    # 生成帧 index 1,3 各调一次 process；prev 链在关键帧后有 prev → refs=1。
    assert [c[0] for c in recv.calls] == ["p1", "p3"]
    assert all(n == 1 for _, n in recv.calls)  # prev-only：每个生成帧带 1 个参考帧

    # 身份断言（承重）：仅凭 n_refs==1 无法区分"prev_out 正确复位为前一关键帧"
    # 与"prev_out 残留了错误对象"——两种情况长度都是 1。需比对参考帧的实际像素
    # 内容：生成帧 index1 的参考帧应为 index0 关键帧，index3 的参考帧应为 index2
    # 关键帧（prev-only + interval=2）。关键帧在接收端 = fit_working_size(发送端
    # 解码得到的原始帧, max_side)，用同一份视频解码结果构造期望值逐像素比对，
    # 避免假设视频编解码器对纯色帧完全无损。
    from semantic_transmission.common.video_io import read_frames
    from semantic_transmission.receiver.klein_receiver import fit_working_size

    src_frames, _ = read_frames(src)
    expected_kf0 = fit_working_size(Image.fromarray(src_frames[0]).convert("RGB"), 512)
    expected_kf2 = fit_working_size(Image.fromarray(src_frames[2]).convert("RGB"), 512)
    ref_for_index1 = recv.ref_images[0][0]  # 生成帧 index1 的唯一参考帧
    ref_for_index3 = recv.ref_images[1][0]  # 生成帧 index3 的唯一参考帧
    assert ref_for_index1.size == (64, 48)
    assert ref_for_index1.tobytes() == expected_kf0.tobytes()
    assert ref_for_index3.size == (64, 48)
    assert ref_for_index3.tobytes() == expected_kf2.tobytes()

    result = box[0]
    assert result.stats.keyframe_count == 3
    assert result.stats.generated_frames == 2
    assert result.stats.keyframe_indices == [0, 2, 4]
    assert result.output_path == out


class _FailingRefReceiver(_RefRecordingReceiver):
    """生成帧全部抛异常，验证失败帧填充 + prev 链不被污染。"""

    def process(self, edge_image, prompt_text, seed=None, reference_images=None):
        self.calls.append((prompt_text, len(reference_images or [])))
        raise RuntimeError("fake gen failure")


def test_receiver_temporal_failed_generated_frames(tmp_path):
    from semantic_transmission.common.video_io import read_frames

    src = tmp_path / "in.mp4"
    _make_input_video(src, 5, fps=8.0)
    out = tmp_path / "out.mp4"
    port = _find_free_port()
    box = []

    def recv_thread():
        box.append(
            VideoRelayReceiver(_FailingRefReceiver()).run(
                "127.0.0.1", port, out, timeout=10.0, reference_mode="prev"
            )
        )

    t = threading.Thread(target=recv_thread)
    t.start()
    time.sleep(0.2)
    policy = TemporalPolicyConfig(keyframe_interval=2, reference_mode="prev")
    VideoRelaySender(LocalCannyExtractor()).run(
        src, "127.0.0.1", port, prompt_fn=lambda i, f: f"p{i}", temporal_policy=policy
    )
    t.join(timeout=15.0)
    assert not t.is_alive()

    frames, _ = read_frames(out)
    assert len(frames) == 5  # 失败生成帧被关键帧填充，帧数守恒
    assert box[0].failed_indices == [1, 3]
    assert box[0].stats.keyframe_count == 3


class _NoRefReceiver(BaseReceiver):
    """process 不接受 reference_images——触发能力门控。"""

    config = _ConfigStub()

    def process(self, edge_image, prompt_text, seed=None):
        return Image.new("RGB", (512, 384))

    def process_batch(self, frames):
        raise NotImplementedError


def test_receiver_temporal_capability_gate(tmp_path):
    import pytest

    out = tmp_path / "out.mp4"
    port = _find_free_port()
    with pytest.raises(TypeError, match="reference_images"):
        VideoRelayReceiver(_NoRefReceiver()).run(
            "127.0.0.1", port, out, timeout=1.0, reference_mode="prev"
        )


def _valid_kf_png(size=(64, 48), color=(10, 20, 30)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color=color).save(buf, format="PNG")
    return buf.getvalue()


def test_receiver_temporal_malformed_keyframe_does_not_abort(tmp_path):
    """畸形关键帧包（frame_type=keyframe 但 edge_image 非法字节，relay 裸 TCP
    无校验，真实场景可能出现）：该帧应记为失败，不能让 Image 解码异常从 while
    循环冒泡、作废已缓存的所有帧；prev_out/last_kf 也不应被畸形帧污染。
    """
    from semantic_transmission.common.video_io import read_frames
    from semantic_transmission.pipeline.relay import (
        SocketRelaySender,
        TransmissionPacket,
    )

    out = tmp_path / "out.mp4"
    port = _find_free_port()
    recv = _RefRecordingReceiver()
    box = []

    def recv_thread():
        box.append(
            VideoRelayReceiver(recv).run(
                "127.0.0.1", port, out, timeout=10.0, reference_mode="prev"
            )
        )

    t = threading.Thread(target=recv_thread)
    t.start()
    time.sleep(0.2)

    total = 3
    with SocketRelaySender("127.0.0.1", port) as s:
        # idx0：合法关键帧
        s.send(
            TransmissionPacket(
                edge_image=_valid_kf_png(),
                prompt_text="",
                metadata={
                    "frame_index": 0,
                    "total_frames": total,
                    "fps": 8.0,
                    "frame_type": "keyframe",
                },
            )
        )
        # idx1：畸形关键帧——非法字节，Image.open 会抛 UnidentifiedImageError。
        s.send(
            TransmissionPacket(
                edge_image=b"not a png",
                prompt_text="",
                metadata={
                    "frame_index": 1,
                    "total_frames": total,
                    "fps": 8.0,
                    "frame_type": "keyframe",
                },
            )
        )
        # idx2：正常生成帧，携 prompt。
        edge_buf = io.BytesIO()
        Image.new("RGB", (64, 48), color=(5, 6, 7)).save(edge_buf, format="PNG")
        s.send(
            TransmissionPacket(
                edge_image=edge_buf.getvalue(),
                prompt_text="p2",
                metadata={
                    "frame_index": 2,
                    "total_frames": total,
                    "fps": 8.0,
                    "frame_type": "generated",
                },
            )
        )

    t.join(timeout=15.0)
    assert not t.is_alive(), "receiver thread timed out"

    result = box[0]
    # 畸形关键帧记为失败，其余帧不受影响、整段仍成功合成。
    assert result.failed_indices == [1]
    # 失败关键帧不计入 keyframe_indices/keyframe_count（与生成帧失败分支对称）。
    assert result.stats.keyframe_indices == [0]
    assert result.stats.keyframe_count == 1
    assert result.stats.generated_frames == total - 1

    # prev_out/last_kf 未被畸形帧污染：生成帧 idx2 的参考帧应仍是 idx0 的关键帧
    # （身份断言：若 prev_out 被畸形帧复位为 None/污染对象，refs 长度或内容会变）。
    assert recv.calls == [("p2", 1)]
    ref = recv.ref_images[0][0]
    assert ref.tobytes() == Image.new("RGB", (64, 48), color=(10, 20, 30)).tobytes()

    # 帧数守恒：整段仍合成，输出帧数 == total（畸形帧未作废已缓存的帧）。
    frames, _ = read_frames(out)
    assert len(frames) == total


def test_stateless_receiver_rejects_temporal_packet(tmp_path):
    """无状态接收端（reference_mode=None）收到带 frame_type 的时序包应 fail-fast。

    对应真实误配置场景：发送端默认时序（video-sender --keyframe-interval 12
    发关键帧整帧包 + metadata.frame_type），若接收端被显式配成
    --backend diffusers（无状态），整帧包会被当 Canny 边缘图静默喂给生成器，
    第 0/12/24... 帧静默劣化不报错。此处验证接收端能识别并 loud 报错。
    """
    from semantic_transmission.pipeline.relay import (
        SocketRelaySender,
        TransmissionPacket,
    )

    out = tmp_path / "out.mp4"
    port = _find_free_port()
    errors = []

    def recv_thread():
        try:
            VideoRelayReceiver(_RefRecordingReceiver()).run(
                "127.0.0.1", port, out, timeout=5.0, reference_mode=None
            )
        except Exception as e:
            errors.append(e)

    t = threading.Thread(target=recv_thread)
    t.start()
    time.sleep(0.2)

    buf = io.BytesIO()
    Image.new("RGB", (8, 8), color=(1, 1, 1)).save(buf, format="PNG")
    with SocketRelaySender("127.0.0.1", port) as s:
        s.send(
            TransmissionPacket(
                edge_image=buf.getvalue(),
                prompt_text="",
                metadata={
                    "frame_index": 0,
                    "total_frames": 1,
                    "fps": 8.0,
                    "frame_type": "keyframe",
                },
            )
        )
    t.join(timeout=10.0)
    assert not t.is_alive(), "receiver thread timed out"

    assert len(errors) == 1
    assert isinstance(errors[0], ConnectionError)
    msg = str(errors[0])
    assert "无状态" in msg and "frame_type" in msg
