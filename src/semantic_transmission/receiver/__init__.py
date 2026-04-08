"""接收端模块：提供 Diffusers 接收端工厂函数。"""

from typing import Any

from semantic_transmission.receiver.base import BaseReceiver
from semantic_transmission.receiver.base import BatchOutput as BatchOutput
from semantic_transmission.receiver.base import FrameInput as FrameInput


def create_receiver(**kwargs: Any) -> BaseReceiver:
    """创建 Diffusers 接收端实例。

    Args:
        **kwargs: 可选初始化参数。
            config (DiffusersReceiverConfig | None): 模型配置；未传入时使用默认值。

    Returns:
        ``DiffusersReceiver`` 实例（以 ``BaseReceiver`` 类型返回）。
    """
    from semantic_transmission.common.config import DiffusersReceiverConfig
    from semantic_transmission.receiver.diffusers_receiver import DiffusersReceiver

    config = kwargs.get("config") or DiffusersReceiverConfig()
    return DiffusersReceiver(config)
