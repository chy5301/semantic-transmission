"""video_eval 逐帧 + 整段评估测试（无 GPU：仅 PSNR/SSIM + mock LPIPS）。"""

import json
import math
from unittest.mock import MagicMock

import numpy as np
import pytest

from semantic_transmission.evaluation.video_eval import (
    evaluate_video,
    summarize_metrics,
)


def _frame(val):
    return np.full((16, 16, 3), val, dtype=np.uint8)


def test_frame_count_mismatch_raises():
    with pytest.raises(ValueError):
        evaluate_video(
            [_frame(10)], [_frame(10), _frame(20)], with_lpips=False, with_clip=False
        )


def test_prompts_length_mismatch_raises():
    with pytest.raises(ValueError):
        evaluate_video(
            [_frame(10), _frame(20)],
            [_frame(11), _frame(21)],
            prompts=["only-one"],
            with_lpips=False,
            with_clip=False,
        )


def test_basic_psnr_ssim_per_frame_and_summary():
    orig = [_frame(100), _frame(150)]
    rest = [_frame(110), _frame(151)]
    report = evaluate_video(orig, rest, with_lpips=False, with_clip=False)
    assert report["frame_count"] == 2
    assert len(report["frames"]) == 2
    assert report["frames"][0]["index"] == 0
    assert isinstance(report["frames"][0]["metrics"]["psnr"], float)
    assert report["frames"][0]["metrics"]["lpips"] is None
    assert report["frames"][0]["metrics"]["clip_score"] is None
    assert report["summary"]["psnr"]["count"] == 2
    assert report["summary"]["psnr"]["mean"] is not None


def test_summarize_metrics_handles_none():
    frames = [
        {"metrics": {"psnr": 20.0, "ssim": 0.8, "lpips": None, "clip_score": None}},
        {"metrics": {"psnr": 30.0, "ssim": 0.6, "lpips": 0.2, "clip_score": None}},
    ]
    summary = summarize_metrics(frames)
    assert summary["psnr"]["mean"] == pytest.approx(25.0)
    assert summary["lpips"]["count"] == 1
    assert summary["clip_score"]["count"] == 0
    assert summary["clip_score"]["mean"] is None


def test_identical_frames_psnr_is_none_not_inf():
    """完全相同的帧：psnr 应为 None（非 inf），summary 不含 inf，报告可 JSON 序列化。"""
    frame = _frame(128)
    report = evaluate_video([frame], [frame.copy()], with_lpips=False, with_clip=False)
    assert report["frames"][0]["metrics"]["psnr"] is None, (
        "identical frame psnr must be None"
    )
    summary_psnr = report["summary"]["psnr"]
    assert summary_psnr["mean"] is None or math.isfinite(summary_psnr["mean"]), (
        "summary psnr mean must be finite or None, not inf"
    )
    dumped = json.dumps(report)
    assert "Infinity" not in dumped, "JSON report must not contain bare Infinity"
    assert "NaN" not in dumped, "JSON report must not contain bare NaN"


def test_mixed_identical_and_different_frames_summary():
    """一帧相同 + 一帧不同：summary psnr count == 1，mean 有限。"""
    frame_same = _frame(128)
    orig = [frame_same, _frame(100)]
    rest = [frame_same.copy(), _frame(110)]
    report = evaluate_video(orig, rest, with_lpips=False, with_clip=False)
    # 第 0 帧：identical → psnr None
    assert report["frames"][0]["metrics"]["psnr"] is None
    # 第 1 帧：differing → psnr finite float
    assert isinstance(report["frames"][1]["metrics"]["psnr"], float)
    assert math.isfinite(report["frames"][1]["metrics"]["psnr"])
    # summary 只统计有限帧
    assert report["summary"]["psnr"]["count"] == 1
    assert math.isfinite(report["summary"]["psnr"]["mean"])
    # JSON 可序列化
    dumped = json.dumps(report)
    assert "Infinity" not in dumped


def test_lpips_with_mock_model(monkeypatch):
    import torch

    mock_model = MagicMock()
    mock_model.return_value = torch.tensor(0.42)
    monkeypatch.setattr(
        "semantic_transmission.evaluation.video_eval.load_lpips_model",
        lambda device=None: mock_model,
    )
    orig = [_frame(100), _frame(150)]
    rest = [_frame(110), _frame(151)]
    report = evaluate_video(orig, rest, with_lpips=True, with_clip=False)
    assert report["frames"][0]["metrics"]["lpips"] == pytest.approx(0.42)
