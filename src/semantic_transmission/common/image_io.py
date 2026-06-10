"""统一的图像加载与格式转换工具。

提供 :func:`load_as_rgb` 作为整个项目的图像加载入口，消除散落在
receiver/sender/evaluation/scripts/cli/gui 中的
``Image.open(...).convert("RGB")`` 与 ``Image.fromarray(...)`` 重复代码。

设计目标：
- 一个函数处理 ``str | Path | bytes | numpy.ndarray | PIL.Image.Image`` 五种输入；
- 返回值统一为 RGB 模式的 :class:`PIL.Image.Image`，下游可直接 ``np.array()`` 或
  传给 ControlNet / VLM；
- 不依赖 :mod:`evaluation.utils`，避免循环导入；和 ``to_numpy()`` 职责互补——
  本模块负责"加载"，:func:`evaluation.utils.to_numpy` 负责"指标计算前的 ndarray 归一化"。
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Union

import numpy as np
from numpy.typing import NDArray
from PIL import Image

ImageSource = Union[str, Path, bytes, NDArray[np.uint8], Image.Image]
"""``load_as_rgb`` 支持的所有输入类型别名。"""


def load_as_rgb(source: ImageSource) -> Image.Image:
    """将任意常见输入统一加载为 RGB 模式的 :class:`PIL.Image.Image`。

    Args:
        source: 图像来源，支持以下任意类型：

            - ``str`` / :class:`pathlib.Path`: 文件路径；
            - ``bytes``: 原始字节流（如 PNG/JPEG 编码后内容），通过
              :class:`io.BytesIO` 解码；
            - :class:`numpy.ndarray`: ``(H, W)``、``(H, W, 3)`` 或 ``(H, W, 4)``
              的 uint8 数组，灰度图会扩展为 3 通道，RGBA 会丢弃 alpha；
            - :class:`PIL.Image.Image`: 任意 mode 的 PIL 图像。

    Returns:
        RGB 模式的 :class:`PIL.Image.Image`。即便输入已是 RGB，仍会返回一个
        新对象引用（PIL 内部对同模式 ``convert`` 是 no-op，不复制像素）。

    Raises:
        TypeError: 当 ``source`` 类型不在上述列表中时。
        ValueError: 当 ``source`` 是 ndarray 但形状不支持时。
    """
    if isinstance(source, Image.Image):
        img = source
    elif isinstance(source, (str, Path)):
        img = Image.open(source)
    elif isinstance(source, bytes):
        img = Image.open(io.BytesIO(source))
    elif isinstance(source, np.ndarray):
        img = _ndarray_to_pil(source)
    else:
        raise TypeError(
            f"load_as_rgb 不支持的输入类型: {type(source).__name__}，"
            "期望 str | Path | bytes | numpy.ndarray | PIL.Image.Image"
        )

    if img.mode != "RGB":
        img = img.convert("RGB")
    return img


def image_to_numpy(source: ImageSource) -> NDArray[np.uint8]:
    """将任意输入加载并转为 ``(H, W, 3)`` uint8 RGB numpy 数组。

    内部实现：``np.asarray(load_as_rgb(source))``。当下游需要 ndarray
    （例如 Canny 提取、CLIP 编码、PSNR/SSIM 计算）时使用此 helper，避免
    手写 ``np.array(Image.open(...).convert("RGB"))`` 两步。

    Returns:
        ``(H, W, 3)`` uint8 RGB 数组。
    """
    return np.asarray(load_as_rgb(source))


def _ndarray_to_pil(arr: NDArray[np.uint8]) -> Image.Image:
    """将形状各异的 numpy 数组转为 RGB PIL Image。

    - ``(H, W)`` 灰度: 复制 3 次成 RGB；
    - ``(H, W, 3)`` RGB: 直接构造；
    - ``(H, W, 4)`` RGBA: 丢弃 alpha 通道。

    其他形状均抛 :class:`ValueError`。
    """
    if arr.ndim == 2:
        rgb = np.stack([arr] * 3, axis=-1)
        return Image.fromarray(rgb, mode="RGB")
    if arr.ndim == 3:
        if arr.shape[2] == 3:
            return Image.fromarray(arr, mode="RGB")
        if arr.shape[2] == 4:
            return Image.fromarray(arr[:, :, :3].copy(), mode="RGB")
    raise ValueError(
        f"load_as_rgb 不支持的数组形状: {arr.shape}，期望 (H,W) / (H,W,3) / (H,W,4)"
    )


__all__ = ["ImageSource", "load_as_rgb", "image_to_numpy"]
