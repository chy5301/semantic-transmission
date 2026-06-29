"""从视频抽取指定帧并预处理到方形。"""

from collections.abc import Sequence
from pathlib import Path

import cv2
import imageio.v3 as iio
import numpy as np
from numpy.typing import NDArray


def extract_frames(
    video_path: str | Path, indices: Sequence[int]
) -> list[NDArray[np.uint8]]:
    """读取视频指定帧号（RGB）。越界帧号抛 IndexError。"""
    frames = iio.imread(video_path, index=None)  # (N, H, W, 3) RGB
    n = len(frames)
    out: list[NDArray[np.uint8]] = []
    for idx in indices:
        if idx < 0 or idx >= n:
            raise IndexError(f"帧号 {idx} 越界（视频共 {n} 帧）")
        out.append(np.asarray(frames[idx], dtype=np.uint8))
    return out


def resize_frame(frame: NDArray[np.uint8], size: int) -> NDArray[np.uint8]:
    """等比缩放后中心裁剪到 size×size。"""
    h, w = frame.shape[:2]
    scale = size / min(h, w)
    nh, nw = round(h * scale), round(w * scale)
    resized = cv2.resize(frame, (nw, nh), interpolation=cv2.INTER_AREA)
    top = (nh - size) // 2
    left = (nw - size) // 2
    return resized[top : top + size, left : left + size]
