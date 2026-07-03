"""阶段 2 时序策略与质量拆分单测（无 GPU）。"""

import pytest
from PIL import Image

from scripts.poc.klein_ab.phase2 import (
    TemporalPolicyConfig,
    build_reference_images,
    is_keyframe,
    split_summary,
)


def _cfg(**kw):
    return TemporalPolicyConfig(**kw)


def test_is_keyframe_interval_12():
    c = _cfg(keyframe_interval=12)
    assert is_keyframe(0, c) is True
    assert is_keyframe(12, c) is True
    assert is_keyframe(5, c) is False
    assert is_keyframe(11, c) is False


def test_is_keyframe_disabled_when_interval_non_positive():
    c = _cfg(keyframe_interval=0)
    assert is_keyframe(0, c) is False
    assert is_keyframe(12, c) is False


def test_build_refs_none_mode_empty():
    assert (
        build_reference_images(
            "none", Image.new("RGB", (8, 8)), Image.new("RGB", (8, 8))
        )
        == []
    )


def test_build_refs_prev_only():
    prev = Image.new("RGB", (8, 8), (1, 1, 1))
    kf = Image.new("RGB", (8, 8), (2, 2, 2))
    refs = build_reference_images("prev", prev, kf)
    assert refs == [prev]


def test_build_refs_keyframe_only():
    prev = Image.new("RGB", (8, 8), (1, 1, 1))
    kf = Image.new("RGB", (8, 8), (2, 2, 2))
    assert build_reference_images("keyframe", prev, kf) == [kf]


def test_build_refs_prev_keyframe_order():
    prev = Image.new("RGB", (8, 8), (1, 1, 1))
    kf = Image.new("RGB", (8, 8), (2, 2, 2))
    assert build_reference_images("prev_keyframe", prev, kf) == [prev, kf]  # prev 在前


def test_build_refs_drops_none_prev():
    kf = Image.new("RGB", (8, 8), (2, 2, 2))
    assert build_reference_images("prev_keyframe", None, kf) == [kf]


def test_build_refs_invalid_mode_raises():
    with pytest.raises(ValueError, match="reference_mode"):
        build_reference_images("bogus", None, None)


def test_split_summary_excludes_keyframe_indices():
    # 构造 4 帧逐帧指标：关键帧 {0} 给满分 ssim=1.0，生成帧 ssim=0.5
    frames = [
        {
            "index": 0,
            "metrics": {"psnr": 99.0, "ssim": 1.0, "lpips": 0.0, "clip_score": 40.0},
        },
        {
            "index": 1,
            "metrics": {"psnr": 15.0, "ssim": 0.5, "lpips": 0.4, "clip_score": 30.0},
        },
        {
            "index": 2,
            "metrics": {"psnr": 15.0, "ssim": 0.5, "lpips": 0.4, "clip_score": 30.0},
        },
        {
            "index": 3,
            "metrics": {"psnr": 15.0, "ssim": 0.5, "lpips": 0.4, "clip_score": 30.0},
        },
    ]
    out = split_summary(frames, keyframe_indices=[0])
    assert out["delivered"]["ssim"]["count"] == 4
    assert out["generated_only"]["ssim"]["count"] == 3  # 排除关键帧 0
    assert out["generated_only"]["ssim"]["mean"] == pytest.approx(0.5)
    assert out["delivered"]["ssim"]["mean"] > out["generated_only"]["ssim"]["mean"]
