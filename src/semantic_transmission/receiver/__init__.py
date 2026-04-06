"""接收端模块：提供后端切换工厂函数。"""

from typing import Any

from semantic_transmission.receiver.base import BaseReceiver


def create_receiver(backend: str, **kwargs: Any) -> BaseReceiver:
    """根据后端类型创建接收端实例。

    Args:
        backend: 后端类型，"comfyui" 或 "diffusers"。
        **kwargs: 后端特定的初始化参数。
            comfyui 后端:
                host (str): ComfyUI 服务地址，默认 "127.0.0.1"。
                port (int): ComfyUI 服务端口，默认 8188。
                timeout (int): 连接超时秒数，默认 30。
                workflow_path (str | Path | None): 自定义工作流路径。
            diffusers 后端:
                config (DiffusersReceiverConfig | None): 模型配置。

    Returns:
        BaseReceiver 实例。

    Raises:
        ValueError: 不支持的后端类型。
    """
    if backend == "comfyui":
        from semantic_transmission.common.comfyui_client import ComfyUIClient
        from semantic_transmission.common.config import ComfyUIConfig
        from semantic_transmission.receiver.comfyui_receiver import ComfyUIReceiver

        config = ComfyUIConfig(
            host=kwargs.get("host", "127.0.0.1"),
            port=kwargs.get("port", 8188),
            timeout=kwargs.get("timeout", 30),
        )
        client = ComfyUIClient(config)
        return ComfyUIReceiver(client, workflow_path=kwargs.get("workflow_path"))  # type: ignore[return-value]

    if backend == "diffusers":
        raise NotImplementedError("Diffusers 后端将在 M-05 中实现")

    raise ValueError(f"不支持的接收端后端: {backend!r}，可选: 'comfyui', 'diffusers'")
