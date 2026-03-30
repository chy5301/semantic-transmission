"""评估脚本的单元测试。"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from PIL import Image

# 将 scripts 目录加入模块搜索路径
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from evaluate import (
    compute_summary,
    discover_samples,
    evaluate_sample,
    find_original_image,
    format_table,
    main,
)


# ─── Fixtures ───────────────────────────────────────────────────────────────


def _make_image(path: Path, size: tuple[int, int] = (32, 32)) -> None:
    """创建随机测试图片。"""
    arr = np.random.randint(0, 255, (*size, 3), dtype=np.uint8)
    Image.fromarray(arr).save(path)


@pytest.fixture()
def sample_dir(tmp_path: Path):
    """创建模拟的评估目录结构。"""
    input_dir = tmp_path / "input"
    originals_dir = tmp_path / "originals"
    input_dir.mkdir()
    originals_dir.mkdir()

    # 样本 1: 完整（含 prompt）
    s1 = input_dir / "01-canyon_jeep"
    s1.mkdir()
    _make_image(s1 / "restored.png")
    (s1 / "prompt.txt").write_text("a jeep in a canyon", encoding="utf-8")

    # 样本 2: 无 prompt
    s2 = input_dir / "02-rock_climbing"
    s2.mkdir()
    _make_image(s2 / "restored.png")

    # 样本 3: 无 restored（应被跳过）
    s3 = input_dir / "03-empty"
    s3.mkdir()

    # 原图
    _make_image(originals_dir / "canyon_jeep.jpg")
    _make_image(originals_dir / "rock_climbing.jpeg")

    return {
        "input_dir": input_dir,
        "originals_dir": originals_dir,
    }


# ─── TestFindOriginalImage ──────────────────────────────────────────────────


class TestFindOriginalImage:
    def test_finds_jpg(self, tmp_path: Path):
        _make_image(tmp_path / "canyon_jeep.jpg")
        result = find_original_image("01-canyon_jeep", tmp_path)
        assert result is not None
        assert result.name == "canyon_jeep.jpg"

    def test_finds_jpeg(self, tmp_path: Path):
        _make_image(tmp_path / "rock_climbing.jpeg")
        result = find_original_image("02-rock_climbing", tmp_path)
        assert result is not None
        assert result.name == "rock_climbing.jpeg"

    def test_finds_png(self, tmp_path: Path):
        _make_image(tmp_path / "test_image.png")
        result = find_original_image("05-test_image", tmp_path)
        assert result is not None
        assert result.name == "test_image.png"

    def test_not_found_returns_none(self, tmp_path: Path):
        result = find_original_image("99-nonexistent", tmp_path)
        assert result is None

    def test_strips_numeric_prefix(self, tmp_path: Path):
        _make_image(tmp_path / "sample.jpg")
        result = find_original_image("123-sample", tmp_path)
        assert result is not None
        assert result.name == "sample.jpg"

    def test_underscore_prefix(self, tmp_path: Path):
        _make_image(tmp_path / "sample.jpg")
        result = find_original_image("01_sample", tmp_path)
        assert result is not None
        assert result.name == "sample.jpg"

    def test_no_prefix(self, tmp_path: Path):
        _make_image(tmp_path / "sample.jpg")
        result = find_original_image("sample", tmp_path)
        assert result is not None
        assert result.name == "sample.jpg"


# ─── TestDiscoverSamples ────────────────────────────────────────────────────


class TestDiscoverSamples:
    def test_discovers_valid_samples(self, sample_dir):
        samples = discover_samples(sample_dir["input_dir"])
        names = [s["name"] for s in samples]
        assert "01-canyon_jeep" in names
        assert "02-rock_climbing" in names

    def test_skips_without_restored(self, sample_dir):
        samples = discover_samples(sample_dir["input_dir"])
        names = [s["name"] for s in samples]
        assert "03-empty" not in names

    def test_sorted_order(self, sample_dir):
        samples = discover_samples(sample_dir["input_dir"])
        names = [s["name"] for s in samples]
        assert names == sorted(names)

    def test_skips_non_directories(self, sample_dir):
        (sample_dir["input_dir"] / "stray_file.txt").write_text("hi")
        samples = discover_samples(sample_dir["input_dir"])
        names = [s["name"] for s in samples]
        assert "stray_file.txt" not in names


# ─── TestComputeSummary ─────────────────────────────────────────────────────


class TestComputeSummary:
    def test_mean_and_std(self):
        results = [
            {"metrics": {"psnr": 20.0, "ssim": 0.8, "lpips": 0.3, "clip_score": 70.0}},
            {"metrics": {"psnr": 30.0, "ssim": 0.6, "lpips": 0.1, "clip_score": 80.0}},
        ]
        summary = compute_summary(results)
        assert summary["psnr"]["mean"] == pytest.approx(25.0)
        assert summary["psnr"]["count"] == 2
        assert summary["ssim"]["mean"] == pytest.approx(0.7)

    def test_handles_none_values(self):
        results = [
            {"metrics": {"psnr": 20.0, "ssim": 0.8, "lpips": None, "clip_score": None}},
            {"metrics": {"psnr": 30.0, "ssim": 0.6, "lpips": 0.2, "clip_score": None}},
        ]
        summary = compute_summary(results)
        assert summary["lpips"]["count"] == 1
        assert summary["lpips"]["mean"] == pytest.approx(0.2)
        assert summary["clip_score"]["count"] == 0
        assert summary["clip_score"]["mean"] is None

    def test_all_none(self):
        results = [
            {
                "metrics": {
                    "psnr": None,
                    "ssim": None,
                    "lpips": None,
                    "clip_score": None,
                }
            },
        ]
        summary = compute_summary(results)
        for metric in ("psnr", "ssim", "lpips", "clip_score"):
            assert summary[metric]["mean"] is None
            assert summary[metric]["std"] is None
            assert summary[metric]["count"] == 0

    def test_single_value_zero_std(self):
        results = [
            {"metrics": {"psnr": 25.0, "ssim": 0.7, "lpips": 0.2, "clip_score": None}},
        ]
        summary = compute_summary(results)
        assert summary["psnr"]["std"] == pytest.approx(0.0)


# ─── TestFormatTable ────────────────────────────────────────────────────────


class TestFormatTable:
    def _make_results_and_summary(self):
        results = [
            {
                "name": "01-test_a",
                "metrics": {
                    "psnr": 20.5,
                    "ssim": 0.75,
                    "lpips": 0.3,
                    "clip_score": None,
                },
            },
            {
                "name": "02-test_b",
                "metrics": {
                    "psnr": 25.0,
                    "ssim": 0.85,
                    "lpips": 0.2,
                    "clip_score": 72.5,
                },
            },
        ]
        summary = compute_summary(results)
        return results, summary

    def test_contains_sample_names(self):
        results, summary = self._make_results_and_summary()
        table = format_table(results, summary)
        assert "01-test_a" in table
        assert "02-test_b" in table

    def test_contains_summary_row(self):
        results, summary = self._make_results_and_summary()
        table = format_table(results, summary)
        assert "均值" in table
        assert "标准差" in table

    def test_na_for_none_values(self):
        results, summary = self._make_results_and_summary()
        table = format_table(results, summary)
        assert "N/A" in table


# ─── TestEvaluateSample ─────────────────────────────────────────────────────


class TestEvaluateSample:
    def test_psnr_ssim_computed(self, tmp_path: Path):
        orig = tmp_path / "orig.png"
        rest = tmp_path / "rest.png"
        _make_image(orig, (64, 64))
        _make_image(rest, (64, 64))

        metrics = evaluate_sample(orig, rest, None)
        assert isinstance(metrics["psnr"], float)
        assert isinstance(metrics["ssim"], float)
        assert metrics["lpips"] is None
        assert metrics["clip_score"] is None

    def test_identical_images(self, tmp_path: Path):
        img_path = tmp_path / "img.png"
        arr = np.full((32, 32, 3), 128, dtype=np.uint8)
        Image.fromarray(arr).save(img_path)

        metrics = evaluate_sample(img_path, img_path, None)
        assert metrics["ssim"] == pytest.approx(1.0)

    def test_lpips_with_mock_model(self, tmp_path: Path):
        import torch

        orig = tmp_path / "orig.png"
        rest = tmp_path / "rest.png"
        _make_image(orig, (32, 32))
        _make_image(rest, (32, 32))

        mock_model = MagicMock()
        mock_model.return_value = torch.tensor(0.42)

        metrics = evaluate_sample(orig, rest, None, lpips_model=mock_model)
        assert metrics["lpips"] == pytest.approx(0.42)
        mock_model.assert_called_once()

    def test_lpips_none_when_no_model(self, tmp_path: Path):
        orig = tmp_path / "orig.png"
        rest = tmp_path / "rest.png"
        _make_image(orig, (32, 32))
        _make_image(rest, (32, 32))

        metrics = evaluate_sample(orig, rest, None, lpips_model=None)
        assert metrics["lpips"] is None

    def test_clip_none_without_prompt(self, tmp_path: Path):
        orig = tmp_path / "orig.png"
        rest = tmp_path / "rest.png"
        _make_image(orig, (32, 32))
        _make_image(rest, (32, 32))

        mock_clip = MagicMock()
        mock_proc = MagicMock()

        metrics = evaluate_sample(
            orig, rest, None, clip_model=mock_clip, clip_processor=mock_proc
        )
        assert metrics["clip_score"] is None


# ─── TestCLIHelp ────────────────────────────────────────────────────────────


class TestCLIHelp:
    def test_help_exits_zero(self):
        with pytest.raises(SystemExit) as exc_info:
            main(["--help"])
        assert exc_info.value.code == 0


# ─── TestEndToEnd ───────────────────────────────────────────────────────────


class TestEndToEnd:
    @patch("evaluate.load_clip_model")
    @patch("evaluate.load_lpips_model")
    def test_full_run(self, mock_load_lpips, mock_load_clip, sample_dir, tmp_path):
        import torch

        # Mock LPIPS
        mock_lpips = MagicMock()
        mock_lpips.return_value = torch.tensor(0.35)
        mock_load_lpips.return_value = mock_lpips

        # Mock CLIP
        mock_clip_model = MagicMock()
        mock_clip_proc = MagicMock()

        mock_img_feat = torch.tensor([[0.6, 0.8]])
        mock_txt_feat = torch.tensor([[0.6, 0.8]])
        mock_clip_model.get_image_features.return_value = mock_img_feat
        mock_clip_model.get_text_features.return_value = mock_txt_feat
        mock_clip_proc.return_value = {
            "pixel_values": torch.randn(1, 3, 32, 32),
            "input_ids": torch.tensor([[1, 2, 3]]),
            "attention_mask": torch.tensor([[1, 1, 1]]),
        }
        mock_load_clip.return_value = (mock_clip_model, mock_clip_proc)

        output_json = tmp_path / "results.json"

        exit_code = main(
            [
                "--input-dir",
                str(sample_dir["input_dir"]),
                "--original-dir",
                str(sample_dir["originals_dir"]),
                "--output",
                str(output_json),
            ]
        )

        assert exit_code == 0
        assert output_json.exists()

        import json

        report = json.loads(output_json.read_text(encoding="utf-8"))
        assert report["metadata"]["sample_count"] == 2
        assert len(report["samples"]) == 2
        assert "summary" in report

        # 所有样本都应有 PSNR 和 SSIM
        for sample in report["samples"]:
            assert sample["metrics"]["psnr"] is not None
            assert sample["metrics"]["ssim"] is not None

    def test_nonexistent_input_dir(self, tmp_path):
        exit_code = main(
            [
                "--input-dir",
                str(tmp_path / "nonexistent"),
                "--original-dir",
                str(tmp_path),
            ]
        )
        assert exit_code == 1

    def test_no_lpips_flag(self, sample_dir, tmp_path):
        output_json = tmp_path / "results.json"
        exit_code = main(
            [
                "--input-dir",
                str(sample_dir["input_dir"]),
                "--original-dir",
                str(sample_dir["originals_dir"]),
                "--output",
                str(output_json),
                "--no-lpips",
                "--no-clip",
            ]
        )
        assert exit_code == 0

        import json

        report = json.loads(output_json.read_text(encoding="utf-8"))
        for sample in report["samples"]:
            assert sample["metrics"]["lpips"] is None
            assert sample["metrics"]["clip_score"] is None
