"""发送端抽象基类定义。"""

from abc import ABC, abstractmethod

import numpy as np
from numpy.typing import NDArray

from semantic_transmission.common.types import SenderOutput


class BaseSender(ABC):
    """发送端抽象基类：将图像转换为文本描述。"""

    @abstractmethod
    def describe(self, image: NDArray[np.uint8]) -> SenderOutput:
        """对输入图像生成结构化文本描述。

        Args:
            image: 输入图像，RGB 格式的 numpy 数组，shape 为 (H, W, 3)。

        Returns:
            SenderOutput: 包含文本描述和元数据。
        """


class BaseConditionExtractor(ABC):
    """条件提取器抽象基类：从图像中提取结构化条件信息。"""

    @abstractmethod
    def extract(self, image: NDArray[np.uint8]) -> NDArray[np.uint8]:
        """从输入图像提取条件图。

        Args:
            image: 输入图像，RGB 格式的 numpy 数组，shape 为 (H, W, 3)。

        Returns:
            条件图，uint8 numpy 数组。
        """
