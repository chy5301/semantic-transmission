"""Qwen-Image + InstantX ControlNet 加载。

GGUF transformer（24GB 唯一可行）。注意：transformer 用 **diffusers 原生**
``QwenImageTransformer2DModel``（支持 GGUF ``from_single_file``，且其 forward 接受
``controlnet_block_samples``，InstantX pipeline 正是这样注入 controlnet 残差），
**不用** InstantX 自带的同名自定义类——后者不在 GGUF 兼容注册表，``from_single_file``
会报 ``FromOriginalModelMixin ... only compatible with ...``。controlnet 与 pipeline
仍用 InstantX 自定义类。
"""

import os
import sys
from pathlib import Path

import torch
from diffusers import GGUFQuantizationConfig, QwenImageTransformer2DModel

_CACHE = Path(os.environ.get("MODEL_CACHE_DIR", "D:/Downloads/Models"))
QWEN_BASE = _CACHE / "Qwen" / "Qwen-Image"
INSTANTX_DIR = _CACHE / "InstantX" / "Qwen-Image-ControlNet-Union"
GGUF_PATH = _CACHE / "QuantStack" / "Qwen-Image-GGUF" / "Qwen_Image-Q4_K_M.gguf"

sys.path.insert(0, str(INSTANTX_DIR))


def load_qwen_controlnet():
    from controlnet_qwenimage import QwenImageControlNetModel  # type: ignore
    from pipeline_qwenimage_controlnet import QwenImageControlNetPipeline  # type: ignore

    controlnet = QwenImageControlNetModel.from_pretrained(
        str(INSTANTX_DIR), torch_dtype=torch.bfloat16
    )
    # 主路径：GGUF transformer 塞进自定义类
    transformer = QwenImageTransformer2DModel.from_single_file(
        str(GGUF_PATH),
        quantization_config=GGUFQuantizationConfig(compute_dtype=torch.bfloat16),
        torch_dtype=torch.bfloat16,
        config=str(QWEN_BASE / "transformer"),
    )
    pipe = QwenImageControlNetPipeline.from_pretrained(
        str(QWEN_BASE),
        controlnet=controlnet,
        transformer=transformer,
        torch_dtype=torch.bfloat16,
        local_files_only=True,
    )
    # sequential offload：accelerate 对每个子模块挂 hook 自动管理设备，绕开
    # model_cpu_offload 下 RoPE buffer / 文本编码器输入留在 CPU 导致的
    # "index is on cpu vs cuda" 设备不匹配（代价：慢，逐层搬运）。
    pipe.enable_sequential_cpu_offload()
    return pipe
