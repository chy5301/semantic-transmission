"""视频流编排：video→video 保底骨架。

VideoPipeline 复用现有逐帧管道（LocalCannyExtractor + receiver.process_batch），
串接 video_io 解码/编码，并在收帧后做失败帧填充 + 序列级 frame_postprocess。
VLM 不在本模块——prompt 由调用方通过 prompt_fn 注入，保证可在无 GPU 下单测。
"""

from __future__ import annotations

from typing import Callable

from PIL import Image

FramePostprocessor = Callable[[list[Image.Image]], list[Image.Image]]
"""序列级帧后处理钩子：list[Image] -> list[Image]。

D1 恒等透传。D5 插帧（返回更长帧列表）/ D6 超分（逐帧映射）替换此实现。
"""


def identity_postprocess(frames: list[Image.Image]) -> list[Image.Image]:
    """D1 默认钩子：原样返回。"""
    return frames


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


__all__ = ["FramePostprocessor", "identity_postprocess", "_fill_failed_frames"]
