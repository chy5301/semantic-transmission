"""参考帧时序策略纯逻辑（编排层无状态纯函数，可无 GPU 单测）。

时序策略不进接收端：接收端保持无状态单帧契约，此处只做"给定跨帧状态 →
判定关键帧 / 构造参考帧列表"的纯函数，由 VideoPipeline 持状态串行编排。
从 scripts/poc/klein_ab/phase2.py 毕业（PoC 现从本模块重导出）。
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Any

_VALID_MODES = {"none", "prev", "keyframe", "prev_keyframe"}

FRAME_TYPE_KEYFRAME = "keyframe"
"""relay metadata.frame_type 取值：整帧透传的关键帧包。"""

FRAME_TYPE_GENERATED = "generated"
"""relay metadata.frame_type 取值：Canny 边缘图 + prompt 的生成帧包。"""


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

    顺序：prev 在前、keyframe 在后（对齐设计 [canny, prev, keyframe]）。
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


def require_temporal_capable(receiver: Any) -> int:
    """时序补偿能力门控：校验 receiver 支持串行参考帧补偿，返回工作分辨率上限。

    单机 VideoPipeline._run_temporal 与双机 VideoRelayReceiver._run_temporal
    共用此函数，保证两处门控文案一致（不重复内联 inspect 检查）。

    Returns:
        receiver.config.max_side（时序路径用于关键帧缩放的工作分辨率上限）。

    Raises:
        TypeError: receiver.process 不接受 reference_images 参数（提示改用
            --backend klein）；或 receiver 无 config 属性、或 config 无
            max_side 属性（时序补偿前提不满足）。
    """
    params = inspect.signature(receiver.process).parameters
    if "reference_images" not in params:
        raise TypeError(
            "时序补偿要求 receiver.process 接受 reference_images 参数，"
            f"当前接收端 {type(receiver).__name__} 不支持——请用 --backend klein"
        )
    if not hasattr(receiver, "config") or not hasattr(receiver.config, "max_side"):
        raise TypeError(
            "时序补偿要求 receiver.config.max_side 存在（用于关键帧缩放工作分辨率），"
            f"当前接收端 {type(receiver).__name__} 的 config 不支持时序补偿"
        )
    return receiver.config.max_side


__all__ = [
    "TemporalPolicyConfig",
    "is_keyframe",
    "build_reference_images",
    "require_temporal_capable",
    "FRAME_TYPE_KEYFRAME",
    "FRAME_TYPE_GENERATED",
]
