"""CLI 入口点和子命令测试。

使用 click.testing.CliRunner 测试各子命令的 --help 输出和参数解析。
"""

from click.testing import CliRunner

from semantic_transmission.cli.main import cli


class TestCLIEntryPoint:
    """测试 CLI 主入口。"""

    def test_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "语义传输系统 CLI 工具" in result.output

    def test_version(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "semantic-tx" in result.output
        assert "0.1.0" in result.output

    def test_no_args_shows_usage(self):
        runner = CliRunner()
        result = runner.invoke(cli, [])
        assert "Usage:" in result.output


class TestSenderCommand:
    """测试 sender 子命令。"""

    def test_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["sender", "--help"])
        assert result.exit_code == 0
        assert "--image" in result.output
        assert "--prompt" in result.output
        assert "--auto-prompt" in result.output
        assert "--relay-host" in result.output

    def test_missing_required_args(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["sender"])
        assert result.exit_code != 0


class TestReceiverCommand:
    """测试 receiver 子命令。"""

    def test_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["receiver", "--help"])
        assert result.exit_code == 0
        assert "--relay-host" in result.output
        assert "--relay-port" in result.output
        assert "--continuous" in result.output
        assert "--output-dir" in result.output
        # M-11: 已移除 --backend / --comfyui-host / --comfyui-port
        assert "--backend" not in result.output
        assert "--comfyui-host" not in result.output


class TestDemoCommand:
    """测试 demo 子命令。"""

    def test_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["demo", "--help"])
        assert result.exit_code == 0
        assert "--image" in result.output
        assert "--prompt" in result.output
        assert "--auto-prompt" in result.output
        assert "--threshold1" in result.output
        assert "--output-dir" in result.output
        assert "--seed" in result.output
        # M-11: 已移除 --backend / --receiver-host / --receiver-port
        assert "--backend" not in result.output
        assert "--receiver-host" not in result.output

    def test_missing_required_args(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["demo"])
        assert result.exit_code != 0


class TestCheckCommand:
    """测试 check 子命令组（vlm / diffusers / relay）。"""

    def test_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["check", "--help"])
        assert result.exit_code == 0
        # M-11: 三个新子命令
        assert "vlm" in result.output
        assert "diffusers" in result.output
        assert "relay" in result.output
        # M-11: 旧子命令已移除
        assert "connection" not in result.output
        assert "workflows" not in result.output

    def test_vlm_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["check", "vlm", "--help"])
        assert result.exit_code == 0
        assert "--model-path" in result.output

    def test_diffusers_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["check", "diffusers", "--help"])
        assert result.exit_code == 0

    def test_relay_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["check", "relay", "--help"])
        assert result.exit_code == 0
        assert "--host" in result.output
        assert "--port" in result.output
        assert "--timeout" in result.output

    def test_relay_requires_host_and_port(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["check", "relay"])
        assert result.exit_code != 0

    def test_vlm_invokes_check_function(self, monkeypatch):
        import semantic_transmission.cli.check as check_module

        called = {}

        def fake_check(path):
            called["path"] = path
            return True, "OK"

        monkeypatch.setattr(check_module, "check_vlm_model", fake_check)
        runner = CliRunner()
        result = runner.invoke(cli, ["check", "vlm", "--model-path", "/tmp/vlm"])
        assert result.exit_code == 0
        assert called["path"] == "/tmp/vlm"
        assert "OK" in result.output

    def test_diffusers_invokes_check_function(self, monkeypatch):
        import semantic_transmission.cli.check as check_module

        called = {}

        def fake_check(config):
            called["config"] = config
            return True, "Diffusers OK"

        monkeypatch.setattr(check_module, "check_diffusers_receiver_model", fake_check)
        runner = CliRunner()
        result = runner.invoke(cli, ["check", "diffusers"])
        assert result.exit_code == 0
        assert "Diffusers OK" in result.output
        assert called["config"] is not None

    def test_relay_unreachable_exits_nonzero(self):
        runner = CliRunner()
        # 使用保留端口 1（大概率无服务），快速超时
        result = runner.invoke(
            cli,
            [
                "check",
                "relay",
                "--host",
                "127.0.0.1",
                "--port",
                "1",
                "--timeout",
                "0.5",
            ],
        )
        assert result.exit_code != 0
        assert "连接失败" in result.output


class TestDownloadCommand:
    """测试 download 子命令。"""

    def test_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["download", "--help"])
        assert result.exit_code == 0
        assert "--comfyui-dir" in result.output
        assert "--proxy" in result.output
        assert "--no-mirror" in result.output
        assert "--cache-dir" in result.output
        assert "--dry-run" in result.output


class TestCommandDiscovery:
    """测试所有子命令都已注册。"""

    def test_all_commands_registered(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        for cmd in ["sender", "receiver", "demo", "check", "download"]:
            assert cmd in result.output, f"子命令 {cmd} 未在 --help 中列出"
