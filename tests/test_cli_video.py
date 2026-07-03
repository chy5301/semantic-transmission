"""semantic-tx video 子命令参数校验测试（不加载模型）。"""

from PIL import Image

from click.testing import CliRunner

from semantic_transmission.cli.main import cli
from semantic_transmission.cli.video import video
from semantic_transmission.common.video_io import write_frames


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


def test_video_reports_clean_error_on_pipeline_failure(tmp_path, monkeypatch):
    """pipeline.run 抛异常时，CLI 输出干净的「视频处理失败」而非裸 traceback。"""
    # 造一个真实小视频（3 帧），确保通过 read_frames 校验
    src = tmp_path / "in.mp4"
    write_frames(
        src,
        [Image.new("RGB", (32, 24), color=(i * 80, 0, 0)) for i in range(3)],
        fps=8.0,
    )

    # monkeypatch create_receiver → 哑对象（避免加载 GPU 模型）
    import semantic_transmission.cli.video as video_mod
    from semantic_transmission.receiver.base import BaseReceiver

    class _DummyReceiver(BaseReceiver):
        def process(self, edge_image, prompt_text, seed=None):
            raise RuntimeError("不应被调用")

    monkeypatch.setattr(video_mod, "create_receiver", lambda *a, **k: _DummyReceiver())

    # monkeypatch VideoPipeline.run → 直接抛异常
    from semantic_transmission.pipeline import video_pipeline as vp_mod

    monkeypatch.setattr(
        vp_mod.VideoPipeline,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("模拟管道崩溃")),
    )

    result = CliRunner().invoke(video, ["--input", str(src), "--prompt", "test"])

    assert result.exit_code != 0
    assert "视频处理失败" in result.output


def test_video_rejects_invalid_backend(tmp_path):
    src = tmp_path / "in.mp4"
    src.write_bytes(b"x")
    result = CliRunner().invoke(
        video, ["--input", str(src), "--prompt", "a", "--backend", "nope"]
    )
    assert result.exit_code != 0
    assert "nope" in result.output or "Invalid" in result.output


def test_video_passes_backend_to_factory(tmp_path, monkeypatch):
    src = tmp_path / "in.mp4"
    write_frames(
        src, [Image.new("RGB", (32, 24), color=(0, 0, 0)) for _ in range(2)], fps=8.0
    )

    import semantic_transmission.cli.video as video_mod
    from semantic_transmission.receiver.base import BaseReceiver

    captured = {}

    class _Dummy(BaseReceiver):
        def process(self, edge_image, prompt_text, seed=None):
            return Image.new("RGB", (16, 16))

    def fake_create(*args, backend="diffusers", **kwargs):
        captured["backend"] = backend
        return _Dummy()

    monkeypatch.setattr(video_mod, "create_receiver", fake_create)

    out = tmp_path / "out" / "out.mp4"
    result = CliRunner().invoke(
        video,
        [
            "--input",
            str(src),
            "--output",
            str(out),
            "--prompt",
            "a",
            "--backend",
            "klein",
        ],
    )
    assert result.exit_code == 0, result.output
    assert captured["backend"] == "klein"
