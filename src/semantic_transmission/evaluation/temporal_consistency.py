"""视频时间一致性指标：相邻帧 MAE + 光流 warp-error。

面向"还原视频闪烁量化"——drop-in 逐帧独立生成在近静止段剧烈闪烁，本模块给出
可对比数值证据，与目视条带互补。帧为 (H, W, 3) uint8 RGB ndarray。
"""

from __future__ import annotations

import cv2
import numpy as np


def _to_gray(frame: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(frame.astype(np.uint8), cv2.COLOR_RGB2GRAY)


def frame_mae_series(frames: list[np.ndarray]) -> list[float]:
    """相邻帧平均绝对差序列，长度 = len(frames)-1（0-255 尺度）。"""
    out: list[float] = []
    for t in range(1, len(frames)):
        a = frames[t].astype(np.float64)
        b = frames[t - 1].astype(np.float64)
        out.append(float(np.abs(a - b).mean()))
    return out


def _remap_by_flow(img: np.ndarray, flow: np.ndarray) -> np.ndarray:
    """按稠密光流重采样 img。"""
    h, w = flow.shape[:2]
    grid_x, grid_y = np.meshgrid(np.arange(w), np.arange(h))
    map_x = (grid_x + flow[..., 0]).astype(np.float32)
    map_y = (grid_y + flow[..., 1]).astype(np.float32)
    return cv2.remap(
        img,
        map_x,
        map_y,
        interpolation=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_REPLICATE,
    )


def warp_error_series(
    frames: list[np.ndarray], flow_frames: list[np.ndarray]
) -> list[float]:
    """warp-error 序列：在 flow_frames 上算后向光流，warp frames[t-1] 后比 frames[t]。

    通常 frames=还原帧、flow_frames=原始帧——用真实运动扣掉合法位移、只留闪烁残差。
    两列表长度须一致。

    注：Farneback 对恒等/近静止帧不返回严格零流，加上 INTER_LINEAR 非整数重采样，
    warp-error 有 ~0.008（0-255 尺度）的算法地板；报告解读须以此为基线，不可把该量级
    读作"绝对零闪烁"。
    """
    if len(frames) != len(flow_frames):
        raise ValueError(
            f"frames({len(frames)}) 与 flow_frames({len(flow_frames)}) 长度不一致"
        )
    out: list[float] = []
    for t in range(1, len(frames)):
        flow = cv2.calcOpticalFlowFarneback(
            _to_gray(flow_frames[t]),
            _to_gray(flow_frames[t - 1]),
            None,
            0.5,
            3,
            15,
            3,
            5,
            1.2,
            0,
        )
        warped = _remap_by_flow(frames[t - 1], flow)
        err = np.abs(frames[t].astype(np.float64) - warped.astype(np.float64)).mean()
        out.append(float(err))
    return out


def _mean_or_none(values: list[float]) -> float | None:
    return float(np.mean(values)) if values else None


def temporal_report(
    restored: list[np.ndarray],
    original: list[np.ndarray],
    keyframe_indices: list[int] | None = None,
) -> dict:
    """两读时间一致性报告：交付（含关键帧边界）/ 生成帧间（排除边界）+ 原始对照。

    转移 t（连接 t-1 与 t）计入"生成帧间"当且仅当 t-1 与 t 都非关键帧。
    """
    kf = set(keyframe_indices or [])
    mae = frame_mae_series(restored)
    warp = warp_error_series(restored, original)
    orig_mae = frame_mae_series(original)

    gen_t = [t for t in range(1, len(restored)) if t not in kf and (t - 1) not in kf]

    def _sub(series: list[float]) -> list[float]:
        return [series[t - 1] for t in gen_t]

    return {
        "delivered": {"mae": _mean_or_none(mae), "warp_error": _mean_or_none(warp)},
        "generated_only": {
            "mae": _mean_or_none(_sub(mae)),
            "warp_error": _mean_or_none(_sub(warp)),
        },
        "original_reference": {"mae": _mean_or_none(orig_mae)},
        "keyframe_count": len(kf),
    }


__all__ = ["frame_mae_series", "warp_error_series", "temporal_report"]
