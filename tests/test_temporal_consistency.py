"""时间一致性指标单测（无 GPU，纯 numpy/cv2）。"""

import numpy as np

from semantic_transmission.evaluation.temporal_consistency import (
    frame_mae_series,
    temporal_report,
    warp_error_series,
)


def _textured(shift=0):
    """64x64 带纹理的确定性帧，可整体平移 shift 像素（用于光流可验证）。"""
    yy, xx = np.mgrid[0:64, 0:64]
    pat = (np.sin(xx / 3.0) + np.cos(yy / 4.0)) * 60 + 128
    img = np.clip(pat, 0, 255).astype(np.uint8)
    img = np.roll(img, shift, axis=1)
    return np.stack([img, img, img], axis=-1)


def test_frame_mae_identical_is_zero():
    f = _textured()
    assert frame_mae_series([f, f.copy(), f.copy()]) == [0.0, 0.0]


def test_frame_mae_counts_transitions():
    frames = [_textured(0), _textured(2), _textured(4)]
    series = frame_mae_series(frames)
    assert len(series) == 2
    assert all(v > 0 for v in series)


def test_warp_error_near_zero_for_identical():
    # Farneback 对恒等帧不返回零流（max ~0.17px），INTER_LINEAR 重采样有 ~0.008/255 地板，
    # 故用 <0.05 容差而非 <1e-6（对抗审核确认 1e-6 恒失败）
    f = _textured()
    errs = warp_error_series([f, f.copy()], [f, f.copy()])
    assert errs[0] < 0.05


def test_warp_error_below_raw_mae_for_pure_translation():
    # 还原=原始（restored==flow_frames），纯平移场景 warp 应显著降低残差
    frames = [_textured(0), _textured(2)]
    raw = frame_mae_series(frames)[0]
    warped = warp_error_series(frames, frames)[0]
    assert warped < raw  # 光流补偿了平移


def test_temporal_report_splits_by_keyframe():
    # 6 帧，关键帧下标 {0, 3}；关键帧那几帧设为原样、其余带抖动
    restored = [
        _textured(0),
        _textured(5),
        _textured(5),
        _textured(0),
        _textured(5),
        _textured(5),
    ]
    original = [_textured(0)] * 6
    rep = temporal_report(restored, original, keyframe_indices=[0, 3])
    assert rep["keyframe_count"] == 2
    # generated_only 排除触及关键帧(0,3)的转移 → 只剩 t=2 和 t=5
    assert rep["generated_only"]["mae"] is not None
    assert rep["delivered"]["mae"] >= rep["generated_only"]["mae"] - 1e-9
    assert rep["original_reference"]["mae"] == 0.0
