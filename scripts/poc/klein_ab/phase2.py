"""阶段 2 参考帧时序策略 + 质量两栏拆分（编排层纯逻辑，可单测）。

时序策略不进接收端：接收端保持无状态单帧契约，此处只做"给定跨帧状态 →
构造参考帧列表 / 判定关键帧 / 拆分质量指标"的纯函数，由 run_phase2.py 持状态编排。
"""

from __future__ import annotations

from dataclasses import dataclass

from semantic_transmission.evaluation.video_eval import summarize_metrics

_VALID_MODES = {"none", "prev", "keyframe", "prev_keyframe"}


@dataclass
class TemporalPolicyConfig:
    """参考帧时序策略配置。

    - keyframe_interval: N；<=0 关闭关键帧（退回 drop-in）。
    - reference_mode: none | prev | keyframe | prev_keyframe。
    - keyframe_passthrough: 关键帧那一帧是否直接透传原图（不生成）。
    """

    keyframe_interval: int = 12
    reference_mode: str = "prev"
    keyframe_passthrough: bool = True


def is_keyframe(index: int, config: TemporalPolicyConfig) -> bool:
    """index 是否为关键帧下标（interval>0 且 index 整除 interval）。"""
    return config.keyframe_interval > 0 and index % config.keyframe_interval == 0


def build_reference_images(mode: str, prev_output, last_keyframe) -> list:
    """构造接在 canny 之后的额外参考帧列表。

    顺序：prev 在前、keyframe 在后（对齐设计 C = [canny, prev, keyframe]）。
    prev_output / last_keyframe 为 None 时该项跳过。
    """
    if mode not in _VALID_MODES:
        raise ValueError(f"未知 reference_mode: {mode!r}，支持 {sorted(_VALID_MODES)}")
    refs = []
    if mode in ("prev", "prev_keyframe") and prev_output is not None:
        refs.append(prev_output)
    if mode in ("keyframe", "prev_keyframe") and last_keyframe is not None:
        refs.append(last_keyframe)
    return refs


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
