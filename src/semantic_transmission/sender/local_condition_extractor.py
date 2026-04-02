"""本地条件提取器：使用 OpenCV 提取 Canny 边缘，不依赖 ComfyUI。"""

import cv2
import numpy as np
from numpy.typing import NDArray

from semantic_transmission.sender.base import BaseConditionExtractor


class LocalCannyExtractor(BaseConditionExtractor):
    """使用 OpenCV 本地提取 Canny 边缘图。"""

    def __init__(self, threshold1: int = 100, threshold2: int = 200):
        """初始化 Canny 边缘提取器。

        Args:
            threshold1: Canny 低阈值
            threshold2: Canny 高阈值
        """
        self.threshold1 = threshold1
        self.threshold2 = threshold2

    def extract(self, image: NDArray[np.uint8]) -> NDArray[np.uint8]:
        """从输入图像提取 Canny 边缘图。

        Args:
            image: 输入图像，RGB 格式的 numpy 数组，shape 为 (H, W, 3)

        Returns:
            Canny 边缘图，uint8 numpy 数组，shape 为 (H, W)
        """
        # 转换为灰度图
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)

        # 提取 Canny 边缘
        edges = cv2.Canny(gray, self.threshold1, self.threshold2)

        return edges
