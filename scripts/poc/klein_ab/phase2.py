"""阶段 2 质量两栏拆分（评估期关注点，留在 PoC 不进生产管道）。

时序纯逻辑（TemporalPolicyConfig / is_keyframe / build_reference_images）已毕业到
src/semantic_transmission/pipeline/temporal_policy.py，此处重导出以保持 run_phase2.py
及其单测的导入路径不变、不重复实现。split_summary 依赖 baseline 对照做质量拆分，
属评估期工具，留在 PoC。
"""

from __future__ import annotations

from semantic_transmission.evaluation.video_eval import summarize_metrics
from semantic_transmission.pipeline.temporal_policy import (
    TemporalPolicyConfig,
    build_reference_images,
    is_keyframe,
)


def split_summary(frames: list[dict], keyframe_indices) -> dict:
    """质量指标两栏：delivered（全帧）/ generated_only（排除关键帧下标）。

    透传关键帧 R[t]≡O[t] 会拿满分 SSIM/PSNR、拉高均值；generated_only 剔除以隔离
    生成帧真实水平。frames 为 evaluate_video 返回的逐帧列表（含 index + metrics）。
    """
    kf = set(keyframe_indices or [])
    return {
        "delivered": summarize_metrics(frames),
        "generated_only": summarize_metrics(
            [f for f in frames if f["index"] not in kf]
        ),
    }


__all__ = [
    "TemporalPolicyConfig",
    "is_keyframe",
    "build_reference_images",
    "split_summary",
]
