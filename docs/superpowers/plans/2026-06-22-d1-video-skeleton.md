# D1 保底骨架 video→video 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 跑通单机离线 `video → 逐帧语义还原 → video` 保底骨架，并为 D2 relay / D5 插帧 / D6 超分预留接口。

**Architecture:** 新增 `common/video_io.py`（imageio[ffmpeg] 帧序列读写）与 `pipeline/video_pipeline.py`（`VideoPipeline` 编排：解码→逐帧 Canny+构造 FrameInput→复用 `receiver.process_batch`→失败帧填充→序列级 `frame_postprocess` 空钩子→编码），薄 CLI 子命令 `semantic-tx video` 装配。VLM 不进 pipeline，由 CLI 通过 `prompt_fn` 注入，保证 pipeline 可在无 GPU 下单测。

**Tech Stack:** Python 3.10+ / uv / click / imageio[ffmpeg] / OpenCV(Canny) / Diffusers 接收端（复用）/ pytest

**设计依据：** [D1 骨架设计 spec](../specs/2026-06-22-d1-video-skeleton-design.md)

## Global Constraints

- 所有 Python 操作走 `uv`：`uv run pytest`、`uv run ruff check .`、`uv add ...`，禁止直接 `python`/`pip`/`pytest`
- 推送前 `uv run ruff check .` 与 `uv run ruff format --check .` 必须通过（CI 检查范围是整个 `.`）
- 单测不依赖 GPU/CUDA（CI 无 GPU）：用 fake receiver + 合成微视频
- 工作分支 `feature/video-stream-pipeline`（已创建）；feature branch → PR，禁止直接改 main
- Commit 遵循 Angular Convention，subject/body 用中文，不含工具生成标记与 Co-Authored-By
- 测试视频尺寸用**偶数宽高**（libx264 yuv420p 要求宽高可被 2 整除）

---

### Task 1: 视频 I/O 模块 `common/video_io.py`

**Files:**
- Create: `src/semantic_transmission/common/video_io.py`
- Test: `tests/test_video_io.py`
- Modify: `pyproject.toml`（经 `uv add` 自动）

**Interfaces:**
- Consumes: 无（最底层）
- Produces:
  - `VideoMeta(fps: float, width: int, height: int, frame_count: int)` 数据类
  - `read_frames(path: str | Path) -> tuple[list[NDArray[np.uint8]], VideoMeta]`
  - `write_frames(path: str | Path, frames: list[Image.Image], fps: float) -> None`

- [ ] **Step 1: 添加 imageio[ffmpeg] 依赖**

Run: `uv add "imageio[ffmpeg]"`
Expected: `pyproject.toml` 的 `[project.dependencies]` 出现 `imageio[ffmpeg]`，`uv.lock` 同步，安装含捆绑的 `imageio-ffmpeg` 二进制。

- [ ] **Step 2: 写失败测试 `tests/test_video_io.py`**

```python
"""video_io 帧序列读写往返测试。"""

import numpy as np
import pytest
from PIL import Image

from semantic_transmission.common.video_io import read_frames, write_frames


def test_write_then_read_roundtrip(tmp_path):
    """写 3 帧再读回，帧数与尺寸一致。"""
    frames = [Image.new("RGB", (64, 48), color=(i * 60, 0, 0)) for i in range(3)]
    out = tmp_path / "clip.mp4"

    write_frames(out, frames, fps=10.0)
    read, meta = read_frames(out)

    assert len(read) == 3
    assert meta.width == 64
    assert meta.height == 48
    assert meta.frame_count == 3
    assert read[0].dtype == np.uint8
    assert read[0].shape == (48, 64, 3)


def test_write_empty_frames_raises(tmp_path):
    """空帧列表抛 ValueError。"""
    with pytest.raises(ValueError):
        write_frames(tmp_path / "x.mp4", [], fps=10.0)
```

- [ ] **Step 3: 运行测试确认失败**

Run: `uv run pytest tests/test_video_io.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'semantic_transmission.common.video_io'`）

- [ ] **Step 4: 实现 `common/video_io.py`**

```python
"""视频解码/编码工具：基于 imageio[ffmpeg] 的帧序列读写。

与 :mod:`common.image_io` 并列——image_io 负责单图加载，video_io 负责
视频与帧序列互转。底层用 imageio 的 ffmpeg 插件（``imageio[ffmpeg]`` 自带
静态二进制，免系统安装 ffmpeg）。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import imageio.v2 as imageio
import numpy as np
from numpy.typing import NDArray
from PIL import Image


@dataclass
class VideoMeta:
    """视频元数据。"""

    fps: float
    width: int
    height: int
    frame_count: int


def read_frames(path: str | Path) -> tuple[list[NDArray[np.uint8]], VideoMeta]:
    """解码视频为 RGB ndarray 帧列表 + 元数据。

    Args:
        path: 视频文件路径。

    Returns:
        ``(frames, meta)``，frames 为 ``(H, W, 3)`` uint8 RGB 数组列表。

    Raises:
        ValueError: 视频无可解码帧。
    """
    path = Path(path)
    reader = imageio.get_reader(path)
    try:
        meta = reader.get_meta_data()
        frames = [np.asarray(frame, dtype=np.uint8) for frame in reader]
    finally:
        reader.close()

    if not frames:
        raise ValueError(f"视频无可解码帧: {path}")

    height, width = frames[0].shape[:2]
    fps = float(meta.get("fps", 0.0))
    return frames, VideoMeta(
        fps=fps, width=width, height=height, frame_count=len(frames)
    )


def write_frames(path: str | Path, frames: list[Image.Image], fps: float) -> None:
    """将 PIL 帧列表编码为视频。

    Args:
        path: 输出视频路径（父目录自动创建）。
        frames: PIL Image 帧列表。
        fps: 输出帧率。

    Raises:
        ValueError: 帧列表为空。
    """
    if not frames:
        raise ValueError("帧列表为空，无法写视频")

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    writer = imageio.get_writer(path, fps=fps)
    try:
        for frame in frames:
            writer.append_data(np.asarray(frame, dtype=np.uint8))
    finally:
        writer.close()


__all__ = ["VideoMeta", "read_frames", "write_frames"]
```

- [ ] **Step 5: 运行测试确认通过**

Run: `uv run pytest tests/test_video_io.py -v`
Expected: PASS（2 passed）

- [ ] **Step 6: lint + 提交**

```bash
uv run ruff format src/semantic_transmission/common/video_io.py tests/test_video_io.py
uv run ruff check .
git add src/semantic_transmission/common/video_io.py tests/test_video_io.py pyproject.toml uv.lock
git commit -F - <<'EOF'
feat(common): 新增 video_io 帧序列读写模块

基于 imageio[ffmpeg] 封装 read_frames/write_frames，与 image_io 并列，
为视频流骨架提供视频与 RGB 帧序列互转。
EOF
```

---

### Task 2: 帧后处理钩子与失败帧填充 `pipeline/video_pipeline.py`（纯函数部分）

**Files:**
- Create: `src/semantic_transmission/pipeline/video_pipeline.py`
- Test: `tests/test_video_pipeline.py`

**Interfaces:**
- Consumes: 无
- Produces:
  - `FramePostprocessor = Callable[[list[Image.Image]], list[Image.Image]]`
  - `identity_postprocess(frames: list[Image.Image]) -> list[Image.Image]`
  - `_fill_failed_frames(images: list[Image.Image | None]) -> list[Image.Image]`

- [ ] **Step 1: 写失败测试 `tests/test_video_pipeline.py`**

```python
"""video_pipeline 纯函数与编排测试。"""

import pytest
from PIL import Image

from semantic_transmission.pipeline.video_pipeline import (
    _fill_failed_frames,
    identity_postprocess,
)


def _img(color):
    return Image.new("RGB", (8, 8), color=color)


def test_identity_postprocess_returns_same_list():
    frames = [_img((1, 0, 0)), _img((2, 0, 0))]
    assert identity_postprocess(frames) is frames


def test_fill_middle_failed_uses_previous():
    a, b = _img((1, 0, 0)), _img((2, 0, 0))
    result = _fill_failed_frames([a, None, b])
    assert result == [a, a, b]


def test_fill_leading_failed_uses_first_valid():
    a = _img((1, 0, 0))
    result = _fill_failed_frames([None, a])
    assert result == [a, a]


def test_fill_all_failed_raises():
    with pytest.raises(ValueError):
        _fill_failed_frames([None, None])
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run pytest tests/test_video_pipeline.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'semantic_transmission.pipeline.video_pipeline'`）

- [ ] **Step 3: 实现纯函数部分（先建文件，编排类下一任务补）**

```python
"""视频流编排：video→video 保底骨架。

VideoPipeline 复用现有逐帧管道（LocalCannyExtractor + receiver.process_batch），
串接 video_io 解码/编码，并在收帧后做失败帧填充 + 序列级 frame_postprocess。
VLM 不在本模块——prompt 由调用方通过 prompt_fn 注入，保证可在无 GPU 下单测。
"""

from __future__ import annotations

from typing import Callable

from PIL import Image

FramePostprocessor = Callable[[list[Image.Image]], list[Image.Image]]
"""序列级帧后处理钩子：list[Image] -> list[Image]。

D1 恒等透传。D5 插帧（返回更长帧列表）/ D6 超分（逐帧映射）替换此实现。
"""


def identity_postprocess(frames: list[Image.Image]) -> list[Image.Image]:
    """D1 默认钩子：原样返回。"""
    return frames


def _fill_failed_frames(images: list[Image.Image | None]) -> list[Image.Image]:
    """用上一成功帧填充失败帧（None），保证输出帧数 = 输入帧数。

    前导 None 用第一帧成功帧回填；中间 None 用上一成功帧填充。

    Raises:
        ValueError: 全部帧失败（无可用帧）。
    """
    valid = [img for img in images if img is not None]
    if not valid:
        raise ValueError("所有帧生成失败，无可用帧")

    filled: list[Image.Image] = []
    last: Image.Image = valid[0]  # 前导 None 用第一帧成功帧
    for img in images:
        if img is not None:
            last = img
        filled.append(last)
    return filled


__all__ = ["FramePostprocessor", "identity_postprocess", "_fill_failed_frames"]
```

- [ ] **Step 4: 运行测试确认通过**

Run: `uv run pytest tests/test_video_pipeline.py -v`
Expected: PASS（4 passed）

- [ ] **Step 5: lint + 提交**

```bash
uv run ruff format src/semantic_transmission/pipeline/video_pipeline.py tests/test_video_pipeline.py
uv run ruff check .
git add src/semantic_transmission/pipeline/video_pipeline.py tests/test_video_pipeline.py
git commit -F - <<'EOF'
feat(pipeline): 新增帧后处理钩子与失败帧填充

序列级 frame_postprocess 空钩子（identity）+ _fill_failed_frames
用上一成功帧填充失败帧，保证输出帧数守恒。
EOF
```

---

### Task 3: VideoPipeline 编排类

**Files:**
- Modify: `src/semantic_transmission/pipeline/video_pipeline.py`（追加 `VideoPipeline` 类）
- Test: `tests/test_video_pipeline.py`（追加编排测试）

**Interfaces:**
- Consumes:
  - `common.video_io.read_frames`、`write_frames`（Task 1）
  - `_fill_failed_frames`、`identity_postprocess`、`FramePostprocessor`（Task 2）
  - `common.image_io.load_as_rgb`
  - `receiver.base.BaseReceiver.process_batch(list[FrameInput]) -> BatchOutput`、`FrameInput`
  - `sender.local_condition_extractor.LocalCannyExtractor.extract(NDArray) -> NDArray`
- Produces:
  - `VideoPipeline(receiver, extractor, frame_postprocess=identity_postprocess)`
  - `VideoPipeline.run(input_path, output_path, prompt_fn, seed=None, fps=None) -> BatchResult`
    其中 `prompt_fn: PromptFn = Callable[[int, Any], str]`（第二参数运行时为 RGB ndarray 帧）

- [ ] **Step 1: 追加失败测试到 `tests/test_video_pipeline.py`**

在文件末尾追加（顶部 import 也补上）：

```python
from semantic_transmission.common.video_io import read_frames, write_frames
from semantic_transmission.pipeline.video_pipeline import VideoPipeline
from semantic_transmission.receiver.base import BaseReceiver
from semantic_transmission.sender.local_condition_extractor import LocalCannyExtractor


class _FakeReceiver(BaseReceiver):
    """不碰 GPU 的接收端：按调用顺序返回固定绿图，可指定某些帧抛异常。"""

    def __init__(self, fail_indices=()):
        self.fail_indices = set(fail_indices)
        self._i = -1

    def process(self, edge_image, prompt_text, seed=None):
        self._i += 1
        if self._i in self.fail_indices:
            raise RuntimeError("fake failure")
        return Image.new("RGB", (64, 48), color=(0, 255, 0))


def _make_input_video(path, n):
    write_frames(
        path,
        [Image.new("RGB", (64, 48), color=(i * 30 % 256, 0, 0)) for i in range(n)],
        fps=8.0,
    )


def test_run_preserves_frame_count(tmp_path):
    src = tmp_path / "in.mp4"
    _make_input_video(src, 4)
    pipe = VideoPipeline(_FakeReceiver(), LocalCannyExtractor())

    stats = pipe.run(src, tmp_path / "out.mp4", prompt_fn=lambda i, f: "t", seed=0)

    read, _ = read_frames(tmp_path / "out.mp4")
    assert len(read) == 4
    assert stats.total == 4
    assert stats.success == 4


def test_run_invokes_postprocess(tmp_path):
    src = tmp_path / "in.mp4"
    _make_input_video(src, 3)
    calls = []

    def spy(frames):
        calls.append(len(frames))
        return frames

    pipe = VideoPipeline(_FakeReceiver(), LocalCannyExtractor(), frame_postprocess=spy)
    pipe.run(src, tmp_path / "out.mp4", prompt_fn=lambda i, f: "t")

    assert calls == [3]


def test_run_fills_failed_frames(tmp_path):
    src = tmp_path / "in.mp4"
    _make_input_video(src, 3)
    pipe = VideoPipeline(_FakeReceiver(fail_indices=[1]), LocalCannyExtractor())

    stats = pipe.run(src, tmp_path / "out.mp4", prompt_fn=lambda i, f: "t")

    read, _ = read_frames(tmp_path / "out.mp4")
    assert len(read) == 3
    assert stats.failed == 1
    assert stats.success == 2


def test_run_passes_frame_ndarray_to_prompt_fn(tmp_path):
    src = tmp_path / "in.mp4"
    _make_input_video(src, 2)
    seen = []

    def prompt_fn(i, frame):
        seen.append((i, type(frame).__name__, frame.shape))
        return f"p{i}"

    pipe = VideoPipeline(_FakeReceiver(), LocalCannyExtractor())
    pipe.run(src, tmp_path / "out.mp4", prompt_fn=prompt_fn)

    assert [s[0] for s in seen] == [0, 1]
    assert seen[0][1] == "ndarray"
    assert seen[0][2] == (48, 64, 3)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run pytest tests/test_video_pipeline.py -v`
Expected: FAIL（`ImportError: cannot import name 'VideoPipeline'`）

- [ ] **Step 3: 追加 `VideoPipeline` 到 `video_pipeline.py`**

把顶部 `from typing import Callable` 改为 `from typing import Any, Callable`，并在 import 区追加：

```python
from semantic_transmission.common.image_io import load_as_rgb
from semantic_transmission.common.video_io import read_frames, write_frames
from semantic_transmission.pipeline.batch_processor import BatchResult
from semantic_transmission.receiver.base import BaseReceiver, FrameInput
from semantic_transmission.sender.local_condition_extractor import LocalCannyExtractor
```

在 `identity_postprocess` 之后定义 prompt 函数类型别名（不引入 numpy，避免未使用 import；
第二参数运行时是 RGB ndarray，语义在 docstring 说明）：

```python
PromptFn = Callable[[int, Any], str]
"""逐帧 prompt 提供器：(frame_index, frame_rgb_ndarray) -> prompt_text。"""
```

在 `_fill_failed_frames` 之后追加类（并把 `VideoPipeline`、`PromptFn` 加进 `__all__`）：

```python
class VideoPipeline:
    """video→video 编排：解码→逐帧 Canny+构造 FrameInput→process_batch→
    失败帧填充→frame_postprocess→编码。"""

    def __init__(
        self,
        receiver: BaseReceiver,
        extractor: LocalCannyExtractor,
        frame_postprocess: FramePostprocessor = identity_postprocess,
    ):
        self.receiver = receiver
        self.extractor = extractor
        self.frame_postprocess = frame_postprocess

    def run(
        self,
        input_path,
        output_path,
        prompt_fn: PromptFn,
        seed: int | None = None,
        fps: float | None = None,
    ) -> BatchResult:
        """跑通一段视频的 video→video 闭环，返回逐帧/整段统计。

        Args:
            input_path: 输入视频路径。
            output_path: 输出视频路径。
            prompt_fn: ``(frame_index, frame_rgb_ndarray) -> prompt_text``。
            seed: 透传给每帧的随机种子。
            fps: 输出帧率，None 时沿用输入 fps。

        Returns:
            BatchResult 逐帧计时 + 成功率统计。
        """
        frames, meta = read_frames(input_path)

        frame_inputs: list[FrameInput] = []
        for i, frame in enumerate(frames):
            edge_np = self.extractor.extract(frame)
            edge_img = load_as_rgb(edge_np)
            frame_inputs.append(
                FrameInput(
                    edge_image=edge_img,
                    prompt_text=prompt_fn(i, frame),
                    seed=seed,
                    metadata={"name": f"frame_{i:04d}", "index": i},
                )
            )

        output = self.receiver.process_batch(frame_inputs)
        filled = _fill_failed_frames(output.images)
        processed = self.frame_postprocess(filled)
        write_frames(output_path, processed, fps=fps or meta.fps)
        return output.stats
```

- [ ] **Step 4: 运行测试确认通过**

Run: `uv run pytest tests/test_video_pipeline.py -v`
Expected: PASS（8 passed）

- [ ] **Step 5: lint + 提交**

```bash
uv run ruff format src/semantic_transmission/pipeline/video_pipeline.py tests/test_video_pipeline.py
uv run ruff check .
git add src/semantic_transmission/pipeline/video_pipeline.py tests/test_video_pipeline.py
git commit -F - <<'EOF'
feat(pipeline): 新增 VideoPipeline 编排类

复用 LocalCannyExtractor + receiver.process_batch 串接 video_io，
prompt 经 prompt_fn 注入（VLM 解耦），收帧后失败帧填充 + frame_postprocess。
EOF
```

---

### Task 4: CLI 子命令 `semantic-tx video`

**Files:**
- Create: `src/semantic_transmission/cli/video.py`
- Modify: `src/semantic_transmission/cli/main.py`（注册 `video`）
- Test: `tests/test_cli_video.py`

**Interfaces:**
- Consumes:
  - `pipeline.video_pipeline.VideoPipeline`（Task 3）
  - `receiver.create_receiver`、`sender.local_condition_extractor.LocalCannyExtractor`
  - `common.config.load_config`（提供 `canny_low_threshold` / `canny_high_threshold` / `vlm_model_name` / `vlm_model_path`）
- Produces: click command `video`（注册进 `cli` group）

- [ ] **Step 1: 写失败测试 `tests/test_cli_video.py`**

测试只覆盖**不触发 GPU/模型加载**的参数校验（校验在创建 receiver 之前）：

```python
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
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run pytest tests/test_cli_video.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'semantic_transmission.cli.video'`）

- [ ] **Step 3: 实现 `cli/video.py`**

```python
"""semantic-tx video 子命令：端到端视频语义传输 video→video。

发送端逐帧本地 Canny，接收端 Diffusers 本地推理。prompt 策略沿用 demo：
--prompt 整段共用 / --auto-prompt 逐帧 VLM，二者互斥。
"""

import json
from pathlib import Path

import click

from semantic_transmission.common.config import load_config
from semantic_transmission.pipeline.video_pipeline import VideoPipeline
from semantic_transmission.receiver import create_receiver
from semantic_transmission.sender.local_condition_extractor import LocalCannyExtractor


@click.command()
@click.option(
    "--input",
    "input_path",
    required=True,
    type=click.Path(exists=True, path_type=Path),
    help="输入视频路径",
)
@click.option(
    "--output",
    "output_path",
    default=Path("output/video/out.mp4"),
    type=click.Path(path_type=Path),
    help="输出视频路径（默认 output/video/out.mp4）",
)
@click.option("--prompt", default=None, type=str, help="手动描述文本（整段共用）")
@click.option(
    "--auto-prompt",
    is_flag=True,
    default=False,
    help="使用 VLM (Qwen2.5-VL) 为每帧自动生成描述",
)
@click.option(
    "--threshold1",
    default=None,
    type=int,
    help="Canny 低阈值（默认读 config.toml [sender].canny_low_threshold）",
)
@click.option(
    "--threshold2",
    default=None,
    type=int,
    help="Canny 高阈值（默认读 config.toml [sender].canny_high_threshold）",
)
@click.option("--seed", default=None, type=int, help="随机种子（透传给每帧）")
@click.option(
    "--fps", default=None, type=float, help="输出帧率（默认沿用输入视频 fps）"
)
def video(
    input_path,
    output_path,
    prompt,
    auto_prompt,
    threshold1,
    threshold2,
    seed,
    fps,
):
    """端到端视频语义传输：video → 逐帧语义还原 → video。"""
    if not prompt and not auto_prompt:
        raise click.UsageError("必须指定 --prompt 或 --auto-prompt 之一")
    if prompt and auto_prompt:
        raise click.UsageError("--prompt 和 --auto-prompt 不能同时使用")

    cfg = load_config()
    if threshold1 is None:
        threshold1 = cfg.canny_low_threshold
    if threshold2 is None:
        threshold2 = cfg.canny_high_threshold

    extractor = LocalCannyExtractor(threshold1=threshold1, threshold2=threshold2)
    receiver = create_receiver()

    vlm_sender = None
    if auto_prompt:
        from semantic_transmission.sender.qwen_vl_sender import QwenVLSender

        vlm_sender = QwenVLSender(
            model_name=cfg.vlm_model_name,
            model_path=cfg.vlm_model_path or None,
        )

        def prompt_fn(index, frame):
            return vlm_sender.describe(frame).text
    else:

        def prompt_fn(index, frame):
            return prompt

    pipeline = VideoPipeline(receiver, extractor)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    click.echo(f"处理视频: {input_path} → {output_path}")
    try:
        stats = pipeline.run(
            input_path, output_path, prompt_fn, seed=seed, fps=fps
        )
    finally:
        if vlm_sender is not None:
            vlm_sender.unload()

    summary_path = output_path.parent / "summary.json"
    summary_path.write_text(
        json.dumps(stats.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
    )
    click.echo(
        f"完成：{stats.success}/{stats.total} 帧成功，"
        f"总耗时 {stats.total_time:.1f}s，统计写入 {summary_path}"
    )
```

- [ ] **Step 4: 注册子命令到 `cli/main.py`**

在 import 区加入（与现有 import 同区，按字母序靠近 `sender`）：

```python
from semantic_transmission.cli.video import video
```

在 `cli.add_command(gui)` 之后加入：

```python
cli.add_command(video)
```

- [ ] **Step 5: 运行测试确认通过**

Run: `uv run pytest tests/test_cli_video.py -v`
Expected: PASS（3 passed）

- [ ] **Step 6: 全量测试 + lint**

Run:
```bash
uv run pytest tests/test_video_io.py tests/test_video_pipeline.py tests/test_cli_video.py -v
uv run ruff check .
uv run ruff format --check .
```
Expected: 全部 PASS，ruff 无报错。

- [ ] **Step 7: 提交**

```bash
git add src/semantic_transmission/cli/video.py src/semantic_transmission/cli/main.py tests/test_cli_video.py
git commit -F - <<'EOF'
feat(cli): 新增 semantic-tx video 子命令

薄封装 VideoPipeline，--prompt/--auto-prompt 互斥沿用 demo 约定，
逐帧 prompt 经 prompt_fn 注入，输出视频 + summary.json 统计。
EOF
```

---

## 冒烟验证（手动，需 GPU，不进 CI）

实施完成后手动跑一次真实闭环（准备一段小分辨率短片 `sample.mp4`，宽高为偶数）：

```bash
uv run semantic-tx video --input sample.mp4 --prompt "a driving scene on a city road" --output output/video/out.mp4
```
Expected: 生成 `output/video/out.mp4`（与输入同帧数）+ `output/video/summary.json`（逐帧计时、成功率）。

## 完成后

- 推送分支 `feature/video-stream-pipeline`，开 PR（关联 #41 视频流主线）
- 验收对照 spec §8：闭环跑通 + 单测全绿 + ruff 通过 + 不依赖 klein/relay
