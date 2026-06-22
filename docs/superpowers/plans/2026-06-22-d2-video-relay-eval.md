# D2 主线实施计划：保底闭环接 relay 双机 + 视频质量评估

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 D1 的单机 video→video 闭环拆成双机 relay 路径（发送端 Canny+VLM 逐帧发包，接收端 Diffusers 逐帧还原合视频），并新增视频质量评估（逐帧四指标 + 整段汇总）。

**Architecture:** 核心编排放 `pipeline/video_relay.py`（`VideoRelaySender` / `VideoRelayReceiver`），CLI 做薄封装；协议复用现有 `TransmissionPacket`，仅在 `metadata` 约定新增 `frame_index`/`total_frames`/`fps` 字段（不改二进制帧格式）。评估核心放 `evaluation/video_eval.py`，`scripts/evaluate_video.py` 做 argparse 薄封装，对称现有 `scripts/evaluate.py`。

**Tech Stack:** Python ≥3.10、click（CLI）、argparse（scripts）、imageio（video_io）、socket（relay）、skimage/lpips/CLIP（评估）、pytest（测试）、uv（依赖与运行）、ruff（检查/格式化）。

## Global Constraints

- 所有 Python 操作走 `uv`：`uv run pytest`、`uv run ruff check .`、`uv run ruff format --check .`，禁止裸 `python`/`pytest`/`ruff`。
- 推送前本地必须 `uv run ruff check .` 与 `uv run ruff format --check .` 通过；CI 检查范围是整个项目（`.`）。
- 所有新增核心逻辑必须无 GPU 可单测（relay 用 `127.0.0.1` + 线程；receiver 用 fake；评估用 `with_lpips=False`/`with_clip=False` 或 mock）。
- Commit message 遵循 Angular 约定、subject/body 用中文，不含工具生成标记或 Co-Authored-By。
- 已在隔离 worktree 的工作分支上（`feature/video-relay-and-eval`）；本计划不切换分支。
- 协议帧格式不变：仅复用 `TransmissionPacket.metadata` 现有自由字段，键名固定为 `frame_index`（int）、`total_frames`（int）、`fps`（float）、`name`（str）、可选 `seed`（int）。
- 范围边界：不做流式 I/O、不做帧间一致性/时间维度指标、不接 klein、不做真实行车视频测试。

---

### Task 1: VideoRelaySender（发送端编排）

**Files:**
- Create: `src/semantic_transmission/pipeline/video_relay.py`
- Test: `tests/test_video_relay.py`

**Interfaces:**
- Consumes: `read_frames(path) -> (list[ndarray], VideoMeta)`、`load_as_rgb(ndarray) -> PIL.Image`、`LocalCannyExtractor().extract(ndarray) -> ndarray`、`SocketRelaySender(host, port)`（上下文管理器，`.send(TransmissionPacket)`）、`TransmissionPacket(edge_image: bytes, prompt_text: str, metadata: dict)`、`PromptFn = Callable[[int, Any], str]`（来自 `pipeline.video_pipeline`）。
- Produces:
  - `VideoSendStats`（dataclass）：`total_frames: int`、`total_time: float`、`frames: list[dict]`，方法 `to_dict() -> dict`。
  - `class VideoRelaySender.__init__(self, extractor: LocalCannyExtractor)`
  - `VideoRelaySender.run(self, input_path, host: str, port: int, prompt_fn: PromptFn, *, seed: int | None = None, fps: float | None = None, save_frames_dir: Path | None = None) -> VideoSendStats`

- [ ] **Step 1: 写失败测试**

写入 `tests/test_video_relay.py`：

```python
"""video_relay 发送端/接收端编排测试（无 GPU）。"""

import io
import threading
import time

from PIL import Image

from semantic_transmission.common.video_io import write_frames
from semantic_transmission.pipeline.relay import (
    SocketRelayReceiver,
    SocketRelaySender,
    TransmissionPacket,
)
from semantic_transmission.pipeline.video_relay import VideoRelaySender
from semantic_transmission.sender.local_condition_extractor import LocalCannyExtractor


def _find_free_port() -> int:
    import socket as _socket

    with _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _make_input_video(path, n, fps=8.0):
    write_frames(
        path,
        [Image.new("RGB", (64, 48), color=(i * 30 % 256, 0, 0)) for i in range(n)],
        fps=fps,
    )


def test_sender_sends_all_frames_with_metadata(tmp_path):
    src = tmp_path / "in.mp4"
    _make_input_video(src, 3, fps=8.0)
    port = _find_free_port()
    received = []

    def recv_thread():
        with SocketRelayReceiver("127.0.0.1", port) as r:
            for _ in range(3):
                received.append(r.receive(timeout=5.0))

    t = threading.Thread(target=recv_thread)
    t.start()
    time.sleep(0.2)

    sender = VideoRelaySender(LocalCannyExtractor())
    stats = sender.run(
        src, "127.0.0.1", port, prompt_fn=lambda i, f: f"p{i}", seed=7
    )

    t.join(timeout=5.0)
    assert len(received) == 3
    assert [p.metadata["frame_index"] for p in received] == [0, 1, 2]
    assert all(p.metadata["total_frames"] == 3 for p in received)
    assert all(abs(p.metadata["fps"] - 8.0) < 0.01 for p in received)
    assert all(p.metadata["seed"] == 7 for p in received)
    assert received[1].prompt_text == "p1"
    assert received[0].edge_image[:8] == b"\x89PNG\r\n\x1a\n"  # PNG 魔数
    assert stats.total_frames == 3
    assert len(stats.frames) == 3


def test_sender_prompt_fn_failure_falls_back_empty(tmp_path):
    src = tmp_path / "in.mp4"
    _make_input_video(src, 2)
    port = _find_free_port()
    received = []

    def recv_thread():
        with SocketRelayReceiver("127.0.0.1", port) as r:
            for _ in range(2):
                received.append(r.receive(timeout=5.0))

    t = threading.Thread(target=recv_thread)
    t.start()
    time.sleep(0.2)

    def flaky(i, f):
        if i == 1:
            raise RuntimeError("VLM 单帧失败")
        return f"ok{i}"

    VideoRelaySender(LocalCannyExtractor()).run(
        src, "127.0.0.1", port, prompt_fn=flaky
    )
    t.join(timeout=5.0)
    assert received[0].prompt_text == "ok0"
    assert received[1].prompt_text == ""


def test_sender_explicit_fps_overrides_meta(tmp_path):
    src = tmp_path / "in.mp4"
    _make_input_video(src, 2, fps=8.0)
    port = _find_free_port()
    received = []

    def recv_thread():
        with SocketRelayReceiver("127.0.0.1", port) as r:
            for _ in range(2):
                received.append(r.receive(timeout=5.0))

    t = threading.Thread(target=recv_thread)
    t.start()
    time.sleep(0.2)

    VideoRelaySender(LocalCannyExtractor()).run(
        src, "127.0.0.1", port, prompt_fn=lambda i, f: "t", fps=5.0
    )
    t.join(timeout=5.0)
    assert all(abs(p.metadata["fps"] - 5.0) < 0.01 for p in received)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/test_video_relay.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'semantic_transmission.pipeline.video_relay'`）

- [ ] **Step 3: 实现 VideoRelaySender**

写入 `src/semantic_transmission/pipeline/video_relay.py`：

```python
"""视频流双机 relay 编排：发送端逐帧打包发送 / 接收端逐帧还原合视频。

与 video_pipeline 的单机闭环对称——本模块把发送与接收拆到两个进程/机器，
靠 TransmissionPacket.metadata 的 frame_index/total_frames/fps 对齐帧序。
VLM 经 prompt_fn 注入，保证可在无 GPU 下单测。
"""

from __future__ import annotations

import io
import time
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image

from semantic_transmission.common.image_io import load_as_rgb
from semantic_transmission.common.video_io import read_frames
from semantic_transmission.pipeline.relay import SocketRelaySender, TransmissionPacket
from semantic_transmission.pipeline.video_pipeline import PromptFn
from semantic_transmission.sender.local_condition_extractor import LocalCannyExtractor


def _encode_edge_png(edge_img: Image.Image) -> bytes:
    """PIL 边缘图编码为 PNG bytes。"""
    buf = io.BytesIO()
    edge_img.save(buf, format="PNG")
    return buf.getvalue()


@dataclass
class VideoSendStats:
    """发送端统计：总帧数 + 逐帧耗时/体积。"""

    total_frames: int
    total_time: float = 0.0
    frames: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "total_frames": self.total_frames,
            "total_time": self.total_time,
            "frames": self.frames,
        }


class VideoRelaySender:
    """发送端编排：read_frames → 逐帧 Canny + prompt_fn → 逐帧发包。"""

    def __init__(self, extractor: LocalCannyExtractor):
        self.extractor = extractor

    def run(
        self,
        input_path,
        host: str,
        port: int,
        prompt_fn: PromptFn,
        *,
        seed: int | None = None,
        fps: float | None = None,
        save_frames_dir: Path | None = None,
    ) -> VideoSendStats:
        """跑通发送端：解码视频、逐帧提边缘+取 prompt、逐帧发送。

        Args:
            input_path: 输入视频路径。
            host: 接收端 IP。
            port: 接收端端口。
            prompt_fn: ``(frame_index, frame_rgb_ndarray) -> prompt_text``。
            seed: 透传给每帧（写入 metadata.seed）。
            fps: 输出帧率，None 时沿用输入 fps，写入 metadata.fps。
            save_frames_dir: 非 None 时把每帧边缘图存盘（调试用）。

        Returns:
            VideoSendStats 逐帧统计。
        """
        frames, meta = read_frames(input_path)
        out_fps = fps if fps is not None else meta.fps
        total = len(frames)
        stats = VideoSendStats(total_frames=total)
        if save_frames_dir is not None:
            save_frames_dir = Path(save_frames_dir)
            save_frames_dir.mkdir(parents=True, exist_ok=True)

        t_all = time.time()
        with SocketRelaySender(host, port) as relay:
            for i, frame in enumerate(frames):
                edge_np = self.extractor.extract(frame)
                edge_img = load_as_rgb(edge_np)
                try:
                    prompt_text = prompt_fn(i, frame)
                except Exception:
                    prompt_text = ""
                edge_bytes = _encode_edge_png(edge_img)
                metadata: dict = {
                    "frame_index": i,
                    "total_frames": total,
                    "fps": out_fps,
                    "name": f"frame_{i:04d}",
                }
                if seed is not None:
                    metadata["seed"] = seed
                packet = TransmissionPacket(
                    edge_image=edge_bytes,
                    prompt_text=prompt_text,
                    metadata=metadata,
                )
                t0 = time.time()
                relay.send(packet)
                relay_elapsed = time.time() - t0
                if save_frames_dir is not None:
                    edge_img.save(save_frames_dir / f"frame_{i:04d}_edge.png")
                stats.frames.append(
                    {
                        "index": i,
                        "relay": relay_elapsed,
                        "prompt_len": len(prompt_text),
                        "packet_bytes": len(edge_bytes)
                        + len(prompt_text.encode("utf-8")),
                    }
                )
        stats.total_time = time.time() - t_all
        return stats


__all__ = ["VideoSendStats", "VideoRelaySender"]
```

- [ ] **Step 4: 跑测试确认通过**

Run: `uv run pytest tests/test_video_relay.py -v`
Expected: PASS（3 个测试通过）

- [ ] **Step 5: 格式化与检查**

Run: `uv run ruff format src/semantic_transmission/pipeline/video_relay.py tests/test_video_relay.py && uv run ruff check .`
Expected: 无报错

- [ ] **Step 6: 提交**

```bash
git add src/semantic_transmission/pipeline/video_relay.py tests/test_video_relay.py
git commit -m "feat: 视频流双机发送端 VideoRelaySender（逐帧打包发送）"
```

---

### Task 2: VideoRelayReceiver（接收端编排 + 收齐合成）

**Files:**
- Modify: `src/semantic_transmission/pipeline/video_relay.py`
- Test: `tests/test_video_relay.py`

**Interfaces:**
- Consumes: `SocketRelayReceiver(host, port)`（`.start()`、`.accept(timeout)`、`.receive(timeout) -> TransmissionPacket`、`.close()`）、`BaseReceiver.process(edge_image, prompt_text, seed) -> Image`、`BatchResult(total)` 与 `SampleResult(name, status, error, timings)`（来自 `pipeline.batch_processor`）、`_fill_failed_frames(list[Image|None]) -> list[Image]`（来自 `pipeline.video_pipeline`）、`write_frames(path, list[Image], fps)`。
- Produces:
  - `VideoReceiveResult`（dataclass）：`stats: BatchResult`、`fps: float`、`prompts: list[str]`、`output_path: Path`。
  - `_order_buffer(buffer: dict[int, Image | None], total: int) -> list[Image | None]`（按 index 排序，缺帧填 None）。
  - `class VideoRelayReceiver.__init__(self, receiver: BaseReceiver)`
  - `VideoRelayReceiver.run(self, host: str, port: int, output_path, *, timeout: float | None = None) -> VideoReceiveResult`

- [ ] **Step 1: 写失败测试**

追加到 `tests/test_video_relay.py`（顶部 import 增加 `read_frames`、`BaseReceiver`、`VideoRelayReceiver`、`_order_buffer`）：

```python
from semantic_transmission.common.video_io import read_frames, write_frames  # noqa: F811
from semantic_transmission.pipeline.video_relay import (  # noqa: F811
    VideoRelayReceiver,
    VideoRelaySender,
    _order_buffer,
)
from semantic_transmission.receiver.base import BaseReceiver


class _FakeReceiver(BaseReceiver):
    """不碰 GPU：返回固定绿图，可指定某些 frame_index 抛异常。"""

    def __init__(self, fail_indices=()):
        self.fail_indices = set(fail_indices)

    def process(self, edge_image, prompt_text, seed=None):
        idx = int(prompt_text.split("-")[-1]) if prompt_text else -1
        if idx in self.fail_indices:
            raise RuntimeError("fake failure")
        return Image.new("RGB", (64, 48), color=(0, 255, 0))


def _png_bytes():
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), color=(1, 1, 1)).save(buf, format="PNG")
    return buf.getvalue()


def _send_packets(host, port, n, fps=8.0, indices=None):
    indices = indices if indices is not None else list(range(n))
    with SocketRelaySender(host, port) as s:
        for i in indices:
            s.send(
                TransmissionPacket(
                    edge_image=_png_bytes(),
                    prompt_text=f"idx-{i}",
                    metadata={"frame_index": i, "total_frames": n, "fps": fps},
                )
            )


def test_order_buffer_sorts_by_index():
    a = Image.new("RGB", (4, 4), (1, 0, 0))
    b = Image.new("RGB", (4, 4), (2, 0, 0))
    c = Image.new("RGB", (4, 4), (3, 0, 0))
    ordered = _order_buffer({2: c, 0: a, 1: b}, 3)
    assert ordered == [a, b, c]


def test_order_buffer_missing_frame_is_none():
    a = Image.new("RGB", (4, 4), (1, 0, 0))
    ordered = _order_buffer({0: a}, 2)
    assert ordered == [a, None]


def test_receiver_assembles_video(tmp_path):
    port = _find_free_port()
    out = tmp_path / "out.mp4"
    box = []

    def recv_thread():
        box.append(VideoRelayReceiver(_FakeReceiver()).run("127.0.0.1", port, out, timeout=5.0))

    t = threading.Thread(target=recv_thread)
    t.start()
    time.sleep(0.2)
    _send_packets("127.0.0.1", port, 3)
    t.join(timeout=10.0)

    frames, meta = read_frames(out)
    assert len(frames) == 3
    result = box[0]
    assert result.stats.total == 3
    assert result.stats.success == 3
    assert result.prompts == ["idx-0", "idx-1", "idx-2"]
    assert abs(result.fps - 8.0) < 0.01


def test_receiver_fills_failed_frames(tmp_path):
    port = _find_free_port()
    out = tmp_path / "out.mp4"
    box = []

    def recv_thread():
        box.append(
            VideoRelayReceiver(_FakeReceiver(fail_indices=[1])).run(
                "127.0.0.1", port, out, timeout=5.0
            )
        )

    t = threading.Thread(target=recv_thread)
    t.start()
    time.sleep(0.2)
    _send_packets("127.0.0.1", port, 3)
    t.join(timeout=10.0)

    frames, _ = read_frames(out)
    assert len(frames) == 3  # 失败帧被填充，帧数守恒
    assert box[0].stats.failed == 1
    assert box[0].stats.success == 2


def test_sender_receiver_end_to_end(tmp_path):
    src = tmp_path / "in.mp4"
    write_frames(
        src,
        [Image.new("RGB", (64, 48), (i * 40 % 256, 0, 0)) for i in range(4)],
        fps=6.0,
    )
    out = tmp_path / "out.mp4"
    port = _find_free_port()
    box = []

    def recv_thread():
        box.append(VideoRelayReceiver(_FakeReceiver()).run("127.0.0.1", port, out, timeout=10.0))

    t = threading.Thread(target=recv_thread)
    t.start()
    time.sleep(0.2)
    VideoRelaySender(LocalCannyExtractor()).run(
        src, "127.0.0.1", port, prompt_fn=lambda i, f: f"idx-{i}"
    )
    t.join(timeout=15.0)

    frames, _ = read_frames(out)
    assert len(frames) == 4
    assert box[0].stats.success == 4
```

> 注：`test_sender_receiver_end_to_end` 中发送端 prompt 用 `f"idx-{i}"`，与 `_FakeReceiver` 解析 `frame_index` 的约定一致（仅测试用）。

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/test_video_relay.py -v -k "order_buffer or assembles or fills_failed or end_to_end"`
Expected: FAIL（`ImportError: cannot import name 'VideoRelayReceiver'`）

- [ ] **Step 3: 实现 VideoRelayReceiver**

在 `src/semantic_transmission/pipeline/video_relay.py` 顶部 import 区追加：

```python
from semantic_transmission.common.video_io import read_frames, write_frames
from semantic_transmission.pipeline.batch_processor import BatchResult, SampleResult
from semantic_transmission.pipeline.relay import (
    SocketRelayReceiver,
    SocketRelaySender,
    TransmissionPacket,
)
from semantic_transmission.pipeline.video_pipeline import PromptFn, _fill_failed_frames
from semantic_transmission.receiver.base import BaseReceiver
```

> 合并已有 import：删掉原来仅 `read_frames`、仅 `SocketRelaySender, TransmissionPacket`、仅 `PromptFn` 的行，用上面的合并版替换，避免重复导入。

在文件末尾（`__all__` 之前）追加：

```python
@dataclass
class VideoReceiveResult:
    """接收端结果：统计 + fps + 逐帧 prompt + 输出路径。"""

    stats: BatchResult
    fps: float
    prompts: list[str]
    output_path: Path


def _order_buffer(
    buffer: dict[int, Image.Image | None], total: int
) -> list[Image.Image | None]:
    """按 frame_index 排序为有序列表，缺失帧位填 None。"""
    return [buffer.get(i) for i in range(total)]


class VideoRelayReceiver:
    """接收端编排：收包 → 按 index 缓冲 → process → 收齐合成视频。"""

    def __init__(self, receiver: BaseReceiver):
        self.receiver = receiver

    def run(
        self,
        host: str,
        port: int,
        output_path,
        *,
        timeout: float | None = None,
    ) -> VideoReceiveResult:
        """监听端口、逐帧接收并还原，收齐 total_frames 后合成视频。

        Args:
            host: 监听地址。
            port: 监听端口。
            output_path: 输出视频路径。
            timeout: accept/receive 超时秒数，None 为无限等待。

        Returns:
            VideoReceiveResult（含 BatchResult、fps、逐帧 prompt、输出路径）。

        Raises:
            ConnectionError: 收齐前连接中断。
            ValueError: 全部帧失败（无可用帧合成）。
        """
        output_path = Path(output_path)
        relay = SocketRelayReceiver(host, port)
        relay.start()
        relay.accept(timeout=timeout)

        buffer: dict[int, Image.Image | None] = {}
        prompt_buffer: dict[int, str] = {}
        total: int | None = None
        fps: float = 30.0
        batch: BatchResult | None = None
        received = 0

        try:
            while total is None or received < total:
                packet = relay.receive(timeout=timeout)
                idx = int(packet.metadata["frame_index"])
                if total is None:
                    total = int(packet.metadata["total_frames"])
                    fps = float(packet.metadata["fps"])
                    batch = BatchResult(total=total)
                seed = packet.metadata.get("seed")
                sample = SampleResult(name=f"frame_{idx:04d}", status="success")
                t0 = time.time()
                try:
                    img = self.receiver.process(
                        packet.edge_image, packet.prompt_text, seed=seed
                    )
                except Exception as e:
                    img = None
                    sample.status = "failed"
                    sample.error = str(e)
                sample.timings["process"] = time.time() - t0
                batch.add_sample(sample)
                buffer[idx] = img
                prompt_buffer[idx] = packet.prompt_text
                received += 1
        finally:
            relay.close()

        assert batch is not None and total is not None
        batch.total_time = sum(s.timings.get("process", 0) for s in batch.samples)
        ordered = _order_buffer(buffer, total)
        filled = _fill_failed_frames(ordered)
        write_frames(output_path, filled, fps=fps)
        prompts = [prompt_buffer.get(i, "") for i in range(total)]
        return VideoReceiveResult(
            stats=batch, fps=fps, prompts=prompts, output_path=output_path
        )
```

更新 `__all__`：

```python
__all__ = [
    "VideoSendStats",
    "VideoRelaySender",
    "VideoReceiveResult",
    "VideoRelayReceiver",
    "_order_buffer",
]
```

- [ ] **Step 4: 跑测试确认通过**

Run: `uv run pytest tests/test_video_relay.py -v`
Expected: PASS（全部测试通过，含端到端）

- [ ] **Step 5: 格式化与检查**

Run: `uv run ruff format src/semantic_transmission/pipeline/video_relay.py tests/test_video_relay.py && uv run ruff check .`
Expected: 无报错

- [ ] **Step 6: 提交**

```bash
git add src/semantic_transmission/pipeline/video_relay.py tests/test_video_relay.py
git commit -m "feat: 视频流双机接收端 VideoRelayReceiver（收齐合成视频）"
```

---

### Task 3: video-sender / video-receiver CLI 子命令

**Files:**
- Create: `src/semantic_transmission/cli/video_sender.py`
- Create: `src/semantic_transmission/cli/video_receiver.py`
- Modify: `src/semantic_transmission/cli/main.py`
- Test: `tests/test_cli_video_relay.py`

**Interfaces:**
- Consumes: `VideoRelaySender`、`VideoRelayReceiver`、`VideoReceiveResult`（Task 1/2）、`load_config()`（`.canny_low_threshold`/`.canny_high_threshold`/`.vlm_model_name`/`.vlm_model_path`）、`create_receiver()`、`LocalCannyExtractor`、`QwenVLSender`。
- Produces:
  - `video_sender`（click command，注册名 `video-sender`）
  - `video_receiver`（click command，注册名 `video-receiver`）

- [ ] **Step 1: 写失败测试（CLI 参数校验，不触发模型）**

写入 `tests/test_cli_video_relay.py`：

```python
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
    result = runner.invoke(
        video_sender, ["--relay-host", "127.0.0.1", "--prompt", "x"]
    )
    assert result.exit_code != 0


def test_video_receiver_help_lists_options():
    runner = CliRunner()
    result = runner.invoke(video_receiver, ["--help"])
    assert result.exit_code == 0
    assert "--relay-host" in result.output
    assert "--output" in result.output
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/test_cli_video_relay.py -v`
Expected: FAIL（`ModuleNotFoundError: ...cli.video_sender`）

- [ ] **Step 3: 实现 video_sender CLI**

写入 `src/semantic_transmission/cli/video_sender.py`：

```python
"""semantic-tx video-sender 子命令：视频流双机发送端。

逐帧本地 Canny + 可选 VLM，经 TCP relay 逐帧发送到接收端机器。
prompt 策略沿用 video：--prompt 整段共用 / --auto-prompt 逐帧 VLM，互斥。
"""

import json
from pathlib import Path

import click

from semantic_transmission.common.config import load_config
from semantic_transmission.pipeline.video_relay import VideoRelaySender
from semantic_transmission.sender.local_condition_extractor import LocalCannyExtractor


@click.command(name="video-sender")
@click.option(
    "--input",
    "input_path",
    required=True,
    type=click.Path(exists=True, path_type=Path),
    help="输入视频路径",
)
@click.option("--relay-host", required=True, help="接收端机器 IP 地址")
@click.option("--relay-port", default=9000, type=int, help="接收端端口（默认 9000）")
@click.option("--prompt", default=None, type=str, help="手动描述文本（整段共用）")
@click.option(
    "--auto-prompt",
    is_flag=True,
    default=False,
    help="使用 VLM (Qwen2.5-VL) 为每帧自动生成描述",
)
@click.option("--threshold1", default=None, type=int, help="Canny 低阈值")
@click.option("--threshold2", default=None, type=int, help="Canny 高阈值")
@click.option("--seed", default=None, type=int, help="随机种子（透传给每帧）")
@click.option("--fps", default=None, type=float, help="输出帧率（默认沿用输入 fps）")
@click.option(
    "--save-frames-dir",
    default=None,
    type=click.Path(path_type=Path),
    help="可选：把每帧边缘图存盘（调试用）",
)
@click.option(
    "--summary",
    "summary_path",
    default=Path("output/video_relay/sender_summary.json"),
    type=click.Path(path_type=Path),
    help="发送端统计 JSON 输出路径",
)
def video_sender(
    input_path,
    relay_host,
    relay_port,
    prompt,
    auto_prompt,
    threshold1,
    threshold2,
    seed,
    fps,
    save_frames_dir,
    summary_path,
):
    """视频流双机发送端：逐帧 Canny + 描述 → 经 relay 发送。"""
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

    click.echo(f"发送视频: {input_path} → {relay_host}:{relay_port}")
    sender = VideoRelaySender(extractor)
    try:
        stats = sender.run(
            input_path,
            relay_host,
            relay_port,
            prompt_fn,
            seed=seed,
            fps=fps,
            save_frames_dir=save_frames_dir,
        )
    except Exception as e:
        raise click.ClickException(f"发送失败: {e}") from e
    finally:
        if vlm_sender is not None:
            vlm_sender.unload()

    summary_path = Path(summary_path)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(
        json.dumps(stats.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
    )
    click.echo(
        f"完成：发送 {stats.total_frames} 帧，"
        f"总耗时 {stats.total_time:.1f}s，统计写入 {summary_path}"
    )
```

- [ ] **Step 4: 实现 video_receiver CLI**

写入 `src/semantic_transmission/cli/video_receiver.py`：

```python
"""semantic-tx video-receiver 子命令：视频流双机接收端。

监听端口逐帧接收 → Diffusers 还原 → 按帧序收齐合成视频，并写 summary
（含每帧 prompt，供 evaluate_video 算 CLIP）。
"""

import json
from pathlib import Path

import click

from semantic_transmission.pipeline.video_relay import VideoRelayReceiver
from semantic_transmission.receiver import create_receiver


@click.command(name="video-receiver")
@click.option(
    "--relay-host", default="0.0.0.0", help="监听地址（默认 0.0.0.0）"
)
@click.option("--relay-port", default=9000, type=int, help="监听端口（默认 9000）")
@click.option(
    "--output",
    "output_path",
    default=Path("output/video_relay/out.mp4"),
    type=click.Path(path_type=Path),
    help="输出视频路径（默认 output/video_relay/out.mp4）",
)
@click.option(
    "--timeout",
    default=None,
    type=float,
    help="accept/receive 超时秒数（默认无限等待）",
)
def video_receiver(relay_host, relay_port, output_path, timeout):
    """视频流双机接收端：逐帧接收还原 → 收齐合成视频。"""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    click.echo(f"监听 {relay_host}:{relay_port}，输出 → {output_path}")
    recv = create_receiver()
    receiver = VideoRelayReceiver(recv)
    try:
        result = receiver.run(
            relay_host, relay_port, output_path, timeout=timeout
        )
    except Exception as e:
        raise click.ClickException(f"接收失败: {e}") from e
    finally:
        if hasattr(recv, "unload"):
            try:
                recv.unload()
            except Exception as exc:
                click.echo(f"[WARN] receiver.unload() 失败: {exc}")

    summary = result.stats.to_dict()
    summary["fps"] = result.fps
    summary["frames"] = [
        {"index": i, "prompt": p} for i, p in enumerate(result.prompts)
    ]
    summary_path = output_path.parent / "receiver_summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    click.echo(
        f"完成：{result.stats.success}/{result.stats.total} 帧成功，"
        f"视频写入 {output_path}，统计写入 {summary_path}"
    )
```

- [ ] **Step 5: 注册到 main.py**

修改 `src/semantic_transmission/cli/main.py`：在 import 区 `from semantic_transmission.cli.video import video` 之后添加：

```python
from semantic_transmission.cli.video_receiver import video_receiver
from semantic_transmission.cli.video_sender import video_sender
```

在 `cli.add_command(video)` 之后添加：

```python
cli.add_command(video_sender)
cli.add_command(video_receiver)
```

- [ ] **Step 6: 跑测试确认通过**

Run: `uv run pytest tests/test_cli_video_relay.py -v`
Expected: PASS（4 个测试通过）

- [ ] **Step 7: 验证子命令已注册**

Run: `uv run semantic-tx --help`
Expected: 输出中包含 `video-sender` 与 `video-receiver`

- [ ] **Step 8: 格式化与检查**

Run: `uv run ruff format src/semantic_transmission/cli/ tests/test_cli_video_relay.py && uv run ruff check .`
Expected: 无报错

- [ ] **Step 9: 提交**

```bash
git add src/semantic_transmission/cli/video_sender.py src/semantic_transmission/cli/video_receiver.py src/semantic_transmission/cli/main.py tests/test_cli_video_relay.py
git commit -m "feat: 新增 video-sender/video-receiver CLI 子命令"
```

---

### Task 4: evaluation/video_eval.py（视频逐帧 + 整段评估核心）

**Files:**
- Create: `src/semantic_transmission/evaluation/video_eval.py`
- Test: `tests/test_video_eval.py`

**Interfaces:**
- Consumes: `compute_psnr(a, b) -> float`、`compute_ssim(a, b) -> float`、`compute_lpips(a, b, loss_fn, device) -> float`、`load_lpips_model(device)`、`compute_clip_score(img, text, model, processor, device) -> float`、`load_clip_model(device) -> (model, processor)`（均来自 `evaluation` 包）。
- Produces:
  - `summarize_metrics(frames: list[dict]) -> dict`（按 psnr/ssim/lpips/clip_score 出 `{mean, std, count}`，None 跳过）。
  - `evaluate_video(original_frames: list, restored_frames: list, prompts: list[str] | None = None, *, device: str | None = None, with_lpips: bool = True, with_clip: bool = True) -> dict`，返回 `{"frame_count": int, "frames": [{"index": i, "metrics": {...}}], "summary": {...}}`。

- [ ] **Step 1: 写失败测试**

写入 `tests/test_video_eval.py`：

```python
"""video_eval 逐帧 + 整段评估测试（无 GPU：仅 PSNR/SSIM + mock LPIPS）。"""

from unittest.mock import MagicMock

import numpy as np
import pytest

from semantic_transmission.evaluation.video_eval import (
    evaluate_video,
    summarize_metrics,
)


def _frame(val):
    return np.full((16, 16, 3), val, dtype=np.uint8)


def test_frame_count_mismatch_raises():
    with pytest.raises(ValueError):
        evaluate_video([_frame(10)], [_frame(10), _frame(20)], with_lpips=False, with_clip=False)


def test_prompts_length_mismatch_raises():
    with pytest.raises(ValueError):
        evaluate_video(
            [_frame(10), _frame(20)],
            [_frame(11), _frame(21)],
            prompts=["only-one"],
            with_lpips=False,
            with_clip=False,
        )


def test_basic_psnr_ssim_per_frame_and_summary():
    orig = [_frame(100), _frame(150)]
    rest = [_frame(110), _frame(151)]
    report = evaluate_video(orig, rest, with_lpips=False, with_clip=False)
    assert report["frame_count"] == 2
    assert len(report["frames"]) == 2
    assert report["frames"][0]["index"] == 0
    assert isinstance(report["frames"][0]["metrics"]["psnr"], float)
    assert report["frames"][0]["metrics"]["lpips"] is None
    assert report["frames"][0]["metrics"]["clip_score"] is None
    assert report["summary"]["psnr"]["count"] == 2
    assert report["summary"]["psnr"]["mean"] is not None


def test_summarize_metrics_handles_none():
    frames = [
        {"metrics": {"psnr": 20.0, "ssim": 0.8, "lpips": None, "clip_score": None}},
        {"metrics": {"psnr": 30.0, "ssim": 0.6, "lpips": 0.2, "clip_score": None}},
    ]
    summary = summarize_metrics(frames)
    assert summary["psnr"]["mean"] == pytest.approx(25.0)
    assert summary["lpips"]["count"] == 1
    assert summary["clip_score"]["count"] == 0
    assert summary["clip_score"]["mean"] is None


def test_lpips_with_mock_model(monkeypatch):
    import torch

    mock_model = MagicMock()
    mock_model.return_value = torch.tensor(0.42)
    monkeypatch.setattr(
        "semantic_transmission.evaluation.video_eval.load_lpips_model",
        lambda device=None: mock_model,
    )
    orig = [_frame(100), _frame(150)]
    rest = [_frame(110), _frame(151)]
    report = evaluate_video(orig, rest, with_lpips=True, with_clip=False)
    assert report["frames"][0]["metrics"]["lpips"] == pytest.approx(0.42)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/test_video_eval.py -v`
Expected: FAIL（`ModuleNotFoundError: ...evaluation.video_eval`）

- [ ] **Step 3: 实现 video_eval**

写入 `src/semantic_transmission/evaluation/video_eval.py`：

```python
"""视频质量评估：逐帧 PSNR/SSIM/LPIPS/CLIP + 整段均值/标准差汇总。

与图片版 scripts/evaluate.py 对称——本模块面向「原视频帧 vs 还原视频帧」
逐帧对齐评估，帧数必须一致（D2 无插帧）。LPIPS/CLIP 可关闭以便无 GPU 单测。
"""

from __future__ import annotations

import statistics

from .perceptual_metrics import compute_lpips, load_lpips_model
from .pixel_metrics import compute_psnr, compute_ssim
from .semantic_metrics import compute_clip_score, load_clip_model

_METRIC_NAMES = ("psnr", "ssim", "lpips", "clip_score")


def summarize_metrics(frames: list[dict]) -> dict:
    """对逐帧指标求均值/标准差/有效计数，None 值跳过。"""
    summary: dict = {}
    for name in _METRIC_NAMES:
        values = [
            f["metrics"][name]
            for f in frames
            if f["metrics"].get(name) is not None
        ]
        if values:
            mean = statistics.mean(values)
            std = statistics.pstdev(values) if len(values) > 1 else 0.0
            summary[name] = {"mean": mean, "std": std, "count": len(values)}
        else:
            summary[name] = {"mean": None, "std": None, "count": 0}
    return summary


def evaluate_video(
    original_frames: list,
    restored_frames: list,
    prompts: list[str] | None = None,
    *,
    device: str | None = None,
    with_lpips: bool = True,
    with_clip: bool = True,
) -> dict:
    """逐帧评估原视频帧 vs 还原视频帧，并汇总整段统计。

    Args:
        original_frames: 原视频帧列表（ndarray 或 PIL）。
        restored_frames: 还原视频帧列表，长度须与 original_frames 一致。
        prompts: 逐帧描述文本，给定时长度须等于帧数，用于算 CLIP。
        device: 计算设备，None 自动。
        with_lpips: 是否计算 LPIPS（关闭则跳过模型加载）。
        with_clip: 是否计算 CLIP Score（需 prompts，否则逐帧跳过）。

    Returns:
        ``{"frame_count": N, "frames": [...], "summary": {...}}``。

    Raises:
        ValueError: 帧数不一致，或 prompts 长度与帧数不符。
    """
    if len(original_frames) != len(restored_frames):
        raise ValueError(
            f"帧数不一致：原 {len(original_frames)} vs 还原 {len(restored_frames)}"
        )
    if prompts is not None and len(prompts) != len(original_frames):
        raise ValueError(
            f"prompts 长度 {len(prompts)} 与帧数 {len(original_frames)} 不符"
        )

    lpips_model = load_lpips_model(device=device) if with_lpips else None
    clip_model = None
    clip_processor = None
    if with_clip and prompts is not None and any(prompts):
        clip_model, clip_processor = load_clip_model(device=device)

    frames: list[dict] = []
    for i, (orig, rest) in enumerate(zip(original_frames, restored_frames)):
        metrics: dict = {
            "psnr": compute_psnr(orig, rest),
            "ssim": compute_ssim(orig, rest),
            "lpips": None,
            "clip_score": None,
        }
        if lpips_model is not None:
            metrics["lpips"] = compute_lpips(
                orig, rest, loss_fn=lpips_model, device=device
            )
        if clip_model is not None and prompts is not None and prompts[i]:
            metrics["clip_score"] = compute_clip_score(
                rest,
                prompts[i],
                model=clip_model,
                processor=clip_processor,
                device=device,
            )
        frames.append({"index": i, "metrics": metrics})

    return {
        "frame_count": len(frames),
        "frames": frames,
        "summary": summarize_metrics(frames),
    }


__all__ = ["summarize_metrics", "evaluate_video"]
```

- [ ] **Step 4: 跑测试确认通过**

Run: `uv run pytest tests/test_video_eval.py -v`
Expected: PASS（5 个测试通过）

- [ ] **Step 5: 格式化与检查**

Run: `uv run ruff format src/semantic_transmission/evaluation/video_eval.py tests/test_video_eval.py && uv run ruff check .`
Expected: 无报错

- [ ] **Step 6: 提交**

```bash
git add src/semantic_transmission/evaluation/video_eval.py tests/test_video_eval.py
git commit -m "feat: 视频质量评估核心 evaluate_video（逐帧+整段汇总）"
```

---

### Task 5: scripts/evaluate_video.py（视频评估脚本封装）

**Files:**
- Create: `scripts/evaluate_video.py`
- Test: `tests/test_evaluate_video_script.py`

**Interfaces:**
- Consumes: `read_frames(path) -> (list[ndarray], VideoMeta)`、`evaluate_video(...)`（Task 4）、`resolve_device(device)`（可从 `evaluate.py` 复用同名逻辑，本脚本内重新实现一份以保持脚本自包含）。
- Produces: `main(argv: list[str] | None = None) -> int`，CLI 参数 `--original`、`--restored`、`--prompts`、`--output`、`--device`、`--no-lpips`、`--no-clip`。

- [ ] **Step 1: 写失败测试**

写入 `tests/test_evaluate_video_script.py`：

```python
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
        [Image.fromarray(np.full((32, 32, 3), base + i * 5, np.uint8)) for i in range(n)],
        fps=8.0,
    )


def test_help_exits_zero():
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0


def test_nonexistent_original_returns_1(tmp_path):
    rest = tmp_path / "rest.mp4"
    _make_video(rest, 2, 100)
    code = main(
        ["--original", str(tmp_path / "nope.mp4"), "--restored", str(rest)]
    )
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
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/test_evaluate_video_script.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'evaluate_video'`）

- [ ] **Step 3: 实现脚本**

写入 `scripts/evaluate_video.py`：

```python
"""批量评估视频还原质量：逐帧 PSNR/SSIM/LPIPS/CLIP + 整段汇总。

用法示例：
    uv run python scripts/evaluate_video.py \\
        --original input.mp4 --restored output/video_relay/out.mp4

    uv run python scripts/evaluate_video.py \\
        --original input.mp4 --restored out.mp4 \\
        --prompts output/video_relay/receiver_summary.json \\
        --output output/evaluation/video_results.json --device cuda
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from semantic_transmission.common.video_io import read_frames
from semantic_transmission.evaluation.video_eval import evaluate_video


def resolve_device(device: str | None) -> str | None:
    """解析计算设备，None 时自动检测 cuda。"""
    if device is not None:
        return device
    try:
        import torch

        if torch.cuda.is_available():
            return "cuda"
    except ImportError:
        pass
    return None


def load_prompts(prompts_path: Path) -> list[str] | None:
    """从 receiver_summary.json 读取逐帧 prompt（按 index 排序）。"""
    data = json.loads(prompts_path.read_text(encoding="utf-8"))
    frames = data.get("frames")
    if not frames:
        return None
    ordered = sorted(frames, key=lambda f: f["index"])
    return [f.get("prompt", "") for f in ordered]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="评估视频还原质量：逐帧 PSNR/SSIM/LPIPS/CLIP + 整段汇总",
    )
    parser.add_argument("--original", type=Path, required=True, help="原始视频路径")
    parser.add_argument("--restored", type=Path, required=True, help="还原视频路径")
    parser.add_argument(
        "--prompts",
        type=Path,
        default=None,
        help="receiver_summary.json，提供逐帧 prompt 以算 CLIP",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("video_evaluation_results.json"),
        help="JSON 报告输出路径",
    )
    parser.add_argument("--device", type=str, default=None, help="cuda / cpu（默认自动）")
    parser.add_argument("--no-lpips", action="store_true", help="跳过 LPIPS")
    parser.add_argument("--no-clip", action="store_true", help="跳过 CLIP Score")

    args = parser.parse_args(argv)

    if not args.original.is_file():
        print(f"错误: 原视频不存在: {args.original}", file=sys.stderr)
        return 1
    if not args.restored.is_file():
        print(f"错误: 还原视频不存在: {args.restored}", file=sys.stderr)
        return 1

    device = resolve_device(args.device)
    orig_frames, _ = read_frames(args.original)
    rest_frames, _ = read_frames(args.restored)

    prompts = None
    if args.prompts is not None and args.prompts.is_file():
        prompts = load_prompts(args.prompts)

    try:
        report = evaluate_video(
            orig_frames,
            rest_frames,
            prompts=prompts,
            device=device,
            with_lpips=not args.no_lpips,
            with_clip=not args.no_clip,
        )
    except ValueError as e:
        print(f"错误: {e}", file=sys.stderr)
        return 1

    report["metadata"] = {
        "original": str(args.original),
        "restored": str(args.restored),
        "device": device or "cpu",
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    s = report["summary"]
    print("=" * 60)
    print("  视频还原质量评估（整段汇总）")
    print("=" * 60)
    print(f"  帧数:        {report['frame_count']}")
    for name in ("psnr", "ssim", "lpips", "clip_score"):
        v = s[name]
        if v["mean"] is None:
            print(f"  {name:<12s} N/A")
        else:
            print(f"  {name:<12s} mean={v['mean']:.4f}  std={v['std']:.4f}  n={v['count']}")
    print("=" * 60)
    print(f"  结果已保存至: {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: 跑测试确认通过**

Run: `uv run pytest tests/test_evaluate_video_script.py -v`
Expected: PASS（4 个测试通过）

- [ ] **Step 5: 格式化与检查**

Run: `uv run ruff format scripts/evaluate_video.py tests/test_evaluate_video_script.py && uv run ruff check .`
Expected: 无报错

- [ ] **Step 6: 全量测试 + 提交**

Run: `uv run pytest`
Expected: 全绿（含既有测试）

```bash
git add scripts/evaluate_video.py tests/test_evaluate_video_script.py
git commit -m "feat: 新增 scripts/evaluate_video.py 视频评估脚本"
```

---

## 最终验证（全部任务完成后）

- [ ] **完整 CI 校验**

Run: `uv run ruff check . && uv run ruff format --check . && uv run pytest`
Expected: 全绿

- [ ] **GPU 冒烟（手动，单卡 127.0.0.1 双进程模拟双机）**

终端 A（接收端）：
```bash
uv run semantic-tx video-receiver --relay-host 127.0.0.1 --relay-port 9000 --output output/video_relay/out.mp4 --timeout 120
```
终端 B（发送端，用 `--prompt` 整段、不加载 VLM，规避同机显存争用）：
```bash
uv run semantic-tx video-sender --input <5~8帧512×288短片> --relay-host 127.0.0.1 --relay-port 9000 --prompt "a driving scene on a road"
```
评估：
```bash
uv run python scripts/evaluate_video.py --original <同一短片> --restored output/video_relay/out.mp4 --prompts output/video_relay/receiver_summary.json --device cuda
```
Expected: `out.mp4` 帧数 = 输入帧数；`receiver_summary.json` 成功率符合预期；评估打印逐帧/整段指标并写 JSON。

---

## Self-Review 记录

- **Spec 覆盖**：双机发送端（Task 1）、接收端收齐合成（Task 2）、CLI 子命令（Task 3）、逐帧+整段评估核心（Task 4）、对称 scripts 评估脚本（Task 5）；协议 metadata 扩展在 Task 1 落地（`frame_index`/`total_frames`/`fps`）；失败帧填充复用 `_fill_failed_frames`（Task 2）；帧序对齐用 `_order_buffer`（Task 2）；CLIP prompt 来源经 receiver_summary（Task 3 写、Task 5 读）。范围边界（无流式/无帧间一致性/无 klein/无真实行车测试）均未引入。
- **类型一致性**：`VideoSendStats.to_dict()`、`VideoReceiveResult.{stats,fps,prompts,output_path}`、`evaluate_video(...) -> {"frame_count","frames","summary"}`、`summarize_metrics(frames)`、`_order_buffer(buffer, total)` 在定义任务与消费任务间签名一致。
- **无占位符**：所有步骤含可执行代码与命令。
