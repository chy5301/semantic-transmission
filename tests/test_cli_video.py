"""semantic-tx video 子命令参数校验测试（不加载模型）。"""

from click.testing import CliRunner

from semantic_transmission.cli.main import cli
from semantic_transmission.cli.video import video


def test_video_registered():
    assert "video" in cli.commands


def test_video_requires_a_prompt(tmp_path):
    fake = tmp_path / "in.mp4"
    fake.write_bytes(b"not really a video")
    result = CliRunner().invoke(video, ["--input", str(fake)])
    assert result.exit_code != 0
    assert "必须指定" in result.output


def test_video_prompt_and_auto_conflict(tmp_path):
    fake = tmp_path / "in.mp4"
    fake.write_bytes(b"not really a video")
    result = CliRunner().invoke(
        video, ["--input", str(fake), "--prompt", "a", "--auto-prompt"]
    )
    assert result.exit_code != 0
    assert "不能同时" in result.output
