"""接收端抽象基类定义。"""

from abc import ABC, abstractmethod
from pathlib import Path

from PIL import Image


class BaseReceiver(ABC):
    """接收端抽象基类：从文本描述和条件图还原图像。"""

    @abstractmethod
    def process(
        self,
        edge_image: Image.Image | bytes | str | Path,
        prompt_text: str,
        seed: int | None = None,
    ) -> Image.Image:
        """根据文本描述和条件图还原图像。

        Args:
            edge_image: 条件图（如 Canny 边缘图），PIL Image、bytes 或文件路径。
            prompt_text: 图像描述文本。
            seed: 随机种子，None 时随机生成。

        Returns:
            还原图像 PIL.Image。
        """
