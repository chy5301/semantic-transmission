"""视频流编排：video→video 保底骨架。

VideoPipeline 复用现有逐帧管道（LocalCannyExtractor + receiver.process_batch），
串接 video_io 解码/编码，并在收帧后做失败帧填充 + 序列级 frame_postprocess。
VLM 不在本模块——prompt 由调用方通过 prompt_fn 注入，保证可在无 GPU 下单测。
"""

from __future__ import annotations

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
