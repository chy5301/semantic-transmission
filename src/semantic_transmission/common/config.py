"""ComfyUI 连接配置。"""

import os
from dataclasses import dataclass


@dataclass
class ComfyUIConfig:
    """ComfyUI 服务连接配置。

    支持通过环境变量 COMFYUI_HOST / COMFYUI_PORT / COMFYUI_TIMEOUT 覆盖默认值。
    """

    host: str = "127.0.0.1"
    port: int = 8188
    timeout: int = 30

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    @property
    def ws_url(self) -> str:
        return f"ws://{self.host}:{self.port}/ws"

    @classmethod
    def from_env(cls) -> "ComfyUIConfig":
        """从环境变量构造配置实例。"""
        return cls(
            host=os.environ.get("COMFYUI_HOST", "127.0.0.1"),
            port=int(os.environ.get("COMFYUI_PORT", "8188")),
            timeout=int(os.environ.get("COMFYUI_TIMEOUT", "30")),
        )
