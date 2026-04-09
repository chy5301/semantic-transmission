"""模型就绪检测纯函数。

CLI 和 GUI 共享的单一数据源，判断 VLM / Diffusers 接收端模型资源是否完整可用。
不依赖 Gradio / click，便于在任意上下文调用。
"""

import os

from semantic_transmission.common.config import (
    DiffusersReceiverConfig,
    get_default_vlm_path,
)


def check_vlm_model(model_path: str | None = None) -> tuple[bool, str]:
    """检查 VLM 模型是否就绪。

    Args:
        model_path: VLM 模型本地路径；为空时回退到 ``get_default_vlm_path()``。

    Returns:
        ``(ok, message)``：``ok`` 表示路径存在且包含 ``config.json``；
        ``message`` 为人类可读的状态描述。
    """
    path = model_path or get_default_vlm_path()
    if not path:
        return False, (
            "未设置 VLM 模型路径（环境变量 MODEL_CACHE_DIR 未配置，且未显式传入路径）"
        )
    if not os.path.isdir(path):
        return False, f"VLM 模型目录不存在：{path}"
    config_file = os.path.join(path, "config.json")
    if not os.path.isfile(config_file):
        return False, f"VLM 模型目录缺少 config.json：{path}"
    return True, f"VLM 模型就绪：{path}"


def check_diffusers_receiver_model(
    config: DiffusersReceiverConfig | None = None,
) -> tuple[bool, str]:
    """检查 Diffusers 接收端所需的三处模型资源是否就绪。

    检查项：
    1. Transformer GGUF 量化文件（``config.transformer_path``）
    2. ControlNet 权重文件（``config.controlnet_name``）
    3. HF cache 中的 Pipeline 基础组件（text_encoder / tokenizer / scheduler / vae）
       对应 ``HF_HOME`` 或 ``~/.cache/huggingface/hub`` 下的 ``models--{model_name}`` 子目录

    Args:
        config: Diffusers 接收端配置；未传入时使用 ``DiffusersReceiverConfig()`` 默认值。

    Returns:
        ``(ok, message)``：``ok`` 表示三处资源全部存在；
        ``message`` 为多行状态描述（每项一条 ``✓`` / ``✗`` 记录）。
    """
    cfg = config or DiffusersReceiverConfig()
    lines: list[str] = []
    all_ok = True

    # 1) transformer GGUF
    tf_path = cfg.transformer_path
    if tf_path and os.path.isfile(tf_path):
        lines.append(f"✓ transformer GGUF：{tf_path}")
    else:
        all_ok = False
        lines.append(f"✗ transformer GGUF 缺失：{tf_path or '(未配置)'}")

    # 2) ControlNet 权重
    cn_path = cfg.controlnet_name
    if cn_path and os.path.isfile(cn_path):
        lines.append(f"✓ ControlNet 权重：{cn_path}")
    else:
        all_ok = False
        lines.append(f"✗ ControlNet 权重缺失：{cn_path or '(未配置)'}")

    # 3) HF cache 下 pipeline base 组件
    hf_home = os.environ.get("HF_HOME") or os.path.expanduser("~/.cache/huggingface")
    hub_dir = os.path.join(hf_home, "hub")
    cache_subdir = f"models--{cfg.model_name.replace('/', '--')}"
    cache_path = os.path.join(hub_dir, cache_subdir)
    if os.path.isdir(cache_path):
        lines.append(f"✓ HF cache pipeline base：{cache_path}")
    else:
        all_ok = False
        lines.append(f"✗ HF cache pipeline base 缺失：{cache_path}")

    header = "Diffusers 接收端模型就绪" if all_ok else "Diffusers 接收端模型未就绪"
    return all_ok, header + "\n" + "\n".join(lines)
