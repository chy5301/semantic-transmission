"""接收端模型配置与公共路径工具。"""

import os
from dataclasses import dataclass, fields


def get_default_vlm_path() -> str | None:
    """获取 VLM 模型默认本地路径。

    基于环境变量 MODEL_CACHE_DIR 拼接 Qwen2.5-VL-7B-Instruct 路径。
    未设置 MODEL_CACHE_DIR 时返回 None。
    """
    cache_dir = os.environ.get("MODEL_CACHE_DIR")
    if cache_dir:
        return os.path.join(cache_dir, "Qwen", "Qwen2.5-VL-7B-Instruct")
    return None


def get_default_z_image_path(filename: str) -> str:
    """获取 Z-Image-Turbo 模型文件默认本地路径。

    基于环境变量 MODEL_CACHE_DIR 拼接路径。
    未设置 MODEL_CACHE_DIR 时返回文件名本身。
    """
    cache_dir = os.environ.get("MODEL_CACHE_DIR")
    if cache_dir:
        return os.path.join(cache_dir, "Z-Image-Turbo", filename)
    return filename


@dataclass
class DiffusersReceiverConfig:
    """Diffusers 接收端模型配置。

    支持通过环境变量 DIFFUSERS_MODEL_NAME / DIFFUSERS_CONTROLNET_NAME 等覆盖默认值。
    """

    model_name: str = "Tongyi-MAI/Z-Image-Turbo"
    controlnet_name: str = ""
    transformer_path: str = ""
    device: str = "cuda"
    num_inference_steps: int = 9
    guidance_scale: float = 1.0
    torch_dtype: str = "bfloat16"

    def __post_init__(self):
        if not self.transformer_path:
            self.transformer_path = get_default_z_image_path("z-image-turbo-Q8_0.gguf")
        if not self.controlnet_name:
            self.controlnet_name = get_default_z_image_path(
                "Z-Image-Turbo-Fun-Controlnet-Union.safetensors"
            )

    @classmethod
    def from_env(cls) -> "DiffusersReceiverConfig":
        """从环境变量构造配置实例。"""
        kwargs = {}
        for f in fields(cls):
            env_key = f"DIFFUSERS_{f.name.upper()}"
            val = os.environ.get(env_key)
            if val is not None:
                if f.type in (int, float):
                    try:
                        kwargs[f.name] = f.type(val)
                    except (ValueError, TypeError) as e:
                        raise ValueError(
                            f"环境变量 {env_key}={val!r} 无法转换为 {f.type.__name__}"
                        ) from e
                else:
                    kwargs[f.name] = val
        return cls(**kwargs)
