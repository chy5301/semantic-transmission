"""视频流双机 relay 编排：发送端逐帧打包发送 / 接收端逐帧还原合视频。

与 video_pipeline 的单机闭环对称——本模块把发送与接收拆到两个进程/机器，
靠 TransmissionPacket.metadata 的 frame_index/total_frames/fps 对齐帧序。
VLM 经 prompt_fn 注入，保证可在无 GPU 下单测。
"""

from __future__ import annotations

import io
import time
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image

from semantic_transmission.common.image_io import load_as_rgb
from semantic_transmission.common.video_io import read_frames, write_frames
from semantic_transmission.pipeline.batch_processor import BatchResult, SampleResult
from semantic_transmission.pipeline.relay import (
    SocketRelayReceiver,
    SocketRelaySender,
    TransmissionPacket,
)
from semantic_transmission.pipeline.video_pipeline import PromptFn, _fill_failed_frames
from semantic_transmission.receiver.base import BaseReceiver
from semantic_transmission.sender.local_condition_extractor import LocalCannyExtractor


def _encode_edge_png(edge_img: Image.Image) -> bytes:
    """PIL 边缘图编码为 PNG bytes。"""
    buf = io.BytesIO()
    edge_img.save(buf, format="PNG")
    return buf.getvalue()


@dataclass
class VideoSendStats:
    """发送端统计：总帧数 + 逐帧耗时/体积。"""

    total_frames: int
    total_time: float = 0.0
    frames: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "total_frames": self.total_frames,
            "total_time": self.total_time,
            "frames": self.frames,
        }


class VideoRelaySender:
    """发送端编排：read_frames → 逐帧 Canny + prompt_fn → 逐帧发包。"""

    def __init__(self, extractor: LocalCannyExtractor):
        self.extractor = extractor

    def run(
        self,
        input_path,
        host: str,
        port: int,
        prompt_fn: PromptFn,
        *,
        seed: int | None = None,
        fps: float | None = None,
        save_frames_dir: Path | None = None,
    ) -> VideoSendStats:
        """跑通发送端：解码视频、逐帧提边缘+取 prompt、逐帧发送。

        Args:
            input_path: 输入视频路径。
            host: 接收端 IP。
            port: 接收端端口。
            prompt_fn: ``(frame_index, frame_rgb_ndarray) -> prompt_text``。
            seed: 透传给每帧（写入 metadata.seed）。
            fps: 输出帧率，None 时沿用输入 fps，写入 metadata.fps。
            save_frames_dir: 非 None 时把每帧边缘图存盘（调试用）。

        Returns:
            VideoSendStats 逐帧统计。
        """
        frames, meta = read_frames(input_path)
        out_fps = fps if fps is not None else meta.fps
        total = len(frames)
        stats = VideoSendStats(total_frames=total)
        if save_frames_dir is not None:
            save_frames_dir = Path(save_frames_dir)
            save_frames_dir.mkdir(parents=True, exist_ok=True)

        t_all = time.time()
        with SocketRelaySender(host, port) as relay:
            for i, frame in enumerate(frames):
                edge_np = self.extractor.extract(frame)
                edge_img = load_as_rgb(edge_np)
                try:
                    prompt_text = prompt_fn(i, frame)
                except Exception:
                    prompt_text = ""
                edge_bytes = _encode_edge_png(edge_img)
                metadata: dict = {
                    "frame_index": i,
                    "total_frames": total,
                    "fps": out_fps,
                    "name": f"frame_{i:04d}",
                }
                if seed is not None:
                    metadata["seed"] = seed
                packet = TransmissionPacket(
                    edge_image=edge_bytes,
                    prompt_text=prompt_text,
                    metadata=metadata,
                )
                t0 = time.time()
                relay.send(packet)
                relay_elapsed = time.time() - t0
                if save_frames_dir is not None:
                    edge_img.save(save_frames_dir / f"frame_{i:04d}_edge.png")
                stats.frames.append(
                    {
                        "index": i,
                        "relay": relay_elapsed,
                        "prompt_len": len(prompt_text),
                        "packet_bytes": len(edge_bytes)
                        + len(prompt_text.encode("utf-8")),
                    }
                )
        stats.total_time = time.time() - t_all
        return stats


@dataclass
class VideoReceiveResult:
    """接收端结果：统计 + fps + 逐帧 prompt + 输出路径。"""

    stats: BatchResult
    fps: float
    prompts: list[str]
    output_path: Path


def _order_buffer(
    buffer: dict[int, Image.Image | None], total: int
) -> list[Image.Image | None]:
    """按 frame_index 排序为有序列表，缺失帧位填 None。"""
    return [buffer.get(i) for i in range(total)]


class VideoRelayReceiver:
    """接收端编排：收包 → 按 index 缓冲 → process → 收齐合成视频。"""

    def __init__(self, receiver: BaseReceiver):
        self.receiver = receiver

    def run(
        self,
        host: str,
        port: int,
        output_path,
        *,
        timeout: float | None = None,
    ) -> VideoReceiveResult:
        """监听端口、逐帧接收并还原，收齐 total_frames 后合成视频。

        Args:
            host: 监听地址。
            port: 监听端口。
            output_path: 输出视频路径。
            timeout: accept/receive 超时秒数，None 为无限等待。

        Returns:
            VideoReceiveResult（含 BatchResult、fps、逐帧 prompt、输出路径）。

        Raises:
            ConnectionError: 收齐前连接中断。
            ValueError: 全部帧失败（无可用帧合成）。
        """
        output_path = Path(output_path)
        relay = SocketRelayReceiver(host, port)
        relay.start()
        relay.accept(timeout=timeout)

        buffer: dict[int, Image.Image | None] = {}
        prompt_buffer: dict[int, str] = {}
        total: int | None = None
        fps: float = 30.0
        batch: BatchResult | None = None
        received = 0

        try:
            while total is None or received < total:
                try:
                    packet = relay.receive(timeout=timeout)
                except ConnectionError:
                    raise
                except (TimeoutError, OSError, EOFError) as exc:
                    raise ConnectionError("收齐前连接中断") from exc
                idx = int(packet.metadata["frame_index"])
                if total is None:
                    total = int(packet.metadata["total_frames"])
                    fps = float(packet.metadata["fps"])
                    batch = BatchResult(total=total)
                seed = packet.metadata.get("seed")
                sample = SampleResult(name=f"frame_{idx:04d}", status="success")
                t0 = time.time()
                try:
                    img = self.receiver.process(
                        packet.edge_image, packet.prompt_text, seed=seed
                    )
                except Exception as e:
                    img = None
                    sample.status = "failed"
                    sample.error = str(e)
                sample.timings["process"] = time.time() - t0
                batch.add_sample(sample)
                buffer[idx] = img
                prompt_buffer[idx] = packet.prompt_text
                received += 1
        finally:
            relay.close()

        if batch is None or total is None:
            raise ValueError("未收到任何数据包，无法合成视频")
        batch.total_time = sum(s.timings.get("process", 0) for s in batch.samples)
        ordered = _order_buffer(buffer, total)
        filled = _fill_failed_frames(ordered)
        write_frames(output_path, filled, fps=fps)
        prompts = [prompt_buffer.get(i, "") for i in range(total)]
        return VideoReceiveResult(
            stats=batch, fps=fps, prompts=prompts, output_path=output_path
        )


__all__ = [
    "VideoSendStats",
    "VideoRelaySender",
    "VideoReceiveResult",
    "VideoRelayReceiver",
    "_order_buffer",
]
