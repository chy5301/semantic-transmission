"""DiffusersReceiver 单元测试（mock pipeline）。"""

import io
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import torch
from PIL import Image

from semantic_transmission.common.config import DiffusersReceiverConfig
from semantic_transmission.receiver.diffusers_receiver import (
    DiffusersReceiver,
    _TORCH_DTYPE_MAP,
)


def _make_png_bytes() -> bytes:
    img = Image.new("RGB", (4, 4), color=(128, 128, 128))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _make_pil_image() -> Image.Image:
    return Image.new("RGB", (64, 64), color=(200, 100, 50))


def _make_mock_pipeline():
    """创建 mock pipeline，返回包含 images 属性的结果。"""
    pipeline = MagicMock()
    result = MagicMock()
    result.images = [_make_pil_image()]
    pipeline.return_value = result
    pipeline.to.return_value = pipeline
    return pipeline


PROMPT_TEXT = "A desert road with mountains in the background."


class TestInit:
    def test_default_config(self):
        receiver = DiffusersReceiver()
        assert receiver.config.model_name == "Tongyi-MAI/Z-Image-Turbo"
        assert not receiver.is_loaded

    def test_custom_config(self):
        config = DiffusersReceiverConfig(
            num_inference_steps=4,
            guidance_scale=2.0,
        )
        receiver = DiffusersReceiver(config)
        assert receiver.config.num_inference_steps == 4
        assert receiver.config.guidance_scale == 2.0


class TestLoadUnload:
    @patch("diffusers.ZImageControlNetPipeline")
    @patch("diffusers.ZImageControlNetModel")
    def test_load_creates_pipeline(self, mock_model_cls, mock_pipe_cls):
        mock_pipe = _make_mock_pipeline()
        mock_pipe_cls.from_pretrained.return_value = mock_pipe

        receiver = DiffusersReceiver()
        receiver.load()

        assert receiver.is_loaded
        mock_model_cls.from_pretrained.assert_called_once()
        mock_pipe_cls.from_pretrained.assert_called_once()

    @patch("diffusers.ZImageControlNetPipeline")
    @patch("diffusers.ZImageControlNetModel")
    def test_load_skips_if_already_loaded(self, mock_model_cls, mock_pipe_cls):
        mock_pipe = _make_mock_pipeline()
        mock_pipe_cls.from_pretrained.return_value = mock_pipe

        receiver = DiffusersReceiver()
        receiver.load()
        receiver.load()  # 第二次调用应跳过

        mock_pipe_cls.from_pretrained.assert_called_once()

    def test_unload_releases_pipeline(self):
        receiver = DiffusersReceiver()
        receiver._pipeline = MagicMock()
        assert receiver.is_loaded

        receiver.unload()
        assert not receiver.is_loaded

    def test_unload_when_not_loaded(self):
        receiver = DiffusersReceiver()
        receiver.unload()  # 不应报错
        assert not receiver.is_loaded


class TestProcess:
    @pytest.fixture
    def receiver_with_mock_pipeline(self):
        receiver = DiffusersReceiver()
        receiver._pipeline = _make_mock_pipeline()
        return receiver

    @pytest.fixture
    def edge_image_path(self, tmp_path) -> Path:
        img = Image.new("L", (64, 64), color=255)
        path = tmp_path / "canny_edge.png"
        img.save(path, format="PNG")
        return path

    def test_returns_pil_image(self, receiver_with_mock_pipeline, edge_image_path):
        result = receiver_with_mock_pipeline.process(edge_image_path, PROMPT_TEXT)
        assert isinstance(result, Image.Image)

    def test_accepts_pil_image(self, receiver_with_mock_pipeline):
        edge = Image.new("L", (64, 64), color=128)
        result = receiver_with_mock_pipeline.process(edge, PROMPT_TEXT)
        assert isinstance(result, Image.Image)

    def test_accepts_bytes(self, receiver_with_mock_pipeline):
        edge_bytes = _make_png_bytes()
        result = receiver_with_mock_pipeline.process(edge_bytes, PROMPT_TEXT)
        assert isinstance(result, Image.Image)

    def test_accepts_str_path(self, receiver_with_mock_pipeline, edge_image_path):
        result = receiver_with_mock_pipeline.process(str(edge_image_path), PROMPT_TEXT)
        assert isinstance(result, Image.Image)

    def test_seed_passed_to_generator(
        self, receiver_with_mock_pipeline, edge_image_path
    ):
        receiver_with_mock_pipeline.process(edge_image_path, PROMPT_TEXT, seed=42)
        call_kwargs = receiver_with_mock_pipeline._pipeline.call_args[1]
        assert call_kwargs["prompt"] == PROMPT_TEXT
        assert call_kwargs["num_inference_steps"] == 9
        assert call_kwargs["guidance_scale"] == 1.0
        generator = call_kwargs["generator"]
        assert isinstance(generator, torch.Generator)

    def test_seed_zero_is_valid(self, receiver_with_mock_pipeline, edge_image_path):
        receiver_with_mock_pipeline.process(edge_image_path, PROMPT_TEXT, seed=0)
        call_kwargs = receiver_with_mock_pipeline._pipeline.call_args[1]
        generator = call_kwargs["generator"]
        assert isinstance(generator, torch.Generator)

    def test_seed_none_generates_random(
        self, receiver_with_mock_pipeline, edge_image_path
    ):
        receiver_with_mock_pipeline.process(edge_image_path, PROMPT_TEXT)
        call_kwargs = receiver_with_mock_pipeline._pipeline.call_args[1]
        assert "generator" in call_kwargs

    def test_passes_control_image(self, receiver_with_mock_pipeline, edge_image_path):
        receiver_with_mock_pipeline.process(edge_image_path, PROMPT_TEXT, seed=1)
        call_kwargs = receiver_with_mock_pipeline._pipeline.call_args[1]
        assert isinstance(call_kwargs["control_image"], Image.Image)

    def test_auto_loads_if_not_loaded(self, edge_image_path):
        """process 自动触发 load。"""
        receiver = DiffusersReceiver()
        mock_pipe = _make_mock_pipeline()

        with (
            patch("diffusers.ZImageControlNetPipeline") as mock_pipe_cls,
            patch("diffusers.ZImageControlNetModel"),
        ):
            mock_pipe_cls.from_pretrained.return_value = mock_pipe
            result = receiver.process(edge_image_path, PROMPT_TEXT)

        assert isinstance(result, Image.Image)
        assert receiver.is_loaded


class TestTorchDtypeMap:
    def test_known_dtypes(self):
        assert _TORCH_DTYPE_MAP["float16"] == torch.float16
        assert _TORCH_DTYPE_MAP["bfloat16"] == torch.bfloat16
        assert _TORCH_DTYPE_MAP["float32"] == torch.float32
