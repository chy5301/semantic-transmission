# klein 阶段 3 productionize（一）时序策略毕业到 VideoPipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把已在 PoC 验证有效（闪烁 MAE 降 ~76%）的有状态串行时序策略从 `scripts/poc/klein_ab/` 毕业到生产管道，让 `semantic-tx video --backend klein` 默认走 prev-only@N12 时序策略而非被证否的 drop-in baseline。

**Architecture:** 三段落地——(A) 时序纯逻辑迁到 `src/semantic_transmission/pipeline/temporal_policy.py`，PoC 从 src 重导出；(B) `VideoPipeline.run()` 新增可选 `temporal_policy` 参数，`None` 走现有无状态 `process_batch` 路径（逐字节向后兼容），非 `None` 走新私有串行方法 `_run_temporal`（持 prev/keyframe 状态、关键帧透传、透传帧跳过 VLM、失败帧隔离、尺寸一致）；(C) `cli/video.py` 新增时序 flag，按 backend 解析默认值并做 klein-only 门控。全部逻辑用无 GPU 的 fake receiver 单测覆盖。

**Tech Stack:** Python ≥3.10 · click（CLI）· PIL/Pillow · pytest · uv（依赖与命令）· ruff（lint/format）。生成模型 klein（`Flux2KleinPipeline`）仅在手动 GPU 冒烟时真正加载，单测全程不碰 GPU。

## Global Constraints

- 所有 Python 命令一律走 `uv`：`uv run pytest`、`uv run ruff check .`、`uv run ruff format --check .`（禁止裸 `python`/`pytest`/`ruff`）。
- 推送/完成前 `uv run ruff check .`、`uv run ruff format --check .`、`uv run pytest` 三者全绿；CI 检查范围是整个项目 `.`，不止 `src/`。
- commit message 遵循 Angular Convention，subject/body 用中文；**不得**包含 `Generated with [Claude Code]` 或 `Co-Authored-By: Claude` 等标记。
- `temporal_policy=None` 时 `VideoPipeline.run()` 行为必须与改动前**逐字节向后兼容**（现有 `test_video_pipeline.py` 全部保持通过）。
- 接收端基类 `BaseReceiver.process()` 签名**不拓宽**（保持 `(edge_image, prompt_text, seed)` 无状态单帧契约）；多参考能力由 `KleinReceiver.process(reference_images=...)` 提供，串行路径通过能力门控使用。
- `split_summary` **不迁入** src（评估期关注点，留在 PoC）。迁移仅限 `TemporalPolicyConfig` / `is_keyframe` / `build_reference_images`。
- 时序补偿仅 `--backend klein` 支持；`--backend diffusers`（Z-Image 非多参考模型）显式传时序参数须报错。

---

### Task 1: 时序纯逻辑迁移到 src（A）

把 `TemporalPolicyConfig` / `is_keyframe` / `build_reference_images` 从 PoC 搬到 `src/`，PoC 改为重导出，`split_summary` 留在 PoC。

**Files:**
- Create: `src/semantic_transmission/pipeline/temporal_policy.py`
- Modify: `scripts/poc/klein_ab/phase2.py`（改为从 src 重导出，保留 `split_summary`）
- Create: `tests/test_temporal_policy.py`
- 保持不动（回归验证用）：`tests/poc/test_phase2_policy.py`、`scripts/poc/klein_ab/run_phase2.py`

**Interfaces:**
- Produces:
  - `TemporalPolicyConfig(keyframe_interval: int = 12, reference_mode: str = "prev", keyframe_passthrough: bool = True)` — dataclass
  - `is_keyframe(index: int, config: TemporalPolicyConfig) -> bool`
  - `build_reference_images(mode: str, prev_output, last_keyframe) -> list`
  - 模块级 `__all__ = ["TemporalPolicyConfig", "is_keyframe", "build_reference_images"]`

- [ ] **Step 1: 写失败测试** `tests/test_temporal_policy.py`

```python
"""时序策略纯逻辑单测（无 GPU）——针对 src 版本。"""

import pytest
from PIL import Image

from semantic_transmission.pipeline.temporal_policy import (
    TemporalPolicyConfig,
    build_reference_images,
    is_keyframe,
)


def _cfg(**kw):
    return TemporalPolicyConfig(**kw)


def test_defaults():
    c = TemporalPolicyConfig()
    assert c.keyframe_interval == 12
    assert c.reference_mode == "prev"
    assert c.keyframe_passthrough is True


def test_is_keyframe_interval_12():
    c = _cfg(keyframe_interval=12)
    assert is_keyframe(0, c) is True
    assert is_keyframe(12, c) is True
    assert is_keyframe(5, c) is False
    assert is_keyframe(11, c) is False


def test_is_keyframe_disabled_when_interval_non_positive():
    c = _cfg(keyframe_interval=0)
    assert is_keyframe(0, c) is False
    assert is_keyframe(12, c) is False


def test_build_refs_none_mode_empty():
    a, b = Image.new("RGB", (8, 8)), Image.new("RGB", (8, 8))
    assert build_reference_images("none", a, b) == []


def test_build_refs_prev_only():
    prev = Image.new("RGB", (8, 8), (1, 1, 1))
    kf = Image.new("RGB", (8, 8), (2, 2, 2))
    assert build_reference_images("prev", prev, kf) == [prev]


def test_build_refs_keyframe_only():
    prev = Image.new("RGB", (8, 8), (1, 1, 1))
    kf = Image.new("RGB", (8, 8), (2, 2, 2))
    assert build_reference_images("keyframe", prev, kf) == [kf]


def test_build_refs_prev_keyframe_order():
    prev = Image.new("RGB", (8, 8), (1, 1, 1))
    kf = Image.new("RGB", (8, 8), (2, 2, 2))
    assert build_reference_images("prev_keyframe", prev, kf) == [prev, kf]


def test_build_refs_drops_none_prev():
    kf = Image.new("RGB", (8, 8), (2, 2, 2))
    assert build_reference_images("prev_keyframe", None, kf) == [kf]


def test_build_refs_invalid_mode_raises():
    with pytest.raises(ValueError, match="reference_mode"):
        build_reference_images("bogus", None, None)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/test_temporal_policy.py -v`
Expected: FAIL —— `ModuleNotFoundError: No module named 'semantic_transmission.pipeline.temporal_policy'`

- [ ] **Step 3: 建 src 模块** `src/semantic_transmission/pipeline/temporal_policy.py`

```python
"""参考帧时序策略纯逻辑（编排层无状态纯函数，可无 GPU 单测）。

时序策略不进接收端：接收端保持无状态单帧契约，此处只做"给定跨帧状态 →
判定关键帧 / 构造参考帧列表"的纯函数，由 VideoPipeline 持状态串行编排。
从 scripts/poc/klein_ab/phase2.py 毕业（PoC 现从本模块重导出）。
"""

from __future__ import annotations

from dataclasses import dataclass

_VALID_MODES = {"none", "prev", "keyframe", "prev_keyframe"}


@dataclass
class TemporalPolicyConfig:
    """参考帧时序策略配置。

    - keyframe_interval: N；<=0 关闭关键帧（退回 drop-in）。
    - reference_mode: none | prev | keyframe | prev_keyframe。
    - keyframe_passthrough: 关键帧那一帧是否直接透传原图（不生成）。
    """

    keyframe_interval: int = 12
    reference_mode: str = "prev"
    keyframe_passthrough: bool = True


def is_keyframe(index: int, config: TemporalPolicyConfig) -> bool:
    """index 是否为关键帧下标（interval>0 且 index 整除 interval）。"""
    return config.keyframe_interval > 0 and index % config.keyframe_interval == 0


def build_reference_images(mode: str, prev_output, last_keyframe) -> list:
    """构造接在 canny 之后的额外参考帧列表。

    顺序：prev 在前、keyframe 在后（对齐设计 [canny, prev, keyframe]）。
    prev_output / last_keyframe 为 None 时该项跳过。
    """
    if mode not in _VALID_MODES:
        raise ValueError(f"未知 reference_mode: {mode!r}，支持 {sorted(_VALID_MODES)}")
    refs = []
    if mode in ("prev", "prev_keyframe") and prev_output is not None:
        refs.append(prev_output)
    if mode in ("keyframe", "prev_keyframe") and last_keyframe is not None:
        refs.append(last_keyframe)
    return refs


__all__ = [
    "TemporalPolicyConfig",
    "is_keyframe",
    "build_reference_images",
]
```

- [ ] **Step 4: 跑测试确认通过**

Run: `uv run pytest tests/test_temporal_policy.py -v`
Expected: PASS（10 项全绿）

- [ ] **Step 5: PoC `phase2.py` 改为重导出**（全文替换 `scripts/poc/klein_ab/phase2.py`）

```python
"""阶段 2 质量两栏拆分（评估期关注点，留在 PoC 不进生产管道）。

时序纯逻辑（TemporalPolicyConfig / is_keyframe / build_reference_images）已毕业到
src/semantic_transmission/pipeline/temporal_policy.py，此处重导出以保持 run_phase2.py
及其单测的导入路径不变、不重复实现。split_summary 依赖 baseline 对照做质量拆分，
属评估期工具，留在 PoC。
"""

from __future__ import annotations

from semantic_transmission.evaluation.video_eval import summarize_metrics
from semantic_transmission.pipeline.temporal_policy import (
    TemporalPolicyConfig,
    build_reference_images,
    is_keyframe,
)


def split_summary(frames: list[dict], keyframe_indices) -> dict:
    """质量指标两栏：delivered（全帧）/ generated_only（排除关键帧下标）。

    透传关键帧 R[t]≡O[t] 会拿满分 SSIM/PSNR、拉高均值；generated_only 剔除以隔离
    生成帧真实水平。frames 为 evaluate_video 返回的逐帧列表（含 index + metrics）。
    """
    kf = set(keyframe_indices or [])
    return {
        "delivered": summarize_metrics(frames),
        "generated_only": summarize_metrics(
            [f for f in frames if f["index"] not in kf]
        ),
    }


__all__ = [
    "TemporalPolicyConfig",
    "is_keyframe",
    "build_reference_images",
    "split_summary",
]
```

- [ ] **Step 6: 跑 PoC 回归测试确认重导出没破坏 harness 单测**

Run: `uv run pytest tests/poc/test_phase2_policy.py -v`
Expected: PASS（该测试从 `scripts.poc.klein_ab.phase2` 导入四个符号，经重导出后仍全绿）

- [ ] **Step 7: lint + format + 提交**

```bash
uv run ruff check src/semantic_transmission/pipeline/temporal_policy.py scripts/poc/klein_ab/phase2.py tests/test_temporal_policy.py
uv run ruff format src/semantic_transmission/pipeline/temporal_policy.py scripts/poc/klein_ab/phase2.py tests/test_temporal_policy.py
git add src/semantic_transmission/pipeline/temporal_policy.py scripts/poc/klein_ab/phase2.py tests/test_temporal_policy.py
git commit -m "refactor: 时序策略纯逻辑从 PoC 毕业到 pipeline/temporal_policy"
```

---

### Task 2: BatchResult 扩展时序统计字段（§7）

给 `BatchResult` 加可选的关键帧统计字段，`to_dict()` 仅在时序路径（字段被赋值）时输出，保证无状态路径 summary 逐字节不变。

**Files:**
- Modify: `src/semantic_transmission/pipeline/batch_processor.py:47-78`（`BatchResult` dataclass + `to_dict`）
- Modify: `tests/test_video_pipeline.py`（新增针对扩展字段的测试；文件已存在，追加）

**Interfaces:**
- Consumes: 无
- Produces: `BatchResult` 新增三个可选字段
  - `keyframe_count: int | None = None`
  - `generated_frames: int | None = None`
  - `keyframe_indices: list[int] | None = None`
  - `to_dict()`：当 `keyframe_indices is not None` 时，额外输出 `"keyframe_count"` / `"generated_frames"` / `"keyframe_indices"` 三个键；否则输出与改动前完全一致。

- [ ] **Step 1: 写失败测试**（追加到 `tests/test_video_pipeline.py` 末尾）

```python
def test_batch_result_to_dict_omits_keyframe_fields_by_default():
    """无状态路径：keyframe_indices 未赋值时 to_dict 不含时序字段（逐字节向后兼容）。"""
    from semantic_transmission.pipeline.batch_processor import BatchResult

    d = BatchResult(total=3, success=3).to_dict()
    assert "keyframe_count" not in d
    assert "generated_frames" not in d
    assert "keyframe_indices" not in d


def test_batch_result_to_dict_includes_keyframe_fields_when_set():
    """时序路径：赋值后 to_dict 输出三个关键帧统计字段。"""
    from semantic_transmission.pipeline.batch_processor import BatchResult

    b = BatchResult(total=5, success=5)
    b.keyframe_count = 1
    b.generated_frames = 4
    b.keyframe_indices = [0]
    d = b.to_dict()
    assert d["keyframe_count"] == 1
    assert d["generated_frames"] == 4
    assert d["keyframe_indices"] == [0]
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/test_video_pipeline.py -k batch_result -v`
Expected: FAIL —— 第二个测试报 `AttributeError: 'BatchResult' object has no attribute 'keyframe_count'`（或 to_dict 不含该键）

- [ ] **Step 3: 扩展 `BatchResult`**（`src/semantic_transmission/pipeline/batch_processor.py`）

在 dataclass 字段区（`samples` 之后）追加三个可选字段：

```python
@dataclass
class BatchResult:
    """整个批量处理结果汇总。"""

    total: int
    success: int = 0
    failed: int = 0
    skipped: int = 0
    total_time: float = 0.0
    samples: list[SampleResult] = field(default_factory=list)
    # 时序（temporal）路径专用统计；无状态路径保持 None，to_dict 不输出这些键。
    keyframe_count: int | None = None
    generated_frames: int | None = None
    keyframe_indices: list[int] | None = None
```

`to_dict` 改为在末尾按需追加时序字段：

```python
    def to_dict(self) -> dict:
        """转换为字典用于 JSON 序列化。"""
        d = {
            "total": self.total,
            "success": self.success,
            "failed": self.failed,
            "skipped": self.skipped,
            "total_time": self.total_time,
            "success_rate": (self.success / self.total * 100) if self.total > 0 else 0,
            "samples": [s.to_dict() for s in self.samples],
        }
        # 时序路径才输出关键帧统计。三字段由 _run_temporal 作为一个整体同时赋值，
        # 故以 keyframe_indices 是否为 None 作单一存在性判据；无状态路径三者均 None，
        # to_dict 逐字节兼容旧输出。
        if self.keyframe_indices is not None:
            d["keyframe_count"] = self.keyframe_count
            d["generated_frames"] = self.generated_frames
            d["keyframe_indices"] = self.keyframe_indices
        return d
```

- [ ] **Step 4: 跑测试确认通过**

Run: `uv run pytest tests/test_video_pipeline.py -k batch_result -v`
Expected: PASS（2 项）

- [ ] **Step 5: 跑全量 batch/relay 回归，确认扩展没破坏既有 to_dict 消费方**

Run: `uv run pytest tests/test_relay.py tests/test_video_pipeline.py -q`
Expected: PASS（既有测试全绿，证明无状态 to_dict 未变）

- [ ] **Step 6: lint + format + 提交**

```bash
uv run ruff check src/semantic_transmission/pipeline/batch_processor.py tests/test_video_pipeline.py
uv run ruff format src/semantic_transmission/pipeline/batch_processor.py tests/test_video_pipeline.py
git add src/semantic_transmission/pipeline/batch_processor.py tests/test_video_pipeline.py
git commit -m "feat: BatchResult 增可选时序统计字段（keyframe_count/generated_frames/keyframe_indices）"
```

---

### Task 3: 时序产物保存辅助函数（§5 / §7）

新建 `_save_temporal_artifacts`：透传关键帧无描述条目（标记 `passthrough: true`），语义码率只计生成帧，edges 只存生成帧。与无状态 `_save_artifacts` 并存、互不影响。

**Files:**
- Modify: `src/semantic_transmission/pipeline/video_pipeline.py`（新增模块级函数 `_save_temporal_artifacts`，紧接现有 `_save_artifacts` 之后）
- Modify: `tests/test_video_pipeline.py`（追加测试）

**Interfaces:**
- Consumes: `FrameInput`（已有，`from semantic_transmission.receiver.base import FrameInput`），其 `metadata["index"]` 为帧下标、`prompt_text`、`edge_image`（PIL.Image）
- Produces: `_save_temporal_artifacts(artifacts_dir, generated_inputs, passthrough_indices, total_frames, meta) -> None`
  - `generated_inputs: list[FrameInput]` —— 仅生成帧（每个 `metadata["index"]` 为真实帧下标，`edge_image` 为 PIL）
  - `passthrough_indices: list[int]` —— 透传关键帧下标（这些帧无 prompt、无 edge）
  - `total_frames: int`、`meta`（须有 `.fps` 属性）
  - 产出 `artifacts_dir/prompts.json`（`frames` 含全部下标，透传帧标 `{"index": i, "passthrough": true}`；`semantic_bitrate` 仅计生成帧）+ `artifacts_dir/edges/frame_XXXX.png`（仅生成帧）

- [ ] **Step 1: 写失败测试**（追加到 `tests/test_video_pipeline.py` 末尾）

```python
def test_save_temporal_artifacts_marks_passthrough_and_counts_generated(tmp_path):
    """透传关键帧标 passthrough、无 edge；码率只计生成帧。"""
    import json
    from types import SimpleNamespace

    from semantic_transmission.pipeline.video_pipeline import _save_temporal_artifacts
    from semantic_transmission.receiver.base import FrameInput

    def _edge():
        return Image.new("RGB", (16, 12), color=(255, 255, 255))

    # 4 帧：0 为透传关键帧，1/2/3 为生成帧
    generated = [
        FrameInput(edge_image=_edge(), prompt_text=f"描述 {i}",
                   metadata={"index": i, "name": f"frame_{i:04d}"})
        for i in (1, 2, 3)
    ]
    artifacts = tmp_path / "art"
    _save_temporal_artifacts(
        artifacts,
        generated_inputs=generated,
        passthrough_indices=[0],
        total_frames=4,
        meta=SimpleNamespace(fps=25.0),
    )

    data = json.loads((artifacts / "prompts.json").read_text(encoding="utf-8"))
    assert data["total_frames"] == 4
    assert data["generated_frames"] == 3
    assert data["keyframe_indices"] == [0]
    # frames 覆盖全部下标；透传帧标记、无 prompt
    assert data["frames"][0] == {"index": 0, "passthrough": True}
    assert data["frames"][1]["prompt"] == "描述 1"
    assert data["frames"][1]["byte_count"] == len("描述 1".encode("utf-8"))
    # 码率仅计 3 个生成帧
    expected_total = sum(len(f"描述 {i}".encode("utf-8")) for i in (1, 2, 3))
    assert data["semantic_bitrate"]["total_bytes"] == expected_total
    assert data["semantic_bitrate"]["avg_bytes_per_generated_frame"] == round(
        expected_total / 3, 2
    )
    # edges 只有 3 张（生成帧），透传帧 frame_0000 无 edge
    pngs = sorted(p.name for p in (artifacts / "edges").glob("*.png"))
    assert pngs == ["frame_0001.png", "frame_0002.png", "frame_0003.png"]
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/test_video_pipeline.py -k save_temporal_artifacts -v`
Expected: FAIL —— `ImportError: cannot import name '_save_temporal_artifacts'`

- [ ] **Step 3: 实现 `_save_temporal_artifacts`**（加在 `video_pipeline.py` 中 `_save_artifacts` 定义之后、`class VideoPipeline` 之前）

```python
def _save_temporal_artifacts(
    artifacts_dir,
    generated_inputs: list[FrameInput],
    passthrough_indices,
    total_frames: int,
    meta,
) -> None:
    """时序路径的语义中间产物保存：透传关键帧无描述、码率仅计生成帧。

    与无状态 ``_save_artifacts`` 并存。透传关键帧发整帧、不发 prompt（§5 VLM 跳过），
    故其在 ``prompts.json`` 中仅留 ``{"index": i, "passthrough": true}``、不产 edge；
    语义码率（压缩率账本）只累加生成帧的 prompt 字节。
    """
    artifacts_dir = Path(artifacts_dir)
    edges_dir = artifacts_dir / "edges"
    edges_dir.mkdir(parents=True, exist_ok=True)

    passthrough = set(passthrough_indices or [])
    by_index = {fi.metadata["index"]: fi for fi in generated_inputs}

    frames_meta: list[dict[str, Any]] = []
    total_bytes = 0
    for i in range(total_frames):
        if i in passthrough:
            frames_meta.append({"index": i, "passthrough": True})
            continue
        fi = by_index[i]
        prompt = fi.prompt_text
        byte_count = len(prompt.encode("utf-8"))
        total_bytes += byte_count
        frames_meta.append(
            {
                "index": i,
                "prompt": prompt,
                "char_count": len(prompt),
                "byte_count": byte_count,
            }
        )
        fi.edge_image.save(edges_dir / f"frame_{i:04d}.png")

    generated = total_frames - len(passthrough)
    avg_bytes = total_bytes / generated if generated else 0.0
    payload = {
        "total_frames": total_frames,
        "generated_frames": generated,
        "keyframe_indices": sorted(passthrough),
        "fps": meta.fps,
        "semantic_bitrate": {
            "total_bytes": total_bytes,
            "avg_bytes_per_generated_frame": round(avg_bytes, 2),
            "avg_bytes_per_second": round(avg_bytes * meta.fps, 2),
        },
        "frames": frames_meta,
    }
    (artifacts_dir / "prompts.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
```

- [ ] **Step 4: 跑测试确认通过**

Run: `uv run pytest tests/test_video_pipeline.py -k save_temporal_artifacts -v`
Expected: PASS

- [ ] **Step 5: lint + format + 提交**

```bash
uv run ruff check src/semantic_transmission/pipeline/video_pipeline.py tests/test_video_pipeline.py
uv run ruff format src/semantic_transmission/pipeline/video_pipeline.py tests/test_video_pipeline.py
git add src/semantic_transmission/pipeline/video_pipeline.py tests/test_video_pipeline.py
git commit -m "feat: 时序产物保存——透传帧标记 passthrough、码率仅计生成帧"
```

---

### Task 4: VideoPipeline 串行时序路径 `_run_temporal`（B，核心）

`run()` 新增 `temporal_policy` 参数分派；`None` 走原路径（向后兼容），非 `None` 走 `_run_temporal`（能力门控、prev/keyframe 状态、关键帧透传、透传帧跳过 VLM、失败帧隔离、尺寸一致、时序统计）。

**Files:**
- Modify: `src/semantic_transmission/pipeline/video_pipeline.py`（`import`、`VideoPipeline.run` 加 `temporal_policy` 参数与分派、新增私有方法 `_run_temporal`、`__all__` 不变）
- Modify: `tests/test_video_pipeline.py`（追加 `FakeReferenceReceiver` 与串行路径测试）

**Interfaces:**
- Consumes:
  - `TemporalPolicyConfig` / `is_keyframe` / `build_reference_images`（Task 1，`from semantic_transmission.pipeline.temporal_policy import ...`）
  - `BatchResult` 的时序字段（Task 2）
  - `_save_temporal_artifacts`（Task 3）
  - `fit_working_size`（`from semantic_transmission.receiver.klein_receiver import fit_working_size`，**在 `_run_temporal` 内部惰性导入**，避免无状态路径被动导入 torch）
  - `receiver.process(edge, prompt, seed=..., reference_images=...)`（KleinReceiver 已支持）；`receiver.config.max_side`（工作分辨率）
- Produces:
  - `VideoPipeline.run(..., temporal_policy: TemporalPolicyConfig | None = None) -> BatchResult`
  - `VideoPipeline._run_temporal(input_path, output_path, prompt_fn, policy, seed, fps, on_prompts_ready, save_artifacts_to) -> BatchResult`（返回的 `BatchResult` 已设 `keyframe_count`/`generated_frames`/`keyframe_indices`）

- [ ] **Step 1: 写失败测试**（追加到 `tests/test_video_pipeline.py`；含 fake 多参考接收端）

```python
class _FakeReferenceReceiver(BaseReceiver):
    """无 GPU 多参考接收端：记录每帧收到的 reference_images / prompt；
    可指定某些「生成帧序号」抛异常。带 config.max_side 供透传帧缩放。"""

    def __init__(self, fail_gen_calls=(), max_side=64):
        from types import SimpleNamespace

        self.config = SimpleNamespace(max_side=max_side)
        self.calls = []  # 每次 process 调用：{"prompt":..., "refs":[...]}
        self._fail = set(fail_gen_calls)
        self._n = -1

    def process(self, edge_image, prompt_text, seed=None, reference_images=None):
        self._n += 1
        self.calls.append({"prompt": prompt_text, "refs": list(reference_images or [])})
        if self._n in self._fail:
            raise RuntimeError("fake gen failure")
        # 返回工作分辨率大小的图（与透传帧尺寸一致：64 长边 → 64x48 源缩不变）
        return Image.new("RGB", (64, 48), color=(0, 255, 0))


def _temporal_cfg(**kw):
    from semantic_transmission.pipeline.temporal_policy import TemporalPolicyConfig

    return TemporalPolicyConfig(**kw)


def test_temporal_none_is_backward_compatible(tmp_path):
    """temporal_policy=None 时输出与旧无状态路径一致（帧数/成功数不变）。"""
    src = tmp_path / "in.mp4"
    _make_input_video(src, 4)
    pipe = VideoPipeline(_FakeReceiver(), LocalCannyExtractor())

    stats = pipe.run(
        src, tmp_path / "out.mp4", prompt_fn=lambda i, f: "t", temporal_policy=None
    )
    read, _ = read_frames(tmp_path / "out.mp4")
    assert len(read) == 4
    assert stats.total == 4 and stats.success == 4
    assert stats.keyframe_indices is None  # 无状态路径不带时序字段


def test_temporal_prev_chain_refs(tmp_path):
    """prev 模式：第 i 生成帧收到的 refs == [上一帧输出]。"""
    src = tmp_path / "in.mp4"
    _make_input_video(src, 4)
    rec = _FakeReferenceReceiver()
    pipe = VideoPipeline(rec, LocalCannyExtractor())

    # interval=12 → 仅帧 0 是关键帧（透传）；帧 1/2/3 生成
    pipe.run(
        src, tmp_path / "out.mp4", prompt_fn=lambda i, f: f"p{i}",
        temporal_policy=_temporal_cfg(keyframe_interval=12, reference_mode="prev"),
    )
    # 3 次生成调用（帧 1/2/3）
    assert len(rec.calls) == 3
    # 帧 1 的 refs = [帧 0 透传图]；帧 2 的 refs = [帧 1 输出]；帧 3 = [帧 2 输出]
    assert len(rec.calls[0]["refs"]) == 1
    assert len(rec.calls[1]["refs"]) == 1
    assert len(rec.calls[2]["refs"]) == 1


def test_temporal_passthrough_keyframe_not_generated(tmp_path):
    """关键帧透传：is_keyframe 下标不调用 process，输出为原图（缩放后）。"""
    src = tmp_path / "in.mp4"
    _make_input_video(src, 3)
    rec = _FakeReferenceReceiver()
    pipe = VideoPipeline(rec, LocalCannyExtractor())

    pipe.run(
        src, tmp_path / "out.mp4", prompt_fn=lambda i, f: "p",
        temporal_policy=_temporal_cfg(keyframe_interval=2),  # 关键帧 {0, 2}
    )
    # 帧 0、2 透传，仅帧 1 生成 → 1 次 process 调用
    assert len(rec.calls) == 1


def test_temporal_passthrough_skips_prompt_fn(tmp_path):
    """透传关键帧下标不调用 prompt_fn（§5 VLM 跳过优化）。"""
    src = tmp_path / "in.mp4"
    _make_input_video(src, 4)
    described = []
    pipe = VideoPipeline(_FakeReferenceReceiver(), LocalCannyExtractor())

    pipe.run(
        src, tmp_path / "out.mp4",
        prompt_fn=lambda i, f: described.append(i) or "p",
        temporal_policy=_temporal_cfg(keyframe_interval=2),  # 关键帧 {0, 2} 透传
    )
    # 只有生成帧 1、3 被描述
    assert described == [1, 3]


def test_temporal_failed_frame_does_not_poison_prev_chain(tmp_path):
    """某生成帧失败 → 下一帧 refs 仍指向上一成功帧、非 None。"""
    src = tmp_path / "in.mp4"
    _make_input_video(src, 4)
    # 关键帧 {0}；生成帧调用序 0->帧1, 1->帧2, 2->帧3；令第 1 次（帧2）失败
    rec = _FakeReferenceReceiver(fail_gen_calls=[1])
    pipe = VideoPipeline(rec, LocalCannyExtractor())

    stats = pipe.run(
        src, tmp_path / "out.mp4", prompt_fn=lambda i, f: "p",
        temporal_policy=_temporal_cfg(keyframe_interval=12, reference_mode="prev"),
    )
    # 帧3（第 2 次调用）的 refs 必须非空（用帧1 的成功输出，而非帧2 的 None）
    assert len(rec.calls[2]["refs"]) == 1
    assert rec.calls[2]["refs"][0] is not None
    assert stats.failed == 1


def test_temporal_stats_and_size_consistency(tmp_path):
    """时序统计字段正确 + 透传帧与生成帧输出尺寸一致（帧数守恒）。"""
    src = tmp_path / "in.mp4"
    _make_input_video(src, 4)
    pipe = VideoPipeline(_FakeReferenceReceiver(), LocalCannyExtractor())

    stats = pipe.run(
        src, tmp_path / "out.mp4", prompt_fn=lambda i, f: "p",
        temporal_policy=_temporal_cfg(keyframe_interval=2),  # 关键帧 {0,2} 透传
    )
    read, _ = read_frames(tmp_path / "out.mp4")
    assert len(read) == 4  # 帧数守恒
    assert stats.keyframe_count == 2
    assert stats.generated_frames == 2
    assert stats.keyframe_indices == [0, 2]


def test_temporal_requires_reference_capable_receiver(tmp_path):
    """能力门控：receiver.process 不接受 reference_images 时抛明确错误、不静默降级。"""
    src = tmp_path / "in.mp4"
    _make_input_video(src, 2)
    pipe = VideoPipeline(_FakeReceiver(), LocalCannyExtractor())  # 无 reference_images

    with pytest.raises(TypeError, match="reference_images"):
        pipe.run(
            src, tmp_path / "out.mp4", prompt_fn=lambda i, f: "p",
            temporal_policy=_temporal_cfg(),
        )


def test_temporal_non_passthrough_keyframe_updates_anchor(tmp_path):
    """passthrough=False：关键帧不透传但仍更新 last_kf 锚点，全部帧都生成。

    覆盖 `if i in kf_set` 非透传关键帧分支（其余测试均 passthrough=True，从不触发它）。
    """
    src = tmp_path / "in.mp4"
    _make_input_video(src, 4)
    rec = _FakeReferenceReceiver()
    pipe = VideoPipeline(rec, LocalCannyExtractor())

    # 关键帧 {0,2}，passthrough 关，reference_mode=keyframe → refs=[last_kf 锚点]
    stats = pipe.run(
        src, tmp_path / "out.mp4", prompt_fn=lambda i, f: "p",
        temporal_policy=_temporal_cfg(
            keyframe_interval=2, keyframe_passthrough=False, reference_mode="keyframe"
        ),
    )
    # 无透传 → 4 帧全部走 process（触发锚点更新分支）
    assert len(rec.calls) == 4
    # 锚点在 i=0（帧0）与 i=2（帧2）各更新一次 → 帧1、帧3 的参考锚点是不同对象
    assert rec.calls[1]["refs"][0] is not rec.calls[3]["refs"][0]
    # 非透传：无透传关键帧 → keyframe_count=0、全部帧计入 generated（与 total 对账）
    assert stats.keyframe_count == 0
    assert stats.generated_frames == 4
    assert stats.keyframe_indices == []
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/test_video_pipeline.py -k temporal -v`
Expected: FAIL —— `run()` 尚无 `temporal_policy` 参数（`TypeError: run() got an unexpected keyword argument 'temporal_policy'`）

- [ ] **Step 3: 更新 `video_pipeline.py` 顶部导入**

在现有 import 区补充（`time` 标准库 + 时序符号；`fit_working_size` 不在顶部导入，见 `_run_temporal` 内惰性导入）：

```python
import json
import time
from pathlib import Path
from typing import Any, Callable

from PIL import Image

from semantic_transmission.common.image_io import load_as_rgb
from semantic_transmission.common.video_io import read_frames, write_frames
from semantic_transmission.pipeline.batch_processor import BatchResult, SampleResult
from semantic_transmission.pipeline.temporal_policy import (
    TemporalPolicyConfig,
    build_reference_images,
    is_keyframe,
)
from semantic_transmission.receiver.base import BaseReceiver, FrameInput
from semantic_transmission.sender.local_condition_extractor import LocalCannyExtractor
```

> 说明：原 `from ...batch_processor import BatchResult` 保留并加 `SampleResult`；删掉不再需要的 `BatchResult`-only 行的重复。若原文件仅 `from ...batch_processor import BatchResult`，替换为上面含 `SampleResult` 的一行。

- [ ] **Step 4: `run()` 增参数与分派**（改 `VideoPipeline.run` 签名与函数体开头）

签名末尾加 `temporal_policy` 参数：

```python
    def run(
        self,
        input_path,
        output_path,
        prompt_fn: PromptFn,
        seed: int | None = None,
        fps: float | None = None,
        on_prompts_ready: Callable[[], None] | None = None,
        save_artifacts_to: Path | None = None,
        temporal_policy: TemporalPolicyConfig | None = None,
    ) -> BatchResult:
```

在 docstring 之后、`frames, meta = read_frames(input_path)` 之前插入分派：

```python
        # temporal_policy 非空 → 走有状态串行时序路径（klein 关键帧主线）；
        # 为空 → 现有无状态 process_batch 路径，逐字节向后兼容。
        if temporal_policy is not None:
            return self._run_temporal(
                input_path,
                output_path,
                prompt_fn,
                temporal_policy,
                seed=seed,
                fps=fps,
                on_prompts_ready=on_prompts_ready,
                save_artifacts_to=save_artifacts_to,
            )
```

（`run()` 其余无状态逻辑保持不动。）

- [ ] **Step 5: 实现 `_run_temporal`**（加在 `run()` 方法之后、`__all__` 之前）

```python
    def _run_temporal(
        self,
        input_path,
        output_path,
        prompt_fn: PromptFn,
        policy: TemporalPolicyConfig,
        seed: int | None = None,
        fps: float | None = None,
        on_prompts_ready: Callable[[], None] | None = None,
        save_artifacts_to: Path | None = None,
    ) -> BatchResult:
        """有状态串行时序路径：关键帧透传 + 中间帧带参考帧生成。

        与 run() 无状态路径的差别集中在两处：透传关键帧跳过 prompt_fn 与 process
        （§5），生成阶段持 prev/keyframe 状态构造参考帧（§4）。透传帧缩到与生成帧
        相同的工作分辨率以保尺寸一致；生成失败帧记 None、不污染 prev 链。
        """
        # 惰性导入：fit_working_size 依赖 klein_receiver（间接 import torch），
        # 只在时序路径需要，避免无状态路径被动引入重依赖。
        from semantic_transmission.receiver.klein_receiver import fit_working_size

        # 能力门控：串行路径要求 receiver.process 接受 reference_images（§3.3/§8）。
        import inspect

        params = inspect.signature(self.receiver.process).parameters
        if "reference_images" not in params:
            raise TypeError(
                "时序补偿要求 receiver.process 接受 reference_images 参数，"
                f"当前接收端 {type(self.receiver).__name__} 不支持——请用 --backend klein"
            )

        max_side = self.receiver.config.max_side
        frames, meta = read_frames(input_path)
        n = len(frames)
        kf_set = {i for i in range(n) if is_keyframe(i, policy)}
        passthrough = policy.keyframe_passthrough
        # 透传关键帧下标集合：仅 passthrough 开启时透传帧才跳过 prompt/生成。
        passthrough_set = kf_set if passthrough else set()

        # 前半段：仅对非透传帧提 Canny + prompt（透传帧不需要，§5 VLM 跳过）。
        generated_inputs: list[FrameInput] = []
        for i, frame in enumerate(frames):
            if i in passthrough_set:
                continue
            edge_img = load_as_rgb(self.extractor.extract(frame))
            try:
                prompt_text = prompt_fn(i, frame)
            except Exception:
                prompt_text = ""
            generated_inputs.append(
                FrameInput(
                    edge_image=edge_img,
                    prompt_text=prompt_text,
                    seed=seed,
                    metadata={"name": f"frame_{i:04d}", "index": i},
                )
            )

        # 语义产物须在 VLM 释放前保存（此时 prompt 已全部就绪）。
        if save_artifacts_to is not None:
            _save_temporal_artifacts(
                save_artifacts_to,
                generated_inputs,
                sorted(passthrough_set),
                n,
                meta,
            )
        if on_prompts_ready is not None:
            on_prompts_ready()

        # 生成阶段：串行、持状态。
        inputs_by_index = {fi.metadata["index"]: fi for fi in generated_inputs}
        outputs: list[Image.Image | None] = [None] * n
        keyframe_indices: list[int] = []
        prev_out: Image.Image | None = None
        last_kf: Image.Image | None = None
        batch = BatchResult(total=n)

        for i in range(n):
            if i in passthrough_set:
                kf = fit_working_size(load_as_rgb(frames[i]), max_side)
                outputs[i] = kf
                keyframe_indices.append(i)
                prev_out = kf  # 链首复位到真关键帧
                last_kf = kf
                batch.add_sample(
                    SampleResult(
                        name=f"frame_{i:04d}",
                        status="success",
                        timings={"process": 0.0},
                    )
                )
                continue
            if i in kf_set:
                # 关键帧但 passthrough=False：仍更新锚，正常生成。
                last_kf = fit_working_size(load_as_rgb(frames[i]), max_side)

            fi = inputs_by_index[i]
            refs = build_reference_images(policy.reference_mode, prev_out, last_kf)
            sample = SampleResult(name=fi.metadata["name"], status="success")
            t0 = time.time()
            try:
                img = self.receiver.process(
                    fi.edge_image,
                    fi.prompt_text,
                    seed=seed,
                    reference_images=refs,
                )
            except Exception as e:
                sample.status = "failed"
                sample.error = str(e)
                img = None
            sample.timings["process"] = time.time() - t0
            batch.add_sample(sample)
            outputs[i] = img
            prev_out = img if img is not None else prev_out  # 失败帧不污染 prev 链

        batch.total_time = sum(s.timings.get("process", 0) for s in batch.samples)
        # keyframe_indices 记录“透传关键帧”下标（沿用 spec §7 / PoC run_policy 口径）。
        # --no-keyframe-passthrough 时无透传帧 → keyframe_count=0、全部帧计入
        # generated_frames，始终保持 keyframe_count + generated_frames == total 不变量。
        batch.keyframe_count = len(keyframe_indices)
        batch.generated_frames = n - len(keyframe_indices)
        batch.keyframe_indices = keyframe_indices

        filled = _fill_failed_frames(outputs)
        processed = self.frame_postprocess(filled)
        write_frames(output_path, processed, fps=fps if fps is not None else meta.fps)
        return batch
```

- [ ] **Step 6: 跑时序测试确认通过**

Run: `uv run pytest tests/test_video_pipeline.py -k temporal -v`
Expected: PASS（7 项时序测试全绿）

- [ ] **Step 7: 跑整个 video_pipeline 测试确认无状态路径未回归**

Run: `uv run pytest tests/test_video_pipeline.py -v`
Expected: PASS（原有 + 新增全绿，证明 `temporal_policy=None` 逐字节兼容）

- [ ] **Step 8: lint + format + 提交**

```bash
uv run ruff check src/semantic_transmission/pipeline/video_pipeline.py tests/test_video_pipeline.py
uv run ruff format src/semantic_transmission/pipeline/video_pipeline.py tests/test_video_pipeline.py
git add src/semantic_transmission/pipeline/video_pipeline.py tests/test_video_pipeline.py
git commit -m "feat: VideoPipeline 增有状态串行时序路径 _run_temporal（关键帧透传+参考帧补偿）"
```

---

### Task 5: CLI 时序 flag 与 backend 门控（C）

`semantic-tx video` 加 `--reference-mode` / `--keyframe-interval` / `--keyframe-passthrough`，按 backend 解析默认值（klein→prev、diffusers→none），diffusers 显式传时序参数报错，并把 `temporal_policy` 透传给 `pipeline.run`。

**Files:**
- Modify: `src/semantic_transmission/cli/video.py`（加三个 option、默认解析与门控、构造 `TemporalPolicyConfig`、透传）
- Modify: `tests/test_cli_video.py`（追加门控与默认解析测试）

**Interfaces:**
- Consumes: `TemporalPolicyConfig`（`from semantic_transmission.pipeline.temporal_policy import TemporalPolicyConfig`）；`VideoPipeline.run(..., temporal_policy=...)`（Task 4）
- Produces: CLI 新增 flag，行为——
  - `--reference-mode` choice `none|prev|keyframe|prev_keyframe`，`default=None`（哨兵）
  - 未显式指定时：`klein → "prev"`，`diffusers → "none"`
  - `--backend diffusers` 且显式传非 `none` 的 `--reference-mode` → `click.UsageError`
  - 解析后 `reference_mode == "none"` → `temporal_policy=None`（无状态路径）；否则构造 `TemporalPolicyConfig(reference_mode=..., keyframe_interval=..., keyframe_passthrough=...)` 传入 `pipeline.run`

- [ ] **Step 1: 写失败测试**（追加到 `tests/test_cli_video.py` 末尾）

```python
def _capture_run(monkeypatch):
    """monkeypatch create_receiver → 哑对象；捕获 VideoPipeline.run 收到的 temporal_policy。"""
    import semantic_transmission.cli.video as video_mod
    from semantic_transmission.pipeline import video_pipeline as vp_mod
    from semantic_transmission.receiver.base import BaseReceiver

    class _Dummy(BaseReceiver):
        def process(self, edge_image, prompt_text, seed=None):
            return Image.new("RGB", (16, 16))

    monkeypatch.setattr(video_mod, "create_receiver", lambda *a, **k: _Dummy())

    captured = {}

    def fake_run(self, *args, **kwargs):
        captured["temporal_policy"] = kwargs.get("temporal_policy", "MISSING")
        from semantic_transmission.pipeline.batch_processor import BatchResult

        return BatchResult(total=0)

    monkeypatch.setattr(vp_mod.VideoPipeline, "run", fake_run)
    return captured


def _make_src(tmp_path, n=2):
    src = tmp_path / "in.mp4"
    write_frames(
        src, [Image.new("RGB", (32, 24), color=(0, 0, 0)) for _ in range(n)], fps=8.0
    )
    return src


def test_video_diffusers_explicit_reference_mode_errors(tmp_path):
    src = _make_src(tmp_path)
    result = CliRunner().invoke(
        video,
        ["--input", str(src), "--prompt", "a", "--backend", "diffusers",
         "--reference-mode", "prev"],
    )
    assert result.exit_code != 0
    assert "klein" in result.output


def test_video_klein_defaults_to_prev_policy(tmp_path, monkeypatch):
    captured = _capture_run(monkeypatch)
    src = _make_src(tmp_path)
    result = CliRunner().invoke(
        video,
        ["--input", str(src), "--output", str(tmp_path / "o" / "out.mp4"),
         "--prompt", "a", "--backend", "klein"],
    )
    assert result.exit_code == 0, result.output
    tp = captured["temporal_policy"]
    assert tp is not None and tp.reference_mode == "prev" and tp.keyframe_interval == 12


def test_video_diffusers_defaults_to_no_temporal(tmp_path, monkeypatch):
    captured = _capture_run(monkeypatch)
    src = _make_src(tmp_path)
    result = CliRunner().invoke(
        video,
        ["--input", str(src), "--output", str(tmp_path / "o" / "out.mp4"),
         "--prompt", "a", "--backend", "diffusers"],
    )
    assert result.exit_code == 0, result.output
    assert captured["temporal_policy"] is None


def test_video_reference_mode_none_disables_temporal_on_klein(tmp_path, monkeypatch):
    captured = _capture_run(monkeypatch)
    src = _make_src(tmp_path)
    result = CliRunner().invoke(
        video,
        ["--input", str(src), "--output", str(tmp_path / "o" / "out.mp4"),
         "--prompt", "a", "--backend", "klein", "--reference-mode", "none"],
    )
    assert result.exit_code == 0, result.output
    assert captured["temporal_policy"] is None
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/test_cli_video.py -k "reference_mode or temporal or defaults" -v`
Expected: FAIL —— video 尚无 `--reference-mode` 选项（`no such option` / 默认仍不传 `temporal_policy`）

- [ ] **Step 3: 加 CLI option 与导入**（`cli/video.py`）

顶部导入区补充：

```python
from semantic_transmission.pipeline.temporal_policy import TemporalPolicyConfig
```

在 `--backend` option 之后、`--fps` option 之前插入三个 option：

```python
@click.option(
    "--reference-mode",
    type=click.Choice(["none", "prev", "keyframe", "prev_keyframe"]),
    default=None,
    help="时序参考帧模式（仅 klein 支持）。缺省按 backend 解析："
    "klein→prev（默认时序补偿），diffusers→none（无时序）。none=复现 drop-in baseline。",
)
@click.option(
    "--keyframe-interval",
    default=12,
    type=int,
    help="关键帧间隔 N（每 N 帧一个关键帧，默认 12）",
)
@click.option(
    "--keyframe-passthrough/--no-keyframe-passthrough",
    default=True,
    help="关键帧是否直接透传原图（不生成、跳过 VLM 描述，默认开）",
)
```

- [ ] **Step 4: 函数签名加参数**（`def video(...)` 参数表，在 `backend` 之后、`fps` 之前加）

```python
    backend,
    reference_mode,
    keyframe_interval,
    keyframe_passthrough,
    fps,
    save_artifacts,
```

- [ ] **Step 5: 加默认解析、门控与构造**（在现有 `--prompt/--auto-prompt` 互斥校验之后插入）

```python
    # 时序参考帧默认解析与 backend 门控：
    # - 未显式指定 --reference-mode（None 哨兵）时：klein→prev，diffusers→none。
    # - diffusers 显式传非 none 时序参数直接报错（Z-Image 非多参考模型，不支持时序）。
    if reference_mode is None:
        reference_mode = "prev" if backend == "klein" else "none"
    elif backend != "klein" and reference_mode != "none":
        raise click.UsageError("时序补偿仅 klein 后端支持（--backend klein）")

    temporal_policy = None
    if reference_mode != "none":
        temporal_policy = TemporalPolicyConfig(
            keyframe_interval=keyframe_interval,
            reference_mode=reference_mode,
            keyframe_passthrough=keyframe_passthrough,
        )
```

- [ ] **Step 6: 透传给 `pipeline.run`**（在现有 `pipeline.run(...)` 调用的 kwargs 里加 `temporal_policy=temporal_policy`）

```python
        stats = pipeline.run(
            input_path,
            output_path,
            prompt_fn,
            seed=seed,
            fps=fps,
            on_prompts_ready=on_prompts_ready,
            save_artifacts_to=output_path.parent if save_artifacts else None,
            temporal_policy=temporal_policy,
        )
```

- [ ] **Step 7: 跑 CLI 测试确认通过**

Run: `uv run pytest tests/test_cli_video.py -v`
Expected: PASS（原有 + 新增 4 项全绿）

- [ ] **Step 8: lint + format + 提交**

```bash
uv run ruff check src/semantic_transmission/cli/video.py tests/test_cli_video.py
uv run ruff format src/semantic_transmission/cli/video.py tests/test_cli_video.py
git add src/semantic_transmission/cli/video.py tests/test_cli_video.py
git commit -m "feat: video CLI 增时序 flag——klein 默认 prev-only@N12、diffusers 门控"
```

---

### Task 6: 全量验证与文档更新

跑全套检查确认整体绿，并把新 flag 补进 CLI 参考文档。

**Files:**
- Modify: `docs/cli-reference.md`（`semantic-tx video` 段补三个新 flag）
- Verify only: 整个测试套件 + ruff

- [ ] **Step 1: 全量测试**

Run: `uv run pytest`
Expected: PASS（全绿；重点确认 `test_video_pipeline.py` / `test_cli_video.py` / `tests/poc/test_phase2_policy.py` / `test_temporal_policy.py` 均通过）

- [ ] **Step 2: 全量 lint 与格式检查（与 CI 一致）**

Run: `uv run ruff check .`
Run: `uv run ruff format --check .`
Expected: 两者均 "All checks passed" / 无需重格式化

- [ ] **Step 3: 更新 `docs/cli-reference.md`**

在 `semantic-tx video` 子命令的参数表中补入（放在 `--backend` 行之后）：

| flag | 类型 | 默认 | 说明 |
|---|---|---|---|
| `--reference-mode` | `none\|prev\|keyframe\|prev_keyframe` | 按 backend（klein→prev / diffusers→none） | 时序参考帧模式，仅 klein 支持；none 复现 drop-in baseline |
| `--keyframe-interval` | int | 12 | 关键帧间隔 N |
| `--keyframe-passthrough / --no-keyframe-passthrough` | bool | on | 关键帧透传原图并跳过 VLM 描述 |

并补一句默认行为说明：`--backend klein` 缺省即启用 prev-only@N12 时序补偿（已验证闪烁 MAE 降 ~76%）；`--backend diffusers` 显式传时序参数会报错。

- [ ] **Step 4: 提交文档**

```bash
uv run ruff check .
git add docs/cli-reference.md
git commit -m "docs: cli-reference 补 video 时序 flag（reference-mode/keyframe-interval/passthrough）"
```

- [ ] **Step 5: 手动 GPU 冒烟（不进 CI，需 RTX 5090 + klein 模型就绪）**

Run: `uv run semantic-tx video --backend klein --reference-mode prev --keyframe-interval 12 --input <少量帧行车视频> --prompt "a dashcam road scene"`
Expected: 端到端跑通、输出帧数 = 输入帧数、无 OOM；`summary.json` 含 `keyframe_count`/`generated_frames`/`keyframe_indices`；`prompts.json` 中关键帧标 `passthrough: true`。
> 此步为人工验收（对应 spec §10 最后一项），非自动化，若无 GPU 环境可交由具备条件者执行。

---

## Self-Review

**1. Spec coverage（逐条对齐 spec §10 验收标准 + 各节要求）**

| spec 要求 | 覆盖任务 |
|---|---|
| §1-A / §3.1 / §10①：temporal_policy.py 落 src、PoC 重导出、run_phase2 及单测仍可跑；split_summary 不迁 | Task 1（Step 5-6 验证 PoC 单测） |
| §7：summary.json 增 keyframe_count/generated_frames/keyframe_indices；无状态 summary 不变 | Task 2 + Task 4 Step 5 赋值 |
| §5：透传关键帧跳过 prompt_fn；prompts.json 标 passthrough、码率仅计生成帧 | Task 3（产物）+ Task 4 Step 5（跳 prompt_fn） |
| §1-B / §3.2 / §4 / §10②：run(temporal_policy=...) 串行路径、None 逐字节兼容、prev 链失败隔离、尺寸一致、关键帧复位 | Task 4 |
| §3.3 / §8 / §10④：能力门控（receiver 不支持 reference_images 抛错） | Task 4 Step 5 + 测试 `test_temporal_requires_reference_capable_receiver` |
| §1-C / §6 / §2 / §10③：CLI flag、klein 默认 prev-only@N12、diffusers 门控、none 走无状态 | Task 5 |
| §9 / §10④⑤：无 GPU 单测覆盖 refs/透传/跳 VLM/失败隔离/向后兼容/尺寸/门控 | Task 4 + Task 5 测试 |
| §10⑥：ruff + format + pytest 全绿 | 各任务末尾 + Task 6 Step 1-2 |
| §10⑦：手动 GPU 冒烟 | Task 6 Step 5 |

无未覆盖的 spec 要求。**明确排除项**（spec §1「不做」）：relay 整帧低频传输（第二个 spec）、速度优化、diffusers 多参考、长视频流式化——本 plan 均未触及，符合范围。

**2. Placeholder scan**：无 TBD/TODO/"添加适当错误处理" 等占位；每个改代码的 step 均含完整代码块与可运行命令 + 预期输出。

**3. Type consistency**：
- `TemporalPolicyConfig`/`is_keyframe`/`build_reference_images` 签名在 Task 1 定义，Task 4/5 消费一致。
- `BatchResult` 字段名 `keyframe_count`/`generated_frames`/`keyframe_indices` 在 Task 2 定义，Task 4 Step 5 与 Task 5 测试、Task 6 文档全程同名。
- `_save_temporal_artifacts(artifacts_dir, generated_inputs, passthrough_indices, total_frames, meta)` 在 Task 3 定义，Task 4 Step 5 调用时实参顺序一致（`save_artifacts_to, generated_inputs, sorted(passthrough_set), n, meta`）。
- `receiver.process(edge, prompt, seed=..., reference_images=...)` 与 `KleinReceiver.process` 现有签名一致；`FakeReferenceReceiver.process` 同签名。
- `_run_temporal` 参数顺序与 `run()` 分派处（Task 4 Step 4）传参一致。

## 对抗性复核回应（2026-07-05）

一次独立会话对本 plan 做了对抗性复核，逐条处置如下：

- **[已采纳] 非透传路径零测试覆盖（中危）**：`if i in kf_set` 非透传关键帧锚点更新分支原先无测试触发。Task 4 已补 `test_temporal_non_passthrough_keyframe_updates_anchor`（`keyframe_passthrough=False` + `reference_mode="keyframe"`，断言 4 帧全生成、锚点在关键帧处更新、`keyframe_count=0`）。
- **[保留 + 加注释] `keyframe_indices` 语义（中危→评低危）**：字段只记录透传关键帧，是 spec §7 明确要求的"沿用 PoC `run_policy` 口径"，非 plan 偏离。现设计保持 `keyframe_count + generated_frames == total` 不变量；reviewer 的"始终从 kf_set 填充"方案会破坏该对账。故**保留 spec 字段名**，加代码注释点明语义，并由新增非透传测试锁定 `keyframe_count=0` 为预期行为。若后续确需向 `--no-keyframe-passthrough` 用户暴露关键帧位置，属 spec 层改动，另议。
- **[承认取舍，列为可选 follow-up] 前半段重复（低危）**：`run()` 与 `_run_temporal` 前半段近乎重复。本 plan 刻意保持两路并存以护住无状态路径的逐字节兼容，不在合并前重构。合并后可另开一支提取 `_collect_frame_inputs(frames, prompt_fn, seed, skip=...)`。
- **[采纳其精神] `to_dict()` 条件脆弱（低危）**：三个时序字段由 `_run_temporal` 作为整体同时赋值，以 `keyframe_indices` 作单一存在性判据正确；对广泛使用的 `BatchResult` 加 `__post_init__` 校验属过度设计。Task 2 已补注释说明该约定。
