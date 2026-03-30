"""像素级质量评估指标：PSNR 和 SSIM。"""

from __future__ import annotations

from skimage.metrics import peak_signal_noise_ratio, structural_similarity

from .utils import ImageInput, align_sizes, to_numpy


def compute_psnr(
    original: ImageInput,
    reconstructed: ImageInput,
    *,
    data_range: int = 255,
) -> float:
    """计算峰值信噪比（PSNR）。

    Args:
        original: 原始图像
        reconstructed: 还原图像
        data_range: 像素值范围，uint8 图像为 255

    Returns:
        PSNR 值（dB），越高越好。完全相同时返回 inf。
    """
    a = to_numpy(original)
    b = to_numpy(reconstructed)
    a, b = align_sizes(a, b)
    return float(peak_signal_noise_ratio(a, b, data_range=data_range))


def compute_ssim(
    original: ImageInput,
    reconstructed: ImageInput,
    *,
    data_range: int = 255,
) -> float:
    """计算结构相似度（SSIM）。

    Args:
        original: 原始图像
        reconstructed: 还原图像
        data_range: 像素值范围，uint8 图像为 255

    Returns:
        SSIM 值，范围 [0, 1]，越高越好。完全相同时为 1.0。
    """
    a = to_numpy(original)
    b = to_numpy(reconstructed)
    a, b = align_sizes(a, b)
    return float(structural_similarity(a, b, data_range=data_range, channel_axis=-1))
