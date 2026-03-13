"""语义传输系统的公共数据类型定义。"""

from dataclasses import dataclass, field
from typing import Any

import numpy as np
from numpy.typing import NDArray


@dataclass
class SenderOutput:
    """发送端输出：图像的文本描述及元数据。"""

    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TransmissionData:
    """传输数据：文本描述 + 条件图像 + 元数据。"""

    text: str
    condition_image: NDArray[np.uint8]
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ReceiverOutput:
    """接收端输出：还原图像及元数据。"""

    image: NDArray[np.uint8]
    metadata: dict[str, Any] = field(default_factory=dict)
