"""项目配置与公共路径工具。"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, fields
from pathlib import Path

import tomllib


@dataclass
class DiffusersReceiverConfig:
    """Diffusers 接收端模型配置。

    支持通过环境变量 DIFFUSERS_MODEL_NAME / DIFFUSERS_CONTROLNET_NAME 等覆盖默认值。

    ``__post_init__`` 中空的 ``transformer_path`` / ``controlnet_name`` 会回退到
    ``ProjectConfig`` 的对应字段（含 ``MODEL_CACHE_DIR`` 环境变量经 ``config.toml``
    展开的最终绝对路径）。
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
        if not self.transformer_path or not self.controlnet_name:
            project_config = load_config()
            if not self.transformer_path:
                self.transformer_path = project_config.diffusers_transformer_path
            if not self.controlnet_name:
                self.controlnet_name = project_config.diffusers_controlnet_name

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


@dataclass
class KleinReceiverConfig:
    """FLUX.2-klein-9B 接收端配置。

    支持 ``KLEIN_*`` 环境变量覆盖。``__post_init__`` 中空的 ``model_dir`` 回退到
    ``MODEL_CACHE_DIR``（经 ``load_config`` 解析）下的 klein 模型目录。
    """

    model_dir: str = ""
    device: str = "cuda"
    num_inference_steps: int = 4
    guidance_scale: float = 1.0
    torch_dtype: str = "bfloat16"
    max_side: int = 768
    enable_vae_tiling: bool = False
    enable_attention_slicing: bool = False

    def __post_init__(self):
        if not self.model_dir:
            project_config = load_config()
            self.model_dir = str(
                Path(project_config.model_cache_dir)
                / "black-forest-labs"
                / "FLUX.2-klein-9B"
            )

    @classmethod
    def from_env(cls) -> "KleinReceiverConfig":
        """从 ``KLEIN_*`` 环境变量构造配置实例。"""

        def _to_bool(v: str) -> bool:
            return v.strip().lower() in ("1", "true", "yes", "on")

        _TYPE_MAP = {"int": int, "float": float, "bool": _to_bool}
        kwargs: dict[str, object] = {}
        for f in fields(cls):
            val = os.environ.get(f"KLEIN_{f.name.upper()}")
            if val is None:
                continue
            type_str = f.type if isinstance(f.type, str) else f.type.__name__
            converter = _TYPE_MAP.get(type_str)
            if converter is not None:
                try:
                    kwargs[f.name] = converter(val)
                except (ValueError, TypeError) as e:
                    raise ValueError(
                        f"环境变量 KLEIN_{f.name.upper()}={val!r} 无法转换为 {type_str}"
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

    def to_vlm_loader_config(self) -> VLMLoaderConfig:
        """从项目配置派生 VLM 模型加载配置。"""
        return VLMLoaderConfig(
            model_name=self.vlm_model_name,
            model_path=self.vlm_model_path,
            quantization=self.vlm_quantization,
            max_new_tokens=self.vlm_max_new_tokens,
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


@dataclass(frozen=True)
class VLMLoaderConfig:
    """Qwen2.5-VL 模型加载器配置（从 ProjectConfig 派生，不直接依赖 ProjectConfig）。"""

    model_name: str = "Qwen/Qwen2.5-VL-7B-Instruct"
    model_path: str = ""
    quantization: str = "int4"
    max_new_tokens: int = 512


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
