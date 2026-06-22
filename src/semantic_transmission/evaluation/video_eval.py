"""视频质量评估：逐帧 PSNR/SSIM/LPIPS/CLIP + 整段均值/标准差汇总。

与图片版 scripts/evaluate.py 对称——本模块面向「原视频帧 vs 还原视频帧」
逐帧对齐评估，帧数必须一致（D2 无插帧）。LPIPS/CLIP 可关闭以便无 GPU 单测。
"""

from __future__ import annotations

import statistics

from .perceptual_metrics import compute_lpips, load_lpips_model
from .pixel_metrics import compute_psnr, compute_ssim
from .semantic_metrics import compute_clip_score, load_clip_model

_METRIC_NAMES = ("psnr", "ssim", "lpips", "clip_score")


def summarize_metrics(frames: list[dict]) -> dict:
    """对逐帧指标求均值/标准差/有效计数，None 值跳过。"""
    summary: dict = {}
    for name in _METRIC_NAMES:
        values = [
            f["metrics"][name] for f in frames if f["metrics"].get(name) is not None
        ]
        if values:
            mean = statistics.mean(values)
            std = statistics.pstdev(values) if len(values) > 1 else 0.0
            summary[name] = {"mean": mean, "std": std, "count": len(values)}
        else:
            summary[name] = {"mean": None, "std": None, "count": 0}
    return summary


def evaluate_video(
    original_frames: list,
    restored_frames: list,
    prompts: list[str] | None = None,
    *,
    device: str | None = None,
    with_lpips: bool = True,
    with_clip: bool = True,
) -> dict:
    """逐帧评估原视频帧 vs 还原视频帧，并汇总整段统计。

    Args:
        original_frames: 原视频帧列表（ndarray 或 PIL）。
        restored_frames: 还原视频帧列表，长度须与 original_frames 一致。
        prompts: 逐帧描述文本，给定时长度须等于帧数，用于算 CLIP。
        device: 计算设备，None 自动。
        with_lpips: 是否计算 LPIPS（关闭则跳过模型加载）。
        with_clip: 是否计算 CLIP Score（需 prompts，否则逐帧跳过）。

    Returns:
        ``{"frame_count": N, "frames": [...], "summary": {...}}``。

    Raises:
        ValueError: 帧数不一致，或 prompts 长度与帧数不符。
    """
    if len(original_frames) != len(restored_frames):
        raise ValueError(
            f"帧数不一致：原 {len(original_frames)} vs 还原 {len(restored_frames)}"
        )
    if prompts is not None and len(prompts) != len(original_frames):
        raise ValueError(
            f"prompts 长度 {len(prompts)} 与帧数 {len(original_frames)} 不符"
        )

    lpips_model = load_lpips_model(device=device) if with_lpips else None
    clip_model = None
    clip_processor = None
    if with_clip and prompts is not None and any(prompts):
        clip_model, clip_processor = load_clip_model(device=device)

    frames: list[dict] = []
    for i, (orig, rest) in enumerate(zip(original_frames, restored_frames)):
        metrics: dict = {
            "psnr": compute_psnr(orig, rest),
            "ssim": compute_ssim(orig, rest),
            "lpips": None,
            "clip_score": None,
        }
        if lpips_model is not None:
            metrics["lpips"] = compute_lpips(
                orig, rest, loss_fn=lpips_model, device=device
            )
        if clip_model is not None and prompts is not None and prompts[i]:
            metrics["clip_score"] = compute_clip_score(
                rest,
                prompts[i],
                model=clip_model,
                processor=clip_processor,
                device=device,
            )
        frames.append({"index": i, "metrics": metrics})

    return {
        "frame_count": len(frames),
        "frames": frames,
        "summary": summarize_metrics(frames),
    }


__all__ = ["summarize_metrics", "evaluate_video"]
