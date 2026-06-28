"""视频流编排：video→video 保底骨架。

VideoPipeline 复用现有逐帧管道（LocalCannyExtractor + receiver.process_batch），
串接 video_io 解码/编码，并在收帧后做失败帧填充 + 序列级 frame_postprocess。
VLM 不在本模块——prompt 由调用方通过 prompt_fn 注入，保证可在无 GPU 下单测。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from PIL import Image

from semantic_transmission.common.image_io import load_as_rgb
from semantic_transmission.common.video_io import read_frames, write_frames
from semantic_transmission.pipeline.batch_processor import BatchResult
from semantic_transmission.receiver.base import BaseReceiver, FrameInput
from semantic_transmission.sender.local_condition_extractor import LocalCannyExtractor

FramePostprocessor = Callable[[list[Image.Image]], list[Image.Image]]
"""序列级帧后处理钩子：list[Image] -> list[Image]。

D1 恒等透传。D5 插帧（返回更长帧列表）/ D6 超分（逐帧映射）替换此实现。
"""


def identity_postprocess(frames: list[Image.Image]) -> list[Image.Image]:
    """D1 默认钩子：原样返回。"""
    return frames


PromptFn = Callable[[int, Any], str]
"""逐帧 prompt 提供器：(frame_index, frame_rgb_ndarray) -> prompt_text。"""


def _fill_failed_frames(images: list[Image.Image | None]) -> list[Image.Image]:
    """用上一成功帧填充失败帧（None），保证输出帧数 = 输入帧数。

    前导 None 用第一帧成功帧回填；中间 None 用上一成功帧填充。

    Raises:
        ValueError: 全部帧失败（无可用帧）。
    """
    valid = [img for img in images if img is not None]
    if not valid:
        raise ValueError("所有帧生成失败，无可用帧")

    filled: list[Image.Image] = []
    last: Image.Image = valid[0]  # 前导 None 用第一帧成功帧
    for img in images:
        if img is not None:
            last = img
        filled.append(last)
    return filled


def _save_artifacts(artifacts_dir, frame_inputs: list[FrameInput], meta) -> None:
    """保存语义传输的中间产物：逐帧 prompt（语义码流）+ Canny 边缘图。

    产出：
        ``prompts.json`` —— 逐帧描述文本 + 字符/字节数 + 整段语义码率统计；
        ``edges/frame_XXXX.png`` —— 每帧条件信息（Canny 边缘图）。

    VLM 描述是语义传输的"压缩码流"，保存它用于复现、质量核查与码率
    （压缩率）统计。须在 VLM 释放前调用（此时 frame_inputs 已含全部 prompt）。
    """
    artifacts_dir = Path(artifacts_dir)
    edges_dir = artifacts_dir / "edges"
    edges_dir.mkdir(parents=True, exist_ok=True)

    frames_meta: list[dict[str, Any]] = []
    total_bytes = 0
    for fi in frame_inputs:
        index = fi.metadata["index"]
        prompt = fi.prompt_text
        byte_count = len(prompt.encode("utf-8"))
        total_bytes += byte_count
        frames_meta.append(
            {
                "index": index,
                "prompt": prompt,
                "char_count": len(prompt),
                "byte_count": byte_count,
            }
        )
        fi.edge_image.save(edges_dir / f"frame_{index:04d}.png")

    n = len(frame_inputs)
    avg_bytes = total_bytes / n if n else 0.0
    payload = {
        "total_frames": n,
        "fps": meta.fps,
        "semantic_bitrate": {
            "total_bytes": total_bytes,
            "avg_bytes_per_frame": round(avg_bytes, 2),
            "avg_bytes_per_second": round(avg_bytes * meta.fps, 2),
        },
        "frames": frames_meta,
    }
    (artifacts_dir / "prompts.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )


class VideoPipeline:
    """video→video 编排：解码→逐帧 Canny+构造 FrameInput→process_batch→
    失败帧填充→frame_postprocess→编码。"""

    def __init__(
        self,
        receiver: BaseReceiver,
        extractor: LocalCannyExtractor,
        frame_postprocess: FramePostprocessor = identity_postprocess,
    ):
        self.receiver = receiver
        self.extractor = extractor
        self.frame_postprocess = frame_postprocess

    def run(
        self,
        input_path,
        output_path,
        prompt_fn: PromptFn,
        seed: int | None = None,
        fps: float | None = None,
        on_prompts_ready: Callable[[], None] | None = None,
        save_artifacts_to: Path | None = None,
    ) -> BatchResult:
        """跑通一段视频的 video→video 闭环，返回逐帧/整段统计。

        Args:
            input_path: 输入视频路径。
            output_path: 输出视频路径。
            prompt_fn: ``(frame_index, frame_rgb_ndarray) -> prompt_text``。
            seed: 透传给每帧的随机种子。
            fps: 输出帧率，None 时沿用输入 fps。
            on_prompts_ready: 全部帧 prompt 生成完毕、接收端 ``process_batch``
                （加载生成模型）之前调用的钩子。auto-prompt 时由调用方传入
                ``vlm_sender.unload``，在生成模型上显存前先释放 VLM，避免
                VLM 与 Diffusers 同驻 24GB 触发 OOM / device_map=auto 的 CPU offload。
            save_artifacts_to: 若提供，将语义中间产物（``prompts.json`` 逐帧描述
                + 码率统计、``edges/`` 边缘图）保存到该目录。None 时不保存。

        Returns:
            BatchResult 逐帧计时 + 成功率统计。
        """
        frames, meta = read_frames(input_path)

        frame_inputs: list[FrameInput] = []
        for i, frame in enumerate(frames):
            edge_np = self.extractor.extract(frame)
            edge_img = load_as_rgb(edge_np)
            try:
                prompt_text = prompt_fn(i, frame)
            except Exception:
                prompt_text = ""
            frame_inputs.append(
                FrameInput(
                    edge_image=edge_img,
                    prompt_text=prompt_text,
                    seed=seed,
                    metadata={"name": f"frame_{i:04d}", "index": i},
                )
            )

        # 保存语义中间产物（prompt 码流 + 边缘图）须在 on_prompts_ready 释放
        # VLM 前完成——此时 frame_inputs 已含全部 prompt 文本。
        if save_artifacts_to is not None:
            _save_artifacts(save_artifacts_to, frame_inputs, meta)

        # VLM 描述阶段已结束：在接收端加载生成模型前释放 VLM 显存，确保两模型
        # 不同时驻留 GPU（见 on_prompts_ready 说明）。
        if on_prompts_ready is not None:
            on_prompts_ready()

        output = self.receiver.process_batch(frame_inputs)
        filled = _fill_failed_frames(output.images)
        processed = self.frame_postprocess(filled)
        write_frames(output_path, processed, fps=fps if fps is not None else meta.fps)
        return output.stats


__all__ = [
    "FramePostprocessor",
    "identity_postprocess",
    "PromptFn",
    "VideoPipeline",
]
