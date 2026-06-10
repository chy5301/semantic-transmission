"""图像预处理工具，为质量评估指标提供统一的输入转换。"""

from __future__ import annotations

from typing import Union

import numpy as np
from numpy.typing import NDArray
from PIL import Image

from semantic_transmission.common.image_io import load_as_rgb

ImageInput = Union[NDArray[np.uint8], Image.Image]


def to_numpy(image: ImageInput) -> NDArray[np.uint8]:
    """将输入图像统一转换为 (H, W, 3) uint8 RGB numpy 数组。

    支持 PIL Image（任意 mode）和 numpy 数组输入。

    注：本函数与 :func:`semantic_transmission.common.image_io.image_to_numpy`
    职责一致；区别在于 ``image_to_numpy`` 还接受 ``str | Path | bytes``，
    而本函数只接受指标计算阶段会拿到的 PIL/ndarray。内部统一委托
    :func:`load_as_rgb` 完成模式归一化，避免与 ``image_io`` 重复实现。
    """
    if isinstance(image, np.ndarray):
        # ndarray 走快速路径：(H,W,3) 命中可零拷贝，(H,W,4)/(H,W) 走 load_as_rgb
        if image.ndim == 3 and image.shape[2] == 3:
            return image
        return np.asarray(load_as_rgb(image))

    if isinstance(image, Image.Image):
        return np.asarray(load_as_rgb(image))

    raise TypeError(f"不支持的输入类型: {type(image)}，期望 numpy.ndarray 或 PIL.Image")


def align_sizes(
    a: NDArray[np.uint8], b: NDArray[np.uint8]
) -> tuple[NDArray[np.uint8], NDArray[np.uint8]]:
    """当两张图像尺寸不同时，resize 到较小图的尺寸。

    使用 LANCZOS 插值保持质量。输入和输出均为 (H, W, 3) uint8。
    """
    h_a, w_a = a.shape[:2]
    h_b, w_b = b.shape[:2]

    if (h_a, w_a) == (h_b, w_b):
        return a, b

    target_h = min(h_a, h_b)
    target_w = min(w_a, w_b)

    def _resize(img: NDArray[np.uint8], h: int, w: int) -> NDArray[np.uint8]:
        if (img.shape[0], img.shape[1]) == (h, w):
            return img
        pil_img = Image.fromarray(img)
        pil_img = pil_img.resize((w, h), Image.LANCZOS)
        return np.array(pil_img)

    return _resize(a, target_h, target_w), _resize(b, target_h, target_w)


def to_tensor_normalized(image: NDArray[np.uint8]):
    """将 (H, W, 3) uint8 数组转换为 (1, 3, H, W) float32 [0, 1] tensor。

    延迟 import torch 以避免不必要的加载。
    """
    import torch

    # (H, W, 3) → (3, H, W) → (1, 3, H, W)
    tensor = (
        torch.from_numpy(image.copy()).permute(2, 0, 1).unsqueeze(0).float() / 255.0
    )
    return tensor
