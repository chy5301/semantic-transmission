"""视频解码/编码工具：基于 imageio[ffmpeg] 的帧序列读写。

与 :mod:`common.image_io` 并列——image_io 负责单图加载，video_io 负责
视频与帧序列互转。底层用 imageio 的 ffmpeg 插件（``imageio[ffmpeg]`` 自带
静态二进制，免系统安装 ffmpeg）。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import imageio.v2 as imageio
import numpy as np
from numpy.typing import NDArray
from PIL import Image


@dataclass
class VideoMeta:
    """视频元数据。"""

    fps: float
    width: int
    height: int
    frame_count: int


def read_frames(path: str | Path) -> tuple[list[NDArray[np.uint8]], VideoMeta]:
    """解码视频为 RGB ndarray 帧列表 + 元数据。

    Args:
        path: 视频文件路径。

    Returns:
        ``(frames, meta)``，frames 为 ``(H, W, 3)`` uint8 RGB 数组列表。

    Raises:
        ValueError: 视频无可解码帧。
    """
    path = Path(path)
    try:
        reader = imageio.get_reader(path)
        try:
            meta = reader.get_meta_data()
            frames = [np.asarray(frame, dtype=np.uint8) for frame in reader]
        finally:
            reader.close()
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"无法解码视频: {path}") from e

    if not frames:
        raise ValueError(f"视频无可解码帧: {path}")

    height, width = frames[0].shape[:2]
    fps = float(meta.get("fps", 0.0))
    return frames, VideoMeta(
        fps=fps, width=width, height=height, frame_count=len(frames)
    )


def write_frames(path: str | Path, frames: list[Image.Image], fps: float) -> None:
    """将 PIL 帧列表编码为视频。

    Args:
        path: 输出视频路径（父目录自动创建）。
        frames: PIL Image 帧列表。
        fps: 输出帧率。

    Raises:
        ValueError: 帧列表为空。
    """
    if not frames:
        raise ValueError("帧列表为空，无法写视频")

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    writer = imageio.get_writer(path, fps=fps)
    try:
        for frame in frames:
            writer.append_data(np.asarray(frame, dtype=np.uint8))
    finally:
        writer.close()


__all__ = ["VideoMeta", "read_frames", "write_frames"]
