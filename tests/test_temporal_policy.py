"""时序策略纯逻辑单测（无 GPU）——针对 src 版本。"""

import pytest
from PIL import Image

from semantic_transmission.pipeline.temporal_policy import (
    TemporalPolicyConfig,
    build_reference_images,
    is_keyframe,
)


def _cfg(**kw):
    return TemporalPolicyConfig(**kw)


def test_defaults():
    c = TemporalPolicyConfig()
    assert c.keyframe_interval == 12
    assert c.reference_mode == "prev"
    assert c.keyframe_passthrough is True


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
    a, b = Image.new("RGB", (8, 8)), Image.new("RGB", (8, 8))
    assert build_reference_images("none", a, b) == []


def test_build_refs_prev_only():
    prev = Image.new("RGB", (8, 8), (1, 1, 1))
    kf = Image.new("RGB", (8, 8), (2, 2, 2))
    assert build_reference_images("prev", prev, kf) == [prev]


def test_build_refs_keyframe_only():
    prev = Image.new("RGB", (8, 8), (1, 1, 1))
    kf = Image.new("RGB", (8, 8), (2, 2, 2))
    assert build_reference_images("keyframe", prev, kf) == [kf]


def test_build_refs_prev_keyframe_order():
    prev = Image.new("RGB", (8, 8), (1, 1, 1))
    kf = Image.new("RGB", (8, 8), (2, 2, 2))
    assert build_reference_images("prev_keyframe", prev, kf) == [prev, kf]


def test_build_refs_drops_none_prev():
    kf = Image.new("RGB", (8, 8), (2, 2, 2))
    assert build_reference_images("prev_keyframe", None, kf) == [kf]


def test_build_refs_invalid_mode_raises():
    with pytest.raises(ValueError, match="reference_mode"):
        build_reference_images("bogus", None, None)
