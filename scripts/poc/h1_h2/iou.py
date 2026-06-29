"""边缘 IoU 度量：H1 结构遵循度的量化判据。"""

import cv2
import numpy as np
from numpy.typing import NDArray


def _binarize(mask: NDArray[np.uint8]) -> NDArray[np.bool_]:
    return mask > 0


def edge_iou(
    canny_a: NDArray[np.uint8],
    canny_b: NDArray[np.uint8],
    dilation: int = 0,
) -> float:
    """两张二值边缘图的交并比。

    Args:
        canny_a, canny_b: 二值边缘图 (H, W)，非零视为边缘。
        dilation: >0 时对两图各做该尺寸椭圆核膨胀，容忍 1px 错位。

    Returns:
        IoU ∈ [0, 1]；并集为空返回 0.0。
    """
    a = _binarize(canny_a)
    b = _binarize(canny_b)
    if dilation > 0:
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (dilation, dilation))
        a = cv2.dilate(a.astype(np.uint8), kernel).astype(bool)
        b = cv2.dilate(b.astype(np.uint8), kernel).astype(bool)
    union = np.logical_or(a, b).sum()
    if union == 0:
        return 0.0
    inter = np.logical_and(a, b).sum()
    return float(inter / union)


def recanny_iou(
    generated_rgb: NDArray[np.uint8],
    input_canny: NDArray[np.uint8],
    low: int = 100,
    high: int = 200,
    dilation: int = 0,
) -> float:
    """对生成图重提 Canny，与输入 Canny 算 IoU。"""
    gray = cv2.cvtColor(generated_rgb, cv2.COLOR_RGB2GRAY)
    gen_canny = cv2.Canny(gray, low, high)
    return edge_iou(gen_canny, input_canny, dilation=dilation)
