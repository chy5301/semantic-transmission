"""接收端抽象基类定义。"""

from abc import ABC, abstractmethod

import numpy as np
from numpy.typing import NDArray

from semantic_transmission.common.types import ReceiverOutput


class BaseReceiver(ABC):
    """接收端抽象基类：从文本描述和条件图还原图像。"""

    @abstractmethod
    def reconstruct(
        self, text: str, condition_image: NDArray[np.uint8]
    ) -> ReceiverOutput:
        """根据文本描述和条件图还原图像。

        Args:
            text: 场景的结构化文本描述。
            condition_image: 条件图（如 Canny 边缘图），uint8 numpy 数组。

        Returns:
            ReceiverOutput: 包含还原图像和元数据。
        """
