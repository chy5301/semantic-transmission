from unittest.mock import MagicMock, patch
from semantic_transmission.gui.video_relay_panel import run_video_sender


def test_sender_empty_path_yields_error():
    gen = run_video_sender(
        None, "127.0.0.1", 9000, "manual", "x", 12, None, None, MagicMock()
    )
    progress, rows, log = next(gen)
    assert "请先上传" in log


def test_sender_runs_and_reports_stats():
    fake_stats = MagicMock()
    fake_stats.to_dict.return_value = {
        "total_frames": 3,
        "keyframe_count": 1,
        "generated_count": 2,
        "keyframe_bytes": 300,
        "generated_bytes": 60,
    }
    with (
        patch("semantic_transmission.gui.video_relay_panel.VideoRelaySender") as MS,
        patch("semantic_transmission.gui.video_relay_panel.LocalCannyExtractor"),
    ):
        MS.return_value.run.return_value = fake_stats
        gen = run_video_sender(
            "in.mp4", "127.0.0.1", 9000, "manual", "x", 12, None, None, MagicMock()
        )
        outputs = list(gen)
    progress, rows, log = outputs[-1]
    assert any(r[0] == "总帧数" for r in rows)
    assert any(r[0] == "关键帧∶生成帧倍率" for r in rows)
    assert "完成" in log
