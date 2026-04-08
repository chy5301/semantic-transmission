"""GUI 批量端到端 Tab 纯函数单元测试。

覆盖 M-15 引入的评估辅助函数：compute_sample_metrics / aggregate_metrics。
不覆盖 GUI 绑定或 render 逻辑（由 create_app() 烟测间接验证）。
"""

from PIL import Image

from semantic_transmission.gui.batch_panel import (
    aggregate_metrics,
    compute_sample_metrics,
)
from semantic_transmission.pipeline.batch_processor import SampleResult


class TestComputeSampleMetrics:
    def test_identical_images_high_psnr(self):
        img = Image.new("RGB", (32, 32), color=(123, 200, 80))
        metrics = compute_sample_metrics(img, img)
        # 完全相同：PSNR → inf, SSIM → 1.0
        assert metrics["ssim"] == 1.0
        # inf 不直接比较，改为检查是否大于阈值
        assert metrics["psnr"] > 100 or metrics["psnr"] == float("inf")
        assert "lpips" not in metrics

    def test_different_images_has_psnr_ssim(self):
        a = Image.new("RGB", (32, 32), color=(255, 0, 0))
        b = Image.new("RGB", (32, 32), color=(0, 255, 0))
        metrics = compute_sample_metrics(a, b)
        assert "psnr" in metrics
        assert "ssim" in metrics
        assert 0 <= metrics["ssim"] <= 1
        assert "lpips" not in metrics

    def test_accepts_file_path(self, tmp_path):
        p1 = tmp_path / "a.png"
        p2 = tmp_path / "b.png"
        Image.new("RGB", (16, 16), color=(50, 50, 50)).save(p1)
        Image.new("RGB", (16, 16), color=(100, 100, 100)).save(p2)
        metrics = compute_sample_metrics(p1, p2)
        assert "psnr" in metrics
        assert "ssim" in metrics

    def test_lpips_included_when_model_passed(self):
        """传入 lpips_model=mock 时应产出 lpips 键。"""
        from unittest.mock import patch

        img = Image.new("RGB", (16, 16), color=(100, 100, 100))
        fake_model = object()

        with patch(
            "semantic_transmission.evaluation.compute_lpips", return_value=0.123
        ) as mock_lpips:
            metrics = compute_sample_metrics(img, img, lpips_model=fake_model)

        mock_lpips.assert_called_once()
        assert metrics["lpips"] == 0.123


class TestAggregateMetrics:
    def test_empty_samples(self):
        assert aggregate_metrics([]) == []

    def test_samples_without_metrics(self):
        samples = [
            SampleResult(name="a", status="success"),
            SampleResult(name="b", status="success"),
        ]
        assert aggregate_metrics(samples) == []

    def test_aggregates_psnr_ssim(self):
        samples = [
            SampleResult(
                name="a",
                status="success",
                metrics={"psnr": 30.0, "ssim": 0.9},
            ),
            SampleResult(
                name="b",
                status="success",
                metrics={"psnr": 20.0, "ssim": 0.7},
            ),
        ]
        rows = aggregate_metrics(samples)
        # 应有 PSNR 和 SSIM 两行（LPIPS 缺失不出现）
        assert len(rows) == 2
        psnr_row = next(r for r in rows if r[0] == "PSNR")
        ssim_row = next(r for r in rows if r[0] == "SSIM")
        assert "25.00 dB" in psnr_row[1]
        assert psnr_row[2] == "2"
        assert "0.8000" in ssim_row[1]

    def test_includes_lpips_when_present(self):
        samples = [
            SampleResult(
                name="a",
                status="success",
                metrics={"psnr": 30.0, "ssim": 0.9, "lpips": 0.1},
            ),
            SampleResult(
                name="b",
                status="success",
                metrics={"psnr": 20.0, "ssim": 0.7, "lpips": 0.3},
            ),
        ]
        rows = aggregate_metrics(samples)
        assert len(rows) == 3
        lpips_row = next(r for r in rows if r[0] == "LPIPS")
        assert "0.2000" in lpips_row[1]

    def test_skips_failed_samples(self):
        samples = [
            SampleResult(
                name="a",
                status="success",
                metrics={"psnr": 30.0, "ssim": 0.9},
            ),
            SampleResult(
                name="b",
                status="failed",
                error="oops",
                metrics={"psnr": 99.0, "ssim": 1.0},  # 应忽略
            ),
        ]
        rows = aggregate_metrics(samples)
        psnr_row = next(r for r in rows if r[0] == "PSNR")
        assert "30.00 dB" in psnr_row[1]
        assert psnr_row[2] == "1"


class TestSampleResultMetricsSerialization:
    def test_to_dict_includes_metrics(self):
        s = SampleResult(
            name="x",
            status="success",
            metrics={"psnr": 30.5, "ssim": 0.95},
        )
        d = s.to_dict()
        assert d["metrics"] == {"psnr": 30.5, "ssim": 0.95}

    def test_default_metrics_empty_dict(self):
        s = SampleResult(name="y", status="success")
        assert s.metrics == {}
        assert s.to_dict()["metrics"] == {}
