"""KleinReceiver 单元测试（无 GPU，注入假 pipe）。"""

from PIL import Image

from semantic_transmission.receiver.klein_receiver import fit_working_size


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
