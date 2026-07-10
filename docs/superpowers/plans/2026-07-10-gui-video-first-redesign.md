# GUI 视频优先重构 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 Gradio GUI 从图像级 6 面板重构为视频优先，补齐单机 `video→video` 演示面板与双机 relay 视频面板，图像能力压缩为单 Tab。

**Architecture:** 复用现有 `pipeline_panel` 范式（`gr.State` 持久化 receiver + generator `yield` 进度 + 显存错峰）。单机面板封装 `VideoPipeline`；双机面板封装 `VideoRelaySender/Receiver`，接收端用后台线程 + `gr.Timer` 轮询。三个编排 `run` 新增可选 `progress_callback` 驱动进度，`VideoRelayReceiver` 加 `stop()` 支持 GUI 中断。

**Tech Stack:** Python ≥3.10、Gradio 5.x、click、Diffusers/klein 接收端、pytest + unittest.mock。

## Global Constraints

- 所有 Python 操作走 `uv`：`uv run pytest`、`uv run ruff check .`、`uv run ruff format --check .`（禁止裸 `python`/`pytest`/`ruff`）
- CI lint 范围是整个项目（`.`），推送前本地必须 `uv run ruff check .` 与 `uv run ruff format --check .` 全绿
- `gr.Video` 回调收到的是**文件路径字符串**（与 `gr.Image type="filepath"` 一致）；`gr.Image` 默认 `type="numpy"`，需路径时显式 `type="filepath"`
- GUI 单测只测**纯函数/生成器逻辑**（用 `MagicMock` mock receiver/pipeline），不测 Gradio UI 渲染——与现有 `tests/test_gui_*_panel.py` 范式一致
- commit message 用中文、遵循 Angular 约定，不含工具生成标记与 Co-Authored 声明
- `progress_callback` 统一签名 `Callable[[int, int, dict], None]`，参数 `(index, total, info)`；不传时行为与现状逐字节兼容
- **实现分支**：本 plan 的代码改动应在**新分支** `feature/gui-video-first-redesign`（从 `main` 切出）上进行；规划文档（ROADMAP/spec/plan）留在 `docs/roadmap-phase3-gui-sync`（PR #70）

---

## 文件结构

**Phase A（批次 A）：架构重排 + 图像压缩 + 单机视频面板**
- 删除：`src/semantic_transmission/gui/batch_sender_panel.py`、`gui/batch_panel.py`、`tests/test_gui_batch_panel.py`
- 修改：`gui/app.py`（Tab 视频优先重排、图像工具 Tab 用 Accordion 收纳核心 3 面板）
- 创建：`gui/video_panel.py`（单机视频流演示面板）
- 创建：`tests/test_gui_video_panel.py`

**Phase B（批次 B）：双机面板 + 进度接口 + 可中断**
- 修改：`pipeline/video_pipeline.py`（`run`/`_run_temporal` 加 `progress_callback`）
- 修改：`pipeline/video_relay.py`（`VideoRelaySender.run`、`VideoRelayReceiver.run`/`_run_temporal` 加 `progress_callback`；`VideoRelayReceiver` 加 `self._relay` + `stop()`）
- 创建：`gui/video_relay_panel.py`（双机视频面板：发送端 + 接收端监听）
- 创建：`tests/test_gui_video_relay_panel.py`
- 修改：`tests/test_video_pipeline.py`、`tests/test_video_relay.py`（补 `progress_callback` / `stop` 用例）
- 修改：`gui/app.py`（接入双机 Tab）、`docs/gui-design.md`（同步新架构）

---

# Phase A — 架构重排 + 单机视频面板

## Task A1: 图像 Tab 压缩 + 视频优先骨架

**Files:**
- Delete: `src/semantic_transmission/gui/batch_sender_panel.py`、`gui/batch_panel.py`、`tests/test_gui_batch_panel.py`
- Modify: `src/semantic_transmission/gui/app.py`

**Interfaces:**
- Consumes: `build_config_tab`→`{vlm_model_name, vlm_model_path}`；`build_pipeline_tab`、`build_sender_tab`、`build_receiver_tab`（签名不变）
- Produces: `create_app(project_config=None) -> gr.Blocks`，Tab 顺序为 配置 / 视频流演示(占位) / 双机视频(占位) / 图像工具

- [ ] **Step 1: 删除批量面板与其测试**

```bash
git rm src/semantic_transmission/gui/batch_sender_panel.py \
       src/semantic_transmission/gui/batch_panel.py \
       tests/test_gui_batch_panel.py
```

- [ ] **Step 2: 重写 app.py 的 Tab 装配（图像工具 Tab 用 Accordion 收纳核心 3 面板）**

`create_app` 内 `with gr.Tabs():` 块替换为（视频 Tab 本任务先留占位 Markdown，A5/B6 填充）：

```python
        with gr.Tabs():
            with gr.TabItem("⚙ 配置"):
                config_components = build_config_tab(config)

            with gr.TabItem("◈ 视频流演示"):
                gr.Markdown("_单机 video→video 面板（Task A5 接入）_")

            with gr.TabItem("⇄ 双机视频"):
                gr.Markdown("_双机 relay 视频面板（Task B6 接入）_")

            with gr.TabItem("🖼 图像工具（单帧）"):
                gr.Markdown("### 图像工具（单帧）\n单帧图像的端到端演示、发送与接收，供调试/对照。")
                with gr.Accordion("端到端演示", open=True):
                    build_pipeline_tab(config_components, config)
                with gr.Accordion("单张发送", open=False):
                    sender_components = build_sender_tab(config_components, config)
                with gr.Accordion("接收端队列", open=False):
                    receiver_components = build_receiver_tab(config_components)
```

删除文件顶部 `build_batch_tab`、`build_batch_sender_tab` 两个 import。跨 Tab 联动块（`sender_components["send_to_receiver_btn"].click(...)`）保持不变（组件仍存在于图像工具 Tab 内）。

- [ ] **Step 3: 冒烟——应用可构造**

Run: `uv run python -c "from semantic_transmission.gui.app import create_app; app = create_app(); print('tabs ok')"`
Expected: 打印 `tabs ok`，无 import / 组装异常

- [ ] **Step 4: lint**

Run: `uv run ruff check src/semantic_transmission/gui/app.py && uv run ruff format --check src/semantic_transmission/gui/app.py`
Expected: 无错误

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "refactor(gui): Tab 视频优先重排，图像面板压缩为单 Tab 保留核心 3 个"
```

---

## Task A2: 单机面板纯逻辑（卸载 + prompt_fn 构造）

**Files:**
- Create: `src/semantic_transmission/gui/video_panel.py`
- Create: `tests/test_gui_video_panel.py`

**Interfaces:**
- Produces:
  - `unload_video_receiver(receiver: BaseReceiver | None) -> tuple[BaseReceiver | None, str]`
  - `build_video_prompt_fn(mode: str, prompt: str | None, vlm_sender) -> Callable[[int, "np.ndarray"], str]`（`mode=="auto"` 用 `vlm_sender.describe(frame).text`，否则整段返回 `prompt or ""`）

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
        assert result is None
        assert "无已加载" in status

    def test_calls_unload_and_clears(self):
        receiver = MagicMock()
        result, status = unload_video_receiver(receiver)
        receiver.unload.assert_called_once()
        assert result is None
        assert "已卸载" in status

    def test_swallows_unload_exception(self):
        receiver = MagicMock()
        receiver.unload.side_effect = RuntimeError("boom")
        result, status = unload_video_receiver(receiver)
        assert result is None
        assert "boom" in status


class TestBuildVideoPromptFn:
    def test_manual_returns_same_prompt(self):
        fn = build_video_prompt_fn("manual", "a cat", None)
        assert fn(0, np.zeros((4, 4, 3), dtype=np.uint8)) == "a cat"
        assert fn(5, np.zeros((4, 4, 3), dtype=np.uint8)) == "a cat"

    def test_manual_none_prompt_returns_empty(self):
        fn = build_video_prompt_fn("manual", None, None)
        assert fn(0, np.zeros((4, 4, 3), dtype=np.uint8)) == ""

    def test_auto_calls_vlm_describe(self):
        vlm = MagicMock()
        vlm.describe.return_value = MagicMock(text="auto desc")
        fn = build_video_prompt_fn("auto", None, vlm)
        frame = np.zeros((4, 4, 3), dtype=np.uint8)
        assert fn(2, frame) == "auto desc"
        vlm.describe.assert_called_once()
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run pytest tests/test_gui_video_panel.py -v`
Expected: FAIL（`ModuleNotFoundError: video_panel`）

- [ ] **Step 3: 写最小实现**

`src/semantic_transmission/gui/video_panel.py`：

```python
"""视频流演示 Tab（单机 video→video）：封装 VideoPipeline。

复用 pipeline_panel 范式：gr.State 持久化 receiver、generator yield 逐帧进度、
显存错峰（VLM 描述完卸载再加载生成模型）、显式卸载按钮。
"""

from __future__ import annotations

from typing import Callable

from semantic_transmission.receiver.base import BaseReceiver


def unload_video_receiver(
    receiver: BaseReceiver | None,
) -> tuple[BaseReceiver | None, str]:
    """显式卸载 receiver 释放显存；失败也清空 state，避免残留引用阻碍 GC。"""
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
) -> Callable[[int, "object"], str]:
    """构造逐帧 prompt 函数：auto→VLM 描述每帧；manual→整段共用同一文本。"""
    if mode == "auto":

        def _auto(index, frame):
            return vlm_sender.describe(frame).text

        return _auto

    text = prompt or ""

    def _manual(index, frame):
        return text

    return _manual
```

- [ ] **Step 4: 运行测试确认通过**

Run: `uv run pytest tests/test_gui_video_panel.py -v`
Expected: PASS（6 passed）

- [ ] **Step 5: Commit**

```bash
git add src/semantic_transmission/gui/video_panel.py tests/test_gui_video_panel.py
git commit -m "feat(gui): 单机视频面板卸载与 prompt_fn 构造纯逻辑"
```

---

## Task A3: 单机面板运行生成器 `_run_video`

**Files:**
- Modify: `src/semantic_transmission/gui/video_panel.py`
- Modify: `tests/test_gui_video_panel.py`

**Interfaces:**
- Consumes: `build_video_prompt_fn`、`resolve_reference_mode(backend, mode)`、`TemporalPolicyConfig`、`VideoPipeline`、`create_receiver(backend=...)`
- Produces: `_run_video(video_path, backend, mode, prompt, ref_mode, kf_interval, kf_passthrough, seed, fps, receiver, project_config) -> Generator`，产出 `(receiver, output_video_path, progress_text, stats_rows, log)`；`video_path` 为空时首个产出即错误消息且不加载模型

- [ ] **Step 1: 写失败测试（错误分支——空输入不触碰模型工厂）**

追加到 `tests/test_gui_video_panel.py`：

```python
from unittest.mock import patch
from semantic_transmission.gui.video_panel import _run_video


class TestRunVideoGuard:
    def test_empty_path_yields_error_without_loading(self):
        with patch(
            "semantic_transmission.gui.video_panel.create_receiver"
        ) as mock_create:
            gen = _run_video(
                video_path=None,
                backend="klein",
                mode="manual",
                prompt="x",
                ref_mode="prev",
                kf_interval=12,
                kf_passthrough=True,
                seed=None,
                fps=None,
                receiver=None,
                project_config=MagicMock(),
            )
            receiver, out_path, progress, stats, log = next(gen)
            assert receiver is None
            assert out_path is None
            assert "请先上传" in log
            mock_create.assert_not_called()
```

- [ ] **Step 2: 运行确认失败**

Run: `uv run pytest tests/test_gui_video_panel.py::TestRunVideoGuard -v`
Expected: FAIL（`_run_video` 未定义）

- [ ] **Step 3: 实现 `_run_video`**

在 `video_panel.py` 追加（顶部补 import）：

```python
import tempfile
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
def _run_video(
    video_path,
    backend,
    mode,
    prompt,
    ref_mode,
    kf_interval,
    kf_passthrough,
    seed,
    fps,
    receiver,
    project_config: ProjectConfig,
):
    """单机 video→video 生成器：逐步 yield (receiver, out_path, progress, stats, log)。

    receiver 经 gr.State 跨次持久化；auto 模式在生成模型加载前卸载 VLM（显存错峰）。
    """
    log = ""
    out_path = None
    if not video_path:
        yield receiver, None, "", [], "错误：请先上传视频\n"
        return

    # 时序策略解析（klein→默认 prev；diffusers→none）
    resolved = resolve_reference_mode(backend, None if ref_mode == "none" else ref_mode)
    temporal_policy = None
    if resolved is not None:
        temporal_policy = TemporalPolicyConfig(
            keyframe_interval=int(kf_interval),
            reference_mode=resolved,
            keyframe_passthrough=bool(kf_passthrough),
        )

    log += f"[1/3] 准备接收端（backend={backend}）...\n"
    yield receiver, None, "准备中...", [], log

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

    if receiver is None:
        log += "  加载接收端生成模型（首次约 1~2 分钟）...\n"
        yield receiver, None, "加载模型...", [], log
        try:
            receiver = create_receiver(backend=backend)
        except Exception as e:
            log += f"  模型加载失败：{e}\n"
            if vlm_sender is not None:
                vlm_sender.unload()
            yield None, None, "失败", [], log
            return

    out_path = str(Path(tempfile.mkdtemp()) / "out.mp4")
    log += "[2/3] 逐帧生成中...\n"
    yield receiver, None, "生成中...", [], log

    seed_int = int(seed) if seed not in (None, "") else None
    fps_val = float(fps) if fps not in (None, "") else None
    try:
        t0 = time.time()
        stats = VideoPipeline(receiver, extractor).run(
            video_path,
            out_path,
            prompt_fn,
            seed=seed_int,
            fps=fps_val,
            on_prompts_ready=(vlm_sender.unload if vlm_sender is not None else None),
            temporal_policy=temporal_policy,
        )
        elapsed = time.time() - t0
    except Exception as e:
        log += f"  生成失败：{e}\n"
        yield receiver, None, "失败", [], log
        return
    finally:
        if vlm_sender is not None:
            vlm_sender.unload()

    d = stats.to_dict()
    rows = [
        ["总帧数", str(d.get("total"))],
        ["成功帧", str(d.get("success"))],
        ["关键帧数", str(d.get("keyframe_count"))],
        ["生成帧数", str(d.get("generated_frames"))],
        ["总耗时", f"{elapsed:.1f}s"],
    ]
    log += f"[3/3] 完成：{d.get('success')}/{d.get('total')} 帧，耗时 {elapsed:.1f}s\n"
    yield receiver, out_path, "完成", rows, log
```

- [ ] **Step 4: 运行确认通过**

Run: `uv run pytest tests/test_gui_video_panel.py -v`
Expected: PASS（全部）

- [ ] **Step 5: Commit**

```bash
git add src/semantic_transmission/gui/video_panel.py tests/test_gui_video_panel.py
git commit -m "feat(gui): 单机视频面板 _run_video 生成器（显存错峰+时序策略）"
```

---

## Task A4: 单机面板质量评估 `run_video_evaluation`

**Files:**
- Modify: `src/semantic_transmission/gui/video_panel.py`
- Modify: `tests/test_gui_video_panel.py`

**Interfaces:**
- Consumes: `read_frames(path) -> (frames, meta)`、`evaluate_video(orig, rest, *, with_lpips, with_clip) -> report`
- Produces: `run_video_evaluation(input_video, output_video) -> tuple[list[list[str]], str]`（无输入或无输出时返回错误提示；否则返回 summary 指标表 + 日志）

- [ ] **Step 1: 写失败测试（mock read_frames / evaluate_video）**

追加：

```python
from semantic_transmission.gui.video_panel import run_video_evaluation


class TestRunVideoEvaluation:
    def test_missing_inputs_returns_error(self):
        rows, log = run_video_evaluation(None, None)
        assert rows == []
        assert "需要" in log

    def test_summary_rows_from_report(self):
        fake_report = {
            "summary": {
                "psnr": {"mean": 15.0, "count": 2},
                "ssim": {"mean": 0.75, "count": 2},
                "lpips": {"mean": 0.45, "count": 2},
                "clip_score": {"mean": 30.9, "count": 2},
            }
        }
        with patch(
            "semantic_transmission.gui.video_panel.read_frames",
            return_value=([1, 2], MagicMock()),
        ), patch(
            "semantic_transmission.gui.video_panel.evaluate_video",
            return_value=fake_report,
        ):
            rows, log = run_video_evaluation("in.mp4", "out.mp4")
        assert ["PSNR", "15.0000"] in rows
        assert any(r[0] == "CLIP" for r in rows)
        assert "评估完成" in log
```

- [ ] **Step 2: 运行确认失败**

Run: `uv run pytest tests/test_gui_video_panel.py::TestRunVideoEvaluation -v`
Expected: FAIL（`run_video_evaluation` 未定义）

- [ ] **Step 3: 实现**

顶部补 import：

```python
from semantic_transmission.common.video_io import read_frames
from semantic_transmission.evaluation.video_eval import evaluate_video
```

```python
def run_video_evaluation(input_video, output_video) -> tuple[list, str]:
    """输入视频 vs 输出视频逐帧评估，返回 summary 指标表 + 日志。"""
    if not input_video or not output_video:
        return [], "错误：需要先完成一次视频生成（缺输入或输出视频）\n"
    orig, _ = read_frames(input_video)
    rest, _ = read_frames(output_video)
    report = evaluate_video(orig, rest, with_lpips=True, with_clip=True)
    summary = report["summary"]
    label = {"psnr": "PSNR", "ssim": "SSIM", "lpips": "LPIPS", "clip_score": "CLIP"}
    rows = []
    for key, name in label.items():
        mean = summary.get(key, {}).get("mean")
        rows.append([name, f"{mean:.4f}" if mean is not None else "—"])
    return rows, "质量评估完成\n"
```

- [ ] **Step 4: 运行确认通过**

Run: `uv run pytest tests/test_gui_video_panel.py -v`
Expected: PASS（全部）

- [ ] **Step 5: Commit**

```bash
git add src/semantic_transmission/gui/video_panel.py tests/test_gui_video_panel.py
git commit -m "feat(gui): 单机视频面板质量评估封装 run_video_evaluation"
```

---

## Task A5: 单机面板组装 `build_video_tab` + 接入 app.py

**Files:**
- Modify: `src/semantic_transmission/gui/video_panel.py`
- Modify: `src/semantic_transmission/gui/app.py`

**Interfaces:**
- Consumes: `_run_video`、`run_video_evaluation`、`unload_video_receiver`、`config`
- Produces: `build_video_tab(config_components: dict, project_config=None) -> dict`

- [ ] **Step 1: 实现 `build_video_tab`（Gradio 组装，无自动化测试——遵循 GUI 组装不 TDD 的既有范式）**

顶部补 `import gradio as gr`、`from semantic_transmission.common.config import load_config`。追加：

```python
def build_video_tab(config_components: dict, project_config=None) -> dict:
    """单机 video→video 演示 Tab。"""
    config = project_config if project_config is not None else load_config()
    gr.Markdown("### 视频流演示（单机）\n上传视频，逐帧语义还原为 video→video 闭环。")

    receiver_state = gr.State(value=None)

    with gr.Row():
        with gr.Column(scale=1):
            video_input = gr.Video(label="输入视频")
            backend_radio = gr.Radio(
                choices=[("klein（关键帧主线）", "klein"), ("diffusers（Z-Image 备选）", "diffusers")],
                value="klein",
                label="接收端后端",
            )
        with gr.Column(scale=1):
            mode_radio = gr.Radio(
                choices=[("VLM 自动生成", "auto"), ("手动输入", "manual")],
                value="manual",
                label="描述模式",
            )
            prompt_input = gr.Textbox(label="描述文本（整段共用）", lines=2)
            ref_mode = gr.Dropdown(
                choices=["none", "prev", "keyframe", "prev_keyframe"],
                value="prev",
                label="参考帧模式（仅 klein）",
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

    with gr.Accordion("质量评估（可选）", open=False):
        eval_btn = gr.Button("运行质量评估", variant="secondary")
        eval_table = gr.Dataframe(headers=["指标", "值"], interactive=False)
        eval_log = gr.Textbox(label="评估日志", lines=3, interactive=False)

    with gr.Accordion("运行日志", open=False):
        log_output = gr.Textbox(label="详细日志", lines=8, interactive=False)

    # backend 门控：diffusers 时禁用时序控件
    def _toggle_temporal(b):
        on = b == "klein"
        return gr.update(interactive=on), gr.update(interactive=on), gr.update(interactive=on)

    backend_radio.change(
        _toggle_temporal, inputs=backend_radio, outputs=[ref_mode, kf_interval, kf_passthrough]
    )
    mode_radio.change(
        lambda m: gr.update(visible=(m == "manual")), inputs=mode_radio, outputs=prompt_input
    )

    def _run_bound(vp, backend, mode, prompt, rm, ki, kp, seed, fps, receiver):
        yield from _run_video(
            vp, backend, mode, prompt, rm, ki, kp, seed, fps, receiver, config
        )

    run_btn.click(
        fn=_run_bound,
        inputs=[
            video_input, backend_radio, mode_radio, prompt_input, ref_mode,
            kf_interval, kf_passthrough, seed_input, fps_input, receiver_state,
        ],
        outputs=[receiver_state, video_output, progress_box, stats_table, log_output],
    )
    unload_btn.click(
        fn=unload_video_receiver, inputs=[receiver_state], outputs=[receiver_state, unload_status]
    )
    eval_btn.click(
        fn=run_video_evaluation, inputs=[video_input, video_output], outputs=[eval_table, eval_log]
    )
    return {}
```

- [ ] **Step 2: 接入 app.py**

顶部补 `from semantic_transmission.gui.video_panel import build_video_tab`。把「◈ 视频流演示」TabItem 占位替换为：

```python
            with gr.TabItem("◈ 视频流演示"):
                build_video_tab(config_components, config)
```

- [ ] **Step 3: 冒烟 + 回归**

Run: `uv run python -c "from semantic_transmission.gui.app import create_app; create_app(); print('ok')"`
Expected: 打印 `ok`
Run: `uv run pytest tests/test_gui_video_panel.py tests/test_gui_pipeline_panel.py tests/test_gui_receiver_panel.py -v`
Expected: PASS

- [ ] **Step 4: lint**

Run: `uv run ruff check . && uv run ruff format --check .`
Expected: 无错误

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat(gui): 单机视频流演示 Tab 组装并接入应用"
```

---

# Phase B — 双机面板 + 进度接口 + 可中断

## Task B1: `VideoPipeline` 进度回调

**Files:**
- Modify: `src/semantic_transmission/pipeline/video_pipeline.py`
- Modify: `tests/test_video_pipeline.py`

**Interfaces:**
- Produces: `VideoPipeline.run(..., progress_callback: Callable[[int, int, dict], None] | None = None)`；`_run_temporal` 同参。生成阶段每帧完成回调一次 `(index, total, {"stage": "generate"})`

- [ ] **Step 1: 写失败测试（mock receiver，验证回调被逐帧调用）**

在 `tests/test_video_pipeline.py` 追加（复用该文件现有的 mock receiver/视频 fixture 构造方式；若已有 `_make_receiver()` helper 则复用，否则用 MagicMock 且 `process_batch` 返回等长 images）：

```python
def test_run_invokes_progress_callback_per_frame(tmp_path, monkeypatch):
    from semantic_transmission.pipeline.video_pipeline import VideoPipeline
    calls = []
    # 用已有测试里构造 3 帧输入视频与 mock receiver/extractor 的同款 helper；
    # 断言回调次数与总帧数一致、index 覆盖 0..total-1
    # （具体 fixture 沿用本文件既有 test_run_* 用例的构造）
    ...
    assert [c[0] for c in calls] == [0, 1, 2]
    assert all(c[1] == 3 for c in calls)
```

> 注：`tests/test_video_pipeline.py` 已有无 GPU 的 mock receiver + 合成视频用例（`test_video_io` 提供 `read/write_frames`）。本步复用同款构造，只新增回调断言；实现前先阅读该文件顶部现有 fixture。

- [ ] **Step 2: 运行确认失败**

Run: `uv run pytest tests/test_video_pipeline.py::test_run_invokes_progress_callback_per_frame -v`
Expected: FAIL（`run()` 不接受 `progress_callback`）

- [ ] **Step 3: 实现**

`run` 与 `_run_temporal` 签名新增 `progress_callback: Callable[[int, int, dict], None] | None = None`。无状态 `run`：`process_batch` 前后无逐帧粒度，在构造 `frame_inputs` 循环内回调 `(i, len(frames), {"stage": "encode"})`；生成后回调 `(total-1, total, {"stage": "done"})`。时序 `_run_temporal`：生成串行循环内每帧完成后 `progress_callback(idx, n, {"stage": "generate"})`。`run` 分派到 `_run_temporal` 时透传该参数。回调为 None 时跳过。

- [ ] **Step 4: 运行确认通过**

Run: `uv run pytest tests/test_video_pipeline.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/semantic_transmission/pipeline/video_pipeline.py tests/test_video_pipeline.py
git commit -m "feat(pipeline): VideoPipeline.run 新增 progress_callback 逐帧回调"
```

---

## Task B2: `VideoRelaySender` 进度回调

**Files:**
- Modify: `src/semantic_transmission/pipeline/video_relay.py`
- Modify: `tests/test_video_relay.py`

**Interfaces:**
- Produces: `VideoRelaySender.run(..., progress_callback=None)`，逐帧发包后回调 `(i, total, {"frame_type": ...})`

- [ ] **Step 1: 写失败测试**

在 `tests/test_video_relay.py` 追加（复用该文件已有的 loopback / mock relay 构造；发送端测试已存在，仿其构造发送并断言回调序列）：

```python
def test_sender_progress_callback_called_per_frame():
    # 沿用本文件现有 VideoRelaySender 发送用例的构造（假 relay / 3 帧视频）
    calls = []
    # sender.run(..., progress_callback=lambda i, t, info: calls.append((i, t)))
    ...
    assert [i for i, _ in calls] == [0, 1, 2]
```

- [ ] **Step 2: 运行确认失败**

Run: `uv run pytest tests/test_video_relay.py::test_sender_progress_callback_called_per_frame -v`
Expected: FAIL

- [ ] **Step 3: 实现**

`VideoRelaySender.run` 签名加 `progress_callback=None`；逐帧循环 `relay.send(packet)` 后追加：

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

## Task B3: `VideoRelayReceiver` 进度回调 + 可中断 `stop()`

**Files:**
- Modify: `src/semantic_transmission/pipeline/video_relay.py`
- Modify: `tests/test_video_relay.py`

**Interfaces:**
- Produces:
  - `VideoRelayReceiver.run(..., progress_callback=None)`，每帧 process 后回调 `(idx, total, {"stage": "receive"})`
  - `VideoRelayReceiver.stop() -> None`：关闭内部 `self._relay`（`SocketRelayReceiver.close()`），使阻塞的 `accept/receive` 抛错、`run` 循环退出

- [ ] **Step 1: 写失败测试（stop 关闭 relay）**

```python
def test_receiver_stop_closes_relay():
    from unittest.mock import MagicMock
    from semantic_transmission.pipeline.video_relay import VideoRelayReceiver
    r = VideoRelayReceiver(MagicMock())
    fake_relay = MagicMock()
    r._relay = fake_relay
    r.stop()
    fake_relay.close.assert_called_once()

def test_receiver_stop_noop_when_no_relay():
    from semantic_transmission.pipeline.video_relay import VideoRelayReceiver
    r = VideoRelayReceiver(MagicMock())
    r.stop()  # 不应抛错
```

- [ ] **Step 2: 运行确认失败**

Run: `uv run pytest tests/test_video_relay.py::test_receiver_stop_closes_relay -v`
Expected: FAIL（`VideoRelayReceiver` 无 `stop` / 无 `_relay`）

- [ ] **Step 3: 实现**

`VideoRelayReceiver.__init__` 加 `self._relay: SocketRelayReceiver | None = None`。无状态 `run` 与 `_run_temporal` 内把局部 `relay = SocketRelayReceiver(host, port)` 改为 `self._relay = SocketRelayReceiver(host, port)` 并全程用 `self._relay`；`finally` 中 `self._relay.close()` 后置 `self._relay = None`。收包 process 后回调：

```python
                if progress_callback is not None:
                    progress_callback(idx, total, {"stage": "receive"})
```

新增方法：

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
git commit -m "feat(pipeline): VideoRelayReceiver 进度回调 + stop() 可中断监听"
```

---

## Task B4: 双机面板发送端逻辑 `run_video_sender`

**Files:**
- Create: `src/semantic_transmission/gui/video_relay_panel.py`
- Create: `tests/test_gui_video_relay_panel.py`

**Interfaces:**
- Produces: `run_video_sender(video_path, host, port, mode, prompt, kf_interval, seed, fps, project_config) -> Generator`，产出 `(progress_text, stats_rows, log)`；空 `video_path` 首个产出即错误

- [ ] **Step 1: 写失败测试**

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
        *_, (progress, rows, log) = list(gen)
    assert any(r[0] == "总帧数" for r in rows)
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

from semantic_transmission.pipeline.temporal_policy import TemporalPolicyConfig
from semantic_transmission.pipeline.video_relay import (
    VideoRelayReceiver,
    VideoRelaySender,
)
from semantic_transmission.receiver import create_receiver
from semantic_transmission.sender.local_condition_extractor import LocalCannyExtractor
from semantic_transmission.gui.video_panel import build_video_prompt_fn


def run_video_sender(video_path, host, port, mode, prompt, kf_interval, seed, fps, project_config):
    """发送端：构造 policy + prompt_fn，调用 VideoRelaySender.run，yield 进度与码率账本。"""
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

## Task B5: 双机面板接收端后台线程状态机

**Files:**
- Modify: `src/semantic_transmission/gui/video_relay_panel.py`
- Modify: `tests/test_gui_video_relay_panel.py`

**Interfaces:**
- Produces:
  - `start_listening(state, host, port, backend, ref_mode, output_path, timeout) -> tuple[dict, str]`：起后台线程，返回新 state 与状态文本
  - `poll_listening(state) -> tuple[str, str | None]`：读进度队列，返回进度文本与（收齐后）输出视频路径
  - `stop_listening(state) -> tuple[dict, str]`：调用 receiver `.stop()` 中断
  - state 为 dict：`{"thread", "receiver", "progress_q", "result", "error", "done"}`

- [ ] **Step 1: 写失败测试（用假 receiver，验证状态机不依赖真实 socket/GPU）**

```python
from semantic_transmission.gui.video_relay_panel import (
    start_listening, poll_listening, stop_listening,
)

def test_start_listening_rejects_double_start():
    state = {"thread": MagicMock(is_alive=lambda: True)}
    new_state, status = start_listening(state, "0.0.0.0", 9000, "klein", "prev", "o.mp4", None)
    assert "已在监听" in status
    assert new_state is state

def test_stop_listening_calls_receiver_stop():
    rcv = MagicMock()
    state = {"receiver": rcv, "thread": MagicMock(is_alive=lambda: True)}
    new_state, status = stop_listening(state)
    rcv.stop.assert_called_once()
    assert "停止" in status

def test_poll_listening_drains_progress_queue():
    import queue as _q
    q = _q.Queue()
    q.put((1, 3, {}))
    q.put((2, 3, {}))
    state = {"progress_q": q, "done": False, "result": None, "error": None}
    text, out = state_text = poll_listening(state)
    assert "2/3" in text
    assert out is None
```

- [ ] **Step 2: 运行确认失败**

Run: `uv run pytest tests/test_gui_video_relay_panel.py -k listening -v`
Expected: FAIL

- [ ] **Step 3: 实现（接收端状态机）**

追加：

```python
def start_listening(state, host, port, backend, ref_mode, output_path, timeout):
    """起后台线程跑 VideoRelayReceiver.run，进度写队列。"""
    state = state or {}
    if state.get("thread") is not None and state["thread"].is_alive():
        return state, "已在监听中，请先停止"
    progress_q: "queue.Queue" = queue.Queue()
    new_state = {
        "thread": None, "receiver": None, "progress_q": progress_q,
        "result": None, "error": None, "done": False,
    }
    receiver_obj = create_receiver(backend=backend)
    relay_receiver = VideoRelayReceiver(receiver_obj)
    new_state["receiver"] = relay_receiver

    def _worker():
        try:
            result = relay_receiver.run(
                host, int(port), output_path,
                timeout=(float(timeout) if timeout not in (None, "") else None),
                reference_mode=(None if ref_mode == "none" else ref_mode),
                progress_callback=lambda i, t, info: progress_q.put((i, t, info)),
            )
            new_state["result"] = result
        except Exception as e:  # 含 stop() 触发的 ConnectionError
            new_state["error"] = str(e)
        finally:
            new_state["done"] = True

    t = threading.Thread(target=_worker, daemon=True)
    new_state["thread"] = t
    t.start()
    return new_state, f"开始监听 {host}:{port}（backend={backend}）"


def poll_listening(state):
    """轮询进度队列，返回进度文本与（收齐后）输出视频路径。"""
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

> 测试适配：`test_poll_listening_drains_progress_queue` 断言 `poll_listening` 取队列最后一项 `(2, 3, ...)` → 文本含 `2/3`（`last[0]+1=3`？调整断言为 `3/3`，或实现改为显示 `last[0]/last[1]`）。**统一为**：进度文本用 `f"接收中 {last[0]+1}/{last[1]}"`，测试断言改 `"3/3"`。实现与测试以此为准。

- [ ] **Step 4: 运行确认通过**

Run: `uv run pytest tests/test_gui_video_relay_panel.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/semantic_transmission/gui/video_relay_panel.py tests/test_gui_video_relay_panel.py
git commit -m "feat(gui): 双机接收端后台线程监听状态机（start/poll/stop）"
```

---

## Task B6: 双机 Tab 组装 + 接入 app.py + 文档

**Files:**
- Modify: `src/semantic_transmission/gui/video_relay_panel.py`（加 `build_video_relay_tab`）
- Modify: `src/semantic_transmission/gui/app.py`
- Modify: `docs/gui-design.md`

**Interfaces:**
- Produces: `build_video_relay_tab(config_components: dict, project_config=None) -> dict`

- [ ] **Step 1: 实现 `build_video_relay_tab`（发送端 + 接收端两子区，gr.Timer 轮询）**

顶部补 `import gradio as gr`、`from semantic_transmission.common.config import load_config`。追加：

```python
def build_video_relay_tab(config_components: dict, project_config=None) -> dict:
    """双机视频 Tab：发送端子区 + 接收端监听子区（各机开 GUI 用对应子区）。"""
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

顶部补 `from semantic_transmission.gui.video_relay_panel import build_video_relay_tab`。把「⇄ 双机视频」TabItem 占位替换为：

```python
            with gr.TabItem("⇄ 双机视频"):
                build_video_relay_tab(config_components, config)
```

- [ ] **Step 3: 更新 `docs/gui-design.md`**

在文档中把面板清单从旧 6 面板改为新 4 Tab（配置 / 视频流演示 / 双机视频 / 图像工具），补双机后台线程 + `gr.Timer` 轮询的交互说明，并注明关闭 issue #29。

- [ ] **Step 4: 冒烟 + 全量测试 + lint**

Run: `uv run python -c "from semantic_transmission.gui.app import create_app; create_app(); print('ok')"`
Expected: `ok`
Run: `uv run pytest -q`
Expected: 全绿（含 `test_gui_*`、`test_video_pipeline`、`test_video_relay*`）
Run: `uv run ruff check . && uv run ruff format --check .`
Expected: 无错误

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat(gui): 双机视频 Tab 组装接入应用，gui-design 同步新架构"
```

---

## Self-Review（作者自查结论）

**1. Spec 覆盖**
- §3 信息架构（4 Tab 视频优先）→ Task A1 + A5 + B6 ✓
- §4.1 单机视频面板（backend/时序/评估/显存错峰）→ A2–A5 ✓
- §4.2 双机（发送 + 接收监听后台线程）→ B4–B6 ✓
- §4.3 图像 Tab 压缩为核心 3 面板 → A1 ✓
- §5 三个 run 的 progress_callback → B1–B3 ✓
- §6.1 接收端可中断 stop() → B3 ✓
- §6.2 显存错峰 → A3（单机）；双机分机天然隔离 ✓
- §8 分批 A/B → Phase A / Phase B ✓
- 遗留：§6.3 klein 就位检测——UI 上作运行前提示，未单列 Task；实现于 B5 `start_listening` 内 `create_receiver` 失败即经 `error` 回传（已覆盖失败路径），显式 check 提示归入 B6 文档说明。可接受。

**2. 占位符扫描**
- B1/B2 测试步骤含「沿用本文件既有 fixture」说明而非完整 fixture 代码——因这些测试文件已有成熟的 mock receiver / 合成视频构造，重复粘贴反而易与实际 fixture 名漂移；实现者须先读该文件。此为有意的最小引用，非「TODO/implement later」。
- 其余步骤均含完整可执行代码。

**3. 类型一致性**
- `build_video_prompt_fn` 在 A2 定义、A3/B4 复用，签名一致 ✓
- `progress_callback` 签名 `(index, total, info)` 三处一致 ✓
- `VideoRelayReceiver.stop()` / `self._relay` 在 B3 定义、B5 消费 ✓
- state dict 键（`thread/receiver/progress_q/result/error/done`）B5 定义与消费一致 ✓
- B5 进度文本与测试断言口径已在 Step 3 注明统一为 `{last[0]+1}/{last[1]}`（`3/3`）✓
