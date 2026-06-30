"""接收端模块：提供 Diffusers 接收端工厂函数。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from semantic_transmission.receiver.base import BaseReceiver
from semantic_transmission.receiver.base import BatchOutput as BatchOutput
from semantic_transmission.receiver.base import FrameInput as FrameInput

if TYPE_CHECKING:
    from semantic_transmission.common.config import (
        DiffusersReceiverConfig,
        KleinReceiverConfig,
    )
    from semantic_transmission.common.model_loader import DiffusersModelLoader


def create_receiver(
    config: DiffusersReceiverConfig | KleinReceiverConfig | None = None,
    *,
    loader: DiffusersModelLoader | None = None,
    backend: str = "diffusers",
) -> BaseReceiver:
    """创建接收端实例。

    ``backend="diffusers"``（默认/备选）返回 ``DiffusersReceiver``（Z-Image）；
    ``backend="klein"`` 返回 ``KleinReceiver``（FLUX.2-klein-9B 关键帧主线）。
    ``config`` 按 backend 解释为对应的接收端配置；``loader`` 仅 diffusers 适用。
    """
    if backend == "diffusers":
        from semantic_transmission.receiver.diffusers_receiver import DiffusersReceiver

        return DiffusersReceiver(config, loader=loader)
    if backend == "klein":
        from semantic_transmission.receiver.klein_receiver import KleinReceiver

        return KleinReceiver(config)
    raise ValueError(f"未知 backend: {backend!r}（支持 'diffusers' / 'klein'）")
