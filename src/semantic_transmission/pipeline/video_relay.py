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
from semantic_transmission.pipeline.temporal_policy import (
    FRAME_TYPE_GENERATED,
    FRAME_TYPE_KEYFRAME,
    TemporalPolicyConfig,
    build_reference_images,
    is_keyframe,
    require_temporal_capable,
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
    """发送端统计：总帧数 + 逐帧耗时/体积 + 时序码率账本。"""

    total_frames: int
    total_time: float = 0.0
    frames: list[dict] = field(default_factory=list)
    # 时序路径码率账本：关键帧整帧 vs 生成帧语义码流的帧数与字节数。
    keyframe_count: int = 0
    generated_count: int = 0
    keyframe_bytes: int = 0
    generated_bytes: int = 0

    def to_dict(self) -> dict:
        return {
            "total_frames": self.total_frames,
            "total_time": self.total_time,
            "keyframe_count": self.keyframe_count,
            "generated_count": self.generated_count,
            "keyframe_bytes": self.keyframe_bytes,
            "generated_bytes": self.generated_bytes,
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
        temporal_policy: "TemporalPolicyConfig | None" = None,
        progress_callback=None,
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
            temporal_policy: 非 None 时按 is_keyframe 分流——关键帧发整帧 RGB
                PNG（空 prompt），生成帧发 Canny 边缘图 + prompt；metadata 打
                frame_type 标签。None 时保持无状态逐帧路径（不加 frame_type）。
            progress_callback: 非 None 时逐帧发包后回调
                ``(i, total, {"frame_type": ...})``，用于 GUI 展示发送进度。

        Returns:
            VideoSendStats 逐帧统计（含时序码率账本）。

        Raises:
            ValueError: temporal_policy 非 None 且 keyframe_passthrough=False
                （relay 时序路径仅支持关键帧整帧透传）。
        """
        # relay 时序路径仅支持 keyframe_passthrough=True（关键帧整帧传输）——
        # 库层 fail-fast 守卫，与 CLI 不暴露 --no-keyframe-passthrough 一致（S3）。
        if temporal_policy is not None and not temporal_policy.keyframe_passthrough:
            raise ValueError(
                "relay 时序路径仅支持 keyframe_passthrough=True（关键帧整帧传输）"
            )
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
                is_kf = temporal_policy is not None and is_keyframe(i, temporal_policy)
                metadata: dict = {
                    "frame_index": i,
                    "total_frames": total,
                    "fps": out_fps,
                    "name": f"frame_{i:04d}",
                }
                if seed is not None:
                    metadata["seed"] = seed

                if is_kf:
                    # 关键帧透传：发整帧 RGB PNG、空 prompt、不提 Canny 不调 prompt_fn。
                    payload_bytes = _encode_edge_png(load_as_rgb(frame))
                    prompt_text = ""
                    metadata["frame_type"] = FRAME_TYPE_KEYFRAME
                    stats.keyframe_count += 1
                    stats.keyframe_bytes += len(payload_bytes)
                else:
                    edge_img = load_as_rgb(self.extractor.extract(frame))
                    try:
                        prompt_text = prompt_fn(i, frame)
                    except Exception:
                        prompt_text = ""
                    payload_bytes = _encode_edge_png(edge_img)
                    if temporal_policy is not None:
                        metadata["frame_type"] = FRAME_TYPE_GENERATED
                        stats.generated_count += 1

                # prompt 字节只算一次，generated_bytes 与 packet_bytes 复用同一个值。
                prompt_bytes = len(prompt_text.encode("utf-8"))
                if temporal_policy is not None and not is_kf:
                    stats.generated_bytes += len(payload_bytes) + prompt_bytes

                packet = TransmissionPacket(
                    edge_image=payload_bytes,
                    prompt_text=prompt_text,
                    metadata=metadata,
                )
                t0 = time.time()
                relay.send(packet)
                relay_elapsed = time.time() - t0
                if save_frames_dir is not None:
                    (save_frames_dir / f"frame_{i:04d}_edge.png").write_bytes(
                        payload_bytes
                    )
                stats.frames.append(
                    {
                        "index": i,
                        "relay": relay_elapsed,
                        "prompt_len": len(prompt_text),
                        "packet_bytes": len(payload_bytes) + prompt_bytes,
                    }
                )
                if progress_callback is not None:
                    progress_callback(
                        i, total, {"frame_type": metadata.get("frame_type")}
                    )
        stats.total_time = time.time() - t_all
        return stats


@dataclass
class VideoReceiveResult:
    """接收端结果：统计 + fps + 逐帧 prompt + 输出路径 + 失败帧索引。"""

    stats: BatchResult
    fps: float
    prompts: list[str]
    output_path: Path
    failed_indices: list[int] = field(default_factory=list)


def _order_buffer(
    buffer: dict[int, Image.Image | None], total: int
) -> list[Image.Image | None]:
    """按 frame_index 排序为有序列表，缺失帧位填 None。"""
    return [buffer.get(i) for i in range(total)]


class VideoRelayReceiver:
    """接收端编排：收包 → 按 index 缓冲 → process → 收齐合成视频。"""

    def __init__(self, receiver: BaseReceiver):
        self.receiver = receiver
        self._relay: SocketRelayReceiver | None = None

    def run(
        self,
        host: str,
        port: int,
        output_path,
        *,
        timeout: float | None = None,
        reference_mode: str | None = None,
        progress_callback=None,
    ) -> VideoReceiveResult:
        """监听端口、逐帧接收并还原，收齐 total_frames 后合成视频。

        Args:
            host: 监听地址。
            port: 监听端口。
            output_path: 输出视频路径。
            timeout: accept/receive 超时秒数，None 为无限等待。
            reference_mode: 非 None 时走 ``_run_temporal``（持状态串行参考帧
                补偿，按 metadata.frame_type 分支）；None 时保持无状态路径
                （逐字节向后兼容）。

        Returns:
            VideoReceiveResult（含 BatchResult、fps、逐帧 prompt、输出路径）。

        Raises:
            ConnectionError: 收齐前连接中断。
            ValueError: 全部帧失败（无可用帧合成）。
            TypeError: reference_mode 非 None 但 receiver.process 不接受
                reference_images（能力门控，提示改用 --backend klein）。
        """
        # 库层防御性归一：CLI 已把 "none" 转成 None 再调用，但直接调库传字符串
        # "none"（Click Choice 的合法取值）会因 "none" is not None 误入时序
        # 分支——在分派前统一归一，保证库层单独调用也安全。
        if reference_mode == "none":
            reference_mode = None
        if reference_mode is not None:
            return self._run_temporal(
                host,
                port,
                output_path,
                reference_mode,
                timeout=timeout,
                progress_callback=progress_callback,
            )
        self._relay = SocketRelayReceiver(host, port)

        buffer: dict[int, Image.Image | None] = {}
        prompt_buffer: dict[int, str] = {}
        total: int | None = None
        fps: float = 30.0
        batch: BatchResult | None = None
        failed_indices: list[int] = []

        try:
            self._relay.start()
            self._relay.accept(timeout=timeout)
            t_start = time.time()
            while total is None or len(buffer) < total:
                try:
                    packet = self._relay.receive(timeout=timeout)
                except ConnectionError:
                    raise
                except (TimeoutError, OSError, EOFError) as exc:
                    raise ConnectionError("收齐前连接中断") from exc
                if packet.metadata.get("frame_type") is not None:
                    # 无状态路径收到时序包（对端是时序发送端）：整帧透传的关键帧
                    # 包若被当 Canny 边缘图喂给无状态 process，会静默劣化而不报错
                    # （见设计文档风险项）。fail-fast 提示改用时序接收端。
                    raise ConnectionError(
                        "收到时序包（含 frame_type）但接收端为无状态模式，"
                        "请用 --backend klein --reference-mode prev"
                    )
                if (
                    packet.metadata.get("frame_index") is None
                    or packet.metadata.get("total_frames") is None
                    or packet.metadata.get("fps") is None
                ):
                    raise ConnectionError("收到缺少必要 metadata 字段的包")
                idx = int(packet.metadata["frame_index"])
                if total is None:
                    total = int(packet.metadata["total_frames"])
                    fps = float(packet.metadata["fps"])
                    batch = BatchResult(total=total)
                if idx in buffer:
                    # 重复 frame_index：跳过重复处理与计数（防御异常发送端重传）
                    continue
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
                    # 上面的去重 continue 已保证每个 idx 只到达此处一次
                    failed_indices.append(idx)
                sample.timings["process"] = time.time() - t0
                batch.add_sample(sample)
                buffer[idx] = img
                prompt_buffer[idx] = packet.prompt_text
                if progress_callback is not None:
                    progress_callback(idx, total, {"stage": "receive"})
        finally:
            self._relay.close()
            self._relay = None

        if batch is None or total is None:
            raise ValueError("未收到任何数据包，无法合成视频")
        batch.total_time = time.time() - t_start
        ordered = _order_buffer(buffer, total)
        filled = _fill_failed_frames(ordered)
        write_frames(output_path, filled, fps=fps)
        prompts = [prompt_buffer.get(i, "") for i in range(total)]
        return VideoReceiveResult(
            stats=batch,
            fps=fps,
            prompts=prompts,
            output_path=output_path,
            failed_indices=sorted(failed_indices),
        )

    def _run_temporal(
        self,
        host: str,
        port: int,
        output_path,
        reference_mode: str,
        *,
        timeout: float | None = None,
        progress_callback=None,
    ) -> VideoReceiveResult:
        """有状态串行时序路径：关键帧透传复位锚点 + 生成帧带参考帧补偿。

        与单机 VideoPipeline._run_temporal 对称——状态（prev_out/last_kf）留在
        接收端，输入改自网络，按 metadata.frame_type 分支。依赖单 TCP 流有序性
        保证帧序到达（prev 链前提）。
        """
        from semantic_transmission.receiver.klein_receiver import fit_working_size

        # 能力门控：与单机 VideoPipeline._run_temporal 共用同一门控
        # （temporal_policy.require_temporal_capable），保证提示文案一致。
        max_side = require_temporal_capable(self.receiver)

        self._relay = SocketRelayReceiver(host, port)
        buffer: dict[int, Image.Image | None] = {}
        prompt_buffer: dict[int, str] = {}
        total: int | None = None
        fps: float = 30.0
        batch: BatchResult | None = None
        failed_indices: list[int] = []
        keyframe_indices: list[int] = []
        prev_out: Image.Image | None = None
        last_kf: Image.Image | None = None

        try:
            self._relay.start()
            self._relay.accept(timeout=timeout)
            t_start = time.time()
            while total is None or len(buffer) < total:
                try:
                    packet = self._relay.receive(timeout=timeout)
                except ConnectionError:
                    raise
                except (TimeoutError, OSError, EOFError) as exc:
                    raise ConnectionError("收齐前连接中断") from exc
                md = packet.metadata
                if (
                    md.get("frame_index") is None
                    or md.get("total_frames") is None
                    or md.get("fps") is None
                    or md.get("frame_type") is None
                ):
                    raise ConnectionError("收到缺少必要 metadata 字段的包")
                idx = int(md["frame_index"])
                if total is None:
                    total = int(md["total_frames"])
                    fps = float(md["fps"])
                    batch = BatchResult(total=total)
                if idx in buffer:
                    continue  # 去重：重复 frame_index 不重复处理
                seed = md.get("seed")

                if md["frame_type"] == FRAME_TYPE_KEYFRAME:
                    t0 = time.time()
                    try:
                        kf = fit_working_size(load_as_rgb(packet.edge_image), max_side)
                    except Exception as e:
                        # 畸形关键帧包（relay 裸 TCP 无校验，Image 解码可能抛
                        # UnidentifiedImageError/OSError 等）：仅废弃该帧——
                        # 不复位 prev_out/last_kf（保留上一有效锚点，畸形帧不
                        # 污染串行链），也不计入 keyframe_indices（失败关键帧
                        # 不计关键帧统计，generated_frames=total-len(
                        # keyframe_indices) 不变量仍成立）。与生成帧失败分支对称。
                        buffer[idx] = None
                        prompt_buffer[idx] = ""
                        failed_indices.append(idx)
                        batch.add_sample(
                            SampleResult(
                                name=f"frame_{idx:04d}",
                                status="failed",
                                error=str(e),
                                timings={"process": time.time() - t0},
                            )
                        )
                        if progress_callback is not None:
                            progress_callback(idx, total, {"stage": "receive"})
                        continue
                    buffer[idx] = kf
                    prompt_buffer[idx] = ""
                    keyframe_indices.append(idx)
                    prev_out = kf  # 链首复位到真关键帧
                    last_kf = kf
                    batch.add_sample(
                        SampleResult(
                            name=f"frame_{idx:04d}",
                            status="success",
                            timings={"process": time.time() - t0},
                        )
                    )
                    if progress_callback is not None:
                        progress_callback(idx, total, {"stage": "receive"})
                    continue
                elif md["frame_type"] == FRAME_TYPE_GENERATED:
                    # 生成帧：带参考帧补偿。
                    refs = build_reference_images(reference_mode, prev_out, last_kf)
                    sample = SampleResult(name=f"frame_{idx:04d}", status="success")
                    t0 = time.time()
                    try:
                        img = self.receiver.process(
                            packet.edge_image,
                            packet.prompt_text,
                            seed=seed,
                            reference_images=refs,
                        )
                    except Exception as e:
                        img = None
                        sample.status = "failed"
                        sample.error = str(e)
                        failed_indices.append(idx)
                    sample.timings["process"] = time.time() - t0
                    batch.add_sample(sample)
                    buffer[idx] = img
                    prompt_buffer[idx] = packet.prompt_text
                    prev_out = (
                        img if img is not None else prev_out
                    )  # 失败帧不污染 prev 链
                    if progress_callback is not None:
                        progress_callback(idx, total, {"stage": "receive"})
                else:
                    # 未知 frame_type：fail-fast，不静默当生成帧处理（拼写漂移等
                    # 场景的防御——隐式 else 会悄悄吞掉未来协议漂移）。
                    raise ConnectionError(f"未知 frame_type: {md['frame_type']!r}")
        finally:
            self._relay.close()
            self._relay = None

        if batch is None or total is None:
            raise ValueError("未收到任何数据包，无法合成视频")
        batch.total_time = time.time() - t_start
        batch.keyframe_count = len(keyframe_indices)
        batch.generated_frames = total - len(keyframe_indices)
        batch.keyframe_indices = sorted(keyframe_indices)

        ordered = _order_buffer(buffer, total)
        filled = _fill_failed_frames(ordered)
        write_frames(output_path, filled, fps=fps)
        prompts = [prompt_buffer.get(i, "") for i in range(total)]
        return VideoReceiveResult(
            stats=batch,
            fps=fps,
            prompts=prompts,
            output_path=output_path,
            failed_indices=sorted(failed_indices),
        )

    def stop(self) -> None:
        """从外部线程中断监听：关闭 socket 使阻塞的 accept/receive 抛错退出。"""
        if self._relay is not None:
            self._relay.close()


__all__ = [
    "VideoSendStats",
    "VideoRelaySender",
    "VideoReceiveResult",
    "VideoRelayReceiver",
    "_order_buffer",
]
