"""video-sender / video-receiver CLI 参数校验测试。"""

from click.testing import CliRunner

from semantic_transmission.cli.video_receiver import video_receiver
from semantic_transmission.cli.video_sender import video_sender


def test_video_sender_requires_prompt_or_auto(tmp_path):
    src = tmp_path / "in.mp4"
    src.write_bytes(b"fake")  # 仅触发 exists 校验，prompt 校验先失败
    runner = CliRunner()
    result = runner.invoke(
        video_sender,
        ["--input", str(src), "--relay-host", "127.0.0.1"],
    )
    assert result.exit_code != 0
    assert "必须指定 --prompt 或 --auto-prompt" in result.output


def test_video_sender_prompt_and_auto_mutually_exclusive(tmp_path):
    src = tmp_path / "in.mp4"
    src.write_bytes(b"fake")
    runner = CliRunner()
    result = runner.invoke(
        video_sender,
        [
            "--input",
            str(src),
            "--relay-host",
            "127.0.0.1",
            "--prompt",
            "x",
            "--auto-prompt",
        ],
    )
    assert result.exit_code != 0
    assert "不能同时使用" in result.output


def test_video_sender_missing_input_errors():
    runner = CliRunner()
    result = runner.invoke(video_sender, ["--relay-host", "127.0.0.1", "--prompt", "x"])
    assert result.exit_code != 0


def test_video_receiver_help_lists_options():
    runner = CliRunner()
    result = runner.invoke(video_receiver, ["--help"])
    assert result.exit_code == 0
    assert "--relay-host" in result.output
    assert "--output" in result.output
