"""时序策略纯逻辑单测（无 GPU）——针对 src 版本。"""

import pytest
from PIL import Image

from semantic_transmission.pipeline.temporal_policy import (
    FRAME_TYPE_GENERATED,
    FRAME_TYPE_KEYFRAME,
    TemporalPolicyConfig,
    build_reference_images,
    is_keyframe,
    require_temporal_capable,
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


def test_frame_type_constants_values():
    """常量取值须与既有裸字符串协议一致（relay 双端已就位包依赖此值）。"""
    assert FRAME_TYPE_KEYFRAME == "keyframe"
    assert FRAME_TYPE_GENERATED == "generated"


class _NoRefProcessReceiver:
    """process 不接受 reference_images——触发第一层能力门控。"""

    class config:
        max_side = 512

    def process(self, edge_image, prompt_text, seed=None):
        raise NotImplementedError


class _NoMaxSideConfigReceiver:
    """process 接受 reference_images，但 config 无 max_side——触发第二层门控。"""

    class config:
        pass

    def process(self, edge_image, prompt_text, seed=None, reference_images=None):
        raise NotImplementedError


class _NoConfigReceiver:
    """process 接受 reference_images，但压根没有 config 属性。"""

    def process(self, edge_image, prompt_text, seed=None, reference_images=None):
        raise NotImplementedError


class _CapableReceiver:
    class config:
        max_side = 768

    def process(self, edge_image, prompt_text, seed=None, reference_images=None):
        raise NotImplementedError


def test_require_temporal_capable_rejects_missing_reference_images_param():
    with pytest.raises(TypeError, match="reference_images"):
        require_temporal_capable(_NoRefProcessReceiver())


def test_require_temporal_capable_rejects_config_without_max_side():
    with pytest.raises(TypeError, match="max_side"):
        require_temporal_capable(_NoMaxSideConfigReceiver())


def test_require_temporal_capable_rejects_missing_config():
    with pytest.raises(TypeError, match="max_side"):
        require_temporal_capable(_NoConfigReceiver())


def test_require_temporal_capable_returns_max_side():
    assert require_temporal_capable(_CapableReceiver()) == 768
