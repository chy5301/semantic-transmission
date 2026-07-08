"""video-sender / video-receiver CLI 参数校验测试。"""

import json

import click
from click.testing import CliRunner

from semantic_transmission.cli.video_receiver import video_receiver
from semantic_transmission.cli.video_sender import video_sender


def _temporal_prompts_payload(total: int, keyframe_interval: int) -> dict:
    """构造与 _save_temporal_artifacts 产物结构一致的 prompts.json payload。"""
    keyframe_indices = [i for i in range(total) if i % keyframe_interval == 0]
    frames = []
    for i in range(total):
        if i in keyframe_indices:
            frames.append({"index": i, "passthrough": True})
        else:
            frames.append({"index": i, "prompt": f"p{i}", "char_count": 2})
    return {
        "total_frames": total,
        "generated_frames": total - len(keyframe_indices),
        "keyframe_indices": keyframe_indices,
        "fps": 8.0,
        "frames": frames,
    }


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
    prompts_json = tmp_path / "p.json"
    prompts_json.write_text("{}", encoding="utf-8")
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
            str(prompts_json),
        ],
    )
    assert result.exit_code != 0
    assert "只能指定" in result.output


def test_video_sender_prompts_json_missing_file_friendly_error(tmp_path):
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
            "--prompts-json",
            str(tmp_path / "missing.json"),
        ],
    )
    assert result.exit_code == 2
    assert not isinstance(result.exception, FileNotFoundError)
    assert "does not exist" in result.output


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


def test_video_receiver_backend_defaults_to_klein():
    """两端默认均时序（klein 主线定位）：video-receiver 默认 --backend klein。"""
    backend_param = next(p for p in video_receiver.params if p.name == "backend")
    assert backend_param.default == "klein"


def test_video_sender_prompts_json_keyframe_interval_mismatch(tmp_path):
    """时序 prompts.json 的关键帧集与重放 --keyframe-interval 不一致时，须
    fail-fast 报错，而非让原关键帧下标被误判为生成帧、静默送空 prompt。
    """
    src = tmp_path / "in.mp4"
    src.write_bytes(b"fake")
    prompts_json = tmp_path / "p.json"
    # 生成时 interval=12 → 关键帧 {0,12}；重放时误用 interval=6 → 期望关键帧
    # {0,6,12,18} 与 payload 的 {0,12} 不一致。
    prompts_json.write_text(
        json.dumps(_temporal_prompts_payload(total=24, keyframe_interval=12)),
        encoding="utf-8",
    )
    runner = CliRunner()
    result = runner.invoke(
        video_sender,
        [
            "--input",
            str(src),
            "--relay-host",
            "127.0.0.1",
            "--prompts-json",
            str(prompts_json),
            "--keyframe-interval",
            "6",
        ],
    )
    assert result.exit_code != 0
    assert "不匹配" in result.output


def test_video_sender_prompts_json_keyframe_interval_match_passes_validation(
    tmp_path,
):
    """interval 与生成时一致时，关键帧集校验应通过（不报"不匹配"），后续失败
    （无效视频/无监听端口）与本校验无关。"""
    src = tmp_path / "in.mp4"
    src.write_bytes(b"fake")
    prompts_json = tmp_path / "p.json"
    prompts_json.write_text(
        json.dumps(_temporal_prompts_payload(total=24, keyframe_interval=12)),
        encoding="utf-8",
    )
    runner = CliRunner()
    result = runner.invoke(
        video_sender,
        [
            "--input",
            str(src),
            "--relay-host",
            "127.0.0.1",
            "--relay-port",
            "1",
            "--prompts-json",
            str(prompts_json),
            "--keyframe-interval",
            "12",
        ],
    )
    assert result.exit_code != 0  # 后续解码/连接失败，非本次校验目标
    assert "不匹配" not in result.output
    assert not isinstance(result.exception, click.UsageError)
