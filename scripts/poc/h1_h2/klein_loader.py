"""klein-9B 加载：bf16 完整 pipeline + CPU offload。

注：本应用 fp8 transformer（H2 速度首选），但 BFL 官方 fp8 单文件为 scaled-fp8
布局，diffusers 0.37.1 的 ``Flux2Transformer2DModel.from_single_file`` 转换器不认
（``convert_flux2_double_stream_blocks`` 对 fused_qkv 0-dim chunk 报错）。按 plan 回退
梯度改用本地 klein-9B 目录的 bf16 transformer + ``enable_model_cpu_offload``（逐模型搬运，
512²下 18GB transformer 可塞进 24GB）。**fp8 单文件加载 = 待解工程点**（H2 因此测的是
bf16 4 步速度，官方「<1s」前提未验）。
"""

import os
from pathlib import Path

import torch
from diffusers import Flux2KleinPipeline

_CACHE = Path(os.environ.get("MODEL_CACHE_DIR", "D:/Downloads/Models"))
KLEIN_DIR = _CACHE / "black-forest-labs" / "FLUX.2-klein-9B"
KLEIN_FP8_PATH = (
    _CACHE
    / "black-forest-labs"
    / "FLUX.2-klein-9b-fp8"
    / "flux-2-klein-9b-fp8.safetensors"
)


def load_klein() -> Flux2KleinPipeline:
    """加载 klein pipeline：本地 bf16 全组件 + model CPU offload。"""
    pipe = Flux2KleinPipeline.from_pretrained(
        str(KLEIN_DIR),
        torch_dtype=torch.bfloat16,
        local_files_only=True,
    )
    pipe.enable_model_cpu_offload()
    return pipe
