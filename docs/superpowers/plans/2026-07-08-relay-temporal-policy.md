# 阶段 3（二）时序策略接入 relay 双机协议 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把单机 `VideoPipeline._run_temporal` 验证过的有状态串行时序策略（关键帧透传 + prev 链参考帧补偿）接入双机 relay：关键帧低频整帧传输、生成帧走语义码流。

**Architecture:** 状态不过线、调度随包过线——发送端按 `is_keyframe(i)` 分流并在 `metadata["frame_type"]` 打标（唯一真相源），接收端只读标签、持 `prev_out`/`last_kf` 串行补偿。协议复用现有 3 字段长度前缀帧，零线格式改动：`edge_image` 字段按 `frame_type` 复用（生成帧装 Canny、关键帧装整帧 RGB PNG）。

**Tech Stack:** Python 3.12 / click CLI / socket TCP relay / PIL / pytest（无 GPU 单测用 `threading` + `_FakeReceiver` loopback）。

## Global Constraints

- 所有 Python 操作走 `uv run`（`uv run pytest`、`uv run ruff check .`、`uv run ruff format .`）。
- 推送前本地必须 `uv run ruff check .` 与 `uv run ruff format --check .` 通过（CI 检查范围为整个项目 `.`）。
- 已在分支 `feature/relay-temporal-policy`（禁止改 main）。
- commit message 遵循 Angular 规范，中文 subject/body，不含工具生成标记与 Co-Authored-By。
- **relay 时序路径限定 `keyframe_passthrough=True`**（收紧 spec §5.1）：非透传关键帧在 relay 中会使接收端缺失 `last_kf` 锚点，破坏 keyframe/prev_keyframe 模式，且违背「整帧传输」前提。故 relay CLI **不暴露** `--no-keyframe-passthrough`。
- 接收端 `process` 签名：`process(self, edge_image, prompt_text, seed=None, reference_images=None) -> Image`。
- `fit_working_size(image: Image, max_side: int) -> Image` 位于 `receiver.klein_receiver`，惰性导入。
- `build_reference_images(mode, prev_output, last_keyframe) -> list`、`is_keyframe(index, config) -> bool` 位于 `pipeline.temporal_policy`。
- 无状态旧路径（`temporal_policy=None` / `reference_mode=None`）必须逐字节向后兼容——现有 `tests/test_video_relay.py`、`tests/test_cli_video_relay.py` 全部保持绿。

---

## File Structure

- `src/semantic_transmission/pipeline/relay.py` — **修改**：`TransmissionPacket.metadata` 增 `frame_type` 语义约定（无需改 dataclass，仅文档）。
- `src/semantic_transmission/pipeline/video_relay.py` — **修改**：`VideoRelaySender.run` 加 `temporal_policy`；`VideoSendStats` 加码率账本；`VideoRelayReceiver.run` 加 `reference_mode` + 新增 `_run_temporal`。
- `src/semantic_transmission/cli/video_sender.py` — **修改**：加 `--keyframe-interval` / `--prompts-json`。
- `src/semantic_transmission/cli/video_receiver.py` — **修改**：加 `--backend` / `--reference-mode`。
- `tests/test_video_relay_temporal.py` — **新建**：发送端分流 + 接收端时序重建单测（无 GPU）。
- `tests/test_cli_video_relay.py` — **修改**：新增 CLI 参数校验用例。
- `docs/test-reports/2026-07-08-relay-temporal-policy-report.md` — **新建**：loopback 验收报告。

---

## Task 1: 发送端时序分流 + 码率账本

**Files:**
- Modify: `src/semantic_transmission/pipeline/video_relay.py`（`VideoSendStats` 加码率账本、`VideoRelaySender.run` 加 `temporal_policy`；整帧编码直接复用既有 `_encode_edge_png`，不新增函数）
- Test: `tests/test_video_relay_temporal.py`

**Interfaces:**
- Consumes: `is_keyframe(index, TemporalPolicyConfig)`、`TemporalPolicyConfig(keyframe_interval, reference_mode, keyframe_passthrough)`（`pipeline.temporal_policy`）；`load_as_rgb`（`common.image_io`）；`_encode_edge_png`（本文件既有）。
- Produces:
  - `VideoRelaySender.run(self, input_path, host, port, prompt_fn, *, seed=None, fps=None, save_frames_dir=None, temporal_policy: TemporalPolicyConfig | None = None) -> VideoSendStats`
  - `VideoSendStats` 新字段：`keyframe_count: int = 0`、`generated_count: int = 0`、`keyframe_bytes: int = 0`、`generated_bytes: int = 0`；`to_dict()` 输出全部字段。
  - 关键帧包：`metadata["frame_type"] == "keyframe"`、`edge_image` 为整帧 RGB PNG、`prompt_text == ""`。
  - 生成帧包：`metadata["frame_type"] == "generated"`、`edge_image` 为 Canny PNG、携带 prompt。

- [ ] **Step 1: 写失败测试——发送端关键帧发整帧、生成帧发 Canny**

在新建文件 `tests/test_video_relay_temporal.py` 写入：

```python
"""video_relay 时序路径（关键帧透传 + 参考帧补偿）单测，无 GPU。"""

import io
import threading
import time

from PIL import Image

from semantic_transmission.common.video_io import write_frames
from semantic_transmission.pipeline.relay import SocketRelayReceiver
from semantic_transmission.pipeline.temporal_policy import TemporalPolicyConfig
from semantic_transmission.pipeline.video_relay import (
    VideoRelaySender,
    VideoRelayReceiver,
)
from semantic_transmission.receiver.base import BaseReceiver
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


def _collect_packets(port, count, out):
    with SocketRelayReceiver("127.0.0.1", port) as r:
        for _ in range(count):
            out.append(r.receive(timeout=5.0))


def test_sender_temporal_tags_keyframe_and_generated(tmp_path):
    src = tmp_path / "in.mp4"
    _make_input_video(src, 5, fps=8.0)
    port = _find_free_port()
    received = []
    t = threading.Thread(target=_collect_packets, args=(port, 5, received))
    t.start()
    time.sleep(0.2)

    policy = TemporalPolicyConfig(keyframe_interval=2, reference_mode="prev")
    VideoRelaySender(LocalCannyExtractor()).run(
        src, "127.0.0.1", port, prompt_fn=lambda i, f: f"p{i}", temporal_policy=policy
    )
    t.join(timeout=5.0)

    # interval=2 → 关键帧 index 0,2,4；生成帧 1,3
    types = [p.metadata["frame_type"] for p in received]
    assert types == ["keyframe", "generated", "keyframe", "generated", "keyframe"]
    # 关键帧：空 prompt + 整帧 PNG（64x48）；生成帧：携 prompt
    kf = received[0]
    assert kf.prompt_text == ""
    assert Image.open(io.BytesIO(kf.edge_image)).size == (64, 48)
    assert received[1].prompt_text == "p1"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run pytest tests/test_video_relay_temporal.py::test_sender_temporal_tags_keyframe_and_generated -v`
Expected: FAIL —— `run()` 不接受 `temporal_policy` 关键字（`TypeError: run() got an unexpected keyword argument 'temporal_policy'`）。

- [ ] **Step 3: 实现发送端时序分流**

在 `src/semantic_transmission/pipeline/video_relay.py`，`VideoSendStats` 加码率账本字段：

```python
@dataclass
class VideoSendStats:
    """发送端统计：总帧数 + 逐帧耗时/体积 + 时序码率账本。"""

    total_frames: int
    total_time: float = 0.0
    frames: list[dict] = field(default_factory=list)
    # 时序路径码率账本：关键帧整帧 vs 生成帧语义码流的帧数与字节数。
    keyframe_count: int = 0
    generated_count: int = 0
    keyframe_bytes: int = 0
    generated_bytes: int = 0

    def to_dict(self) -> dict:
        return {
            "total_frames": self.total_frames,
            "total_time": self.total_time,
            "keyframe_count": self.keyframe_count,
            "generated_count": self.generated_count,
            "keyframe_bytes": self.keyframe_bytes,
            "generated_bytes": self.generated_bytes,
            "frames": self.frames,
        }
```

在 `_encode_edge_png` 下方加整帧编码复用（RGB PNG 与 edge 同为 PIL→PNG，直接复用即可，无需新函数；下方 run 里对整帧调 `_encode_edge_png(load_as_rgb(frame))`）。

改 `VideoRelaySender.run` 签名与循环（新增 `temporal_policy` 参数；`None` 时走原逐帧路径不变，非 `None` 时按 `is_keyframe` 分流）：

```python
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
        temporal_policy: "TemporalPolicyConfig | None" = None,
    ) -> VideoSendStats:
        # relay 时序路径仅支持 keyframe_passthrough=True（关键帧整帧传输）——
        # 库层 fail-fast 守卫，与 CLI 不暴露 --no-keyframe-passthrough 一致（S3）。
        if temporal_policy is not None and not temporal_policy.keyframe_passthrough:
            raise ValueError(
                "relay 时序路径仅支持 keyframe_passthrough=True（关键帧整帧传输）"
            )
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
                is_kf = temporal_policy is not None and is_keyframe(i, temporal_policy)
                metadata: dict = {
                    "frame_index": i,
                    "total_frames": total,
                    "fps": out_fps,
                    "name": f"frame_{i:04d}",
                }
                if seed is not None:
                    metadata["seed"] = seed

                if is_kf:
                    # 关键帧透传：发整帧 RGB PNG、空 prompt、不提 Canny 不调 prompt_fn。
                    frame_bytes = _encode_edge_png(load_as_rgb(frame))
                    prompt_text = ""
                    metadata["frame_type"] = "keyframe"
                    payload_bytes = frame_bytes
                    stats.keyframe_count += 1
                    stats.keyframe_bytes += len(frame_bytes)
                else:
                    edge_img = load_as_rgb(self.extractor.extract(frame))
                    try:
                        prompt_text = prompt_fn(i, frame)
                    except Exception:
                        prompt_text = ""
                    payload_bytes = _encode_edge_png(edge_img)
                    if temporal_policy is not None:
                        metadata["frame_type"] = "generated"
                        stats.generated_count += 1
                        stats.generated_bytes += (
                            len(payload_bytes) + len(prompt_text.encode("utf-8"))
                        )

                packet = TransmissionPacket(
                    edge_image=payload_bytes,
                    prompt_text=prompt_text,
                    metadata=metadata,
                )
                t0 = time.time()
                relay.send(packet)
                relay_elapsed = time.time() - t0
                if save_frames_dir is not None:
                    (save_frames_dir / f"frame_{i:04d}_edge.png").write_bytes(
                        payload_bytes
                    )
                stats.frames.append(
                    {
                        "index": i,
                        "relay": relay_elapsed,
                        "prompt_len": len(prompt_text),
                        "packet_bytes": len(payload_bytes)
                        + len(prompt_text.encode("utf-8")),
                    }
                )
        stats.total_time = time.time() - t_all
        return stats
```

在文件顶部 import 补 `is_keyframe` 与 `TemporalPolicyConfig`（**只导入 Task 1 用到的两个**——`build_reference_images` 留到 Task 2 再加，否则 Task 1 会因 ruff F401 未用导入而挂，S1）：

```python
from semantic_transmission.pipeline.temporal_policy import (
    TemporalPolicyConfig,
    is_keyframe,
)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `uv run pytest tests/test_video_relay_temporal.py::test_sender_temporal_tags_keyframe_and_generated -v`
Expected: PASS

- [ ] **Step 5: 写码率账本测试**

在 `tests/test_video_relay_temporal.py` 追加：

```python
def test_sender_temporal_rate_ledger(tmp_path):
    src = tmp_path / "in.mp4"
    _make_input_video(src, 5, fps=8.0)
    port = _find_free_port()
    received = []
    t = threading.Thread(target=_collect_packets, args=(port, 5, received))
    t.start()
    time.sleep(0.2)

    policy = TemporalPolicyConfig(keyframe_interval=2, reference_mode="prev")
    stats = VideoRelaySender(LocalCannyExtractor()).run(
        src, "127.0.0.1", port, prompt_fn=lambda i, f: f"p{i}", temporal_policy=policy
    )
    t.join(timeout=5.0)

    assert stats.keyframe_count == 3  # index 0,2,4
    assert stats.generated_count == 2  # index 1,3
    assert stats.keyframe_bytes > 0
    assert stats.generated_bytes > 0
    d = stats.to_dict()
    assert d["keyframe_count"] == 3 and d["generated_count"] == 2


def test_sender_temporal_rejects_non_passthrough(tmp_path):
    """relay 时序守卫：keyframe_passthrough=False 直接 fail-fast（S3）。"""
    import pytest

    src = tmp_path / "in.mp4"
    _make_input_video(src, 2)
    policy = TemporalPolicyConfig(
        keyframe_interval=2, reference_mode="prev", keyframe_passthrough=False
    )
    with pytest.raises(ValueError, match="keyframe_passthrough"):
        VideoRelaySender(LocalCannyExtractor()).run(
            src, "127.0.0.1", 9999, prompt_fn=lambda i, f: "x", temporal_policy=policy
        )
```

> 注：守卫在 `read_frames` 之前触发（见 Step 3 代码），故无需真实连接即抛 `ValueError`。

- [ ] **Step 6: 运行测试确认通过**

Run: `uv run pytest tests/test_video_relay_temporal.py -v`
Expected: 两个测试 PASS。

- [ ] **Step 7: 回归 + lint**

Run: `uv run pytest tests/test_video_relay.py tests/test_video_relay_temporal.py -v && uv run ruff check . && uv run ruff format --check .`
Expected: 全绿（旧无状态测试不受影响；无状态路径不加 `frame_type`）。

- [ ] **Step 8: Commit**

```bash
git add src/semantic_transmission/pipeline/video_relay.py tests/test_video_relay_temporal.py
git commit -m "feat: relay 发送端时序分流——关键帧发整帧、生成帧走语义码流

VideoRelaySender.run 接受 temporal_policy，按 is_keyframe 分流并在
metadata.frame_type 打标；VideoSendStats 增码率账本（关键帧整帧字节 vs
生成帧语义字节）。temporal_policy=None 时保持无状态逐帧路径向后兼容。"
```

---

## Task 2: 接收端时序重建（持状态串行补偿）

**Files:**
- Modify: `src/semantic_transmission/pipeline/video_relay.py`（`VideoRelayReceiver.run` 加 `reference_mode`，新增 `_run_temporal`）
- Test: `tests/test_video_relay_temporal.py`（追加）

**Interfaces:**
- Consumes: `build_reference_images(mode, prev_output, last_keyframe)`（已在 Task 1 导入）；`fit_working_size(image, max_side)`（`receiver.klein_receiver`，惰性导入）；`self.receiver.config.max_side`；`self.receiver.process(edge, prompt, seed=, reference_images=)`；`_fill_failed_frames`、`_order_buffer`（本文件既有）。
- Produces:
  - `VideoRelayReceiver.run(self, host, port, output_path, *, timeout=None, reference_mode: str | None = None) -> VideoReceiveResult`
  - `reference_mode` 非 `None` → 走 `_run_temporal`，返回同一 `VideoReceiveResult`；其 `stats.keyframe_count` / `stats.generated_frames` / `stats.keyframe_indices` 按 `_run_temporal` 口径填。
  - 能力门控：`receiver.process` 不接受 `reference_images` 时抛 `TypeError`，提示用 `--backend klein`。

- [ ] **Step 1: 写失败测试——接收端按 frame_type 分支 + prev 链**

在 `tests/test_video_relay_temporal.py` 追加一个能记录 `reference_images` 的 stub 接收端与测试：

```python
class _ConfigStub:
    max_side = 512


class _RefRecordingReceiver(BaseReceiver):
    """记录每次 process 收到的 reference_images 数量，返回可辨识纯色图。"""

    config = _ConfigStub()

    def __init__(self):
        self.calls = []  # list[(prompt_text, num_refs)]

    def process(self, edge_image, prompt_text, seed=None, reference_images=None):
        n_refs = len(reference_images) if reference_images else 0
        self.calls.append((prompt_text, n_refs))
        # 必须与关键帧透传尺寸一致（输入 64x48，fit_working_size(64x48,512)=64x48），
        # 否则 write_frames 混合尺寸抛 ValueError（B2）。
        return Image.new("RGB", (64, 48), color=(0, 0, 255))

    def process_batch(self, frames):  # 抽象方法占位，本测试不用
        raise NotImplementedError


def test_receiver_temporal_passthrough_and_refs(tmp_path):
    src = tmp_path / "in.mp4"
    _make_input_video(src, 5, fps=8.0)
    out = tmp_path / "out.mp4"
    port = _find_free_port()
    recv = _RefRecordingReceiver()
    box = []

    def recv_thread():
        box.append(
            VideoRelayReceiver(recv).run(
                "127.0.0.1", port, out, timeout=10.0, reference_mode="prev"
            )
        )

    t = threading.Thread(target=recv_thread)
    t.start()
    time.sleep(0.2)
    policy = TemporalPolicyConfig(keyframe_interval=2, reference_mode="prev")
    VideoRelaySender(LocalCannyExtractor()).run(
        src, "127.0.0.1", port, prompt_fn=lambda i, f: f"p{i}", temporal_policy=policy
    )
    t.join(timeout=15.0)
    assert not t.is_alive(), "receiver thread timed out"

    # 生成帧 index 1,3 各调一次 process；prev 链在关键帧后有 prev → refs=1。
    assert [c[0] for c in recv.calls] == ["p1", "p3"]
    assert all(n == 1 for _, n in recv.calls)  # prev-only：每个生成帧带 1 个参考帧
    result = box[0]
    assert result.stats.keyframe_count == 3
    assert result.stats.generated_frames == 2
    assert result.stats.keyframe_indices == [0, 2, 4]
    assert result.output_path == out
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run pytest tests/test_video_relay_temporal.py::test_receiver_temporal_passthrough_and_refs -v`
Expected: FAIL —— `run()` 不接受 `reference_mode` 关键字。

- [ ] **Step 3: 实现接收端时序路径**

在 `src/semantic_transmission/pipeline/video_relay.py`，先在文件顶部的 `temporal_policy` 导入里补上 `build_reference_images`（Task 1 未导入，此处 `_run_temporal` 首次用到，S1）：

```python
from semantic_transmission.pipeline.temporal_policy import (
    TemporalPolicyConfig,
    build_reference_images,
    is_keyframe,
)
```

然后 `VideoRelayReceiver.run` 加 `reference_mode` 参数并前置分派；新增 `_run_temporal`。先改 `run` 签名与开头：

```python
    def run(
        self,
        host: str,
        port: int,
        output_path,
        *,
        timeout: float | None = None,
        reference_mode: str | None = None,
    ) -> VideoReceiveResult:
        if reference_mode is not None:
            return self._run_temporal(
                host, port, output_path, reference_mode, timeout=timeout
            )
        # ↓↓↓ 原无状态实现保持不变 ↓↓↓
```

（原 `run` 主体不动，仅在最前面加上上面的分派分支。）

在 `VideoRelayReceiver` 内新增 `_run_temporal` 方法：

```python
    def _run_temporal(
        self,
        host: str,
        port: int,
        output_path,
        reference_mode: str,
        *,
        timeout: float | None = None,
    ) -> VideoReceiveResult:
        """有状态串行时序路径：关键帧透传复位锚点 + 生成帧带参考帧补偿。

        与单机 VideoPipeline._run_temporal 对称——状态（prev_out/last_kf）留在
        接收端，输入改自网络，按 metadata.frame_type 分支。依赖单 TCP 流有序性
        保证帧序到达（prev 链前提）。
        """
        from semantic_transmission.receiver.klein_receiver import fit_working_size

        # 能力门控：串行补偿要求 process 接受 reference_images。
        import inspect

        params = inspect.signature(self.receiver.process).parameters
        if "reference_images" not in params:
            raise TypeError(
                "时序补偿要求 receiver.process 接受 reference_images 参数，"
                f"当前接收端 {type(self.receiver).__name__} 不支持——请用 --backend klein"
            )
        max_side = self.receiver.config.max_side

        relay = SocketRelayReceiver(host, port)
        buffer: dict[int, Image.Image | None] = {}
        prompt_buffer: dict[int, str] = {}
        total: int | None = None
        fps: float = 30.0
        batch: BatchResult | None = None
        failed_indices: list[int] = []
        keyframe_indices: list[int] = []
        prev_out: Image.Image | None = None
        last_kf: Image.Image | None = None

        try:
            relay.start()
            relay.accept(timeout=timeout)
            t_start = time.time()
            while total is None or len(buffer) < total:
                try:
                    packet = relay.receive(timeout=timeout)
                except ConnectionError:
                    raise
                except (TimeoutError, OSError, EOFError) as exc:
                    raise ConnectionError("收齐前连接中断") from exc
                md = packet.metadata
                if (
                    md.get("frame_index") is None
                    or md.get("total_frames") is None
                    or md.get("fps") is None
                    or md.get("frame_type") is None
                ):
                    raise ConnectionError("收到缺少必要 metadata 字段的包")
                idx = int(md["frame_index"])
                if total is None:
                    total = int(md["total_frames"])
                    fps = float(md["fps"])
                    batch = BatchResult(total=total)
                if idx in buffer:
                    continue  # 去重：重复 frame_index 不重复处理
                seed = md.get("seed")

                if md["frame_type"] == "keyframe":
                    kf = fit_working_size(
                        Image.open(io.BytesIO(packet.edge_image)).convert("RGB"),
                        max_side,
                    )
                    buffer[idx] = kf
                    prompt_buffer[idx] = ""
                    keyframe_indices.append(idx)
                    prev_out = kf  # 链首复位到真关键帧
                    last_kf = kf
                    batch.add_sample(
                        SampleResult(
                            name=f"frame_{idx:04d}",
                            status="success",
                            timings={"process": 0.0},
                        )
                    )
                    continue

                # 生成帧：带参考帧补偿。
                refs = build_reference_images(reference_mode, prev_out, last_kf)
                sample = SampleResult(name=f"frame_{idx:04d}", status="success")
                t0 = time.time()
                try:
                    img = self.receiver.process(
                        packet.edge_image,
                        packet.prompt_text,
                        seed=seed,
                        reference_images=refs,
                    )
                except Exception as e:
                    img = None
                    sample.status = "failed"
                    sample.error = str(e)
                    failed_indices.append(idx)
                sample.timings["process"] = time.time() - t0
                batch.add_sample(sample)
                buffer[idx] = img
                prompt_buffer[idx] = packet.prompt_text
                prev_out = img if img is not None else prev_out  # 失败帧不污染 prev 链
        finally:
            relay.close()

        if batch is None or total is None:
            raise ValueError("未收到任何数据包，无法合成视频")
        batch.total_time = time.time() - t_start
        batch.keyframe_count = len(keyframe_indices)
        batch.generated_frames = total - len(keyframe_indices)
        batch.keyframe_indices = sorted(keyframe_indices)

        ordered = _order_buffer(buffer, total)
        filled = _fill_failed_frames(ordered)
        write_frames(output_path, filled, fps=fps)
        prompts = [prompt_buffer.get(i, "") for i in range(total)]
        return VideoReceiveResult(
            stats=batch,
            fps=fps,
            prompts=prompts,
            output_path=output_path,
            failed_indices=sorted(failed_indices),
        )
```

- [ ] **Step 4: 运行测试确认通过**

Run: `uv run pytest tests/test_video_relay_temporal.py::test_receiver_temporal_passthrough_and_refs -v`
Expected: PASS

- [ ] **Step 5: 写失败帧不污染 prev 链 + 能力门控测试**

在 `tests/test_video_relay_temporal.py` 追加：

```python
class _FailingRefReceiver(_RefRecordingReceiver):
    """生成帧全部抛异常，验证失败帧填充 + prev 链不被污染。"""

    def process(self, edge_image, prompt_text, seed=None, reference_images=None):
        self.calls.append((prompt_text, len(reference_images or [])))
        raise RuntimeError("fake gen failure")


def test_receiver_temporal_failed_generated_frames(tmp_path):
    from semantic_transmission.common.video_io import read_frames

    src = tmp_path / "in.mp4"
    _make_input_video(src, 5, fps=8.0)
    out = tmp_path / "out.mp4"
    port = _find_free_port()
    box = []

    def recv_thread():
        box.append(
            VideoRelayReceiver(_FailingRefReceiver()).run(
                "127.0.0.1", port, out, timeout=10.0, reference_mode="prev"
            )
        )

    t = threading.Thread(target=recv_thread)
    t.start()
    time.sleep(0.2)
    policy = TemporalPolicyConfig(keyframe_interval=2, reference_mode="prev")
    VideoRelaySender(LocalCannyExtractor()).run(
        src, "127.0.0.1", port, prompt_fn=lambda i, f: f"p{i}", temporal_policy=policy
    )
    t.join(timeout=15.0)
    assert not t.is_alive()

    frames, _ = read_frames(out)
    assert len(frames) == 5  # 失败生成帧被关键帧填充，帧数守恒
    assert box[0].failed_indices == [1, 3]
    assert box[0].stats.keyframe_count == 3


class _NoRefReceiver(BaseReceiver):
    """process 不接受 reference_images——触发能力门控。"""

    config = _ConfigStub()

    def process(self, edge_image, prompt_text, seed=None):
        return Image.new("RGB", (512, 384))

    def process_batch(self, frames):
        raise NotImplementedError


def test_receiver_temporal_capability_gate(tmp_path):
    import pytest

    out = tmp_path / "out.mp4"
    port = _find_free_port()
    with pytest.raises(TypeError, match="reference_images"):
        VideoRelayReceiver(_NoRefReceiver()).run(
            "127.0.0.1", port, out, timeout=1.0, reference_mode="prev"
        )
```

- [ ] **Step 6: 运行测试确认通过**

Run: `uv run pytest tests/test_video_relay_temporal.py -v`
Expected: 全部 PASS（门控测试在 `accept` 前即抛 `TypeError`，无需真正连接）。

> 注：能力门控在 `_run_temporal` 开头、`relay.start()` 之前触发，故 `_NoRefReceiver` 测试无需发送端连接即可抛错。

- [ ] **Step 7: 回归 + lint**

Run: `uv run pytest tests/test_video_relay.py tests/test_video_relay_temporal.py -v && uv run ruff check . && uv run ruff format --check .`
Expected: 全绿。

- [ ] **Step 8: Commit**

```bash
git add src/semantic_transmission/pipeline/video_relay.py tests/test_video_relay_temporal.py
git commit -m "feat: relay 接收端时序重建——持状态串行参考帧补偿

VideoRelayReceiver.run 加 reference_mode，非 None 时走 _run_temporal：
按 metadata.frame_type 分支，关键帧解码整帧+fit_working_size+复位锚点，
生成帧 build_reference_images+process(reference_images) 串行补偿，失败帧
不污染 prev 链。能力门控要求 process 接受 reference_images（--backend klein）。"
```

---

## Task 3: CLI 暴露时序参数

**Files:**
- Modify: `src/semantic_transmission/cli/video_sender.py`
- Modify: `src/semantic_transmission/cli/video_receiver.py`
- Test: `tests/test_cli_video_relay.py`（追加新用例 + **更新 2 个既有断言**，见 Step 1）

**Interfaces:**
- Consumes: Task 1 的 `VideoRelaySender.run(..., temporal_policy=)`；Task 2 的 `VideoRelayReceiver.run(..., reference_mode=)`；`create_receiver(backend=)`；`TemporalPolicyConfig`。
- Produces:
  - `video-sender` 新增 `--keyframe-interval`（默认 12）、`--prompts-json PATH`（预生成 prompt，不加载 VLM，与 `--prompt`/`--auto-prompt` 三选一）。`--keyframe-interval > 0` 时构造 `TemporalPolicyConfig(keyframe_interval, reference_mode="prev", keyframe_passthrough=True)` 传入。
  - `video-receiver` 新增 `--backend`（默认 `diffusers`，`Choice(["diffusers","klein"])`）、`--reference-mode`（默认 `None`，`Choice(["none","prev","keyframe","prev_keyframe"])`）。传入 `create_receiver(backend=)` 与 `run(reference_mode=)`。

- [ ] **Step 1: 更新既有断言 + 写 CLI 参数校验失败测试**

**先更新 2 个既有用例的断言**（Step 3 会把 prompt 校验消息改为三选一措辞，旧子串不再匹配，B1）——`tests/test_cli_video_relay.py`：

```python
# test_video_sender_requires_prompt_or_auto 内，原断言：
#   assert "必须指定 --prompt 或 --auto-prompt" in result.output
# 改为：
    assert "必须指定 --prompt / --auto-prompt / --prompts-json 之一" in result.output

# test_video_sender_prompt_and_auto_mutually_exclusive 内，原断言：
#   assert "不能同时使用" in result.output
# 改为：
    assert "只能指定一个" in result.output
```

**再追加新用例**：

```python
def test_video_sender_prompts_json_conflicts_with_prompt(tmp_path):
    src = tmp_path / "in.mp4"
    src.write_bytes(b"fake")
    runner = CliRunner()
    result = runner.invoke(
        video_sender,
        [
            "--input", str(src), "--relay-host", "127.0.0.1",
            "--prompt", "x", "--prompts-json", str(tmp_path / "p.json"),
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
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run pytest tests/test_cli_video_relay.py -v`
Expected: 3 个新测试 + 2 个刚更新断言的既有测试 FAIL（选项未定义 / 校验消息尚为旧措辞）；其余既有用例 PASS。

- [ ] **Step 3: 改 `video_sender.py`**

加选项与 prompt 三选一校验、`--prompts-json` 读取、`temporal_policy` 构造。在既有 `@click.option` 后追加：

```python
@click.option(
    "--prompts-json",
    "prompts_json",
    default=None,
    type=click.Path(exists=True, path_type=Path),
    help="从预生成 prompts.json 逐帧读取描述（不加载 VLM，供 loopback 测试）",
)
@click.option(
    "--keyframe-interval",
    default=12,
    type=int,
    help="关键帧间隔 N（每 N 帧一个关键帧透传整帧，默认 12；<=0 关闭时序退回逐帧）",
)
```

在函数签名加 `prompts_json`、`keyframe_interval` 形参。改 prompt 来源校验（三选一）与 `prompt_fn`：

```python
    sources = [prompt is not None, auto_prompt, prompts_json is not None]
    if sum(sources) == 0:
        raise click.UsageError("必须指定 --prompt / --auto-prompt / --prompts-json 之一")
    if sum(sources) > 1:
        raise click.UsageError(
            "--prompt / --auto-prompt / --prompts-json 只能指定一个"
        )
```

（删除原来只判 `--prompt` / `--auto-prompt` 的两处校验，换成上面这段。）

`prompt_fn` 分支加 `--prompts-json`（不加载 VLM）：

```python
    vlm_sender = None
    if auto_prompt:
        from semantic_transmission.sender.qwen_vl_sender import QwenVLSender

        vlm_sender = QwenVLSender(
            model_name=cfg.vlm_model_name,
            model_path=cfg.vlm_model_path or None,
        )

        def prompt_fn(index, frame):
            return vlm_sender.describe(frame).text
    elif prompts_json is not None:
        import json as _json

        payload = _json.loads(prompts_json.read_text(encoding="utf-8"))
        # prompts.json 的 frames: [{index, prompt?, passthrough?}]；关键帧无 prompt。
        by_index = {
            f["index"]: f.get("prompt", "") for f in payload.get("frames", [])
        }

        def prompt_fn(index, frame):
            return by_index.get(index, "")
    else:

        def prompt_fn(index, frame):
            return prompt
```

构造 `temporal_policy` 并传入 `sender.run`。在 import 处加 `TemporalPolicyConfig`，在 `sender.run(...)` 调用加参数：

```python
from semantic_transmission.pipeline.temporal_policy import TemporalPolicyConfig
```

```python
    temporal_policy = None
    if keyframe_interval > 0:
        temporal_policy = TemporalPolicyConfig(
            keyframe_interval=keyframe_interval,
            reference_mode="prev",
            keyframe_passthrough=True,
        )
    ...
        stats = sender.run(
            input_path,
            relay_host,
            relay_port,
            prompt_fn,
            seed=seed,
            fps=fps,
            save_frames_dir=save_frames_dir,
            temporal_policy=temporal_policy,
        )
```

- [ ] **Step 4: 改 `video_receiver.py`**

加 `--backend` / `--reference-mode` 选项与形参，传入 `create_receiver` 与 `run`：

```python
@click.option(
    "--backend",
    type=click.Choice(["diffusers", "klein"]),
    default="diffusers",
    help="接收端后端（时序补偿需 klein）",
)
@click.option(
    "--reference-mode",
    type=click.Choice(["none", "prev", "keyframe", "prev_keyframe"]),
    default=None,
    help="时序参考帧模式（仅 klein）。缺省：klein→prev，diffusers→无时序（逐帧）",
)
```

函数签名加 `backend`、`reference_mode`。函数体解析默认并门控（对齐单机 `video.py` 口径）：

```python
    if reference_mode is None:
        reference_mode = "prev" if backend == "klein" else None
    elif backend != "klein" and reference_mode != "none":
        raise click.UsageError("时序补偿仅 klein 后端支持（--backend klein）")
    # none 归一为 None（无时序，走无状态路径）
    if reference_mode == "none":
        reference_mode = None

    recv = create_receiver(backend=backend)
    receiver = VideoRelayReceiver(recv)
    try:
        result = receiver.run(
            relay_host, relay_port, output_path,
            timeout=timeout, reference_mode=reference_mode,
        )
```

- [ ] **Step 5: 运行测试确认通过**

Run: `uv run pytest tests/test_cli_video_relay.py -v`
Expected: 全部 PASS（含既有 4 个用例）。

- [ ] **Step 6: 回归 + lint**

Run: `uv run pytest -q && uv run ruff check . && uv run ruff format --check .`
Expected: 全绿。

- [ ] **Step 7: Commit**

```bash
git add src/semantic_transmission/cli/video_sender.py src/semantic_transmission/cli/video_receiver.py tests/test_cli_video_relay.py
git commit -m "feat: relay CLI 暴露时序参数

video-sender 加 --keyframe-interval / --prompts-json（预生成 prompt 不加载
VLM，供 loopback 测试），prompt 来源改三选一；video-sender 默认构造
prev-only 时序策略。video-receiver 加 --backend / --reference-mode，
klein 默认 prev、diffusers 无时序。"
```

---

## Task 4: 单机 loopback GPU 验收 + parity 校验 + 报告

> **需 GPU（RTX 5090）+ klein 模型就绪**，无法在 CI 跑；本任务为手动验收 runbook，产出验收报告。执行前先 `uv run semantic-tx check diffusers` 确认 klein 就绪。

**Files:**
- Create: `docs/test-reports/2026-07-08-relay-temporal-policy-report.md`
- Create（临时，可选）: `scripts/poc/relay_parity_compare.py`（逐帧对比脚本）

**Interfaces:**
- Consumes: Task 1–3 的 `video-sender` / `video-receiver` CLI；既有单机 `video --backend klein` 产出的 `prompts.json`。

- [ ] **Step 1: 预生成 prompts.json（复用或现跑）**

复用既有 klein 单机 run 的 `prompts.json`，或现跑一遍（约几分钟到几十分钟，取决于帧数）：

```bash
uv run semantic-tx video --input resources/<行车视频>.mp4 \
  --backend klein --reference-mode prev --keyframe-interval 12 \
  --auto-prompt --seed 0 --output output/klein_single/out.mp4
```

**`--seed 0` 必须显式指定**：`KleinReceiver.process` 在 `seed is None` 时随机取种子、不可复现；基线与 relay（Step 2 `--seed 0`）必须同 seed，否则 §6.3 parity 从根不成立（S2）。记下 `output/klein_single/prompts.json` 与 `output/klein_single/out.mp4`（作 parity 基线）。

- [ ] **Step 2: loopback 双进程跑时序 relay**

终端 A（接收端，先起监听）：

```bash
uv run semantic-tx video-receiver --backend klein --reference-mode prev \
  --relay-host 127.0.0.1 --relay-port 9000 \
  --output output/relay_temporal/out.mp4
```

终端 B（发送端，用预生成 prompt 不加载 VLM）：

```bash
uv run semantic-tx video-sender --input resources/<同一行车视频>.mp4 \
  --relay-host 127.0.0.1 --relay-port 9000 \
  --prompts-json output/klein_single/prompts.json \
  --keyframe-interval 12 --seed 0
```

Expected: 接收端打印 `完成：N/N 帧成功`，产出 `output/relay_temporal/out.mp4` 与 `receiver_summary.json`；发送端 `sender_summary.json` 含码率账本（`keyframe_bytes` / `generated_bytes`）。

- [ ] **Step 3: parity 逐帧对比**

写临时脚本 `scripts/poc/relay_parity_compare.py`，对比 relay 输出与单机基线的逐帧平均绝对差：

```python
"""relay 时序输出 vs 单机 klein 基线的逐帧 parity 对比。"""

import sys

import numpy as np

from semantic_transmission.common.video_io import read_frames


def main(a_path, b_path):
    a, _ = read_frames(a_path)
    b, _ = read_frames(b_path)
    assert len(a) == len(b), f"帧数不一致: {len(a)} vs {len(b)}"
    diffs = [
        float(np.mean(np.abs(x.astype("int16") - y.astype("int16"))))
        for x, y in zip(a, b)
    ]
    print(f"帧数={len(a)} 平均MAE={np.mean(diffs):.3f} 最大MAE={np.max(diffs):.3f}")
    print("逐帧 MAE:", [round(d, 2) for d in diffs])


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
```

```bash
uv run python scripts/poc/relay_parity_compare.py \
  output/relay_temporal/out.mp4 output/klein_single/out.mp4
```

Expected: 关键帧（透传）MAE≈0（PNG 无损，整帧往返精确）；生成帧因同 seed/prompt/policy/参考帧链应逐帧一致，平均 MAE 应极小（接近 0）。若生成帧 MAE 明显偏大，说明"切一刀"引入了偏差（如 canny 阈值不一致、prev 链错位），需排查。记录数值。

- [ ] **Step 4: 写验收报告**

`docs/test-reports/2026-07-08-relay-temporal-policy-report.md`，含：
- 目标与口径（loopback 等价验证双机时序 relay）
- 环境（GPU、klein 版本、视频规格）
- loopback 端到端结果（帧成功率、输出路径）
- **码率账本**：关键帧整帧总字节 vs 生成帧语义总字节、压缩率（引用 `sender_summary.json`）
- **parity 校验**：逐帧 MAE 表 + 结论（「切一刀没切错」）
- 已知局限：单机 loopback 非真机双机（VLM 与 klein 分机才能全流程 auto-prompt）；真机双机演示顺延

报告正文用 Mermaid 画数据流（复用 spec §3 时序图）。

- [ ] **Step 5: 清理临时脚本（可选）并 Commit**

```bash
git add docs/test-reports/2026-07-08-relay-temporal-policy-report.md
# 若保留对比脚本：git add scripts/poc/relay_parity_compare.py
git commit -m "docs: 阶段3(二) relay 时序策略 loopback 验收报告

单机 loopback 双进程验证时序 relay：关键帧整帧透传 + 生成帧语义码流，
含码率账本与 vs 单机 klein 基线的 parity 逐帧对比。补 M1 遗留双机 relay
视频演示（loopback 口径）。"
```

---

## Task 5: 更新 ROADMAP 阶段三进展

**Files:**
- Modify: `docs/ROADMAP.md`（阶段三「klein 目标版主线进展」小节 + 「下一步」）

**Interfaces:** 无代码接口，纯文档。

- [ ] **Step 1: 更新 ROADMAP**

在 `docs/ROADMAP.md` 阶段三「klein 目标版主线进展（2026-07）」列表追加一条阶段 3（二）已完成项，并把第 144 行「下一步 = 阶段 3（二）」改为指向阶段 3（三）或后续项（RIFE 插帧 / 流式 I/O）。追加条目示例：

```markdown
- ✅ **阶段 3（二）时序策略接入 relay 双机协议**（本 PR）：`video-sender`/`video-receiver`
  接入时序策略——关键帧低频整帧传输 + 生成帧走语义码流（`frame_type` 随包过线、
  状态留接收端），限定 `keyframe_passthrough=True`。单机 loopback 双进程验收通过、
  含码率账本与 vs 单机 klein 基线的 parity 校验（补 M1 遗留双机 relay 视频演示，
  loopback 口径）。报告见 [`docs/test-reports/2026-07-08-relay-temporal-policy-report.md`]。
```

把「下一步」改为：

```markdown
**下一步**：真机双机 relay 演示（需两台机器，全流程 auto-prompt）；RIFE 插帧 / 超分 / 流式 I/O（DLSS 式实时分层，ROADMAP 中期项）。
```

- [ ] **Step 2: Commit**

```bash
git add docs/ROADMAP.md
git commit -m "docs: ROADMAP 阶段三补阶段3(二) relay 时序策略接入完成"
```

---

## Self-Review 记录

- **Spec 覆盖**：§2 架构（Task 1/2）、§3 数据流（Task 2 `_run_temporal`）、§4 协议 frame_type 复用（Task 1/2）、§5.1 收发端改动（Task 1/2）、§5.2/5.3 CLI（Task 3）、§6.1 单测（Task 1/2/3）、§6.2 loopback（Task 4）、§6.3 parity（Task 4）、§6.4 报告（Task 4）。§7 风险已在 Global Constraints + Task 4 局限体现。§8 非目标不实现。
- **对 spec 的收紧**：relay 时序路径限定 `keyframe_passthrough=True`，不暴露 `--no-keyframe-passthrough`（见 Global Constraints，理由：接收端对生成帧无原始整帧，非透传关键帧破坏 last_kf 锚点，且违背整帧传输前提）。
- **类型一致性**：`temporal_policy`（Task 1/3）、`reference_mode: str | None`（Task 2/3）、`frame_type ∈ {"keyframe","generated"}`（Task 1 产出 / Task 2 消费）、`BatchResult.keyframe_count/generated_frames/keyframe_indices`（复用既有字段）贯穿一致。
- **无占位符**：各步含完整代码与命令。

### 对抗性审核修正（2026-07-08，独立 subagent）

- **B1**：Task 3 改 prompt 校验消息为三选一措辞会破坏现有 2 个 CLI 测试断言 → Step 1 显式加"更新既有断言"，Step 2 Expected 同步。
- **B2**：Task 2 stub `_RefRecordingReceiver` 返回 512×384 与 64×48 关键帧混合尺寸使 `write_frames` 抛 `ValueError` → 改返回 64×48。
- **S1**：Task 1 提前导入 `build_reference_images` 触发 ruff F401 → 移到 Task 2 首次使用处导入。
- **S2**：Task 4 parity 基线未固定 seed（klein 随机种子不可复现）→ 基线命令加 `--seed 0`。
- **S3**：发送端未落实 `keyframe_passthrough` 守卫 → `run` 入口 fail-fast 断言 `keyframe_passthrough=True`，补守卫测试。
- **N1/N2**：spec §4 向后兼容措辞澄清（时序路径要求带标签，兼容由无状态路径承担）；Task 1 Files 头去掉自相矛盾的"新增 `_encode_rgb_png`"。
- **已验证 OK（审核确认无需改）**：能力门控时机、stub 抽象契约、prev 链/锚点语义与单机对称、协议零改动、单 TCP 有序性、接口签名逐字一致、`to_dict` 向后兼容。
