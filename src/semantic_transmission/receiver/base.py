"""接收端抽象基类定义。"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from PIL import Image

from semantic_transmission.pipeline.batch_processor import BatchResult, SampleResult


@dataclass
class FrameInput:
    """单帧输入：边缘图 + 文本描述 + 可选种子。"""

    edge_image: Image.Image | bytes | str | Path
    prompt_text: str
    seed: int | None = None
    metadata: dict[str, Any] | None = None


@dataclass
class BatchOutput:
    """批量处理输出：图像列表 + 统计信息。"""

    images: list[Image.Image | None] = field(default_factory=list)
    stats: BatchResult = field(default_factory=lambda: BatchResult(total=0))


class BaseReceiver(ABC):
    """接收端抽象基类：从文本描述和条件图还原图像。"""

    @abstractmethod
    def process(
        self,
        edge_image: Image.Image | bytes | str | Path,
        prompt_text: str,
        seed: int | None = None,
    ) -> Image.Image:
        """根据文本描述和条件图还原图像。

        Args:
            edge_image: 条件图（如 Canny 边缘图），PIL Image、bytes 或文件路径。
            prompt_text: 图像描述文本。
            seed: 随机种子，None 时随机生成。

        Returns:
            还原图像 PIL.Image。
        """

    def process_batch(self, frames: list[FrameInput]) -> BatchOutput:
        """批量处理帧序列，逐帧调用 process。

        Args:
            frames: 帧输入列表。

        Returns:
            BatchOutput 包含生成图像列表和统计信息。
        """
        batch = BatchResult(total=len(frames))
        images: list[Image.Image | None] = []
        for i, frame in enumerate(frames):
            name = (
                frame.metadata.get("name", f"frame_{i:04d}")
                if frame.metadata
                else f"frame_{i:04d}"
            )
            sample = SampleResult(name=name, status="success")
            t0 = time.time()
            try:
                img = self.process(frame.edge_image, frame.prompt_text, frame.seed)
                images.append(img)
            except Exception as e:
                sample.status = "failed"
                sample.error = str(e)
                images.append(None)
            sample.timings["process"] = time.time() - t0
            batch.add_sample(sample)
        batch.total_time = sum(s.timings.get("process", 0) for s in batch.samples)
        return BatchOutput(images=images, stats=batch)
