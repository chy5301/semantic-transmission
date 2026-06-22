"""video_eval 逐帧 + 整段评估测试（无 GPU：仅 PSNR/SSIM + mock LPIPS）。"""

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
