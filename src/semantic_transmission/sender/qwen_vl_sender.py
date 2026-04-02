"""基于 Qwen2.5-VL 的发送端：自动生成结构化图像描述。"""

from pathlib import Path

import numpy as np
from numpy.typing import NDArray
from PIL import Image
from qwen_vl_utils import process_vision_info

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

    使用 transformers 原生推理，支持 torchao INT4 量化。
    模型在首次调用 describe() 时延迟加载。
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
    ) -> None:
        self._model_name = model_name
        self._model_path = str(model_path) if model_path else None
        self._quantization = quantization
        self._max_new_tokens = max_new_tokens
        self._system_prompt = system_prompt or _DEFAULT_SYSTEM_PROMPT
        self._model = None
        self._processor = None

    def _load_model(self) -> None:
        """延迟加载模型和处理器（首次 describe 时调用）。"""
        import torch
        from transformers import AutoProcessor, Qwen2_5_VLForConditionalGeneration

        quantization_config = None
        actual_quantization = self._quantization

        if self._quantization == "int4":
            # 优先尝试 torchao INT4（仅 Linux 推荐）
            try:
                from torchao.quantization import TorchAoConfig
                quantization_config = TorchAoConfig("int4_weight_only", group_size=128)
            except (ImportError, Exception) as e:
                print(f"  提示：torchao INT4 不可用（{e}），尝试 bitsandbytes 4-bit...")
                # 回退到 bitsandbytes 4-bit（Windows 友好）
                try:
                    from transformers import BitsAndBytesConfig
                    quantization_config = BitsAndBytesConfig(
                        load_in_4bit=True,
                        bnb_4bit_use_double_quant=True,
                        bnb_4bit_quant_type="nf4",
                        bnb_4bit_compute_dtype=torch.float16
                    )
                    actual_quantization = "bitsandbytes-4bit"
                except (ImportError, Exception) as e2:
                    print(f"  警告：bitsandbytes 4-bit 也不可用（{e2}），回退到 float16")
                    actual_quantization = "float16"

        dtype = torch.float16
        if quantization_config is None:
            dtype = torch.float16
        elif hasattr(quantization_config, "__class__") and "TorchAoConfig" in str(quantization_config.__class__):
            dtype = torch.bfloat16

        # 优先使用本地路径，其次使用 HuggingFace Hub ID
        model_id = self._model_path or self._model_name

        self._model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
            model_id,
            torch_dtype=dtype,
            device_map="auto",
            quantization_config=quantization_config,
        )
        self._processor = AutoProcessor.from_pretrained(model_id)
        self._actual_quantization = actual_quantization

    def describe(self, image: NDArray[np.uint8]) -> SenderOutput:
        """对输入图像生成结构化文本描述。

        Args:
            image: 输入图像，RGB 格式的 numpy 数组，shape 为 (H, W, 3)。

        Returns:
            SenderOutput: 包含文本描述和元数据。
        """
        if self._model is None:
            self._load_model()

        pil_image = Image.fromarray(image)

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

        text = self._processor.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        image_inputs, video_inputs = process_vision_info(messages)
        inputs = self._processor(
            text=[text],
            images=image_inputs,
            videos=video_inputs,
            padding=True,
            return_tensors="pt",
        ).to(self._model.device)

        import torch

        with torch.inference_mode():
            generated_ids = self._model.generate(
                **inputs, max_new_tokens=self._max_new_tokens
            )

        generated_ids_trimmed = [
            out_ids[len(in_ids) :]
            for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
        ]
        output_text = self._processor.batch_decode(
            generated_ids_trimmed,
            skip_special_tokens=True,
            clean_up_tokenization_spaces=False,
        )[0].strip()

        return SenderOutput(
            text=output_text,
            metadata={
                "model": self._model_name,
                "quantization": self._actual_quantization,
            },
        )

    def unload(self) -> None:
        """释放模型和 GPU 显存。"""
        import gc

        self._model = None
        self._processor = None
        gc.collect()

        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass
