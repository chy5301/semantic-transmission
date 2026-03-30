"""感知级质量评估指标：LPIPS。"""

from __future__ import annotations

import lpips
import torch

from .utils import ImageInput, align_sizes, to_numpy, to_tensor_normalized


def load_lpips_model(net: str = "alex", device: str | None = None):
    """加载 LPIPS 模型（可复用以避免重复加载）。

    Args:
        net: 骨干网络，"alex"（推荐，最快）、"vgg" 或 "squeeze"
        device: 计算设备，None 时使用 CPU

    Returns:
        已加载的 LPIPS 模型实例。
    """
    model = lpips.LPIPS(net=net, verbose=False)
    model.eval()
    if device:
        model = model.to(device)
    return model


def compute_lpips(
    original: ImageInput,
    reconstructed: ImageInput,
    *,
    net: str = "alex",
    device: str | None = None,
    loss_fn=None,
) -> float:
    """计算学习感知图像块相似度（LPIPS）。

    使用预训练深度网络提取特征，衡量两张图像在感知层面的差异。

    Args:
        original: 原始图像
        reconstructed: 还原图像
        net: 骨干网络，"alex"（推荐，最快）、"vgg" 或 "squeeze"
        device: 计算设备，None 时使用 CPU
        loss_fn: 预加载的 LPIPS 模型（通过 load_lpips_model 创建），
                 传入时复用该模型，否则每次调用重新加载

    Returns:
        LPIPS 距离值，越低越好。完全相同时为 0.0。
    """
    a = to_numpy(original)
    b = to_numpy(reconstructed)
    a, b = align_sizes(a, b)

    tensor_a = to_tensor_normalized(a)
    tensor_b = to_tensor_normalized(b)

    if device:
        tensor_a = tensor_a.to(device)
        tensor_b = tensor_b.to(device)

    if loss_fn is None:
        loss_fn = load_lpips_model(net=net, device=device)

    with torch.no_grad():
        distance = loss_fn(tensor_a, tensor_b, normalize=True)

    return float(distance.item())
