"""KleinReceiver 单元测试（无 GPU，注入假 pipe）。"""

from PIL import Image

from semantic_transmission.common.config import KleinReceiverConfig
from semantic_transmission.receiver.base import BaseReceiver
from semantic_transmission.receiver.klein_receiver import (
    KleinReceiver,
    _resolve_torch_dtype,
    fit_working_size,
)


class _FakePipe:
    """记录 __call__ 入参的假 pipeline。"""

    def __init__(self):
        self.calls = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        out = type("Out", (), {})()
        out.images = [Image.new("RGB", (kwargs["width"], kwargs["height"]))]
        return out


def _receiver_with_fake_pipe():
    rec = KleinReceiver(KleinReceiverConfig(model_dir="/x", max_side=768))
    fake = _FakePipe()
    rec._pipe = fake
    return rec, fake


def test_is_basereceiver():
    rec = KleinReceiver(KleinReceiverConfig(model_dir="/x"))
    assert isinstance(rec, BaseReceiver)
    assert rec.is_loaded is False


def test_process_passes_klein_kwargs():
    rec, fake = _receiver_with_fake_pipe()
    rec.process(Image.new("RGB", (1920, 1080)), "a desert road", seed=0)
    call = fake.calls[0]
    assert call["image"][0].size == (768, 432)  # 内部已降采样
    assert call["width"] == 768 and call["height"] == 432
    assert call["num_inference_steps"] == 4
    assert call["guidance_scale"] == 1.0
    assert call["prompt"] == "a desert road"
    assert call["generator"].device.type == "cpu"


def test_process_seed_deterministic_generator():
    rec, fake = _receiver_with_fake_pipe()
    rec.process(Image.new("RGB", (512, 512)), "x", seed=123)
    gen = fake.calls[0]["generator"]
    assert gen.initial_seed() == 123


def test_load_idempotent(monkeypatch):
    rec = KleinReceiver(KleinReceiverConfig(model_dir="/x"))
    counter = {"n": 0}

    def fake_build():
        counter["n"] += 1
        return _FakePipe()

    monkeypatch.setattr(rec, "_build_pipeline", fake_build)
    rec.load()
    rec.load()
    assert counter["n"] == 1
    assert rec.is_loaded is True


def test_unload_clears_pipe():
    rec, _ = _receiver_with_fake_pipe()
    assert rec.is_loaded is True
    rec.unload()
    assert rec.is_loaded is False


def test_fit_downscales_16x9_to_max_side():
    out = fit_working_size(Image.new("RGB", (1920, 1080)), max_side=768)
    assert out.size == (768, 432)  # 768=48*16, 432=27*16


def test_fit_downscales_4x3_to_max_side():
    out = fit_working_size(Image.new("RGB", (1280, 960)), max_side=768)
    assert out.size == (768, 576)  # 576=36*16


def test_fit_no_upscale_but_rounds_to_16():
    out = fit_working_size(Image.new("RGB", (100, 100)), max_side=768)
    assert out.size == (96, 96)  # 不放大，向下取 16


def test_fit_keeps_exact_multiple_unchanged():
    src = Image.new("RGB", (320, 240))
    out = fit_working_size(src, max_side=768)
    assert out.size == (320, 240)
    assert out is src  # 尺寸已合规则原样返回


# ── _resolve_torch_dtype ──────────────────────────────────────────────


def test_resolve_torch_dtype_valid():
    import torch

    assert _resolve_torch_dtype("bfloat16") is torch.bfloat16
    assert _resolve_torch_dtype("float16") is torch.float16
    assert _resolve_torch_dtype("float32") is torch.float32


def test_resolve_torch_dtype_invalid_raises():
    import pytest

    with pytest.raises(ValueError, match="BF16"):
        _resolve_torch_dtype("BF16")


# ── 空 images 守卫 ─────────────────────────────────────────────────────


def test_process_raises_on_empty_images():
    """result.images 为空列表时应抛出 RuntimeError。"""

    class _EmptyPipe:
        def __call__(self, **kwargs):
            out = type("Out", (), {})()
            out.images = []
            return out

    rec = KleinReceiver(KleinReceiverConfig(model_dir="/x"))
    rec._pipe = _EmptyPipe()

    import pytest

    with pytest.raises(RuntimeError, match="未生成图像"):
        rec.process(Image.new("RGB", (64, 64)), "test")
