"""项目配置与公共路径工具。"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, fields
from pathlib import Path

import tomllib


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
    scheduler_shift: float = 3.0

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
        _TYPE_MAP: dict[str, type] = {"int": int, "float": float}
        kwargs = {}
        for f in fields(cls):
            env_key = f"DIFFUSERS_{f.name.upper()}"
            val = os.environ.get(env_key)
            if val is not None:
                type_str = f.type if isinstance(f.type, str) else f.type.__name__
                converter = _TYPE_MAP.get(type_str)
                if converter is not None:
                    try:
                        kwargs[f.name] = converter(val)
                    except (ValueError, TypeError) as e:
                        raise ValueError(
                            f"环境变量 {env_key}={val!r} 无法转换为 {type_str}"
                        ) from e
                else:
                    kwargs[f.name] = val
        return cls(**kwargs)


# ---------------------------------------------------------------------------
# ProjectConfig：项目级统一配置
# ---------------------------------------------------------------------------

_ENV_VAR_RE = re.compile(r"\$\{(\w+)}")

_PROJECT_ROOT = Path(__file__).resolve().parents[3]  # src/../../../
_DEFAULT_CONFIG_PATH = _PROJECT_ROOT / "config.toml"
_LOCAL_CONFIG_PATH = _PROJECT_ROOT / "config.local.toml"


def _expand_env_vars(value: str) -> str:
    """展开字符串中的 ``${VAR}`` 环境变量引用。"""

    def _replace(m: re.Match[str]) -> str:
        return os.environ.get(m.group(1), m.group(0))

    return _ENV_VAR_RE.sub(_replace, value)


def _walk_expand(
    obj: dict | list | str | int | float | bool,
) -> dict | list | str | int | float | bool:
    """递归展开嵌套结构中所有字符串值的环境变量。"""
    if isinstance(obj, dict):
        return {k: _walk_expand(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_walk_expand(v) for v in obj]
    if isinstance(obj, str):
        return _expand_env_vars(obj)
    return obj


@dataclass(frozen=True)
class ProjectConfig:
    """项目级统一配置，从 config.toml 加载。

    优先级（低→高）：代码默认 < config.toml < config.local.toml < 环境变量。
    运行时参数（CLI/GUI）由调用方在消费时覆盖，不在此处处理。
    """

    # [models.diffusers]
    diffusers_model_name: str = "Tongyi-MAI/Z-Image-Turbo"
    diffusers_controlnet_name: str = ""
    diffusers_transformer_path: str = ""
    diffusers_torch_dtype: str = "bfloat16"
    diffusers_device: str = "cuda"

    # [models.vlm]
    vlm_model_name: str = "Qwen/Qwen2.5-VL-7B-Instruct"
    vlm_model_path: str = ""
    vlm_quantization: str = "int4"
    vlm_max_new_tokens: int = 512

    # [inference]
    num_inference_steps: int = 9
    guidance_scale: float = 1.0
    scheduler_shift: float = 3.0

    # [sender]
    canny_low_threshold: int = 100
    canny_high_threshold: int = 200

    # [paths]
    model_cache_dir: str = ""
    output_dir: str = "output"
    hf_endpoint: str = ""

    def to_diffusers_loader_config(self) -> DiffusersLoaderConfig:
        """从项目配置派生 Diffusers 模型加载配置。"""
        return DiffusersLoaderConfig(
            model_name=self.diffusers_model_name,
            controlnet_name=self.diffusers_controlnet_name,
            transformer_path=self.diffusers_transformer_path,
            device=self.diffusers_device,
            torch_dtype=self.diffusers_torch_dtype,
            scheduler_shift=self.scheduler_shift,
        )


@dataclass(frozen=True)
class DiffusersLoaderConfig:
    """Diffusers 模型加载器配置（从 ProjectConfig 派生，不直接依赖 ProjectConfig）。"""

    model_name: str = "Tongyi-MAI/Z-Image-Turbo"
    controlnet_name: str = ""
    transformer_path: str = ""
    device: str = "cuda"
    torch_dtype: str = "bfloat16"
    scheduler_shift: float = 3.0


# TOML 嵌套键 → ProjectConfig 平坦字段名的映射
_TOML_FIELD_MAP: dict[tuple[str, ...], str] = {
    ("models", "diffusers", "model_name"): "diffusers_model_name",
    ("models", "diffusers", "controlnet_name"): "diffusers_controlnet_name",
    ("models", "diffusers", "transformer_path"): "diffusers_transformer_path",
    ("models", "diffusers", "torch_dtype"): "diffusers_torch_dtype",
    ("models", "diffusers", "device"): "diffusers_device",
    ("models", "vlm", "model_name"): "vlm_model_name",
    ("models", "vlm", "model_path"): "vlm_model_path",
    ("models", "vlm", "quantization"): "vlm_quantization",
    ("models", "vlm", "max_new_tokens"): "vlm_max_new_tokens",
    ("inference", "num_inference_steps"): "num_inference_steps",
    ("inference", "guidance_scale"): "guidance_scale",
    ("inference", "scheduler_shift"): "scheduler_shift",
    ("sender", "canny_low_threshold"): "canny_low_threshold",
    ("sender", "canny_high_threshold"): "canny_high_threshold",
    ("paths", "model_cache_dir"): "model_cache_dir",
    ("paths", "output_dir"): "output_dir",
    ("paths", "hf_endpoint"): "hf_endpoint",
}


def _flatten_toml(data: dict) -> dict[str, object]:
    """将 TOML 嵌套 dict 按 ``_TOML_FIELD_MAP`` 展平为 ProjectConfig 字段。"""
    result: dict[str, object] = {}
    for keys, field_name in _TOML_FIELD_MAP.items():
        node: object = data
        for k in keys:
            if isinstance(node, dict) and k in node:
                node = node[k]
            else:
                node = None
                break
        if node is not None:
            result[field_name] = node
    return result


def load_config(path: Path | None = None) -> ProjectConfig:
    """加载项目配置。

    加载顺序（后者覆盖前者）：
    1. 代码默认值（``ProjectConfig`` 字段默认）
    2. ``config.toml``（仓库根，checked in）
    3. ``config.local.toml``（仓库根，gitignored）
    4. 环境变量 ``MODEL_CACHE_DIR``

    Args:
        path: 指定 config.toml 路径，None 时使用仓库根。
    """
    merged: dict[str, object] = {}

    # 层 2：config.toml
    config_path = path or _DEFAULT_CONFIG_PATH
    if config_path.is_file():
        with open(config_path, "rb") as f:
            raw = tomllib.load(f)
        merged.update(_flatten_toml(_walk_expand(raw)))

    # 层 3：config.local.toml（与 config.toml 同目录）
    local_path = config_path.parent / "config.local.toml"
    if local_path.is_file():
        with open(local_path, "rb") as f:
            raw = tomllib.load(f)
        merged.update(_flatten_toml(_walk_expand(raw)))

    # 层 4：环境变量覆盖
    env_cache_dir = os.environ.get("MODEL_CACHE_DIR")
    if env_cache_dir:
        merged["model_cache_dir"] = env_cache_dir

    config = ProjectConfig(**merged)

    # 将 HF_ENDPOINT 注入环境变量（huggingface_hub 通过 os.environ 读取）
    if config.hf_endpoint and not os.environ.get("HF_ENDPOINT"):
        os.environ["HF_ENDPOINT"] = config.hf_endpoint

    return config
