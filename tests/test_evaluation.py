"""质量评估模块测试。"""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from PIL import Image

from semantic_transmission.evaluation.utils import (
    align_sizes,
    to_numpy,
    to_tensor_normalized,
)
from semantic_transmission.evaluation.pixel_metrics import compute_psnr, compute_ssim
from semantic_transmission.evaluation.perceptual_metrics import compute_lpips
from semantic_transmission.evaluation.semantic_metrics import compute_clip_score


# ============================================================
# utils 测试
# ============================================================


class TestToNumpy:
    """to_numpy 类型转换测试。"""

    def test_rgb_array_passthrough(self):
        arr = np.zeros((32, 32, 3), dtype=np.uint8)
        result = to_numpy(arr)
        assert result.shape == (32, 32, 3)
        assert result.dtype == np.uint8

    def test_grayscale_array_to_rgb(self):
        arr = np.full((32, 32), 128, dtype=np.uint8)
        result = to_numpy(arr)
        assert result.shape == (32, 32, 3)
        assert np.all(result[:, :, 0] == 128)

    def test_rgba_array_to_rgb(self):
        arr = np.zeros((32, 32, 4), dtype=np.uint8)
        arr[:, :, 0] = 255  # R 通道
        arr[:, :, 3] = 128  # Alpha 通道
        result = to_numpy(arr)
        assert result.shape == (32, 32, 3)
        assert np.all(result[:, :, 0] == 255)

    def test_pil_rgb(self):
        img = Image.new("RGB", (32, 32), (100, 150, 200))
        result = to_numpy(img)
        assert result.shape == (32, 32, 3)
        assert result[0, 0, 0] == 100

    def test_pil_rgba(self):
        img = Image.new("RGBA", (32, 32), (100, 150, 200, 255))
        result = to_numpy(img)
        assert result.shape == (32, 32, 3)
        assert result[0, 0, 0] == 100

    def test_pil_grayscale(self):
        img = Image.new("L", (32, 32), 128)
        result = to_numpy(img)
        assert result.shape == (32, 32, 3)

    def test_pil_palette(self):
        img = Image.new("P", (32, 32))
        result = to_numpy(img)
        assert result.shape == (32, 32, 3)

    def test_invalid_type_raises(self):
        with pytest.raises(TypeError):
            to_numpy("not an image")

    def test_invalid_shape_raises(self):
        arr = np.zeros((32, 32, 5), dtype=np.uint8)
        with pytest.raises(ValueError):
            to_numpy(arr)


class TestAlignSizes:
    """align_sizes 尺寸对齐测试。"""

    def test_same_size_no_change(self):
        a = np.zeros((32, 32, 3), dtype=np.uint8)
        b = np.zeros((32, 32, 3), dtype=np.uint8)
        ra, rb = align_sizes(a, b)
        assert ra.shape == (32, 32, 3)
        assert rb.shape == (32, 32, 3)

    def test_different_sizes_resize_to_smaller(self):
        a = np.zeros((64, 64, 3), dtype=np.uint8)
        b = np.zeros((32, 48, 3), dtype=np.uint8)
        ra, rb = align_sizes(a, b)
        assert ra.shape == (32, 48, 3)
        assert rb.shape == (32, 48, 3)

    def test_only_larger_resized(self):
        a = np.zeros((32, 32, 3), dtype=np.uint8)
        b = np.zeros((64, 64, 3), dtype=np.uint8)
        ra, rb = align_sizes(a, b)
        # a 已经是目标尺寸，不应 resize
        assert ra is a
        assert rb.shape == (32, 32, 3)


class TestToTensorNormalized:
    """to_tensor_normalized tensor 转换测试。"""

    def test_shape(self):
        arr = np.zeros((32, 48, 3), dtype=np.uint8)
        tensor = to_tensor_normalized(arr)
        assert tensor.shape == (1, 3, 32, 48)

    def test_value_range(self):
        arr = np.full((16, 16, 3), 255, dtype=np.uint8)
        tensor = to_tensor_normalized(arr)
        assert tensor.min().item() == pytest.approx(1.0)
        assert tensor.max().item() == pytest.approx(1.0)

    def test_zero_image(self):
        arr = np.zeros((16, 16, 3), dtype=np.uint8)
        tensor = to_tensor_normalized(arr)
        assert tensor.min().item() == pytest.approx(0.0)

    def test_dtype_float32(self):
        import torch

        arr = np.zeros((16, 16, 3), dtype=np.uint8)
        tensor = to_tensor_normalized(arr)
        assert tensor.dtype == torch.float32


# ============================================================
# pixel_metrics 测试
# ============================================================


class TestPSNR:
    """PSNR 指标测试。"""

    def test_identical_images_inf(self):
        img = np.random.randint(0, 256, (32, 32, 3), dtype=np.uint8)
        result = compute_psnr(img, img)
        assert result == float("inf")

    def test_black_vs_white(self):
        black = np.zeros((32, 32, 3), dtype=np.uint8)
        white = np.full((32, 32, 3), 255, dtype=np.uint8)
        result = compute_psnr(black, white)
        # MSE = 255^2, PSNR = 10*log10(255^2/255^2) = 0
        assert result == pytest.approx(0.0, abs=0.01)

    def test_similar_images_high_psnr(self):
        img = np.full((32, 32, 3), 128, dtype=np.uint8)
        noisy = img.copy()
        noisy[0, 0, 0] = 129  # 微小差异
        result = compute_psnr(img, noisy)
        assert result > 40  # 非常相似

    def test_pil_input(self):
        img = Image.new("RGB", (32, 32), (128, 128, 128))
        result = compute_psnr(img, img)
        assert result == float("inf")

    def test_different_sizes(self):
        a = np.full((64, 64, 3), 100, dtype=np.uint8)
        b = np.full((32, 32, 3), 100, dtype=np.uint8)
        result = compute_psnr(a, b)
        assert result == float("inf")


class TestSSIM:
    """SSIM 指标测试。"""

    def test_identical_images_one(self):
        img = np.random.randint(0, 256, (32, 32, 3), dtype=np.uint8)
        result = compute_ssim(img, img)
        assert result == pytest.approx(1.0)

    def test_black_vs_white_low(self):
        black = np.zeros((32, 32, 3), dtype=np.uint8)
        white = np.full((32, 32, 3), 255, dtype=np.uint8)
        result = compute_ssim(black, white)
        assert result < 0.1  # 非常不相似

    def test_pil_input(self):
        img = Image.new("RGB", (32, 32), (128, 128, 128))
        result = compute_ssim(img, img)
        assert result == pytest.approx(1.0)

    def test_different_sizes(self):
        a = np.full((64, 64, 3), 100, dtype=np.uint8)
        b = np.full((32, 32, 3), 100, dtype=np.uint8)
        result = compute_ssim(a, b)
        assert result == pytest.approx(1.0)

    def test_result_range(self):
        a = np.random.randint(0, 256, (32, 32, 3), dtype=np.uint8)
        b = np.random.randint(0, 256, (32, 32, 3), dtype=np.uint8)
        result = compute_ssim(a, b)
        assert -1.0 <= result <= 1.0


# ============================================================
# perceptual_metrics 测试（mock）
# ============================================================


class TestLPIPS:
    """LPIPS 指标测试（mock 模型避免下载权重）。"""

    @patch("semantic_transmission.evaluation.perceptual_metrics.lpips.LPIPS")
    def test_basic_call(self, mock_lpips_cls):
        import torch

        # 设置 mock 返回值
        mock_model = MagicMock()
        mock_model.return_value = torch.tensor([[[[0.25]]]])
        mock_lpips_cls.return_value = mock_model

        a = np.full((32, 32, 3), 100, dtype=np.uint8)
        b = np.full((32, 32, 3), 200, dtype=np.uint8)
        result = compute_lpips(a, b)

        assert result == pytest.approx(0.25)
        mock_lpips_cls.assert_called_once_with(net="alex", verbose=False)
        mock_model.eval.assert_called_once()

    @patch("semantic_transmission.evaluation.perceptual_metrics.lpips.LPIPS")
    def test_normalize_true_passed(self, mock_lpips_cls):
        import torch

        mock_model = MagicMock()
        mock_model.return_value = torch.tensor([[[[0.1]]]])
        mock_lpips_cls.return_value = mock_model

        a = np.full((32, 32, 3), 128, dtype=np.uint8)
        compute_lpips(a, a)

        # 验证 normalize=True 被传递
        call_kwargs = mock_model.call_args
        assert call_kwargs.kwargs.get("normalize") is True

    @patch("semantic_transmission.evaluation.perceptual_metrics.lpips.LPIPS")
    def test_tensor_shape(self, mock_lpips_cls):
        import torch

        mock_model = MagicMock()
        mock_model.return_value = torch.tensor([[[[0.0]]]])
        mock_lpips_cls.return_value = mock_model

        a = np.full((48, 64, 3), 128, dtype=np.uint8)
        compute_lpips(a, a)

        # 验证传入 tensor 的形状
        call_args = mock_model.call_args.args
        assert call_args[0].shape == (1, 3, 48, 64)
        assert call_args[1].shape == (1, 3, 48, 64)

    @patch("semantic_transmission.evaluation.perceptual_metrics.lpips.LPIPS")
    def test_custom_net(self, mock_lpips_cls):
        import torch

        mock_model = MagicMock()
        mock_model.return_value = torch.tensor([[[[0.0]]]])
        mock_lpips_cls.return_value = mock_model

        a = np.full((32, 32, 3), 128, dtype=np.uint8)
        compute_lpips(a, a, net="vgg")

        mock_lpips_cls.assert_called_once_with(net="vgg", verbose=False)

    @patch("semantic_transmission.evaluation.perceptual_metrics.lpips.LPIPS")
    def test_pil_input(self, mock_lpips_cls):
        import torch

        mock_model = MagicMock()
        mock_model.return_value = torch.tensor([[[[0.15]]]])
        mock_lpips_cls.return_value = mock_model

        img = Image.new("RGB", (32, 32), (128, 128, 128))
        result = compute_lpips(img, img)
        assert result == pytest.approx(0.15)

    @patch("semantic_transmission.evaluation.perceptual_metrics.lpips.LPIPS")
    def test_different_sizes(self, mock_lpips_cls):
        import torch

        mock_model = MagicMock()
        mock_model.return_value = torch.tensor([[[[0.2]]]])
        mock_lpips_cls.return_value = mock_model

        a = np.full((64, 64, 3), 128, dtype=np.uint8)
        b = np.full((32, 48, 3), 128, dtype=np.uint8)
        compute_lpips(a, b)

        # 验证对齐后的 tensor 形状
        call_args = mock_model.call_args.args
        assert call_args[0].shape == (1, 3, 32, 48)
        assert call_args[1].shape == (1, 3, 32, 48)


# ============================================================
# semantic_metrics 测试（mock）
# ============================================================


class TestCLIPScore:
    """CLIP Score 指标测试（mock 模型避免下载权重）。"""

    @patch("semantic_transmission.evaluation.semantic_metrics.CLIPProcessor")
    @patch("semantic_transmission.evaluation.semantic_metrics.CLIPModel")
    def test_basic_call(self, mock_model_cls, mock_proc_cls):
        import torch

        # 设置 mock
        mock_model = MagicMock()
        mock_model_cls.from_pretrained.return_value = mock_model

        mock_processor = MagicMock()
        mock_proc_cls.from_pretrained.return_value = mock_processor

        # 模拟 processor 输出
        mock_processor.return_value = {
            "pixel_values": torch.randn(1, 3, 224, 224),
            "input_ids": torch.ones(1, 10, dtype=torch.long),
            "attention_mask": torch.ones(1, 10, dtype=torch.long),
        }

        # 模拟特征向量（归一化后余弦相似度为 0.3）
        img_feat = torch.tensor([[1.0, 0.0]])
        text_feat = torch.tensor([[0.3, 0.9539]])  # cos_sim ≈ 0.3
        mock_model.get_image_features.return_value = img_feat
        mock_model.get_text_features.return_value = text_feat

        img = np.full((32, 32, 3), 128, dtype=np.uint8)
        result = compute_clip_score(img, "a test image")

        # 归一化后：img=[1,0], text=[0.3/1.0, 0.954/1.0]≈[0.3, 0.954]
        # cos_sim = 1*0.3 + 0*0.954 = 0.3 → score = 30.0
        assert result == pytest.approx(30.0, abs=1.0)

    @patch("semantic_transmission.evaluation.semantic_metrics.CLIPProcessor")
    @patch("semantic_transmission.evaluation.semantic_metrics.CLIPModel")
    def test_negative_similarity_clipped_to_zero(self, mock_model_cls, mock_proc_cls):
        import torch

        mock_model = MagicMock()
        mock_model_cls.from_pretrained.return_value = mock_model

        mock_processor = MagicMock()
        mock_proc_cls.from_pretrained.return_value = mock_processor

        mock_processor.return_value = {
            "pixel_values": torch.randn(1, 3, 224, 224),
            "input_ids": torch.ones(1, 10, dtype=torch.long),
            "attention_mask": torch.ones(1, 10, dtype=torch.long),
        }

        # 模拟负余弦相似度
        mock_model.get_image_features.return_value = torch.tensor([[1.0, 0.0]])
        mock_model.get_text_features.return_value = torch.tensor([[-1.0, 0.0]])

        img = np.full((32, 32, 3), 128, dtype=np.uint8)
        result = compute_clip_score(img, "unrelated text")

        assert result == 0.0

    @patch("semantic_transmission.evaluation.semantic_metrics.CLIPProcessor")
    @patch("semantic_transmission.evaluation.semantic_metrics.CLIPModel")
    def test_perfect_similarity(self, mock_model_cls, mock_proc_cls):
        import torch

        mock_model = MagicMock()
        mock_model_cls.from_pretrained.return_value = mock_model

        mock_processor = MagicMock()
        mock_proc_cls.from_pretrained.return_value = mock_processor

        mock_processor.return_value = {
            "pixel_values": torch.randn(1, 3, 224, 224),
            "input_ids": torch.ones(1, 10, dtype=torch.long),
            "attention_mask": torch.ones(1, 10, dtype=torch.long),
        }

        # 相同方向的特征向量 → cos_sim = 1.0
        mock_model.get_image_features.return_value = torch.tensor([[1.0, 0.0]])
        mock_model.get_text_features.return_value = torch.tensor([[1.0, 0.0]])

        img = np.full((32, 32, 3), 128, dtype=np.uint8)
        result = compute_clip_score(img, "perfect match")

        assert result == pytest.approx(100.0)

    @patch("semantic_transmission.evaluation.semantic_metrics.CLIPProcessor")
    @patch("semantic_transmission.evaluation.semantic_metrics.CLIPModel")
    def test_pil_input(self, mock_model_cls, mock_proc_cls):
        import torch

        mock_model = MagicMock()
        mock_model_cls.from_pretrained.return_value = mock_model

        mock_processor = MagicMock()
        mock_proc_cls.from_pretrained.return_value = mock_processor

        mock_processor.return_value = {
            "pixel_values": torch.randn(1, 3, 224, 224),
            "input_ids": torch.ones(1, 10, dtype=torch.long),
            "attention_mask": torch.ones(1, 10, dtype=torch.long),
        }

        mock_model.get_image_features.return_value = torch.tensor([[1.0, 0.0]])
        mock_model.get_text_features.return_value = torch.tensor([[1.0, 0.0]])

        img = Image.new("RGB", (32, 32), (128, 128, 128))
        result = compute_clip_score(img, "a test")

        assert result == pytest.approx(100.0)

    @patch("semantic_transmission.evaluation.semantic_metrics.CLIPProcessor")
    @patch("semantic_transmission.evaluation.semantic_metrics.CLIPModel")
    def test_custom_model_name(self, mock_model_cls, mock_proc_cls):
        import torch

        mock_model = MagicMock()
        mock_model_cls.from_pretrained.return_value = mock_model

        mock_processor = MagicMock()
        mock_proc_cls.from_pretrained.return_value = mock_processor

        mock_processor.return_value = {
            "pixel_values": torch.randn(1, 3, 224, 224),
            "input_ids": torch.ones(1, 10, dtype=torch.long),
            "attention_mask": torch.ones(1, 10, dtype=torch.long),
        }

        mock_model.get_image_features.return_value = torch.tensor([[1.0, 0.0]])
        mock_model.get_text_features.return_value = torch.tensor([[1.0, 0.0]])

        img = np.full((32, 32, 3), 128, dtype=np.uint8)
        compute_clip_score(img, "test", model_name="openai/clip-vit-large-patch14")

        mock_model_cls.from_pretrained.assert_called_once_with(
            "openai/clip-vit-large-patch14"
        )
        mock_proc_cls.from_pretrained.assert_called_once_with(
            "openai/clip-vit-large-patch14"
        )
