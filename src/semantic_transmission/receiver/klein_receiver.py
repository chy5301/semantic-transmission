"""FLUX.2-klein-9B 接收端：image=[Canny]+prompt 4 步生成。"""

from __future__ import annotations

from PIL import Image


def fit_working_size(image: Image.Image, max_side: int) -> Image.Image:
    """保宽高比把长边压到 ``max_side``，宽高各向下取 16 的倍数，不放大。

    klein/Flux 要求尺寸为 16 的倍数；大帧（如 1920×1080）原生分辨率会 OOM，
    故在 receiver 内部降采样到 GPU 可承受的工作分辨率。尺寸已合规则原样返回。
    """
    w, h = image.size
    scale = min(1.0, max_side / max(w, h))
    nw = max(16, int(w * scale) // 16 * 16)
    nh = max(16, int(h * scale) // 16 * 16)
    if (nw, nh) == (w, h):
        return image
    return image.resize((nw, nh), Image.LANCZOS)
