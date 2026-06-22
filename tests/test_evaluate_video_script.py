"""视频评估脚本测试。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from evaluate_video import main  # noqa: E402

from semantic_transmission.common.video_io import write_frames  # noqa: E402


def _make_video(path: Path, n: int, base: int):
    write_frames(
        path,
        [
            Image.fromarray(np.full((32, 32, 3), base + i * 5, np.uint8))
            for i in range(n)
        ],
        fps=8.0,
    )


def test_help_exits_zero():
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0


def test_nonexistent_original_returns_1(tmp_path):
    rest = tmp_path / "rest.mp4"
    _make_video(rest, 2, 100)
    code = main(["--original", str(tmp_path / "nope.mp4"), "--restored", str(rest)])
    assert code == 1


def test_full_run_no_lpips_no_clip(tmp_path):
    orig = tmp_path / "orig.mp4"
    rest = tmp_path / "rest.mp4"
    _make_video(orig, 3, 100)
    _make_video(rest, 3, 110)
    out = tmp_path / "result.json"
    code = main(
        [
            "--original",
            str(orig),
            "--restored",
            str(rest),
            "--output",
            str(out),
            "--no-lpips",
            "--no-clip",
        ]
    )
    assert code == 0
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["frame_count"] == 3
    assert len(report["frames"]) == 3
    assert report["summary"]["psnr"]["count"] == 3
    for f in report["frames"]:
        assert f["metrics"]["lpips"] is None
        assert f["metrics"]["clip_score"] is None


def test_frame_count_mismatch_returns_1(tmp_path):
    orig = tmp_path / "orig.mp4"
    rest = tmp_path / "rest.mp4"
    _make_video(orig, 2, 100)
    _make_video(rest, 3, 110)
    out = tmp_path / "result.json"
    code = main(
        [
            "--original",
            str(orig),
            "--restored",
            str(rest),
            "--output",
            str(out),
            "--no-lpips",
            "--no-clip",
        ]
    )
    assert code == 1


def test_nonexistent_restored_returns_1(tmp_path):
    orig = tmp_path / "orig.mp4"
    _make_video(orig, 2, 100)
    code = main(["--original", str(orig), "--restored", str(tmp_path / "nope.mp4")])
    assert code == 1


def test_corrupt_restored_returns_1(tmp_path):
    """还原视频文件损坏（非视频内容）：read_frames 抛 ValueError，脚本返回 1。"""
    orig = tmp_path / "orig.mp4"
    _make_video(orig, 2, 100)
    rest = tmp_path / "rest.mp4"
    rest.write_bytes(b"not a video")
    code = main(
        [
            "--original",
            str(orig),
            "--restored",
            str(rest),
            "--no-lpips",
            "--no-clip",
        ]
    )
    assert code == 1


def test_prompts_happy_path(tmp_path):
    orig = tmp_path / "orig.mp4"
    rest = tmp_path / "rest.mp4"
    _make_video(orig, 3, 100)
    _make_video(rest, 3, 110)
    prompts_file = tmp_path / "receiver_summary.json"
    prompts_file.write_text(
        json.dumps(
            {
                "frames": [
                    {"index": 0, "prompt": "a"},
                    {"index": 1, "prompt": "b"},
                    {"index": 2, "prompt": "c"},
                ]
            }
        ),
        encoding="utf-8",
    )
    out = tmp_path / "result.json"
    code = main(
        [
            "--original",
            str(orig),
            "--restored",
            str(rest),
            "--prompts",
            str(prompts_file),
            "--output",
            str(out),
            "--no-lpips",
            "--no-clip",
        ]
    )
    assert code == 0
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["frame_count"] == 3
