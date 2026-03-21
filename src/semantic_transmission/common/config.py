"""ComfyUI 连接配置。"""

import os
from dataclasses import dataclass


@dataclass
class ComfyUIConfig:
    """ComfyUI 服务连接配置。

    支持通过环境变量 COMFYUI_HOST / COMFYUI_PORT / COMFYUI_TIMEOUT 覆盖默认值。
    带前缀时（如 prefix="SENDER"），优先读取 COMFYUI_SENDER_HOST，未设置则回退到 COMFYUI_HOST。
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
    def from_env(cls, prefix: str | None = None) -> "ComfyUIConfig":
        """从环境变量构造配置实例。

        Args:
            prefix: 环境变量前缀（如 "SENDER"、"RECEIVER"）。
                    设置后优先读取 COMFYUI_{PREFIX}_HOST 等，未设置则回退到 COMFYUI_HOST。
        """

        def _get(key: str, default: str) -> str:
            if prefix:
                prefixed = f"COMFYUI_{prefix}_{key}"
                val = os.environ.get(prefixed)
                if val is not None:
                    return val
            return os.environ.get(f"COMFYUI_{key}", default)

        return cls(
            host=_get("HOST", "127.0.0.1"),
            port=int(_get("PORT", "8188")),
            timeout=int(_get("TIMEOUT", "30")),
        )


@dataclass
class SemanticTransmissionConfig:
    """语义传输整体配置，包含发送端和接收端的 ComfyUI 连接配置。"""

    sender: ComfyUIConfig
    receiver: ComfyUIConfig

    @classmethod
    def from_env(cls) -> "SemanticTransmissionConfig":
        """从环境变量构造配置。

        发送端读取 COMFYUI_SENDER_HOST/PORT/TIMEOUT，
        接收端读取 COMFYUI_RECEIVER_HOST/PORT/TIMEOUT，
        未设置时均回退到 COMFYUI_HOST/PORT/TIMEOUT。
        """
        return cls(
            sender=ComfyUIConfig.from_env(prefix="SENDER"),
            receiver=ComfyUIConfig.from_env(prefix="RECEIVER"),
        )
