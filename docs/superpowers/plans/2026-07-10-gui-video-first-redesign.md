# GUI 视频优先重构 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 Gradio GUI 从图像级 6 面板重构为视频优先，补齐单机 `video→video` 演示面板与双机 relay 视频面板，图像能力压缩为单 Tab。

**Architecture:** 单机与双机接收端**同构**——都用「后台 daemon 线程跑阻塞的 `run()` + `queue` 回传进度 + `gr.Timer` 轮询刷新」。这是因为 Gradio 事件生成器无法从内部同步阻塞调用里转发 `progress_callback`。三个编排 `run` 新增可选 `progress_callback`（分派到 `_run_temporal` 时必须透传）；`VideoRelayReceiver` 加 `stop()` 支持 GUI 中断。图像面板压缩为单 Tab（Accordion 收纳核心 3 面板）。

**Tech Stack:** Python ≥3.10、Gradio 6.x（本仓库实测 6.10.0，`gr.Timer(...).tick(...)` 可用）、click、Diffusers/klein 接收端、pytest + unittest.mock。

## Global Constraints

- 所有 Python 操作走 `uv`：`uv run pytest`、`uv run ruff check .`、`uv run ruff format --check .`（禁止裸 `python`/`pytest`/`ruff`）
- CI lint 范围是整个项目（`.`），推送前本地必须 `uv run ruff check .` 与 `uv run ruff format --check .` 全绿
- `gr.Video` 回调收到/输出**文件路径字符串**；`gr.Image` 默认 `type="numpy"`，需路径时显式 `type="filepath"`
- **跨线程 `gr.State`**：Gradio 6.10 的 `state_holder` 按引用存取 state（不 deepcopy 运行时值），故后台线程修改的 state dict 与轮询回调读到的是**同一对象**——本 plan 的线程+队列+state 模式依赖此实现细节，升级 Gradio 大版本时需复验
- GUI 单测只测**纯函数/状态机逻辑**（用 `MagicMock`/`monkeypatch`），不测 Gradio UI 渲染——与现有 `tests/test_gui_*_panel.py` 范式一致
- commit message 用中文、遵循 Angular 约定，不含工具生成标记与 Co-Authored 声明
- `progress_callback` 统一签名 `Callable[[int, int, dict], None]`，参数 `(index, total, info)`；不传时行为与现状逐字节兼容
- **分派透传铁律**：`VideoPipeline.run` / `VideoRelayReceiver.run` 在时序参数非空时分派到 `_run_temporal`，分派调用**必须**带上 `progress_callback=progress_callback`，否则 klein 默认时序（主路径）进度全丢
- **实现分支**：代码改动在**新分支** `feature/gui-video-first-redesign`（从 `main` 切出）；规划文档（ROADMAP/spec/plan）留在 `docs/roadmap-phase3-gui-sync`（PR #70）

---

## 文件结构

**Phase A：架构重排 + 图像压缩 + 单机视频面板（后台线程架构）**
- 删除：`gui/batch_sender_panel.py`、`gui/batch_panel.py`、`tests/test_gui_batch_panel.py`
- 修改：`gui/app.py`（Tab 视频优先重排、图像工具 Tab 用 Accordion 收纳核心 3 面板）
- 修改：`pipeline/video_pipeline.py`（`run`/`_run_temporal` 加 `progress_callback` + 分派透传）
- 修改：`tests/test_video_pipeline.py`
- 创建：`gui/video_panel.py`（单机视频面板：纯逻辑 + 线程状态机 + 组装）
- 创建：`tests/test_gui_video_panel.py`

**Phase B：双机面板 + relay 进度接口 + 可中断**
- 修改：`pipeline/video_relay.py`（`VideoRelaySender.run`、`VideoRelayReceiver.run`/`_run_temporal` 加 `progress_callback` + 分派透传；`VideoRelayReceiver` 加 `self._relay` + `stop()`）
- 修改：`tests/test_video_relay.py`
- 创建：`gui/video_relay_panel.py`（双机面板：发送端 + 接收端监听状态机 + 组装）
- 创建：`tests/test_gui_video_relay_panel.py`
- 修改：`gui/app.py`（接入双机 Tab）、`docs/gui-design.md`（同步新架构）

---

# Phase A — 架构重排 + 单机视频面板

## Task A1: 图像 Tab 压缩 + 视频优先骨架

**Files:**
- Delete: `gui/batch_sender_panel.py`、`gui/batch_panel.py`、`tests/test_gui_batch_panel.py`
- Modify: `gui/app.py`

**Interfaces:**
- Produces: `create_app(project_config=None) -> gr.Blocks`，Tab 顺序 配置 / 视频流演示(占位) / 双机视频(占位) / 图像工具

- [ ] **Step 1: 删除批量面板与其测试**

```bash
git rm src/semantic_transmission/gui/batch_sender_panel.py \
       src/semantic_transmission/gui/batch_panel.py \
       tests/test_gui_batch_panel.py
```

- [ ] **Step 2: 重写 app.py 的 Tab 装配**

`create_app` 内 `with gr.Tabs():` 块替换为（视频 Tab 先占位，A6/B5 填充）：

```python
        with gr.Tabs():
            with gr.TabItem("⚙ 配置"):
                config_components = build_config_tab(config)

            with gr.TabItem("◈ 视频流演示"):
                gr.Markdown("_单机 video→video 面板（Task A6 接入）_")

            with gr.TabItem("⇄ 双机视频"):
                gr.Markdown("_双机 relay 视频面板（Task B5 接入）_")

            with gr.TabItem("🖼 图像工具（单帧）"):
                gr.Markdown("### 图像工具（单帧）\n单帧图像的端到端演示、发送与接收，供调试/对照。")
                with gr.Accordion("端到端演示", open=True):
                    build_pipeline_tab(config_components, config)
                with gr.Accordion("单张发送", open=False):
                    sender_components = build_sender_tab(config_components, config)
                with gr.Accordion("接收端队列", open=False):
                    receiver_components = build_receiver_tab(config_components)
```

删除文件顶部 `build_batch_tab`、`build_batch_sender_tab` 两个 import。跨 Tab 联动块（`sender_components["send_to_receiver_btn"].click(...)`）保持不变。

- [ ] **Step 3: 冒烟**

Run: `uv run python -c "from semantic_transmission.gui.app import create_app; create_app(); print('tabs ok')"`
Expected: 打印 `tabs ok`

- [ ] **Step 4: lint**

Run: `uv run ruff check src/semantic_transmission/gui/app.py && uv run ruff format --check src/semantic_transmission/gui/app.py`
Expected: 无错误

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "refactor(gui): Tab 视频优先重排，图像面板压缩为单 Tab 保留核心 3 个"
```

---

## Task A2: 单机面板纯逻辑（卸载 + prompt_fn）

**Files:**
- Create: `gui/video_panel.py`、`tests/test_gui_video_panel.py`

**Interfaces:**
- Produces:
  - `unload_video_receiver(receiver: BaseReceiver | None) -> tuple[BaseReceiver | None, str]`
  - `build_video_prompt_fn(mode: str, prompt: str | None, vlm_sender) -> Callable[[int, object], str]`

- [ ] **Step 1: 写失败测试**

`tests/test_gui_video_panel.py`：

```python
from unittest.mock import MagicMock
import numpy as np
from semantic_transmission.gui.video_panel import (
    unload_video_receiver,
    build_video_prompt_fn,
)


class TestUnloadVideoReceiver:
    def test_none_returns_message(self):
        result, status = unload_video_receiver(None)
        assert result is None and "无已加载" in status

    def test_calls_unload_and_clears(self):
        receiver = MagicMock()
        result, status = unload_video_receiver(receiver)
        receiver.unload.assert_called_once()
        assert result is None and "已卸载" in status

    def test_swallows_unload_exception(self):
        receiver = MagicMock()
        receiver.unload.side_effect = RuntimeError("boom")
        result, status = unload_video_receiver(receiver)
        assert result is None and "boom" in status


class TestBuildVideoPromptFn:
    def test_manual_returns_same_prompt(self):
        fn = build_video_prompt_fn("manual", "a cat", None)
        z = np.zeros((4, 4, 3), dtype=np.uint8)
        assert fn(0, z) == "a cat" and fn(5, z) == "a cat"

    def test_manual_none_prompt_returns_empty(self):
        fn = build_video_prompt_fn("manual", None, None)
        assert fn(0, np.zeros((4, 4, 3), dtype=np.uint8)) == ""

    def test_auto_calls_vlm_describe(self):
        vlm = MagicMock()
        vlm.describe.return_value = MagicMock(text="auto desc")
        fn = build_video_prompt_fn("auto", None, vlm)
        assert fn(2, np.zeros((4, 4, 3), dtype=np.uint8)) == "auto desc"
        vlm.describe.assert_called_once()
```

- [ ] **Step 2: 运行确认失败**

Run: `uv run pytest tests/test_gui_video_panel.py -v`
Expected: FAIL（`ModuleNotFoundError: video_panel`）

- [ ] **Step 3: 写最小实现**

`src/semantic_transmission/gui/video_panel.py`：

```python
"""视频流演示 Tab（单机 video→video）：后台线程 + queue + gr.Timer 轮询。

Gradio 生成器无法从内部同步阻塞的 VideoPipeline.run() 转发进度，故与双机接收端
同构：daemon 线程跑 run(progress_callback=写队列)，gr.Timer 轮询刷新。
"""

from __future__ import annotations

from typing import Callable

from semantic_transmission.receiver.base import BaseReceiver


def unload_video_receiver(
    receiver: BaseReceiver | None,
) -> tuple[BaseReceiver | None, str]:
    """显式卸载 receiver 释放显存；失败也清空 state。"""
    if receiver is None:
        return None, "当前无已加载模型"
    try:
        unload = getattr(receiver, "unload", None)
        if callable(unload):
            unload()
        return None, "Receiver 模型已卸载"
    except Exception as e:
        return None, f"卸载过程出错：{e}"


def build_video_prompt_fn(
    mode: str, prompt: str | None, vlm_sender
) -> Callable[[int, object], str]:
    """构造逐帧 prompt 函数：auto→VLM 描述每帧；manual→整段共用。"""
    if mode == "auto":

        def _auto(index, frame):
            return vlm_sender.describe(frame).text

        return _auto

    text = prompt or ""

    def _manual(index, frame):
        return text

    return _manual
```

- [ ] **Step 4: 运行确认通过**

Run: `uv run pytest tests/test_gui_video_panel.py -v`
Expected: PASS（6 passed）

- [ ] **Step 5: Commit**

```bash
git add src/semantic_transmission/gui/video_panel.py tests/test_gui_video_panel.py
git commit -m "feat(gui): 单机视频面板卸载与 prompt_fn 构造纯逻辑"
```

---

## Task A3: `VideoPipeline` 进度回调 + 分派透传

**Files:**
- Modify: `pipeline/video_pipeline.py`、`tests/test_video_pipeline.py`

**Interfaces:**
- Produces: `VideoPipeline.run(..., progress_callback: Callable[[int, int, dict], None] | None = None)`；`_run_temporal` 同参。无状态路径在 `frame_inputs` 构造循环内每帧回调 `(i, total, {"stage": "encode"})`；`run` 分派到 `_run_temporal` 时透传 `progress_callback`；`_run_temporal` 生成串行循环内每帧回调 `(idx, n, {"stage": "generate"})`

- [ ] **Step 1: 写失败测试（自足：monkeypatch read_frames，mock receiver/extractor）**

追加到 `tests/test_video_pipeline.py`：

```python
from types import SimpleNamespace
from unittest.mock import MagicMock
import numpy as np
from PIL import Image


def _patch_io(monkeypatch, n):
    frames = [np.zeros((8, 8, 3), dtype=np.uint8) for _ in range(n)]
    meta = SimpleNamespace(fps=30.0)
    monkeypatch.setattr(
        "semantic_transmission.pipeline.video_pipeline.read_frames",
        lambda p: (frames, meta),
    )
    monkeypatch.setattr(
        "semantic_transmission.pipeline.video_pipeline.write_frames",
        lambda *a, **k: None,
    )
    return frames


def test_run_stateless_progress_callback_per_frame(monkeypatch, tmp_path):
    from semantic_transmission.pipeline.video_pipeline import VideoPipeline
    from semantic_transmission.pipeline.batch_processor import BatchResult

    _patch_io(monkeypatch, 3)
    receiver = MagicMock()
    out = MagicMock()
    out.images = [Image.new("RGB", (8, 8)) for _ in range(3)]
    out.stats = BatchResult(total=3, success=3)
    receiver.process_batch.return_value = out
    extractor = MagicMock()
    extractor.extract.return_value = np.zeros((8, 8, 3), dtype=np.uint8)

    calls = []
    VideoPipeline(receiver, extractor).run(
        "in.mp4", str(tmp_path / "o.mp4"), lambda i, f: "p",
        progress_callback=lambda i, t, info: calls.append((i, t)),
    )
    assert [c[0] for c in calls] == [0, 1, 2]
    assert all(c[1] == 3 for c in calls)


def test_run_passes_callback_to_temporal(monkeypatch, tmp_path):
    from semantic_transmission.pipeline.video_pipeline import VideoPipeline
    from semantic_transmission.pipeline.temporal_policy import TemporalPolicyConfig

    pipe = VideoPipeline(MagicMock(), MagicMock())
    captured = {}
    monkeypatch.setattr(
        pipe, "_run_temporal",
        lambda *a, **k: captured.update(k) or MagicMock(),
    )
    cb = lambda i, t, info: None
    pipe.run(
        "in.mp4", str(tmp_path / "o.mp4"), lambda i, f: "p",
        temporal_policy=TemporalPolicyConfig(keyframe_interval=12, reference_mode="prev"),
        progress_callback=cb,
    )
    assert captured.get("progress_callback") is cb
```

- [ ] **Step 2: 运行确认失败**

Run: `uv run pytest tests/test_video_pipeline.py -k "progress or temporal_passes or callback" -v`
Expected: FAIL（`run()` 不接受 `progress_callback`）

- [ ] **Step 3: 实现**

`run` 与 `_run_temporal` 签名末尾各加 `progress_callback: Callable[[int, int, dict], None] | None = None`（`Callable` 已在文件 import）。

无状态 `run` 的 `frame_inputs` 构造循环末尾（`video_pipeline.py:250` 后）加：

```python
            if progress_callback is not None:
                progress_callback(i, len(frames), {"stage": "encode"})
```

`run` 分派到 `_run_temporal` 处（`video_pipeline.py:222-231`）补 `progress_callback=progress_callback`：

```python
            return self._run_temporal(
                input_path, output_path, prompt_fn, temporal_policy,
                seed=seed, fps=fps, on_prompts_ready=on_prompts_ready,
                save_artifacts_to=save_artifacts_to,
                progress_callback=progress_callback,
            )
```

`_run_temporal` 生成串行循环内每帧完成后加 `progress_callback(idx, n, {"stage": "generate"})`（回调为 None 时跳过）。

- [ ] **Step 4: 运行确认通过**

Run: `uv run pytest tests/test_video_pipeline.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/semantic_transmission/pipeline/video_pipeline.py tests/test_video_pipeline.py
git commit -m "feat(pipeline): VideoPipeline 进度回调 + 分派透传到时序路径"
```

---

## Task A4: 单机面板后台线程状态机

**Files:**
- Modify: `gui/video_panel.py`、`tests/test_gui_video_panel.py`

**Interfaces:**
- Produces:
  - `start_video(state, video_path, backend, mode, prompt, ref_mode, kf_interval, kf_passthrough, seed, fps, project_config) -> tuple[dict, str]`
  - `poll_video(state) -> tuple[str, str | None, list, str]`（进度文本 / 输出视频路径 / 统计行 / 日志）
  - state dict 键：`{"thread","receiver","progress_q","result","error","done"}`；`result` 为 `{"out_path","stats"}`

- [ ] **Step 1: 写失败测试（不起真实模型/GPU，只验证 guard 与轮询状态机）**

追加：

```python
from unittest.mock import patch
import queue as _q
from semantic_transmission.gui.video_panel import start_video, poll_video


def test_start_video_empty_path_no_thread():
    with patch("semantic_transmission.gui.video_panel.threading.Thread") as T:
        state, status = start_video(
            {}, None, "klein", "manual", "x", "prev", 12, True, None, None, MagicMock()
        )
        assert "请先上传" in status
        T.assert_not_called()


def test_start_video_rejects_when_running():
    alive = MagicMock()
    alive.is_alive.return_value = True
    state, status = start_video(
        {"thread": alive}, "in.mp4", "klein", "manual", "x", "prev", 12, True, None, None, MagicMock()
    )
    assert "已在运行" in status


def test_poll_video_progress_then_done():
    q = _q.Queue()
    q.put((0, 3, {}))
    q.put((1, 3, {}))
    state = {"progress_q": q, "done": False, "error": None, "result": None}
    text, out, rows, log = poll_video(state)
    assert "2/3" in text and out is None

    state2 = {
        "progress_q": _q.Queue(), "done": True, "error": None,
        "result": {"out_path": "o.mp4", "stats": {"total": 3, "success": 3,
                   "keyframe_count": 1, "generated_frames": 2}},
    }
    text2, out2, rows2, log2 = poll_video(state2)
    assert out2 == "o.mp4"
    assert ["总帧数", "3"] in rows2


def test_poll_video_error():
    state = {"progress_q": _q.Queue(), "done": True, "error": "boom", "result": None}
    text, out, rows, log = poll_video(state)
    assert "boom" in text and out is None
```

> 断言口径：`poll_video` 排空队列后取最后一项 `(1,3)` → 文本 `f"生成中 {1+1}/3"` = `"生成中 2/3"`。测试与实现以此为准。

- [ ] **Step 2: 运行确认失败**

Run: `uv run pytest tests/test_gui_video_panel.py -k "start_video or poll_video" -v`
Expected: FAIL（未定义）

- [ ] **Step 3: 实现**

`video_panel.py` 顶部补 import：

```python
import queue
import tempfile
import threading
import time
from pathlib import Path

from semantic_transmission.common.config import ProjectConfig
from semantic_transmission.pipeline.temporal_policy import (
    TemporalPolicyConfig,
    resolve_reference_mode,
)
from semantic_transmission.pipeline.video_pipeline import VideoPipeline
from semantic_transmission.receiver import create_receiver
from semantic_transmission.sender.local_condition_extractor import LocalCannyExtractor
```

```python
def start_video(
    state, video_path, backend, mode, prompt, ref_mode,
    kf_interval, kf_passthrough, seed, fps, project_config: ProjectConfig,
):
    """起后台线程跑 VideoPipeline.run，进度写队列；receiver 经 state 跨次复用。"""
    state = state or {}
    if not video_path:
        return state, "错误：请先上传视频"
    if state.get("thread") is not None and state["thread"].is_alive():
        return state, "已在运行中，请等待完成"

    # H2 防崩：非 klein 后端强制无时序，避免 resolve_reference_mode 抛错
    if backend != "klein":
        ref_mode = "none"
    resolved = resolve_reference_mode(backend, None if ref_mode == "none" else ref_mode)
    policy = None
    if resolved is not None:
        policy = TemporalPolicyConfig(
            keyframe_interval=int(kf_interval),
            reference_mode=resolved,
            keyframe_passthrough=bool(kf_passthrough),
        )

    progress_q: "queue.Queue" = queue.Queue()
    new_state = {
        "thread": None, "receiver": state.get("receiver"),
        "progress_q": progress_q, "result": None, "error": None, "done": False,
    }
    out_path = str(Path(tempfile.mkdtemp()) / "out.mp4")
    extractor = LocalCannyExtractor(
        threshold1=project_config.canny_low_threshold,
        threshold2=project_config.canny_high_threshold,
    )

    def _worker():
        vlm_sender = None
        try:
            if mode == "auto":
                from semantic_transmission.sender.qwen_vl_sender import QwenVLSender

                vlm_sender = QwenVLSender(
                    model_name=project_config.vlm_model_name,
                    model_path=project_config.vlm_model_path or None,
                )
            prompt_fn = build_video_prompt_fn(mode, prompt, vlm_sender)
            receiver = new_state["receiver"]
            if receiver is None:
                receiver = create_receiver(backend=backend)
                new_state["receiver"] = receiver
            t0 = time.time()
            stats = VideoPipeline(receiver, extractor).run(
                video_path, out_path, prompt_fn,
                seed=(int(seed) if seed not in (None, "") else None),
                fps=(float(fps) if fps not in (None, "") else None),
                on_prompts_ready=(vlm_sender.unload if vlm_sender is not None else None),
                temporal_policy=policy,
                progress_callback=lambda i, t, info: progress_q.put((i, t, info)),
            )
            d = stats.to_dict()
            d["_elapsed"] = time.time() - t0
            new_state["result"] = {"out_path": out_path, "stats": d}
        except Exception as e:
            new_state["error"] = str(e)
        finally:
            if vlm_sender is not None:
                try:
                    vlm_sender.unload()
                except Exception:
                    pass
            new_state["done"] = True

    t = threading.Thread(target=_worker, daemon=True)
    new_state["thread"] = t
    t.start()
    return new_state, f"已开始生成（backend={backend}）"


def poll_video(state):
    """轮询进度队列，返回 (进度文本, 输出视频或None, 统计行, 日志)。"""
    if not state:
        return "未运行", None, [], ""
    q = state.get("progress_q")
    last = None
    if q is not None:
        while not q.empty():
            last = q.get()
    if state.get("error"):
        return f"失败：{state['error']}", None, [], state["error"]
    if state.get("done") and state.get("result") is not None:
        d = state["result"]["stats"]
        rows = [
            ["总帧数", str(d.get("total"))],
            ["成功帧", str(d.get("success"))],
            ["关键帧数", str(d.get("keyframe_count"))],
            ["生成帧数", str(d.get("generated_frames"))],
            ["总耗时", f"{d.get('_elapsed', 0):.1f}s"],
        ]
        return "完成", state["result"]["out_path"], rows, "生成完成\n"
    if last is not None:
        return f"生成中 {last[0] + 1}/{last[1]}", None, [], ""
    return "准备/加载模型中...", None, [], ""
```

- [ ] **Step 4: 运行确认通过**

Run: `uv run pytest tests/test_gui_video_panel.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/semantic_transmission/gui/video_panel.py tests/test_gui_video_panel.py
git commit -m "feat(gui): 单机视频面板后台线程状态机（start_video/poll_video）"
```

---

## Task A5: 单机面板质量评估

**Files:**
- Modify: `gui/video_panel.py`、`tests/test_gui_video_panel.py`

**Interfaces:**
- Produces: `run_video_evaluation(input_video, output_video) -> tuple[list[list[str]], str]`；默认 `with_clip=False`（无逐帧 prompt，CLIP 恒空故不列）

- [ ] **Step 1: 写失败测试**

追加：

```python
from semantic_transmission.gui.video_panel import run_video_evaluation


class TestRunVideoEvaluation:
    def test_missing_inputs_returns_error(self):
        rows, log = run_video_evaluation(None, None)
        assert rows == [] and "需要" in log

    def test_summary_rows_no_clip_column(self):
        fake_report = {"summary": {
            "psnr": {"mean": 15.0, "count": 2},
            "ssim": {"mean": 0.75, "count": 2},
            "lpips": {"mean": 0.45, "count": 2},
        }}
        with patch(
            "semantic_transmission.gui.video_panel.read_frames",
            return_value=([1, 2], MagicMock()),
        ), patch(
            "semantic_transmission.gui.video_panel.evaluate_video",
            return_value=fake_report,
        ) as ev:
            rows, log = run_video_evaluation("in.mp4", "out.mp4")
        # with_clip 默认 False，不列 CLIP
        assert ev.call_args.kwargs.get("with_clip") is False
        assert ["PSNR", "15.0000"] in rows
        assert all(r[0] != "CLIP" for r in rows)
        assert "评估完成" in log
```

- [ ] **Step 2: 运行确认失败**

Run: `uv run pytest tests/test_gui_video_panel.py::TestRunVideoEvaluation -v`
Expected: FAIL（未定义）

- [ ] **Step 3: 实现**

顶部补：

```python
from semantic_transmission.common.video_io import read_frames
from semantic_transmission.evaluation.video_eval import evaluate_video
```

```python
def run_video_evaluation(input_video, output_video) -> tuple[list, str]:
    """输入视频 vs 输出视频逐帧评估（PSNR/SSIM/LPIPS）。

    CLIP 需逐帧 prompt（evaluate_video 的 with_clip 门控要求 prompts），单机路径
    未透出逐帧 prompt，故 with_clip=False、不列恒空的 CLIP 列。
    """
    if not input_video or not output_video:
        return [], "错误：需要先完成一次视频生成（缺输入或输出视频）\n"
    orig, _ = read_frames(input_video)
    rest, _ = read_frames(output_video)
    report = evaluate_video(orig, rest, with_lpips=True, with_clip=False)
    summary = report["summary"]
    label = {"psnr": "PSNR", "ssim": "SSIM", "lpips": "LPIPS"}
    rows = []
    for key, name in label.items():
        mean = summary.get(key, {}).get("mean")
        rows.append([name, f"{mean:.4f}" if mean is not None else "—"])
    return rows, "质量评估完成\n"
```

- [ ] **Step 4: 运行确认通过**

Run: `uv run pytest tests/test_gui_video_panel.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/semantic_transmission/gui/video_panel.py tests/test_gui_video_panel.py
git commit -m "feat(gui): 单机视频面板质量评估 run_video_evaluation（PSNR/SSIM/LPIPS）"
```

---

## Task A6: 单机 Tab 组装（线程 + gr.Timer）+ 接入 app.py

**Files:**
- Modify: `gui/video_panel.py`、`gui/app.py`

**Interfaces:**
- Produces: `build_video_tab(config_components: dict, project_config=None) -> dict`

- [ ] **Step 1: 实现 `build_video_tab`（Gradio 组装，无自动化测试——遵循 GUI 组装不 TDD 的既有范式）**

顶部补 `import gradio as gr`、`from semantic_transmission.common.config import load_config`。追加：

```python
def build_video_tab(config_components: dict, project_config=None) -> dict:
    """单机 video→video 演示 Tab（后台线程 + gr.Timer 轮询）。"""
    config = project_config if project_config is not None else load_config()
    gr.Markdown("### 视频流演示（单机）\n上传视频，逐帧语义还原为 video→video 闭环。")

    run_state = gr.State(value={})

    with gr.Row():
        with gr.Column(scale=1):
            video_input = gr.Video(label="输入视频")
            backend_radio = gr.Radio(
                choices=[("klein（关键帧主线）", "klein"), ("diffusers（Z-Image 备选）", "diffusers")],
                value="klein", label="接收端后端",
            )
        with gr.Column(scale=1):
            mode_radio = gr.Radio(
                choices=[("VLM 自动生成", "auto"), ("手动输入", "manual")],
                value="manual", label="描述模式",
            )
            prompt_input = gr.Textbox(label="描述文本（整段共用）", lines=2)
            ref_mode = gr.Dropdown(
                choices=["none", "prev", "keyframe", "prev_keyframe"],
                value="prev", label="参考帧模式（仅 klein）",
            )
            with gr.Row():
                kf_interval = gr.Number(value=12, precision=0, label="关键帧间隔 N")
                kf_passthrough = gr.Checkbox(value=True, label="关键帧透传")
            with gr.Row():
                seed_input = gr.Number(label="随机种子", precision=0, value=None)
                fps_input = gr.Number(label="输出帧率（空=沿用）", value=None)

    with gr.Row():
        run_btn = gr.Button("▶ 运行", variant="primary")
        unload_btn = gr.Button("卸载 Receiver 模型", variant="secondary")
    unload_status = gr.Markdown("")

    progress_box = gr.Textbox(label="进度", interactive=False)
    video_output = gr.Video(label="输出视频", interactive=False)
    stats_table = gr.Dataframe(headers=["指标", "值"], interactive=False)
    timer = gr.Timer(value=1.5, active=True)

    with gr.Accordion("质量评估（可选）", open=False):
        eval_btn = gr.Button("运行质量评估", variant="secondary")
        eval_table = gr.Dataframe(headers=["指标", "值"], interactive=False)
        eval_log = gr.Textbox(label="评估日志", lines=3, interactive=False)

    with gr.Accordion("运行日志", open=False):
        log_output = gr.Textbox(label="详细日志", lines=6, interactive=False)

    # backend 门控（H2）：diffusers 时禁用并把 ref_mode 值置 none
    def _toggle(b):
        on = b == "klein"
        return (
            gr.update(interactive=on, value=("prev" if on else "none")),
            gr.update(interactive=on),
            gr.update(interactive=on),
        )

    backend_radio.change(_toggle, inputs=backend_radio, outputs=[ref_mode, kf_interval, kf_passthrough])
    mode_radio.change(
        lambda m: gr.update(visible=(m == "manual")), inputs=mode_radio, outputs=prompt_input
    )

    def _start_bound(state, vp, backend, mode, prompt, rm, ki, kp, seed, fps):
        return start_video(state, vp, backend, mode, prompt, rm, ki, kp, seed, fps, config)

    run_btn.click(
        _start_bound,
        inputs=[run_state, video_input, backend_radio, mode_radio, prompt_input,
                ref_mode, kf_interval, kf_passthrough, seed_input, fps_input],
        outputs=[run_state, progress_box],
    )
    timer.tick(
        poll_video, inputs=[run_state],
        outputs=[progress_box, video_output, stats_table, log_output],
    )

    def _unload_bound(state):
        state = state or {}
        _, msg = unload_video_receiver(state.get("receiver"))
        state["receiver"] = None
        return state, msg

    unload_btn.click(_unload_bound, inputs=[run_state], outputs=[run_state, unload_status])
    eval_btn.click(
        run_video_evaluation, inputs=[video_input, video_output], outputs=[eval_table, eval_log]
    )
    return {}
```

- [ ] **Step 2: 接入 app.py**

顶部补 `from semantic_transmission.gui.video_panel import build_video_tab`。把「◈ 视频流演示」占位替换为：

```python
            with gr.TabItem("◈ 视频流演示"):
                build_video_tab(config_components, config)
```

- [ ] **Step 3: 冒烟 + 回归 + lint**

Run: `uv run python -c "from semantic_transmission.gui.app import create_app; create_app(); print('ok')"`
Expected: `ok`
Run: `uv run pytest tests/test_gui_video_panel.py tests/test_gui_pipeline_panel.py tests/test_gui_receiver_panel.py tests/test_video_pipeline.py -v`
Expected: PASS
Run: `uv run ruff check . && uv run ruff format --check .`
Expected: 无错误

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "feat(gui): 单机视频流演示 Tab 组装（线程+Timer）并接入应用"
```

---

# Phase B — 双机面板 + relay 进度接口 + 可中断

## Task B1: `VideoRelaySender` 进度回调

**Files:**
- Modify: `pipeline/video_relay.py`、`tests/test_video_relay.py`

**Interfaces:**
- Produces: `VideoRelaySender.run(..., progress_callback=None)`，逐帧发包后回调 `(i, total, {"frame_type": ...})`

- [ ] **Step 1: 写失败测试（自足：monkeypatch read_frames 与 SocketRelaySender）**

追加到 `tests/test_video_relay.py`：

```python
from types import SimpleNamespace
from unittest.mock import MagicMock
import numpy as np


class _FakeRelay:
    def __init__(self, *a, **k):
        pass
    def __enter__(self):
        return self
    def __exit__(self, *a):
        return False
    def send(self, packet):
        pass


def test_sender_progress_callback_per_frame(monkeypatch):
    from semantic_transmission.pipeline.video_relay import VideoRelaySender

    frames = [np.zeros((8, 8, 3), dtype=np.uint8) for _ in range(3)]
    monkeypatch.setattr(
        "semantic_transmission.pipeline.video_relay.read_frames",
        lambda p: (frames, SimpleNamespace(fps=30.0)),
    )
    monkeypatch.setattr(
        "semantic_transmission.pipeline.video_relay.SocketRelaySender", _FakeRelay
    )
    extractor = MagicMock()
    extractor.extract.return_value = np.zeros((8, 8, 3), dtype=np.uint8)

    calls = []
    VideoRelaySender(extractor).run(
        "in.mp4", "127.0.0.1", 9000, lambda i, f: "p",
        progress_callback=lambda i, t, info: calls.append((i, t)),
    )
    assert [i for i, _ in calls] == [0, 1, 2]
    assert all(t == 3 for _, t in calls)
```

- [ ] **Step 2: 运行确认失败**

Run: `uv run pytest tests/test_video_relay.py::test_sender_progress_callback_per_frame -v`
Expected: FAIL

- [ ] **Step 3: 实现**

`VideoRelaySender.run` 签名末尾加 `progress_callback=None`。逐帧循环 `relay.send(packet)` 之后（`video_relay.py:165` 附近，`stats.frames.append(...)` 之后）加：

```python
                if progress_callback is not None:
                    progress_callback(i, total, {"frame_type": metadata.get("frame_type")})
```

- [ ] **Step 4: 运行确认通过**

Run: `uv run pytest tests/test_video_relay.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/semantic_transmission/pipeline/video_relay.py tests/test_video_relay.py
git commit -m "feat(pipeline): VideoRelaySender.run 新增 progress_callback"
```

---

## Task B2: `VideoRelayReceiver` 进度回调 + 分派透传 + 可中断 `stop()`

**Files:**
- Modify: `pipeline/video_relay.py`、`tests/test_video_relay.py`

**Interfaces:**
- Produces:
  - `VideoRelayReceiver.run(..., progress_callback=None)`，每帧 process 后回调 `(idx, total, {"stage": "receive"})`；`run` 分派 `_run_temporal` 时透传 `progress_callback`；`_run_temporal` 同参并回调
  - `VideoRelayReceiver.stop() -> None`：关闭 `self._relay` 使阻塞 accept/receive 抛错退出

- [ ] **Step 1: 写失败测试**

追加：

```python
def test_receiver_stop_closes_relay():
    from unittest.mock import MagicMock
    from semantic_transmission.pipeline.video_relay import VideoRelayReceiver
    r = VideoRelayReceiver(MagicMock())
    fake = MagicMock()
    r._relay = fake
    r.stop()
    fake.close.assert_called_once()


def test_receiver_stop_noop_when_no_relay():
    from unittest.mock import MagicMock
    from semantic_transmission.pipeline.video_relay import VideoRelayReceiver
    VideoRelayReceiver(MagicMock()).stop()  # 不应抛错


def test_receiver_run_passes_callback_to_temporal(monkeypatch, tmp_path):
    from unittest.mock import MagicMock
    from semantic_transmission.pipeline.video_relay import VideoRelayReceiver
    r = VideoRelayReceiver(MagicMock())
    captured = {}
    monkeypatch.setattr(
        r, "_run_temporal",
        lambda *a, **k: captured.update(k) or MagicMock(),
    )
    cb = lambda i, t, info: None
    r.run("0.0.0.0", 9000, str(tmp_path / "o.mp4"), reference_mode="prev", progress_callback=cb)
    assert captured.get("progress_callback") is cb
```

- [ ] **Step 2: 运行确认失败**

Run: `uv run pytest tests/test_video_relay.py -k "receiver_stop or passes_callback" -v`
Expected: FAIL

- [ ] **Step 3: 实现**

`VideoRelayReceiver.__init__` 加 `self._relay: SocketRelayReceiver | None = None`。

无状态 `run` 与 `_run_temporal`：签名末尾加 `progress_callback=None`；把内部局部 `relay = SocketRelayReceiver(host, port)` 改为 `self._relay = SocketRelayReceiver(host, port)` 并全程用 `self._relay`；`finally` 中 `self._relay.close()` 后置 `self._relay = None`。

`run` 分派 `_run_temporal`（`video_relay.py:241-244`）补透传：

```python
        if reference_mode is not None:
            return self._run_temporal(
                host, port, output_path, reference_mode,
                timeout=timeout, progress_callback=progress_callback,
            )
```

无状态 `run` 收包 process 后（`video_relay.py:303` `prompt_buffer[idx]=...` 之后）加：

```python
                if progress_callback is not None:
                    progress_callback(idx, total, {"stage": "receive"})
```

`_run_temporal` 生成/收包循环内同样按 `(idx, total, {"stage": "receive"})` 回调。新增方法：

```python
    def stop(self) -> None:
        """从外部线程中断监听：关闭 socket 使阻塞的 accept/receive 抛错退出。"""
        if self._relay is not None:
            self._relay.close()
```

- [ ] **Step 4: 运行确认通过**

Run: `uv run pytest tests/test_video_relay.py tests/test_video_relay_temporal.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/semantic_transmission/pipeline/video_relay.py tests/test_video_relay.py
git commit -m "feat(pipeline): VideoRelayReceiver 进度回调+分派透传+stop() 可中断"
```

---

## Task B3: 双机面板发送端逻辑 `run_video_sender`

**Files:**
- Create: `gui/video_relay_panel.py`、`tests/test_gui_video_relay_panel.py`

**Interfaces:**
- Produces: `run_video_sender(video_path, host, port, mode, prompt, kf_interval, seed, fps, project_config) -> Generator`，产出 `(progress_text, stats_rows, log)`；空 `video_path` 首个产出即错误

> 说明：发送端本身较快，且 Gradio 生成器无法转发 `VideoRelaySender.run` 内部回调，故此处只给**阶段级**进度（开始/完成）——B1 的 sender 回调供 CLI/未来流式用，GUI 发送端不强求逐帧。

- [ ] **Step 1: 写失败测试**

`tests/test_gui_video_relay_panel.py`：

```python
from unittest.mock import MagicMock, patch
from semantic_transmission.gui.video_relay_panel import run_video_sender


def test_sender_empty_path_yields_error():
    gen = run_video_sender(None, "127.0.0.1", 9000, "manual", "x", 12, None, None, MagicMock())
    progress, rows, log = next(gen)
    assert "请先上传" in log


def test_sender_runs_and_reports_stats():
    fake_stats = MagicMock()
    fake_stats.to_dict.return_value = {
        "total_frames": 3, "keyframe_count": 1, "generated_count": 2,
        "keyframe_bytes": 300, "generated_bytes": 60,
    }
    with patch("semantic_transmission.gui.video_relay_panel.VideoRelaySender") as MS, \
         patch("semantic_transmission.gui.video_relay_panel.LocalCannyExtractor"):
        MS.return_value.run.return_value = fake_stats
        gen = run_video_sender("in.mp4", "127.0.0.1", 9000, "manual", "x", 12, None, None, MagicMock())
        outputs = list(gen)
    progress, rows, log = outputs[-1]
    assert any(r[0] == "总帧数" for r in rows)
    assert any(r[0] == "关键帧∶生成帧倍率" for r in rows)
    assert "完成" in log
```

- [ ] **Step 2: 运行确认失败**

Run: `uv run pytest tests/test_gui_video_relay_panel.py -v`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 实现（发送端部分）**

`src/semantic_transmission/gui/video_relay_panel.py`：

```python
"""双机视频 Tab：发送端触发 + 接收端后台线程监听。"""

from __future__ import annotations

import queue
import threading

from semantic_transmission.gui.video_panel import build_video_prompt_fn
from semantic_transmission.pipeline.temporal_policy import TemporalPolicyConfig
from semantic_transmission.pipeline.video_relay import (
    VideoRelayReceiver,
    VideoRelaySender,
)
from semantic_transmission.receiver import create_receiver
from semantic_transmission.sender.local_condition_extractor import LocalCannyExtractor


def run_video_sender(video_path, host, port, mode, prompt, kf_interval, seed, fps, project_config):
    """发送端：构造 policy + prompt_fn，调 VideoRelaySender.run，yield 阶段进度与码率账本。"""
    if not video_path:
        yield "", [], "错误：请先上传视频\n"
        return
    extractor = LocalCannyExtractor(
        threshold1=project_config.canny_low_threshold,
        threshold2=project_config.canny_high_threshold,
    )
    vlm_sender = None
    if mode == "auto":
        from semantic_transmission.sender.qwen_vl_sender import QwenVLSender

        vlm_sender = QwenVLSender(
            model_name=project_config.vlm_model_name,
            model_path=project_config.vlm_model_path or None,
        )
    prompt_fn = build_video_prompt_fn(mode, prompt, vlm_sender)
    policy = None
    if int(kf_interval) > 0:
        policy = TemporalPolicyConfig(
            keyframe_interval=int(kf_interval),
            reference_mode="prev",
            keyframe_passthrough=True,
        )
    yield "发送中...", [], "开始发送...\n"
    try:
        stats = VideoRelaySender(extractor).run(
            video_path, host, int(port), prompt_fn,
            seed=(int(seed) if seed not in (None, "") else None),
            fps=(float(fps) if fps not in (None, "") else None),
            temporal_policy=policy,
        )
    except Exception as e:
        yield "失败", [], f"发送失败：{e}\n"
        return
    finally:
        if vlm_sender is not None:
            vlm_sender.unload()
    d = stats.to_dict()
    ratio = (d["keyframe_bytes"] / d["generated_bytes"]) if d.get("generated_bytes") else 0
    rows = [
        ["总帧数", str(d["total_frames"])],
        ["关键帧数", str(d["keyframe_count"])],
        ["生成帧数", str(d["generated_count"])],
        ["关键帧字节", str(d["keyframe_bytes"])],
        ["生成帧字节", str(d["generated_bytes"])],
        ["关键帧∶生成帧倍率", f"{ratio:.1f}x"],
    ]
    yield "完成", rows, "发送完成\n"
```

- [ ] **Step 4: 运行确认通过**

Run: `uv run pytest tests/test_gui_video_relay_panel.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/semantic_transmission/gui/video_relay_panel.py tests/test_gui_video_relay_panel.py
git commit -m "feat(gui): 双机视频面板发送端逻辑 run_video_sender"
```

---

## Task B4: 双机接收端后台线程状态机

**Files:**
- Modify: `gui/video_relay_panel.py`、`tests/test_gui_video_relay_panel.py`

**Interfaces:**
- Produces:
  - `start_listening(state, host, port, backend, ref_mode, output_path, timeout) -> tuple[dict, str]`（`create_receiver` 在线程内执行、失败经 `error` 回填——不在主线程裸抛）
  - `poll_listening(state) -> tuple[str, str | None]`
  - `stop_listening(state) -> tuple[dict, str]`
  - state 键：`{"thread","receiver","progress_q","result","error","done"}`

- [ ] **Step 1: 写失败测试**

追加：

```python
import queue as _q
from semantic_transmission.gui.video_relay_panel import (
    start_listening, poll_listening, stop_listening,
)


def test_start_listening_rejects_double_start():
    alive = MagicMock()
    alive.is_alive.return_value = True
    state = {"thread": alive}
    new_state, status = start_listening(state, "0.0.0.0", 9000, "klein", "prev", "o.mp4", None)
    assert "已在监听" in status and new_state is state


def test_stop_listening_calls_receiver_stop():
    rcv = MagicMock()
    new_state, status = stop_listening({"receiver": rcv})
    rcv.stop.assert_called_once()
    assert "停止" in status


def test_poll_listening_drains_queue():
    q = _q.Queue()
    q.put((1, 3, {}))
    q.put((2, 3, {}))
    text, out = poll_listening({"progress_q": q, "done": False, "result": None, "error": None})
    assert "3/3" in text and out is None


def test_poll_listening_done_returns_output():
    result = MagicMock()
    result.output_path = "out.mp4"
    text, out = poll_listening(
        {"progress_q": _q.Queue(), "done": True, "result": result, "error": None}
    )
    assert out == "out.mp4"
```

- [ ] **Step 2: 运行确认失败**

Run: `uv run pytest tests/test_gui_video_relay_panel.py -k listening -v`
Expected: FAIL

- [ ] **Step 3: 实现（接收端状态机——create_receiver 移入线程 try）**

追加：

```python
def start_listening(state, host, port, backend, ref_mode, output_path, timeout):
    """起后台线程跑 VideoRelayReceiver.run，进度写队列。

    create_receiver（klein 加载可能失败/耗时）在 _worker 内执行并被 try 捕获，
    失败经 state["error"] 回填，避免在主线程裸抛堆栈（design §6.3）。
    """
    state = state or {}
    if state.get("thread") is not None and state["thread"].is_alive():
        return state, "已在监听中，请先停止"
    progress_q: "queue.Queue" = queue.Queue()
    new_state = {
        "thread": None, "receiver": None, "progress_q": progress_q,
        "result": None, "error": None, "done": False,
    }

    def _worker():
        try:
            receiver_obj = create_receiver(backend=backend)
            relay_receiver = VideoRelayReceiver(receiver_obj)
            new_state["receiver"] = relay_receiver
            result = relay_receiver.run(
                host, int(port), output_path,
                timeout=(float(timeout) if timeout not in (None, "") else None),
                reference_mode=(None if ref_mode == "none" else ref_mode),
                progress_callback=lambda i, t, info: progress_q.put((i, t, info)),
            )
            new_state["result"] = result
        except Exception as e:  # 含 stop() 触发的 ConnectionError、模型加载失败
            new_state["error"] = str(e)
        finally:
            new_state["done"] = True

    t = threading.Thread(target=_worker, daemon=True)
    new_state["thread"] = t
    t.start()
    return new_state, f"开始监听 {host}:{port}（backend={backend}）"


def poll_listening(state):
    """轮询进度队列，返回 (进度文本, 输出视频或None)。"""
    if not state:
        return "未监听", None
    q = state.get("progress_q")
    last = None
    if q is not None:
        while not q.empty():
            last = q.get()
    if state.get("error"):
        return f"已停止/出错：{state['error']}", None
    if state.get("done") and state.get("result") is not None:
        return "接收完成", str(state["result"].output_path)
    if last is not None:
        return f"接收中 {last[0] + 1}/{last[1]}", None
    return "监听中，等待发送端连接...", None


def stop_listening(state):
    """中断监听：调用 receiver.stop() 关闭 socket。"""
    if not state or state.get("receiver") is None:
        return state or {}, "当前无监听任务"
    try:
        state["receiver"].stop()
        return state, "已请求停止监听"
    except Exception as e:
        return state, f"停止出错：{e}"
```

- [ ] **Step 4: 运行确认通过**

Run: `uv run pytest tests/test_gui_video_relay_panel.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/semantic_transmission/gui/video_relay_panel.py tests/test_gui_video_relay_panel.py
git commit -m "feat(gui): 双机接收端后台线程监听状态机（start/poll/stop，模型加载失败可回填）"
```

---

## Task B5: 双机 Tab 组装 + 接入 app.py + 文档

**Files:**
- Modify: `gui/video_relay_panel.py`（加 `build_video_relay_tab`）、`gui/app.py`、`docs/gui-design.md`

**Interfaces:**
- Produces: `build_video_relay_tab(config_components: dict, project_config=None) -> dict`

- [ ] **Step 1: 实现 `build_video_relay_tab`（发送端 + 接收端两子区，gr.Timer 轮询）**

顶部补 `import gradio as gr`、`from semantic_transmission.common.config import load_config`。追加：

```python
def build_video_relay_tab(config_components: dict, project_config=None) -> dict:
    """双机视频 Tab：发送端子区 + 接收端监听子区。"""
    config = project_config if project_config is not None else load_config()
    gr.Markdown("### 双机视频\n发送端与接收端分处两台机器，各用对应子区。")
    listen_state = gr.State(value={})

    with gr.Accordion("发送端（本机为发送方时使用）", open=True):
        s_video = gr.Video(label="输入视频")
        with gr.Row():
            s_host = gr.Textbox(value="127.0.0.1", label="接收端 IP")
            s_port = gr.Number(value=9000, precision=0, label="端口")
        s_mode = gr.Radio(choices=[("手动", "manual"), ("VLM", "auto")], value="manual", label="描述模式")
        s_prompt = gr.Textbox(label="描述文本", lines=2)
        with gr.Row():
            s_kf = gr.Number(value=12, precision=0, label="关键帧间隔 N")
            s_seed = gr.Number(value=None, precision=0, label="种子")
            s_fps = gr.Number(value=None, label="帧率")
        s_btn = gr.Button("▶ 发送", variant="primary")
        s_progress = gr.Textbox(label="发送进度", interactive=False)
        s_stats = gr.Dataframe(headers=["指标", "值"], interactive=False)
        s_log = gr.Textbox(label="日志", lines=3, interactive=False)

    with gr.Accordion("接收端监听（本机为接收方时使用）", open=False):
        with gr.Row():
            r_host = gr.Textbox(value="0.0.0.0", label="监听地址")
            r_port = gr.Number(value=9000, precision=0, label="端口")
        r_backend = gr.Radio(choices=[("klein", "klein"), ("diffusers", "diffusers")], value="klein", label="后端")
        r_ref = gr.Dropdown(choices=["none", "prev", "keyframe", "prev_keyframe"], value="prev", label="参考帧模式")
        r_out = gr.Textbox(value="output/video_relay/gui_out.mp4", label="输出路径")
        r_timeout = gr.Number(value=None, label="超时秒数（空=无限）")
        with gr.Row():
            r_start = gr.Button("▶ 开始监听", variant="primary")
            r_stop = gr.Button("■ 停止监听", variant="secondary")
        r_status = gr.Markdown("")
        r_progress = gr.Textbox(label="接收进度", interactive=False)
        r_video = gr.Video(label="接收输出视频", interactive=False)
        r_timer = gr.Timer(value=1.5, active=True)

    def _send_bound(vp, host, port, mode, prompt, kf, seed, fps):
        yield from run_video_sender(vp, host, port, mode, prompt, kf, seed, fps, config)

    s_btn.click(
        _send_bound,
        inputs=[s_video, s_host, s_port, s_mode, s_prompt, s_kf, s_seed, s_fps],
        outputs=[s_progress, s_stats, s_log],
    )
    r_start.click(
        start_listening,
        inputs=[listen_state, r_host, r_port, r_backend, r_ref, r_out, r_timeout],
        outputs=[listen_state, r_status],
    )
    r_stop.click(stop_listening, inputs=[listen_state], outputs=[listen_state, r_status])
    r_timer.tick(poll_listening, inputs=[listen_state], outputs=[r_progress, r_video])
    return {}
```

- [ ] **Step 2: 接入 app.py**

顶部补 `from semantic_transmission.gui.video_relay_panel import build_video_relay_tab`。把「⇄ 双机视频」占位替换为：

```python
            with gr.TabItem("⇄ 双机视频"):
                build_video_relay_tab(config_components, config)
```

- [ ] **Step 3: 更新 `docs/gui-design.md`**

把面板清单从旧 6 面板改为新 4 Tab（配置 / 视频流演示 / 双机视频 / 图像工具）；补单机与双机接收端的「后台线程 + `gr.Timer` 轮询」交互说明；注明关闭 issue #29。

- [ ] **Step 4: 冒烟 + 全量测试 + lint**

Run: `uv run python -c "from semantic_transmission.gui.app import create_app; create_app(); print('ok')"`
Expected: `ok`
Run: `uv run pytest -q`
Expected: 全绿
Run: `uv run ruff check . && uv run ruff format --check .`
Expected: 无错误

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat(gui): 双机视频 Tab 组装接入应用，gui-design 同步新架构"
```

---

## Self-Review（作者自查结论，含对抗性复核修复对照）

**1. Spec 覆盖**
- §3 信息架构（4 Tab）→ A1 + A6 + B5 ✓
- §4.1 单机面板（线程+Timer 进度 / backend 门控 / 评估 / 显存错峰）→ A2–A6 ✓
- §4.2 双机（发送 + 接收监听）→ B3–B5 ✓
- §4.3 图像 Tab 压缩核心 3 面板 → A1 ✓
- §5 三个 run 的 progress_callback + 分派透传 → A3 / B1 / B2 ✓
- §6.1 接收端可中断 stop() → B2 ✓
- §6.2 显存错峰 → A4（线程内 on_prompts_ready）✓
- §6.3 klein 就位失败回填而非裸抛 → B4（create_receiver 移入 _worker try）✓

**2. 对抗性复核（2026-07-10）findings 修复对照**
- H1 单机逐帧进度出不来 → 改后台线程+queue+gr.Timer（A4/A6），B1 进度接口前移为 A3 并被线程消费 ✓
- H2 diffusers 门控只禁交互不改值必崩 → A6 `_toggle` 置 `value="none"` + A4 `backend!="klein"` 强制兜底 ✓
- H3 双机 klein/prev 默认路径丢进度 → B2 `run` 分派 `_run_temporal` 透传 `progress_callback`（含专门测试）✓
- M create_receiver 失败裸抛 → B4 移入 `_worker` try 回填 error ✓
- M CLIP 恒空 → A5 默认 `with_clip=False` 不列 CLIP，测试断言其为 False ✓
- M B1/B5 断言自相矛盾 → A3 断言 `[0,1,2]`（无状态仅 encode 循环回调、不加 done 帧）；A4/B4 轮询断言统一为 `{last[0]+1}/{last[1]}`（`3/3`）✓
- Low 版本 → Tech Stack 订正为 Gradio 6.x（实测 6.10.0）✓

**3. 类型一致性**
- `build_video_prompt_fn` 在 A2 定义、A4/B3 复用，签名一致 ✓
- `progress_callback (index,total,info)` A3/B1/B2 三处一致，分派透传均覆盖 ✓
- `VideoRelayReceiver.stop()`/`self._relay` B2 定义、B4 消费 ✓
- 单机 state 键 `{thread,receiver,progress_q,result,error,done}`（`result={out_path,stats}`）A4 定义与 poll/组装一致；双机 state 键同构 B4 一致 ✓
- 轮询进度文本口径 `{last[0]+1}/{last[1]}` 与测试断言一致（单机 A4「2/3」来自 last=(1,3)；双机 B4「3/3」来自 last=(2,3)）✓
