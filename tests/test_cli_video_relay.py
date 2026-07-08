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
    assert "必须指定 --prompt / --auto-prompt / --prompts-json 之一" in result.output


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
    assert "只能指定一个" in result.output


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


def test_video_sender_prompts_json_conflicts_with_prompt(tmp_path):
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
            "--prompts-json",
            str(tmp_path / "p.json"),
        ],
    )
    assert result.exit_code != 0
    assert "只能指定" in result.output


def test_video_sender_help_lists_temporal_options():
    runner = CliRunner()
    result = runner.invoke(video_sender, ["--help"])
    assert result.exit_code == 0
    assert "--keyframe-interval" in result.output
    assert "--prompts-json" in result.output


def test_video_receiver_help_lists_backend_and_reference_mode():
    runner = CliRunner()
    result = runner.invoke(video_receiver, ["--help"])
    assert result.exit_code == 0
    assert "--backend" in result.output
    assert "--reference-mode" in result.output
