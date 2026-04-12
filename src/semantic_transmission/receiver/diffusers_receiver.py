"""Diffusers 接收端：使用 diffusers 库直接推理生成图像。"""

from __future__ import annotations

import io
import random
from pathlib import Path

import torch
from PIL import Image

from semantic_transmission.common.config import (
    DiffusersLoaderConfig,
    DiffusersReceiverConfig,
)
from semantic_transmission.common.model_loader import DiffusersModelLoader
from semantic_transmission.receiver.base import BaseReceiver, BatchOutput, FrameInput


class DiffusersReceiver(BaseReceiver):
    """接收端：使用 ZImageControlNetPipeline 从边缘图 + prompt 生成图像。"""

    def __init__(
        self,
        config: DiffusersReceiverConfig | None = None,
        *,
        loader: DiffusersModelLoader | None = None,
    ) -> None:
        self.config = config or DiffusersReceiverConfig()
        if loader is not None:
            self._loader = loader
        else:
            loader_config = DiffusersLoaderConfig(
                model_name=self.config.model_name,
                controlnet_name=self.config.controlnet_name,
                transformer_path=self.config.transformer_path,
                device=self.config.device,
                torch_dtype=self.config.torch_dtype,
            )
            self._loader = DiffusersModelLoader(loader_config)

    @property
    def is_loaded(self) -> bool:
        """模型是否已加载。"""
        return self._loader.is_loaded

    def load(self) -> None:
        """加载模型到 GPU。如已加载则跳过。"""
        self._loader.load()

    def unload(self) -> None:
        """卸载模型，释放 GPU 显存。"""
        self._loader.unload()

    def process(
        self,
        edge_image: Image.Image | bytes | str | Path,
        prompt_text: str,
        seed: int | None = None,
    ) -> Image.Image:
        """根据边缘图和文本描述生成还原图像。

        Args:
            edge_image: 条件图（Canny 边缘图），PIL Image、bytes 或文件路径。
            prompt_text: 图像描述文本。
            seed: 随机种子，None 时随机生成。

        Returns:
            还原图像 PIL.Image。
        """
        pipeline = self._loader.load()

        condition = self._load_condition_image(edge_image)
        width, height = condition.size  # PIL size 返回 (W, H)

        if seed is None:
            seed = random.randint(0, 2**32 - 1)
        generator = torch.Generator(device=self.config.device).manual_seed(seed)

        result = pipeline(
            prompt=prompt_text,
            control_image=condition,
            height=height,
            width=width,
            num_inference_steps=self.config.num_inference_steps,
            guidance_scale=self.config.guidance_scale,
            generator=generator,
        )
        return result.images[0]

    def process_batch(self, frames: list[FrameInput]) -> BatchOutput:
        """批量处理帧序列，模型常驻 GPU 不反复加载。"""
        self._loader.load()
        return super().process_batch(frames)

    @staticmethod
    def _load_condition_image(
        edge_image: Image.Image | bytes | str | Path,
    ) -> Image.Image:
        """将各种输入格式统一转为 RGB PIL.Image。"""
        if isinstance(edge_image, Image.Image):
            img = edge_image
        elif isinstance(edge_image, bytes):
            img = Image.open(io.BytesIO(edge_image))
        else:
            img = Image.open(edge_image)
        if img.mode != "RGB":
            img = img.convert("RGB")
        return img
