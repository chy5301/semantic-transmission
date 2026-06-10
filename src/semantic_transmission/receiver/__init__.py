"""接收端模块：提供 Diffusers 接收端工厂函数。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from semantic_transmission.receiver.base import BaseReceiver
from semantic_transmission.receiver.base import BatchOutput as BatchOutput
from semantic_transmission.receiver.base import FrameInput as FrameInput

if TYPE_CHECKING:
    from semantic_transmission.common.config import DiffusersReceiverConfig
    from semantic_transmission.common.model_loader import DiffusersModelLoader


def create_receiver(
    config: DiffusersReceiverConfig | None = None,
    *,
    loader: DiffusersModelLoader | None = None,
) -> BaseReceiver:
    """创建 Diffusers 接收端实例。

    可传入 ``loader``（优先）或 ``config``；均为空时使用默认配置。
    """
    from semantic_transmission.receiver.diffusers_receiver import DiffusersReceiver

    return DiffusersReceiver(config, loader=loader)
