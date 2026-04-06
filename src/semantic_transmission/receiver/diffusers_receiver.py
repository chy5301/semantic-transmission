"""Diffusers 接收端：使用 diffusers 库直接推理生成图像。"""

import gc
import random
from pathlib import Path

import torch
from PIL import Image

from semantic_transmission.common.config import DiffusersReceiverConfig
from semantic_transmission.receiver.base import BaseReceiver

_TORCH_DTYPE_MAP = {
    "float16": torch.float16,
    "bfloat16": torch.bfloat16,
    "float32": torch.float32,
}


class DiffusersReceiver(BaseReceiver):
    """接收端：使用 ZImageControlNetPipeline 从边缘图 + prompt 生成图像。"""

    def __init__(self, config: DiffusersReceiverConfig | None = None) -> None:
        self.config = config or DiffusersReceiverConfig()
        self._pipeline = None

    @property
    def is_loaded(self) -> bool:
        """模型是否已加载。"""
        return self._pipeline is not None

    def load(self) -> None:
        """加载模型到 GPU。如已加载则跳过。"""
        if self._pipeline is not None:
            return

        from diffusers import ZImageControlNetModel, ZImageControlNetPipeline

        dtype = _TORCH_DTYPE_MAP.get(self.config.torch_dtype, torch.bfloat16)

        controlnet = ZImageControlNetModel.from_pretrained(
            self.config.controlnet_name,
            torch_dtype=dtype,
        )
        self._pipeline = ZImageControlNetPipeline.from_pretrained(
            self.config.model_name,
            controlnet=controlnet,
            torch_dtype=dtype,
        ).to(self.config.device)

    def unload(self) -> None:
        """卸载模型，释放 GPU 显存。"""
        if self._pipeline is None:
            return
        self._pipeline = None
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        gc.collect()

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
        self.load()
        pipeline = self._pipeline
        if pipeline is None:
            raise RuntimeError("模型加载失败，pipeline 为 None")

        condition = self._load_condition_image(edge_image)

        if seed is None:
            seed = random.randint(0, 2**32 - 1)
        generator = torch.Generator(device=self.config.device).manual_seed(seed)

        result = pipeline(
            prompt=prompt_text,
            control_image=condition,
            num_inference_steps=self.config.num_inference_steps,
            guidance_scale=self.config.guidance_scale,
            generator=generator,
        )
        return result.images[0]

    @staticmethod
    def _load_condition_image(
        edge_image: Image.Image | bytes | str | Path,
    ) -> Image.Image:
        """将各种输入格式统一转为 PIL.Image。"""
        if isinstance(edge_image, Image.Image):
            return edge_image
        if isinstance(edge_image, bytes):
            import io

            return Image.open(io.BytesIO(edge_image))
        return Image.open(edge_image)
