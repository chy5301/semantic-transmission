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
        assert "--comfyui-host" in result.output
        assert "--continuous" in result.output
        assert "--output-dir" in result.output


class TestDemoCommand:
    """测试 demo 子命令。"""

    def test_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["demo", "--help"])
        assert result.exit_code == 0
        assert "--image" in result.output
        assert "--prompt" in result.output
        assert "--auto-prompt" in result.output
        assert "--sender-host" in result.output
        assert "--receiver-host" in result.output
        assert "--output-dir" in result.output
        assert "--seed" in result.output

    def test_missing_required_args(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["demo"])
        assert result.exit_code != 0


class TestCheckCommand:
    """测试 check 子命令组。"""

    def test_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["check", "--help"])
        assert result.exit_code == 0
        assert "connection" in result.output
        assert "workflows" in result.output

    def test_connection_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["check", "connection", "--help"])
        assert result.exit_code == 0
        assert "--host" in result.output
        assert "--port" in result.output

    def test_workflows_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["check", "workflows", "--help"])
        assert result.exit_code == 0
        assert "--host" in result.output
        assert "--sender-only" in result.output
        assert "--receiver-only" in result.output
        assert "--edge-image" in result.output


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
