"""基于 Qwen2.5-VL 的发送端：自动生成结构化图像描述。"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from numpy.typing import NDArray
from qwen_vl_utils import process_vision_info

from semantic_transmission.common.config import VLMLoaderConfig
from semantic_transmission.common.image_io import load_as_rgb
from semantic_transmission.common.model_loader import QwenVLModelLoader
from semantic_transmission.common.types import SenderOutput
from semantic_transmission.sender.base import BaseSender

_DEFAULT_SYSTEM_PROMPT = """\
You are an image description assistant for a semantic image transmission system. \
Your description will be used with a ControlNet model to reconstruct the image \
from its Canny edge map.

Provide a detailed, continuous English description covering the following aspects in order:
[Scene Style] photographic style, rendering type
[Perspective] camera angle, orientation, composition framing
[Main Subject] primary object with color, type, shape, position in frame
[Foreground] ground surface, nearby objects, textures
[Background] distant elements, sky, atmospheric conditions
[Lighting & Color] lighting direction and quality, dominant color palette, mood
[Fine Details] material textures, small elements, surface qualities

Write as a single continuous paragraph without section headers. \
Be specific about colors, materials, positions, and spatial relationships. \
Focus on visual attributes that help reconstruct the image accurately."""


class QwenVLSender(BaseSender):
    """基于 Qwen2.5-VL 的发送端：自动生成结构化图像描述。

    模型生命周期由 ``QwenVLModelLoader`` 管理；首次调用 ``describe()`` 时延迟加载。
    支持双入口构造：传 ``loader=`` 复用已有 loader，或传 kwargs 自动构造 loader。
    """

    DEFAULT_MODEL = "Qwen/Qwen2.5-VL-7B-Instruct"
    DEFAULT_QUANTIZATION = "int4"
    DEFAULT_MAX_TOKENS = 512

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        model_path: str | Path | None = None,
        quantization: str = DEFAULT_QUANTIZATION,
        max_new_tokens: int = DEFAULT_MAX_TOKENS,
        system_prompt: str | None = None,
        *,
        loader: QwenVLModelLoader | None = None,
    ) -> None:
        self._system_prompt = system_prompt or _DEFAULT_SYSTEM_PROMPT
        if loader is not None:
            self._loader = loader
        else:
            self._loader = QwenVLModelLoader(
                VLMLoaderConfig(
                    model_name=model_name,
                    model_path=str(model_path) if model_path else "",
                    quantization=quantization,
                    max_new_tokens=max_new_tokens,
                )
            )

    @property
    def _model_name(self) -> str:
        """对外暴露当前 loader 使用的 model_name（保留旧字段访问形式）。"""
        return self._loader.config.model_name

    @property
    def _quantization(self) -> str:
        """对外暴露 loader 配置的 quantization。"""
        return self._loader.config.quantization

    @property
    def _max_new_tokens(self) -> int:
        """对外暴露 loader 配置的 max_new_tokens。"""
        return self._loader.config.max_new_tokens

    @property
    def _model_path(self) -> str | None:
        """对外暴露 loader 配置的 model_path（保持旧 None 语义）。"""
        return self._loader.config.model_path or None

    @property
    def is_loaded(self) -> bool:
        """模型是否已加载。"""
        return self._loader.is_loaded

    def describe(self, image: NDArray[np.uint8]) -> SenderOutput:
        """对输入图像生成结构化文本描述。

        Args:
            image: 输入图像，RGB 格式的 numpy 数组，shape 为 (H, W, 3)。

        Returns:
            SenderOutput: 包含文本描述和元数据。
        """
        bundle = self._loader.load()
        model = bundle.model
        processor = bundle.processor

        pil_image = load_as_rgb(image)

        messages = [
            {
                "role": "system",
                "content": [{"type": "text", "text": self._system_prompt}],
            },
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": pil_image},
                    {
                        "type": "text",
                        "text": "Describe this image in detail following the required format.",
                    },
                ],
            },
        ]

        text = processor.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        image_inputs, video_inputs = process_vision_info(messages)
        inputs = processor(
            text=[text],
            images=image_inputs,
            videos=video_inputs,
            padding=True,
            return_tensors="pt",
        ).to(model.device)

        import torch

        with torch.inference_mode():
            generated_ids = model.generate(
                **inputs, max_new_tokens=self._max_new_tokens
            )

        generated_ids_trimmed = [
            out_ids[len(in_ids) :]
            for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
        ]
        output_text = processor.batch_decode(
            generated_ids_trimmed,
            skip_special_tokens=True,
            clean_up_tokenization_spaces=False,
        )[0].strip()

        return SenderOutput(
            text=output_text,
            metadata={
                "model": self._model_name,
                "quantization": bundle.actual_quantization,
            },
        )

    def unload(self) -> None:
        """释放模型和 GPU 显存。"""
        self._loader.unload()
