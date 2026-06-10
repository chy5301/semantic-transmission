"""semantic-tx sender 子命令测试（R-08 合并后的单图 + 批量统一入口）。

覆盖：
- --help 文本含新选项（--image / --input-dir / --recursive / --skip-errors）
- 缺少互斥参数报错
- batch-sender 子命令不存在
- 单图模式 fail-fast / 批量模式 continue-on-error 输出结构
- CLI 默认值从 ProjectConfig 读取
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
from click.testing import CliRunner
from PIL import Image

from semantic_transmission.cli import sender as sender_module
from semantic_transmission.cli.main import cli


def _make_test_image(path: Path, size: tuple[int, int] = (64, 64)) -> None:
    """生成一张测试用纯色图。"""
    arr = np.ones((size[1], size[0], 3), dtype=np.uint8) * 128
    Image.fromarray(arr).save(path)


class TestSenderHelp:
    """--help 文本覆盖新选项。"""

    def test_help_lists_new_options(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["sender", "--help"])
        assert result.exit_code == 0
        # 新合并后必备选项
        assert "--image" in result.output
        assert "--input-dir" in result.output
        assert "--prompt" in result.output
        assert "--auto-prompt" in result.output
        assert "--recursive" in result.output
        assert "--skip-errors" in result.output
        assert "--relay-host" in result.output
        assert "--threshold1" in result.output
        assert "--threshold2" in result.output


class TestBatchSenderRemoved:
    """旧 batch-sender 子命令必须不存在。"""

    def test_batch_sender_not_in_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "batch-sender" not in result.output
        assert "batch_sender" not in result.output

    def test_batch_sender_invocation_fails(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["batch-sender", "--help"])
        # click 对未知子命令返回非零退出码
        assert result.exit_code != 0

    def test_module_no_longer_importable(self):
        """cli.batch_sender 模块已删除。"""
        import importlib

        import pytest

        with pytest.raises(ImportError):
            importlib.import_module("semantic_transmission.cli.batch_sender")


class TestMutexValidation:
    """--image / --input-dir 互斥校验 + --prompt / --auto-prompt 互斥。"""

    def test_missing_both_image_and_input_dir(self, tmp_path):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["sender", "--prompt", "test", "--relay-host", "127.0.0.1"],
        )
        assert result.exit_code != 0
        assert "--image" in result.output and "--input-dir" in result.output

    def test_both_image_and_input_dir(self, tmp_path):
        img = tmp_path / "x.png"
        _make_test_image(img)
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "sender",
                "--image",
                str(img),
                "--input-dir",
                str(tmp_path),
                "--prompt",
                "test",
                "--relay-host",
                "127.0.0.1",
            ],
        )
        assert result.exit_code != 0
        assert "不能同时使用" in result.output

    def test_missing_prompt_and_auto_prompt(self, tmp_path):
        img = tmp_path / "x.png"
        _make_test_image(img)
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["sender", "--image", str(img), "--relay-host", "127.0.0.1"],
        )
        assert result.exit_code != 0
        assert "--prompt" in result.output and "--auto-prompt" in result.output

    def test_both_prompt_and_auto_prompt(self, tmp_path):
        img = tmp_path / "x.png"
        _make_test_image(img)
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "sender",
                "--image",
                str(img),
                "--prompt",
                "manual",
                "--auto-prompt",
                "--relay-host",
                "127.0.0.1",
            ],
        )
        assert result.exit_code != 0
        assert "不能同时使用" in result.output

    def test_batch_mode_requires_output_dir(self, tmp_path):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "sender",
                "--input-dir",
                str(tmp_path),
                "--prompt",
                "test",
                "--relay-host",
                "127.0.0.1",
            ],
        )
        assert result.exit_code != 0
        assert "--output-dir" in result.output


class TestSingleImageMode:
    """单图模式扁平输出 + 即使 relay 失败也写本地文件。"""

    def test_single_image_writes_flat_output(self, tmp_path, monkeypatch):
        img = tmp_path / "myimg.png"
        _make_test_image(img)
        output_dir = tmp_path / "out"

        # 让 relay 直接抛错（模拟连接失败），但本地文件仍应落盘
        def _fail_relay(*args, **kwargs):
            raise OSError("simulated relay failure")

        monkeypatch.setattr(
            sender_module, "SocketRelaySender", lambda *a, **k: _fail_relay()
        )

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "sender",
                "--image",
                str(img),
                "--prompt",
                "a test prompt",
                "--relay-host",
                "127.0.0.1",
                "--output-dir",
                str(output_dir),
            ],
        )
        # relay 失败但 CLI 不应 exit 非零（fail-fast 仅限处理本身）
        assert result.exit_code == 0, result.output

        # 扁平输出
        assert (output_dir / "myimg_edge.png").exists()
        assert (output_dir / "myimg_prompt.txt").exists()
        assert (output_dir / "myimg_prompt.txt").read_text(
            encoding="utf-8"
        ) == "a test prompt"


class TestBatchMode:
    """批量模式 NN-name/ 子目录 + batch_summary.json。"""

    def test_batch_writes_subdirs_and_summary(self, tmp_path, monkeypatch):
        input_dir = tmp_path / "imgs"
        input_dir.mkdir()
        for name in ["a", "b"]:
            _make_test_image(input_dir / f"{name}.png")

        output_dir = tmp_path / "out"

        # mock relay send：上下文管理器风格 + connect/send/close 都不抛
        fake_relay = MagicMock()
        fake_relay.connect = MagicMock()
        fake_relay.send = MagicMock()
        fake_relay.close = MagicMock()
        monkeypatch.setattr(
            sender_module, "SocketRelaySender", MagicMock(return_value=fake_relay)
        )

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "sender",
                "--input-dir",
                str(input_dir),
                "--output-dir",
                str(output_dir),
                "--prompt",
                "batch prompt",
                "--relay-host",
                "127.0.0.1",
            ],
        )
        assert result.exit_code == 0, result.output

        # NN-name 子目录
        subdirs = sorted([p.name for p in output_dir.iterdir() if p.is_dir()])
        assert subdirs == ["01-a", "02-b"]
        for sub in subdirs:
            assert (output_dir / sub / "edge.png").exists()
            assert (output_dir / sub / "prompt.txt").exists()
            assert (output_dir / sub / "metadata.json").exists()

        # 汇总
        assert (output_dir / "batch_summary.json").exists()


class TestProjectConfigDefaults:
    """CLI 共享参数默认值从 ProjectConfig 读取（threshold1 / threshold2 等）。"""

    def test_canny_thresholds_default_to_project_config(self, tmp_path, monkeypatch):
        img = tmp_path / "x.png"
        _make_test_image(img)
        output_dir = tmp_path / "out"

        # patch load_config 让默认值变成可识别的特殊值
        from semantic_transmission.common.config import ProjectConfig

        custom = ProjectConfig(canny_low_threshold=33, canny_high_threshold=233)
        monkeypatch.setattr(sender_module, "load_config", lambda: custom)

        # 拦截 LocalCannyExtractor 构造，确认 thresholds 被透传
        seen: dict = {}
        real_extractor = sender_module.LocalCannyExtractor

        def _spy(threshold1, threshold2):
            seen["t1"] = threshold1
            seen["t2"] = threshold2
            return real_extractor(threshold1=threshold1, threshold2=threshold2)

        monkeypatch.setattr(sender_module, "LocalCannyExtractor", _spy)

        # relay 失败不影响 ProjectConfig 默认值验证
        def _fail(*a, **k):
            raise OSError("no relay")

        monkeypatch.setattr(sender_module, "SocketRelaySender", lambda *a, **k: _fail())

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "sender",
                "--image",
                str(img),
                "--prompt",
                "x",
                "--relay-host",
                "127.0.0.1",
                "--output-dir",
                str(output_dir),
            ],
        )
        assert result.exit_code == 0, result.output
        assert seen["t1"] == 33
        assert seen["t2"] == 233

    def test_cli_threshold_overrides_project_config(self, tmp_path, monkeypatch):
        img = tmp_path / "x.png"
        _make_test_image(img)
        output_dir = tmp_path / "out"

        from semantic_transmission.common.config import ProjectConfig

        custom = ProjectConfig(canny_low_threshold=33, canny_high_threshold=233)
        monkeypatch.setattr(sender_module, "load_config", lambda: custom)

        seen: dict = {}
        real_extractor = sender_module.LocalCannyExtractor

        def _spy(threshold1, threshold2):
            seen["t1"] = threshold1
            seen["t2"] = threshold2
            return real_extractor(threshold1=threshold1, threshold2=threshold2)

        monkeypatch.setattr(sender_module, "LocalCannyExtractor", _spy)

        def _fail(*a, **k):
            raise OSError("no relay")

        monkeypatch.setattr(sender_module, "SocketRelaySender", lambda *a, **k: _fail())

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "sender",
                "--image",
                str(img),
                "--prompt",
                "x",
                "--relay-host",
                "127.0.0.1",
                "--output-dir",
                str(output_dir),
                "--threshold1",
                "77",
                "--threshold2",
                "177",
            ],
        )
        assert result.exit_code == 0, result.output
        # CLI 显式值覆盖 ProjectConfig 默认
        assert seen["t1"] == 77
        assert seen["t2"] == 177


class TestProcessOne:
    """核心函数 process_one() 不带 IO/网络的纯逻辑测试。"""

    def test_process_one_manual_prompt(self, tmp_path):
        img = tmp_path / "x.png"
        _make_test_image(img, size=(32, 32))
        extractor = sender_module.LocalCannyExtractor(threshold1=100, threshold2=200)
        result = sender_module.process_one(
            image_path=img,
            extractor=extractor,
            vlm_sender=None,
            prompt="hello",
            seed=42,
        )
        assert result.image_name == "x"
        assert result.prompt_text == "hello"
        assert result.edge_image.size == (32, 32)
        assert result.packet.metadata["seed"] == 42
        assert result.packet.metadata["image_name"] == "x"
        assert result.vlm_elapsed == 0.0
        assert result.original_bytes > 0

    def test_process_one_with_vlm(self, tmp_path):
        img = tmp_path / "y.png"
        _make_test_image(img)
        extractor = sender_module.LocalCannyExtractor(threshold1=100, threshold2=200)

        fake_vlm = MagicMock()
        fake_output = MagicMock()
        fake_output.text = "vlm description"
        fake_vlm.describe.return_value = fake_output

        result = sender_module.process_one(
            image_path=img,
            extractor=extractor,
            vlm_sender=fake_vlm,
            prompt=None,
            seed=None,
        )
        assert result.prompt_text == "vlm description"
        fake_vlm.describe.assert_called_once()
        # 没传 seed 时 metadata 不应含 seed
        assert "seed" not in result.packet.metadata
