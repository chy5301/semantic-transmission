"""DiffusersReceiver 单元测试（mock pipeline）。"""

import io
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import torch
from PIL import Image

from semantic_transmission.common.config import DiffusersReceiverConfig
from semantic_transmission.receiver.base import BatchOutput, FrameInput
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
    @patch("diffusers.GGUFQuantizationConfig")
    @patch("diffusers.ZImageControlNetPipeline")
    @patch("diffusers.ZImageControlNetModel")
    @patch("diffusers.ZImageTransformer2DModel")
    def test_load_creates_pipeline(
        self, mock_xformer_cls, mock_cnet_cls, mock_pipe_cls, mock_quant_cls
    ):
        mock_pipe = _make_mock_pipeline()
        mock_pipe_cls.from_pretrained.return_value = mock_pipe

        receiver = DiffusersReceiver()
        receiver.load()

        assert receiver.is_loaded
        mock_xformer_cls.from_single_file.assert_called_once()
        mock_cnet_cls.from_single_file.assert_called_once()
        mock_pipe_cls.from_pretrained.assert_called_once()
        call_kwargs = mock_pipe_cls.from_pretrained.call_args.kwargs
        assert "transformer" in call_kwargs
        assert "controlnet" in call_kwargs

    @patch("diffusers.GGUFQuantizationConfig")
    @patch("diffusers.ZImageControlNetPipeline")
    @patch("diffusers.ZImageControlNetModel")
    @patch("diffusers.ZImageTransformer2DModel")
    def test_load_skips_if_already_loaded(
        self, mock_xformer_cls, mock_cnet_cls, mock_pipe_cls, mock_quant_cls
    ):
        mock_pipe = _make_mock_pipeline()
        mock_pipe_cls.from_pretrained.return_value = mock_pipe

        receiver = DiffusersReceiver()
        receiver.load()
        receiver.load()  # 第二次调用应跳过

        mock_xformer_cls.from_single_file.assert_called_once()
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
        # 强制 CPU 设备，避免在无 CUDA 驱动的 CI runner 上构造
        # torch.Generator(device="cuda") 触发 cudaErrorInsufficientDriver。
        receiver = DiffusersReceiver(DiffusersReceiverConfig(device="cpu"))
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
        receiver = DiffusersReceiver(DiffusersReceiverConfig(device="cpu"))
        mock_pipe = _make_mock_pipeline()

        with (
            patch("diffusers.ZImageControlNetPipeline") as mock_pipe_cls,
            patch("diffusers.ZImageControlNetModel"),
            patch("diffusers.ZImageTransformer2DModel"),
            patch("diffusers.GGUFQuantizationConfig"),
        ):
            mock_pipe_cls.from_pretrained.return_value = mock_pipe
            result = receiver.process(edge_image_path, PROMPT_TEXT)

        assert isinstance(result, Image.Image)
        assert receiver.is_loaded


class TestProcessBatch:
    @pytest.fixture
    def receiver_with_mock_pipeline(self):
        # 同 TestProcess：强制 CPU 设备避免 CI 触发 CUDA 驱动检查。
        receiver = DiffusersReceiver(DiffusersReceiverConfig(device="cpu"))
        receiver._pipeline = _make_mock_pipeline()
        return receiver

    def test_returns_batch_output(self, receiver_with_mock_pipeline):
        frames = [
            FrameInput(edge_image=_make_pil_image(), prompt_text="frame 0"),
            FrameInput(edge_image=_make_pil_image(), prompt_text="frame 1"),
        ]
        result = receiver_with_mock_pipeline.process_batch(frames)
        assert isinstance(result, BatchOutput)
        assert len(result.images) == 2
        assert result.stats.total == 2
        assert result.stats.success == 2

    def test_empty_frames(self, receiver_with_mock_pipeline):
        result = receiver_with_mock_pipeline.process_batch([])
        assert len(result.images) == 0
        assert result.stats.total == 0

    def test_model_loaded_once(self):
        """process_batch 先 load，批量期间模型只加载一次。"""
        receiver = DiffusersReceiver()
        mock_pipe = _make_mock_pipeline()

        with (
            patch("diffusers.ZImageControlNetPipeline") as mock_pipe_cls,
            patch("diffusers.ZImageControlNetModel"),
            patch("diffusers.ZImageTransformer2DModel"),
            patch("diffusers.GGUFQuantizationConfig"),
        ):
            mock_pipe_cls.from_pretrained.return_value = mock_pipe
            frames = [
                FrameInput(edge_image=_make_pil_image(), prompt_text=f"frame {i}")
                for i in range(3)
            ]
            receiver.process_batch(frames)

        mock_pipe_cls.from_pretrained.assert_called_once()

    def test_seed_per_frame(self, receiver_with_mock_pipeline):
        frames = [
            FrameInput(edge_image=_make_pil_image(), prompt_text="a", seed=10),
            FrameInput(edge_image=_make_pil_image(), prompt_text="b", seed=20),
        ]
        result = receiver_with_mock_pipeline.process_batch(frames)
        assert all(isinstance(img, Image.Image) for img in result.images)

    def test_metadata_name_in_stats(self, receiver_with_mock_pipeline):
        frames = [
            FrameInput(
                edge_image=_make_pil_image(),
                prompt_text="test",
                metadata={"name": "custom_name"},
            ),
        ]
        result = receiver_with_mock_pipeline.process_batch(frames)
        assert result.stats.samples[0].name == "custom_name"

    def test_default_frame_name(self, receiver_with_mock_pipeline):
        frames = [FrameInput(edge_image=_make_pil_image(), prompt_text="test")]
        result = receiver_with_mock_pipeline.process_batch(frames)
        assert result.stats.samples[0].name == "frame_0000"

    def test_failed_frame_tracked(self, receiver_with_mock_pipeline):
        """单帧失败不影响其他帧处理。"""
        pipe = receiver_with_mock_pipeline._pipeline
        call_count = 0

        def side_effect(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise RuntimeError("GPU OOM")
            result = MagicMock()
            result.images = [_make_pil_image()]
            return result

        pipe.side_effect = side_effect
        frames = [
            FrameInput(edge_image=_make_pil_image(), prompt_text=f"frame {i}")
            for i in range(3)
        ]
        result = receiver_with_mock_pipeline.process_batch(frames)
        assert result.stats.total == 3
        assert result.stats.success == 2
        assert result.stats.failed == 1
        assert result.images[0] is not None
        assert result.images[1] is None  # failed frame
        assert result.images[2] is not None

    def test_timings_recorded(self, receiver_with_mock_pipeline):
        frames = [FrameInput(edge_image=_make_pil_image(), prompt_text="test")]
        result = receiver_with_mock_pipeline.process_batch(frames)
        assert "process" in result.stats.samples[0].timings
        assert result.stats.total_time >= 0


class TestTorchDtypeMap:
    def test_known_dtypes(self):
        assert _TORCH_DTYPE_MAP["float16"] == torch.float16
        assert _TORCH_DTYPE_MAP["bfloat16"] == torch.bfloat16
        assert _TORCH_DTYPE_MAP["float32"] == torch.float32
