"""FLUX.2-klein-9B 接收端：image=[Canny]+prompt 4 步生成。"""

from __future__ import annotations

import gc
import random

import torch
from PIL import Image

from semantic_transmission.common.config import KleinReceiverConfig
from semantic_transmission.common.image_io import load_as_rgb
from semantic_transmission.receiver.base import BaseReceiver, BatchOutput, FrameInput

_TORCH_DTYPE_MAP: dict[str, torch.dtype] = {
    "float32": torch.float32,
    "float16": torch.float16,
    "bfloat16": torch.bfloat16,
    "float": torch.float32,
}


def _resolve_torch_dtype(name: str) -> torch.dtype:
    """将 torch_dtype 字符串解析为 ``torch.dtype``，无效值时给出明确错误。"""
    dtype = _TORCH_DTYPE_MAP.get(name)
    if dtype is not None:
        return dtype
    raise ValueError(
        f"不支持的 torch_dtype {name!r}，有效值: {', '.join(sorted(_TORCH_DTYPE_MAP))}"
    )


def fit_working_size(image: Image.Image, max_side: int) -> Image.Image:
    """保宽高比把长边压到 ``max_side``，宽高各向下取 16 的倍数。

    klein/Flux 要求尺寸为 16 的倍数；大帧（如 1920×1080）原生分辨率会 OOM，
    故在 receiver 内部降采样到 GPU 可承受的工作分辨率。
    宽/高不足 16 px 时取 16 px（Flux 要求的最小尺寸），不会放大超过该下限。
    尺寸已合规则原样返回。
    """
    w, h = image.size
    scale = min(1.0, max_side / max(w, h))
    nw = max(16, int(w * scale) // 16 * 16)
    nh = max(16, int(h * scale) // 16 * 16)
    if (nw, nh) == (w, h):
        return image
    return image.resize((nw, nh), Image.LANCZOS)


class KleinReceiver(BaseReceiver):
    """接收端：用 ``Flux2KleinPipeline`` 从 Canny 参考图 + prompt 生成图像。"""

    def __init__(self, config: KleinReceiverConfig | None = None) -> None:
        self.config = config or KleinReceiverConfig()
        self._pipe = None

    @property
    def is_loaded(self) -> bool:
        return self._pipe is not None

    def _build_pipeline(self):
        from diffusers import Flux2KleinPipeline

        pipe = Flux2KleinPipeline.from_pretrained(
            self.config.model_dir,
            torch_dtype=_resolve_torch_dtype(self.config.torch_dtype),
            local_files_only=True,
        )
        pipe.enable_model_cpu_offload()
        if self.config.enable_vae_tiling:
            pipe.enable_vae_tiling()
        if self.config.enable_attention_slicing:
            pipe.enable_attention_slicing()
        return pipe

    def load(self):
        """加载 klein pipeline（幂等）。"""
        if self._pipe is None:
            self._pipe = self._build_pipeline()
        return self._pipe

    def unload(self) -> None:
        """卸载 pipeline，释放显存。"""
        if self._pipe is not None:
            self._pipe = None
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

    def process(
        self,
        edge_image,
        prompt_text,
        seed=None,
    ) -> Image.Image:
        """从 Canny 边缘图 + 文本生成还原图像（内部降采样到工作分辨率）。"""
        pipe = self.load()
        cond = fit_working_size(load_as_rgb(edge_image), self.config.max_side)
        width, height = cond.size
        if seed is None:
            seed = random.randint(0, 2**32 - 1)
        generator = torch.Generator("cpu").manual_seed(seed)
        result = pipe(
            prompt=prompt_text,
            image=[cond],
            guidance_scale=self.config.guidance_scale,
            num_inference_steps=self.config.num_inference_steps,
            height=height,
            width=width,
            generator=generator,
        )
        if not result.images:
            raise RuntimeError("Flux2KleinPipeline 未生成图像（result.images 为空）")
        return result.images[0]

    def process_batch(self, frames: list[FrameInput]) -> BatchOutput:
        """批量处理，模型常驻 GPU 不反复加载。"""
        self.load()
        return super().process_batch(frames)
