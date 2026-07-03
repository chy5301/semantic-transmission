# klein 参考帧时间一致性补偿（阶段 2）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给 klein 接收端加"额外参考帧"能力，并在编排层用可配置时序策略（透传关键帧 + prev 链）压制 drop-in 的剧烈帧间漂移，跑 X@N12/N25 实验并量化时间一致性。

**Architecture:** 接收端保持无状态单帧契约，仅 `process()` 加可选 `reference_images`（`image=[canny, *refs]`）；时序策略（关键帧透传 / prev 链 / 参考列表构造）为纯逻辑放 harness 层 `scripts/poc/klein_ab/phase2.py`，由 `run_phase2.py` 持跨帧状态编排；klein pipeline 不改。时间一致性指标（相邻帧 MAE + 光流 warp-error）落 `src/evaluation/`，作可复用视频指标。

**Tech Stack:** Python 3.10+ / uv、diffusers `Flux2KleinPipeline`（bf16 + model CPU offload）、PIL、numpy、opencv-python（Farneback 光流）、pytest。

## Global Constraints

- **Python 工具一律 `uv run`**（`uv run pytest` / `uv run ruff check .` / `uv run ruff format .`），禁止裸 `python`/`pytest`/`ruff`。
- **CI 检查全项目**：推送前 `uv run ruff check .` 与 `uv run ruff format --check .` 必须通过。
- **`BaseReceiver` 抽象接口不动**：仅 `KleinReceiver` 具体子类加可选 kwarg，`reference_images=None` 时行为与阶段 1 完全一致（零回归）。
- **模型锁定 klein**；工作分辨率 896×496（复用阶段 1 fixture），OOM 才退档并同步重烘 baseline。
- **实验资产复用**：`output/poc/klein-ab-phase1/` 下 `fixture/fixture_frames/`（250 帧原图）、`prompts.json`（冻结 VLM）、`klein/frames/`（drop-in baseline）。
- **长 GPU 任务**：单次推理远超后台 2min，必须 `Start-Process` 脱离跑 + `Monitor` 守候，不在前台直接跑。
- **commit 规范**：Angular 约定 + 中文 subject/body，不含工具生成标记与 Co-Authored-By。
- 设计依据：`docs/superpowers/specs/2026-07-01-klein-phase2-reference-frame-design.md`。

---

### Task 1: KleinReceiver 支持额外参考帧

**Files:**
- Modify: `src/semantic_transmission/receiver/klein_receiver.py`（`process` 方法，约 90-114 行）
- Test: `tests/test_klein_receiver.py`（追加测试）

**Interfaces:**
- Consumes: 现有 `fit_working_size`、`load_as_rgb`、`self.load()`、`self.config`。
- Produces: `KleinReceiver.process(edge_image, prompt_text, seed=None, reference_images=None) -> Image`；`reference_images` 为 `list[Image|bytes|str|Path] | None`，各元素经 `load_as_rgb` 后接在 canny 之后 → `pipe(image=[canny, *refs])`。

- [ ] **Step 1: 写失败测试**（追加到 `tests/test_klein_receiver.py` 末尾）

```python
# ── reference_images（阶段 2 参考帧能力）──────────────────────────────


def test_process_without_reference_images_single_image():
    rec, fake = _receiver_with_fake_pipe()
    rec.process(Image.new("RGB", (768, 432)), "x", seed=0)
    assert len(fake.calls[0]["image"]) == 1  # 仅 canny，行为同阶段 1


def test_process_appends_reference_images_after_canny():
    rec, fake = _receiver_with_fake_pipe()
    ref = Image.new("RGB", (768, 432), (10, 20, 30))
    rec.process(Image.new("RGB", (768, 432)), "x", seed=0, reference_images=[ref])
    imgs = fake.calls[0]["image"]
    assert len(imgs) == 2
    assert imgs[0].size == (768, 432)  # canny 在前
    assert imgs[1].getpixel((0, 0)) == (10, 20, 30)  # 参考帧内容保留


def test_process_multiple_reference_images_keep_order():
    rec, fake = _receiver_with_fake_pipe()
    r1 = Image.new("RGB", (768, 432), (1, 1, 1))
    r2 = Image.new("RGB", (768, 432), (2, 2, 2))
    rec.process(Image.new("RGB", (768, 432)), "x", seed=0, reference_images=[r1, r2])
    imgs = fake.calls[0]["image"]
    assert len(imgs) == 3
    assert imgs[1].getpixel((0, 0)) == (1, 1, 1)
    assert imgs[2].getpixel((0, 0)) == (2, 2, 2)  # 顺序 canny, r1, r2


def test_process_empty_reference_list_single_image():
    rec, fake = _receiver_with_fake_pipe()
    rec.process(Image.new("RGB", (768, 432)), "x", seed=0, reference_images=[])
    assert len(fake.calls[0]["image"]) == 1  # 空列表等价 None
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/test_klein_receiver.py::test_process_appends_reference_images_after_canny -v`
Expected: FAIL —— `TypeError: process() got an unexpected keyword argument 'reference_images'`

- [ ] **Step 3: 改 `process` 实现**（`src/semantic_transmission/receiver/klein_receiver.py`，替换整个 `process` 方法）

```python
    def process(
        self,
        edge_image,
        prompt_text,
        seed=None,
        reference_images=None,
    ) -> Image.Image:
        """从 Canny 边缘图 + 文本生成还原图像（内部降采样到工作分辨率）。

        ``reference_images`` 给定时接在 canny 之后作额外参考帧（klein 原生多参考，
        用于时间一致性补偿）；``None`` 或空列表时行为与单 canny 参考一致。
        参考帧默认已是工作分辨率，不上采样。
        """
        pipe = self.load()
        cond = fit_working_size(load_as_rgb(edge_image), self.config.max_side)
        width, height = cond.size
        images = [cond]
        if reference_images:
            images.extend(load_as_rgb(ref) for ref in reference_images)
        if seed is None:
            seed = random.randint(0, 2**32 - 1)
        generator = torch.Generator("cpu").manual_seed(seed)
        result = pipe(
            prompt=prompt_text,
            image=images,
            guidance_scale=self.config.guidance_scale,
            num_inference_steps=self.config.num_inference_steps,
            height=height,
            width=width,
            generator=generator,
        )
        if not result.images:
            raise RuntimeError("Flux2KleinPipeline 未生成图像（result.images 为空）")
        return result.images[0]
```

- [ ] **Step 4: 跑测试确认通过 + ruff**

Run: `uv run pytest tests/test_klein_receiver.py -v && uv run ruff format src/semantic_transmission/receiver/klein_receiver.py tests/test_klein_receiver.py && uv run ruff check src/semantic_transmission/receiver/klein_receiver.py tests/test_klein_receiver.py`
Expected: 全部 PASS，ruff 无报错

- [ ] **Step 5: Commit**

```bash
git add src/semantic_transmission/receiver/klein_receiver.py tests/test_klein_receiver.py
git commit -m "feat: KleinReceiver 支持额外参考帧 reference_images

process 加可选 reference_images，接在 canny 之后组 image=[canny, *refs]，
用于阶段 2 时间一致性补偿；None/空列表时行为与阶段 1 单参考完全一致（零回归）。
BaseReceiver 抽象接口不动。"
```

---

### Task 2: 时间一致性指标模块（MAE + warp-error）

**Files:**
- Create: `src/semantic_transmission/evaluation/temporal_consistency.py`
- Test: `tests/test_temporal_consistency.py`

**Interfaces:**
- Consumes: `cv2`、`numpy`。帧为 `(H, W, 3)` uint8 RGB ndarray 列表。
- Produces:
  - `frame_mae_series(frames) -> list[float]`（长度 `len-1`）
  - `warp_error_series(frames, flow_frames) -> list[float]`（在 `flow_frames` 上算光流、warp `frames[t-1]` 比 `frames[t]`）
  - `temporal_report(restored, original, keyframe_indices) -> dict`：`{"delivered": {mae, warp_error}, "generated_only": {mae, warp_error}, "original_reference": {mae}, "keyframe_count": int}`

- [ ] **Step 1: 写失败测试**（`tests/test_temporal_consistency.py`）

```python
"""时间一致性指标单测（无 GPU，纯 numpy/cv2）。"""

import numpy as np

from semantic_transmission.evaluation.temporal_consistency import (
    frame_mae_series,
    temporal_report,
    warp_error_series,
)


def _textured(shift=0):
    """64x64 带纹理的确定性帧，可整体平移 shift 像素（用于光流可验证）。"""
    yy, xx = np.mgrid[0:64, 0:64]
    pat = (np.sin(xx / 3.0) + np.cos(yy / 4.0)) * 60 + 128
    img = np.clip(pat, 0, 255).astype(np.uint8)
    img = np.roll(img, shift, axis=1)
    return np.stack([img, img, img], axis=-1)


def test_frame_mae_identical_is_zero():
    f = _textured()
    assert frame_mae_series([f, f.copy(), f.copy()]) == [0.0, 0.0]


def test_frame_mae_counts_transitions():
    frames = [_textured(0), _textured(2), _textured(4)]
    series = frame_mae_series(frames)
    assert len(series) == 2
    assert all(v > 0 for v in series)


def test_warp_error_near_zero_for_identical():
    # Farneback 对恒等帧不返回零流（max ~0.17px），INTER_LINEAR 重采样有 ~0.008/255 地板，
    # 故用 <0.05 容差而非 <1e-6（对抗审核确认 1e-6 恒失败）
    f = _textured()
    errs = warp_error_series([f, f.copy()], [f, f.copy()])
    assert errs[0] < 0.05


def test_warp_error_below_raw_mae_for_pure_translation():
    # 还原=原始（restored==flow_frames），纯平移场景 warp 应显著降低残差
    frames = [_textured(0), _textured(2)]
    raw = frame_mae_series(frames)[0]
    warped = warp_error_series(frames, frames)[0]
    assert warped < raw  # 光流补偿了平移


def test_temporal_report_splits_by_keyframe():
    # 6 帧，关键帧下标 {0, 3}；关键帧那几帧设为原样、其余带抖动
    restored = [_textured(0), _textured(5), _textured(5), _textured(0), _textured(5), _textured(5)]
    original = [_textured(0)] * 6
    rep = temporal_report(restored, original, keyframe_indices=[0, 3])
    assert rep["keyframe_count"] == 2
    # generated_only 排除触及关键帧(0,3)的转移 → 只剩 t=2 和 t=5
    assert rep["generated_only"]["mae"] is not None
    assert rep["delivered"]["mae"] >= rep["generated_only"]["mae"] - 1e-9
    assert rep["original_reference"]["mae"] == 0.0
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/test_temporal_consistency.py -v`
Expected: FAIL —— `ModuleNotFoundError: ...temporal_consistency`

- [ ] **Step 3: 写实现**（`src/semantic_transmission/evaluation/temporal_consistency.py`）

```python
"""视频时间一致性指标：相邻帧 MAE + 光流 warp-error。

面向"还原视频闪烁量化"——drop-in 逐帧独立生成在近静止段剧烈闪烁，本模块给出
可对比数值证据，与目视条带互补。帧为 (H, W, 3) uint8 RGB ndarray。
"""

from __future__ import annotations

import cv2
import numpy as np


def _to_gray(frame: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(frame.astype(np.uint8), cv2.COLOR_RGB2GRAY)


def frame_mae_series(frames: list[np.ndarray]) -> list[float]:
    """相邻帧平均绝对差序列，长度 = len(frames)-1（0-255 尺度）。"""
    out: list[float] = []
    for t in range(1, len(frames)):
        a = frames[t].astype(np.float64)
        b = frames[t - 1].astype(np.float64)
        out.append(float(np.abs(a - b).mean()))
    return out


def _remap_by_flow(img: np.ndarray, flow: np.ndarray) -> np.ndarray:
    """按稠密光流重采样 img。"""
    h, w = flow.shape[:2]
    grid_x, grid_y = np.meshgrid(np.arange(w), np.arange(h))
    map_x = (grid_x + flow[..., 0]).astype(np.float32)
    map_y = (grid_y + flow[..., 1]).astype(np.float32)
    return cv2.remap(
        img,
        map_x,
        map_y,
        interpolation=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_REPLICATE,
    )


def warp_error_series(
    frames: list[np.ndarray], flow_frames: list[np.ndarray]
) -> list[float]:
    """warp-error 序列：在 flow_frames 上算后向光流，warp frames[t-1] 后比 frames[t]。

    通常 frames=还原帧、flow_frames=原始帧——用真实运动扣掉合法位移、只留闪烁残差。
    两列表长度须一致。

    注：Farneback 对恒等/近静止帧不返回严格零流，加上 INTER_LINEAR 非整数重采样，
    warp-error 有 ~0.008（0-255 尺度）的算法地板；报告解读须以此为基线，不可把该量级
    读作"绝对零闪烁"。
    """
    if len(frames) != len(flow_frames):
        raise ValueError(
            f"frames({len(frames)}) 与 flow_frames({len(flow_frames)}) 长度不一致"
        )
    out: list[float] = []
    for t in range(1, len(frames)):
        flow = cv2.calcOpticalFlowFarneback(
            _to_gray(flow_frames[t]),
            _to_gray(flow_frames[t - 1]),
            None,
            0.5,
            3,
            15,
            3,
            5,
            1.2,
            0,
        )
        warped = _remap_by_flow(frames[t - 1], flow)
        err = np.abs(frames[t].astype(np.float64) - warped.astype(np.float64)).mean()
        out.append(float(err))
    return out


def _mean_or_none(values: list[float]) -> float | None:
    return float(np.mean(values)) if values else None


def temporal_report(
    restored: list[np.ndarray],
    original: list[np.ndarray],
    keyframe_indices: list[int] | None = None,
) -> dict:
    """两读时间一致性报告：交付（含关键帧边界）/ 生成帧间（排除边界）+ 原始对照。

    转移 t（连接 t-1 与 t）计入"生成帧间"当且仅当 t-1 与 t 都非关键帧。
    """
    kf = set(keyframe_indices or [])
    mae = frame_mae_series(restored)
    warp = warp_error_series(restored, original)
    orig_mae = frame_mae_series(original)

    gen_t = [t for t in range(1, len(restored)) if t not in kf and (t - 1) not in kf]

    def _sub(series: list[float]) -> list[float]:
        return [series[t - 1] for t in gen_t]

    return {
        "delivered": {"mae": _mean_or_none(mae), "warp_error": _mean_or_none(warp)},
        "generated_only": {
            "mae": _mean_or_none(_sub(mae)),
            "warp_error": _mean_or_none(_sub(warp)),
        },
        "original_reference": {"mae": _mean_or_none(orig_mae)},
        "keyframe_count": len(kf),
    }


__all__ = ["frame_mae_series", "warp_error_series", "temporal_report"]
```

- [ ] **Step 4: 跑测试确认通过 + ruff**

Run: `uv run pytest tests/test_temporal_consistency.py -v && uv run ruff format src/semantic_transmission/evaluation/temporal_consistency.py tests/test_temporal_consistency.py && uv run ruff check src/semantic_transmission/evaluation/temporal_consistency.py tests/test_temporal_consistency.py`
Expected: 全部 PASS，ruff 无报错。若 `test_warp_error_below_raw_mae_for_pure_translation` 偶发不过（Farneback 近似），把平移量 `shift=2` 改 `shift=1` 并重跑——但先按 shift=2 尝试。

- [ ] **Step 5: Commit**

```bash
git add src/semantic_transmission/evaluation/temporal_consistency.py tests/test_temporal_consistency.py
git commit -m "feat: 新增视频时间一致性指标（相邻帧 MAE + 光流 warp-error）

frame_mae_series / warp_error_series / temporal_report，量化还原视频闪烁：
warp-error 用原始帧光流扣掉合法运动、只留闪烁残差；temporal_report 两读拆分
交付（含关键帧边界）与生成帧间（排除边界），供阶段 2 裁决漂移是否被压住。"
```

---

### Task 3: 参考帧时序策略 + 质量两栏拆分（harness 层）

**Files:**
- Create: `scripts/poc/klein_ab/phase2.py`
- Test: `tests/poc/test_phase2_policy.py`

**Interfaces:**
- Consumes: `semantic_transmission.evaluation.video_eval.summarize_metrics`（对逐帧 metrics 求均值/标准差）、PIL。
- Produces:
  - `TemporalPolicyConfig(keyframe_interval=12, reference_mode="prev", keyframe_passthrough=True)`
  - `is_keyframe(index: int, config) -> bool`
  - `build_reference_images(mode: str, prev_output, last_keyframe) -> list`（返回接在 canny 之后的额外参考帧；顺序 prev 在前、keyframe 在后）
  - `split_summary(frames: list[dict], keyframe_indices) -> {"delivered": summary, "generated_only": summary}`

- [ ] **Step 1: 写失败测试**（`tests/poc/test_phase2_policy.py`）

```python
"""阶段 2 时序策略与质量拆分单测（无 GPU）。"""

import pytest
from PIL import Image

from scripts.poc.klein_ab.phase2 import (
    TemporalPolicyConfig,
    build_reference_images,
    is_keyframe,
    split_summary,
)


def _cfg(**kw):
    return TemporalPolicyConfig(**kw)


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
    assert build_reference_images("none", Image.new("RGB", (8, 8)), Image.new("RGB", (8, 8))) == []


def test_build_refs_prev_only():
    prev = Image.new("RGB", (8, 8), (1, 1, 1))
    kf = Image.new("RGB", (8, 8), (2, 2, 2))
    refs = build_reference_images("prev", prev, kf)
    assert refs == [prev]


def test_build_refs_keyframe_only():
    prev = Image.new("RGB", (8, 8), (1, 1, 1))
    kf = Image.new("RGB", (8, 8), (2, 2, 2))
    assert build_reference_images("keyframe", prev, kf) == [kf]


def test_build_refs_prev_keyframe_order():
    prev = Image.new("RGB", (8, 8), (1, 1, 1))
    kf = Image.new("RGB", (8, 8), (2, 2, 2))
    assert build_reference_images("prev_keyframe", prev, kf) == [prev, kf]  # prev 在前


def test_build_refs_drops_none_prev():
    kf = Image.new("RGB", (8, 8), (2, 2, 2))
    assert build_reference_images("prev_keyframe", None, kf) == [kf]


def test_build_refs_invalid_mode_raises():
    with pytest.raises(ValueError, match="reference_mode"):
        build_reference_images("bogus", None, None)


def test_split_summary_excludes_keyframe_indices():
    # 构造 4 帧逐帧指标：关键帧 {0} 给满分 ssim=1.0，生成帧 ssim=0.5
    frames = [
        {"index": 0, "metrics": {"psnr": 99.0, "ssim": 1.0, "lpips": 0.0, "clip_score": 40.0}},
        {"index": 1, "metrics": {"psnr": 15.0, "ssim": 0.5, "lpips": 0.4, "clip_score": 30.0}},
        {"index": 2, "metrics": {"psnr": 15.0, "ssim": 0.5, "lpips": 0.4, "clip_score": 30.0}},
        {"index": 3, "metrics": {"psnr": 15.0, "ssim": 0.5, "lpips": 0.4, "clip_score": 30.0}},
    ]
    out = split_summary(frames, keyframe_indices=[0])
    assert out["delivered"]["ssim"]["count"] == 4
    assert out["generated_only"]["ssim"]["count"] == 3  # 排除关键帧 0
    assert out["generated_only"]["ssim"]["mean"] == pytest.approx(0.5)
    assert out["delivered"]["ssim"]["mean"] > out["generated_only"]["ssim"]["mean"]
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/poc/test_phase2_policy.py -v`
Expected: FAIL —— `ModuleNotFoundError: scripts.poc.klein_ab.phase2`

- [ ] **Step 3: 写实现**（`scripts/poc/klein_ab/phase2.py`）

```python
"""阶段 2 参考帧时序策略 + 质量两栏拆分（编排层纯逻辑，可单测）。

时序策略不进接收端：接收端保持无状态单帧契约，此处只做"给定跨帧状态 →
构造参考帧列表 / 判定关键帧 / 拆分质量指标"的纯函数，由 run_phase2.py 持状态编排。
"""

from __future__ import annotations

from dataclasses import dataclass

from semantic_transmission.evaluation.video_eval import summarize_metrics

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

    顺序：prev 在前、keyframe 在后（对齐设计 C = [canny, prev, keyframe]）。
    prev_output / last_keyframe 为 None 时该项跳过。
    """
    if mode not in _VALID_MODES:
        raise ValueError(
            f"未知 reference_mode: {mode!r}，支持 {sorted(_VALID_MODES)}"
        )
    refs = []
    if mode in ("prev", "prev_keyframe") and prev_output is not None:
        refs.append(prev_output)
    if mode in ("keyframe", "prev_keyframe") and last_keyframe is not None:
        refs.append(last_keyframe)
    return refs


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

- [ ] **Step 4: 跑测试确认通过 + ruff**

Run: `uv run pytest tests/poc/test_phase2_policy.py -v && uv run ruff format scripts/poc/klein_ab/phase2.py tests/poc/test_phase2_policy.py && uv run ruff check scripts/poc/klein_ab/phase2.py tests/poc/test_phase2_policy.py`
Expected: 全部 PASS，ruff 无报错

- [ ] **Step 5: Commit**

```bash
git add scripts/poc/klein_ab/phase2.py tests/poc/test_phase2_policy.py
git commit -m "feat: 阶段 2 参考帧时序策略 + 质量两栏拆分（编排层纯逻辑）

TemporalPolicyConfig / is_keyframe / build_reference_images（X/C/消融一个旋钮）+
split_summary（delivered 全帧 vs generated_only 排除关键帧下标）。纯函数、可单测，
不进接收端——接收端保持无状态单帧契约。"
```

---

### Task 4: 阶段 2 harness（run_phase2.py）+ GPU 有界 smoke 验证

**Files:**
- Create: `scripts/poc/klein_ab/run_phase2.py`

**Interfaces:**
- Consumes: `KleinReceiverConfig`、`create_receiver(backend="klein")`、`load_as_rgb`、`write_frames`、`LocalCannyExtractor`、`load_config`、`evaluate_video`、`_fill_failed_frames`；Task 2 的 `temporal_report`；Task 3 的 `TemporalPolicyConfig / is_keyframe / build_reference_images / split_summary`；复用 `scripts.poc.klein_ab.run_ab` 的 `log / _empty_cache / _reset_peak / _peak_vram_gb / _is_oom`。
- Consumes（磁盘资产）：`output/poc/klein-ab-phase1/fixture/fixture_frames/frame_*.png`（原图）、`prompts.json`、`klein/frames/frame_*.png`（drop-in baseline）。
- Produces: `output/poc/klein-phase2/<label>/` 下 `frames/`、`out.mp4`、`results.json`（含 policy / work_size / 质量两栏 / 时序两读 / baseline 对照 / 显存 / 耗时）、`DONE`(或 `DONE.partial`) sentinel、`compare/grid_*.png`（orig｜canny｜drop-in｜X）+ `compare/strip_static_120-127.png`。

- [ ] **Step 1: 写 harness**（`scripts/poc/klein_ab/run_phase2.py`）

```python
"""klein 阶段 2 参考帧时间一致性补偿 harness（复用阶段 1 资产、单模型 klein）。

流水：读阶段 1 fixture_frames + 冻结 prompts → 多参考 smoke 探显存（有界回退）→
按 TemporalPolicyConfig 主跑（关键帧透传 / 中间帧带参考生成）→ 质量两栏评估 +
时序两读 + baseline 对照 → results.json + DONE sentinel + 目视网格。

健壮性：崩溃写 partial results + DONE.partial；smoke OOM 有界回退并同步重烘 baseline
分辨率；零交互输入。

用法（长 GPU 任务，须脱离跑；以模块方式运行以便 scripts.* 包导入）：
    uv run python -m scripts.poc.klein_ab.run_phase2 \
        --reference-mode prev --keyframe-interval 12 --label x_n12
    # smoke 验证接线（少量帧）：加 --limit 6
"""

from __future__ import annotations

import argparse
import json
import time
import traceback
from pathlib import Path

import numpy as np
from PIL import Image

from scripts.poc.klein_ab.phase2 import (
    TemporalPolicyConfig,
    build_reference_images,
    is_keyframe,
    split_summary,
)
from scripts.poc.klein_ab.run_ab import (
    _empty_cache,
    _is_oom,
    _peak_vram_gb,
    _reset_peak,
    log,
)
from semantic_transmission.common.config import KleinReceiverConfig, load_config
from semantic_transmission.common.image_io import load_as_rgb
from semantic_transmission.common.video_io import write_frames
from semantic_transmission.evaluation.temporal_consistency import temporal_report
from semantic_transmission.evaluation.video_eval import evaluate_video
from semantic_transmission.pipeline.video_pipeline import _fill_failed_frames
from semantic_transmission.receiver import create_receiver
from semantic_transmission.receiver.klein_receiver import fit_working_size
from semantic_transmission.sender.local_condition_extractor import LocalCannyExtractor

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_PHASE1_DIR = _PROJECT_ROOT / "output" / "poc" / "klein-ab-phase1"
_STATIC_WINDOW = (120, 128)  # 近静止段 [120,128)，重点看闪烁


def _load_pngs(frames_dir: Path, limit: int | None) -> list[Image.Image]:
    """按帧号顺序加载 PNG 为 RGB PIL 列表。"""
    paths = sorted(frames_dir.glob("frame_*.png"))
    if limit:
        paths = paths[:limit]
    return [load_as_rgb(p) for p in paths]


def _load_prompts(path: Path, limit: int | None) -> list[str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    ordered = sorted(data["frames"], key=lambda f: f["index"])
    prompts = [f.get("prompt", "") for f in ordered]
    return prompts[:limit] if limit else prompts


def _as_arrays(images: list[Image.Image]) -> list[np.ndarray]:
    return [np.asarray(im) for im in images]


def _fit_all(images: list[Image.Image], max_side: int) -> list[Image.Image]:
    """把整段帧统一降采样到工作分辨率 max_side（保宽高比、round 16）。

    smoke 若从原生分辨率回退到更小 R，fixture / baseline / 透传关键帧都要同步归一化到 R，
    否则透传帧(原生) 与生成帧(R) 尺寸混杂会让 write_frames/temporal_report 崩溃，并把
    X@R 与 baseline@原生 变成不公平的跨分辨率对照（落实 spec §5.4/§9 同步重烘 baseline）。
    """
    return [fit_working_size(im, max_side) for im in images]


def smoke_probe(fixture, canny, policy, candidates, seed):
    """前 3 帧跑真实策略，锁能扛的工作分辨率（多参考显存有界回退）。

    Returns: (max_side, vae_tiling, history)。全候选 OOM 抛 RuntimeError。
    """
    history: list[dict] = []
    test = fixture[: min(3, len(fixture))]
    for cand in candidates:
        for vae_tiling in (False, True):
            label = f"R={cand}, vae_tiling={vae_tiling}"
            log(f"smoke 尝试多参考 {label}（{len(test)} 帧, mode={policy.reference_mode}）")
            rec = None
            try:
                cfg = KleinReceiverConfig(max_side=cand, enable_vae_tiling=vae_tiling)
                rec = create_receiver(config=cfg, backend="klein")
                _reset_peak()
                prev_out = None
                last_kf = None
                for i, frame in enumerate(test):
                    edge = canny.extract(np.asarray(frame))
                    if is_keyframe(i, policy) and policy.keyframe_passthrough:
                        prev_out = frame
                        last_kf = frame
                        continue
                    refs = build_reference_images(
                        policy.reference_mode, prev_out, last_kf
                    )
                    prev_out = rec.process(
                        load_as_rgb(edge), "a dashcam road scene", seed=seed,
                        reference_images=refs,
                    )
                peak = _peak_vram_gb()
                history.append(
                    {"candidate": cand, "vae_tiling": vae_tiling, "result": "ok",
                     "peak_vram_gb": peak}
                )
                log(f"smoke 通过 {label}，峰值显存={peak}GB")
                return cand, vae_tiling, history
            except Exception as e:  # noqa: BLE001
                oom = _is_oom(e)
                history.append(
                    {"candidate": cand, "vae_tiling": vae_tiling,
                     "result": "oom" if oom else "error", "error": str(e)[:300]}
                )
                log(f"smoke 失败 {label}: {'OOM' if oom else type(e).__name__}: {str(e)[:160]}")
                if not oom:
                    raise
            finally:
                if rec is not None:
                    try:
                        rec.unload()
                    except Exception:  # noqa: BLE001
                        pass
                _empty_cache()
    raise RuntimeError(f"smoke 全部候选 OOM；history={history}")


def run_policy(fixture, prompts, canny, policy, max_side, vae_tiling, seed):
    """按策略主跑：关键帧透传、中间帧带参考生成。返回 (输出帧列表, 关键帧下标, 统计)。"""
    cfg = KleinReceiverConfig(max_side=max_side, enable_vae_tiling=vae_tiling)
    rec = create_receiver(config=cfg, backend="klein")
    outputs: list[Image.Image | None] = []
    keyframe_indices: list[int] = []
    prev_out = None
    last_kf = None
    _reset_peak()
    t0 = time.time()
    failed = 0
    try:
        for i, frame in enumerate(fixture):
            if is_keyframe(i, policy) and policy.keyframe_passthrough:
                outputs.append(frame)  # 透传原图，不生成
                keyframe_indices.append(i)
                prev_out = frame  # 链首复位到真关键帧
                last_kf = frame
                continue
            if is_keyframe(i, policy):
                last_kf = frame  # 关键帧但不透传（passthrough=False）时仍更新锚
            edge = canny.extract(np.asarray(frame))
            refs = build_reference_images(policy.reference_mode, prev_out, last_kf)
            try:
                img = rec.process(
                    load_as_rgb(edge), prompts[i], seed=seed, reference_images=refs
                )
            except Exception as e:  # noqa: BLE001
                log(f"[{i}] 生成失败：{type(e).__name__}: {str(e)[:160]}")
                img = None
                failed += 1
            outputs.append(img)
            prev_out = img if img is not None else prev_out
            if (i + 1) % 20 == 0:
                log(f"主跑 {i + 1}/{len(fixture)}")
    finally:
        try:
            rec.unload()
        except Exception:  # noqa: BLE001
            pass
        _empty_cache()
    elapsed = time.time() - t0
    generated = len(fixture) - len(keyframe_indices)
    stat = {
        "frames": len(fixture),
        "keyframe_count": len(keyframe_indices),
        "generated_frames": generated,
        "failed": failed,
        "total_time_s": round(elapsed, 1),
        "avg_s_per_generated": round(elapsed / max(1, generated), 2),
        "peak_vram_gb": _peak_vram_gb(),
    }
    log(
        f"主跑完成：{generated} 生成 + {len(keyframe_indices)} 透传，"
        f"失败 {failed}，均 {stat['avg_s_per_generated']}s/生成帧，峰值 {stat['peak_vram_gb']}GB"
    )
    return outputs, keyframe_indices, stat


def eval_quality(orig_arrays, restored_arrays, prompts, keyframe_indices, device):
    """逐帧质量评估 + 两栏拆分。"""
    report = evaluate_video(orig_arrays, restored_arrays, prompts=prompts, device=device)
    return split_summary(report["frames"], keyframe_indices)


def window_mae(arrays, lo, hi):
    """近静止窗口 [lo,hi) 的相邻帧 MAE 均值（纯闪烁读数）。"""
    from semantic_transmission.evaluation.temporal_consistency import frame_mae_series

    sub = arrays[lo:hi]
    series = frame_mae_series(sub)
    return float(np.mean(series)) if series else None


def _cell(img, size):
    return img if img is not None else Image.new("RGB", size, (40, 40, 40))


def make_grid(orig, canny, restored, baseline, out_dir, static_window=None, n=5):
    """抽 n 帧并排 orig｜canny｜drop-in｜X 网格；并对近静止窗口拼连续帧条带。

    baseline（阶段 1 drop-in，长度须等于 orig）作对照列；为空则退回 orig｜canny｜X。
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    total = len(orig)
    if total == 0:
        return
    has_base = len(baseline) == total
    n = min(n, total)
    idxs = [round(i * (total - 1) / (n - 1)) for i in range(n)] if n > 1 else [0]
    for idx in idxs:
        o = orig[idx]
        edge = load_as_rgb(canny.extract(np.asarray(o)))
        tiles = [o, edge]
        if has_base:
            tiles.append(_cell(baseline[idx], o.size))  # drop-in 对照列
        tiles.append(_cell(restored[idx], o.size))
        h = o.size[1]
        norm = [t if t.size[1] == h else t.resize((int(t.size[0] * h / t.size[1]), h)) for t in tiles]
        w = sum(t.size[0] for t in norm)
        grid = Image.new("RGB", (w, h), (0, 0, 0))
        x = 0
        for t in norm:
            grid.paste(t, (x, 0))
            x += t.size[0]
        grid.save(out_dir / f"grid_{idx:04d}.png")
    cols = "orig|canny|drop-in|X" if has_base else "orig|canny|X"
    log(f"目视网格完成：{len(idxs)} 张（{cols}）→ {out_dir}")
    if static_window is not None:
        _static_strip(orig, restored, baseline, static_window, out_dir)


def _static_strip(orig, restored, baseline, window, out_dir):
    """近静止窗口 [lo,hi) 连续帧横向拼条带，orig / drop-in / X 各一行纵向叠放，直观看闪烁。"""
    lo, hi = window
    hi = min(hi, len(orig))
    if hi - lo < 2:
        return
    rows = [("orig", orig)]
    if len(baseline) == len(orig):
        rows.append(("drop-in", baseline))
    rows.append(("X", restored))
    size = orig[lo].size
    cell_w, cell_h = size
    strips = []
    for _, seq in rows:
        row = Image.new("RGB", (cell_w * (hi - lo), cell_h), (0, 0, 0))
        for j, t in enumerate(range(lo, hi)):
            im = _cell(seq[t], size)
            if im.size != size:
                im = im.resize(size)
            row.paste(im, (j * cell_w, 0))
        strips.append(row)
    strip = Image.new("RGB", (cell_w * (hi - lo), cell_h * len(strips)), (0, 0, 0))
    for r, row in enumerate(strips):
        strip.paste(row, (0, r * cell_h))
    strip.save(out_dir / f"strip_static_{lo}-{hi - 1}.png")
    log(f"近静止条带完成：[{lo},{hi}) × {len(strips)} 行 → strip_static_{lo}-{hi - 1}.png")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="klein 阶段 2 参考帧补偿 harness")
    parser.add_argument("--reference-mode", default="prev",
                        choices=["none", "prev", "keyframe", "prev_keyframe"])
    parser.add_argument("--keyframe-interval", type=int, default=12)
    parser.add_argument("--keyframe-passthrough", action=argparse.BooleanOptionalAction,
                        default=True)
    parser.add_argument("--label", default=None, help="输出子目录名，默认据策略自动生成")
    parser.add_argument("--phase1-dir", type=Path, default=_PHASE1_DIR)
    parser.add_argument("--out-root", type=Path,
                        default=_PROJECT_ROOT / "output" / "poc" / "klein-phase2")
    parser.add_argument("--candidates", default="896,768")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--limit", type=int, default=None, help="仅前 N 帧（smoke 验证接线用）")
    parser.add_argument("--grid", type=int, default=5)
    args = parser.parse_args(argv)

    policy = TemporalPolicyConfig(
        keyframe_interval=args.keyframe_interval,
        reference_mode=args.reference_mode,
        keyframe_passthrough=args.keyframe_passthrough,
    )
    label = args.label or f"{args.reference_mode}_n{args.keyframe_interval}"
    out_dir = args.out_root / label
    out_dir.mkdir(parents=True, exist_ok=True)
    for s in (out_dir / "DONE", out_dir / "DONE.partial"):
        if s.exists():
            s.unlink()

    candidates = [int(x) for x in args.candidates.split(",") if x.strip()]
    cfg = load_config()
    canny = LocalCannyExtractor(cfg.canny_low_threshold, cfg.canny_high_threshold)
    device = "cuda"
    results: dict = {
        "label": label,
        "policy": vars(policy),
        "seed": args.seed,
        "limit": args.limit,
    }
    t_start = time.time()
    ok = True
    try:
        import torch

        device = "cuda" if torch.cuda.is_available() else "cpu"

        fixture = _load_pngs(args.phase1_dir / "fixture" / "fixture_frames", args.limit)
        prompts = _load_prompts(args.phase1_dir / "prompts.json", args.limit)
        if len(fixture) != len(prompts):
            raise ValueError(f"fixture({len(fixture)}) 与 prompts({len(prompts)}) 帧数不符")
        log(f"读阶段 1 资产：{len(fixture)} 帧 @ {fixture[0].size}")

        R, vae_tiling, smoke_hist = smoke_probe(fixture, canny, policy, candidates, args.seed)
        results["smoke"] = {"locked_R": R, "vae_tiling": vae_tiling, "history": smoke_hist}

        # 缺陷 A 修复：smoke 锁定 R 后，把 fixture / baseline 统一归一化到 R，保证透传
        # 关键帧、生成帧、orig、baseline 全序列同尺寸（同步重烘 baseline，落实 §5.4/§9）。
        fixture = _fit_all(fixture, R)
        base_frames = _fit_all(
            _load_pngs(args.phase1_dir / "klein" / "frames", args.limit), R
        )
        results["work_size"] = list(fixture[0].size)
        log(f"工作分辨率归一化到 {fixture[0].size}（R={R}）")

        outputs, keyframe_indices, stat = run_policy(
            fixture, prompts, canny, policy, R, vae_tiling, args.seed
        )
        results["run"] = {**stat, "keyframe_indices": keyframe_indices}

        fdir = out_dir / "frames"
        fdir.mkdir(parents=True, exist_ok=True)
        for i, img in enumerate(outputs):
            if img is not None:
                img.save(fdir / f"frame_{i:04d}.png")
        filled = _fill_failed_frames(outputs)

        # 评估前断言全序列同尺寸，错配 fail-fast（而非静默产出崩溃/不公平数据）
        has_base = len(base_frames) == len(fixture)
        sizes = {im.size for im in filled} | {im.size for im in fixture}
        if has_base:
            sizes |= {im.size for im in base_frames}
        if len(sizes) != 1:
            raise RuntimeError(f"帧尺寸不一致，拒绝产出错配对照：{sorted(sizes)}")

        write_frames(out_dir / "out.mp4", filled, fps=25.0)

        orig_arrays = _as_arrays(fixture)
        rest_arrays = _as_arrays(filled)
        results["quality"] = eval_quality(
            orig_arrays, rest_arrays, prompts, keyframe_indices, device
        )
        results["temporal"] = temporal_report(rest_arrays, orig_arrays, keyframe_indices)
        results["temporal"]["static_window_mae"] = {
            "window": list(_STATIC_WINDOW),
            "restored": window_mae(rest_arrays, *_STATIC_WINDOW),
            "original": window_mae(orig_arrays, *_STATIC_WINDOW),
        }

        # baseline（阶段 1 drop-in，已归一化到 R）在相同下标上对照
        if has_base:
            base_arrays = _as_arrays(base_frames)
            results["baseline"] = {
                "quality": eval_quality(
                    orig_arrays, base_arrays, prompts, keyframe_indices, device
                ),
                "temporal": temporal_report(base_arrays, orig_arrays, keyframe_indices),
            }
            results["baseline"]["temporal"]["static_window_mae"] = {
                "restored": window_mae(base_arrays, *_STATIC_WINDOW),
            }
        else:
            base_frames = []
            log(f"baseline 帧数与 fixture({len(fixture)}) 不符，跳过对照")

        make_grid(
            fixture, canny, outputs, base_frames, out_dir / "compare",
            static_window=_STATIC_WINDOW, n=args.grid,
        )
    except Exception as e:  # noqa: BLE001
        ok = False
        results["fatal_error"] = f"{type(e).__name__}: {e}"
        results["traceback"] = traceback.format_exc()
        log(f"致命错误：{type(e).__name__}: {e}")
        traceback.print_exc()

    results["total_wall_s"] = round(time.time() - t_start, 1)
    (out_dir / "results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    sentinel = out_dir / ("DONE" if ok else "DONE.partial")
    sentinel.write_text(time.strftime("%Y-%m-%d %H:%M:%S"), encoding="utf-8")
    log(f"{'=' * 50}\n结束（{'OK' if ok else 'PARTIAL'}），results.json + {sentinel.name} 已写。"
        f"墙钟 {results['total_wall_s']}s")
    return 0 if ok else 1


if __name__ == "__main__":
    import sys

    sys.exit(main())
```

- [ ] **Step 2: ruff 静态检查**（无 GPU 环节先过格式/lint）

Run: `uv run ruff format scripts/poc/klein_ab/run_phase2.py && uv run ruff check scripts/poc/klein_ab/run_phase2.py`
Expected: 无报错（若报未用 import / 行长，按提示修）

- [ ] **Step 3: 全量单测回归**（确认前序模块无回归）

Run: `uv run pytest -q`
Expected: 全绿（Task 1-3 的测试 + 既有测试）

- [ ] **Step 4: GPU 有界 smoke 验证接线**（少量帧，脱离跑 + Monitor 守候）

这是 harness 的集成验证：跑 6 帧（下标 0 为关键帧透传），证明 smoke 探显存、透传、带参考生成、两栏评估、时序两读、baseline 对照、sentinel 全链路通。**必须脱离跑**（单帧推理超后台 2min 限制）：

```powershell
$env:PYTHONIOENCODING="utf-8"
Start-Process -NoNewWindow -FilePath "uv" -ArgumentList @(
  "run","python","-m","scripts.poc.klein_ab.run_phase2",
  "--reference-mode","prev","--keyframe-interval","12","--limit","6","--label","smoke_x_n12"
) -RedirectStandardOutput "output/poc/klein-phase2/smoke.log" -RedirectStandardError "output/poc/klein-phase2/smoke.err"
```

用 Monitor 守候 sentinel 出现（`output/poc/klein-phase2/smoke_x_n12/DONE` 或 `DONE.partial`）。

- [ ] **Step 5: 核对 smoke 产物**

Run（sentinel 出现后）: `cat output/poc/klein-phase2/smoke_x_n12/results.json`
Expected: `DONE`（非 partial）；`results.json` 含 `smoke.locked_R`、`work_size`、`run.keyframe_indices` 含 `0`、`quality.delivered` / `quality.generated_only` 均有 ssim，`temporal.delivered` / `temporal.generated_only` / `temporal.static_window_mae`、`baseline` 段齐全；`frames/` 有 6 张、`out.mp4` 存在、`compare/grid_*.png`（4 列 orig｜canny｜drop-in｜X）存在。注：`--limit 6` 时近静止窗口 [120,128) 超出范围，`strip_static` 会跳过属正常。若为 `DONE.partial`，读 `fatal_error`/`traceback` 定位并修复后重跑本步。

- [ ] **Step 6: Commit**

```bash
git add scripts/poc/klein_ab/run_phase2.py
git commit -m "feat: 阶段 2 参考帧补偿 harness（run_phase2.py）

复用阶段 1 fixture/冻结 prompt/drop-in baseline，单模型 klein 按 TemporalPolicyConfig
主跑（关键帧透传 + 中间帧带参考生成）；多参考 smoke 探显存有界回退，质量两栏 +
时序两读 + baseline 同下标对照，崩溃写 partial+sentinel。--limit 供 smoke 验证接线。"
```

> 注：`output/poc/` 为 gitignored，产物不入库；只提交 harness 脚本。

---

### Task 5: 全量运行 X@N12 / X@N25 + 阶段 2 报告

**Files:**
- Create: `docs/test-reports/2026-07-01-klein-video-phase2.md`（跑完据 results.json 写）

**Interfaces:**
- Consumes: Task 4 的 `run_phase2.py`；阶段 1 资产。
- Produces: `output/poc/klein-phase2/x_n12/` 与 `x_n25/`（各 250 帧结果 + results.json）；阶段 2 报告。

- [ ] **Step 1: 全量跑 X@N12**（≈2 关键帧/秒，长 GPU 任务，脱离跑 + Monitor 守候）

```powershell
$env:PYTHONIOENCODING="utf-8"
Start-Process -NoNewWindow -FilePath "uv" -ArgumentList @(
  "run","python","-m","scripts.poc.klein_ab.run_phase2",
  "--reference-mode","prev","--keyframe-interval","12","--label","x_n12"
) -RedirectStandardOutput "output/poc/klein-phase2/x_n12.log" -RedirectStandardError "output/poc/klein-phase2/x_n12.err"
```

Monitor 守候 `output/poc/klein-phase2/x_n12/DONE`。预计 ~230 生成帧 × ~15-17s ≈ 60-70min。

- [ ] **Step 2: 全量跑 X@N25**（≈1 关键帧/秒，同上脱离跑）

```powershell
$env:PYTHONIOENCODING="utf-8"
Start-Process -NoNewWindow -FilePath "uv" -ArgumentList @(
  "run","python","-m","scripts.poc.klein_ab.run_phase2",
  "--reference-mode","prev","--keyframe-interval","25","--label","x_n25"
) -RedirectStandardOutput "output/poc/klein-phase2/x_n25.log" -RedirectStandardError "output/poc/klein-phase2/x_n25.err"
```

Monitor 守候 `output/poc/klein-phase2/x_n25/DONE`。

- [ ] **Step 3: 核对两路结果均为 DONE**

Run: `ls output/poc/klein-phase2/x_n12/DONE output/poc/klein-phase2/x_n25/DONE && cat output/poc/klein-phase2/x_n12/results.json output/poc/klein-phase2/x_n25/results.json`
Expected: 两个 DONE 均在；results.json 无 `fatal_error`，`failed` 为 0（或极少）。若 partial，据 traceback 修复重跑。

- [ ] **Step 4: 目视核对闪烁改善**

打开 `output/poc/klein-phase2/x_n12/out.mp4`、`compare/strip_static_120-127.png`（orig / drop-in / X 三行并排近静止段）与 `compare/grid_*.png`（orig｜canny｜drop-in｜X）：重点看近静止 120-127 段 X 相对 drop-in 闪烁是否缓解、是否出现关键帧周期 pop、是否过度冻结（画面不跟真实运动）。

- [ ] **Step 5: 写阶段 2 报告**（`docs/test-reports/2026-07-01-klein-video-phase2.md`）

据两路 results.json 填写以下骨架（数值从 `quality` / `temporal` / `baseline` / `run` 段取；**不要编造**，缺失项标 N/A）：

```markdown
# 阶段 2 结论报告：klein 参考帧时间一致性补偿 X 方案（2026-07-01）

> 设计：[../superpowers/specs/2026-07-01-klein-phase2-reference-frame-design.md](../superpowers/specs/2026-07-01-klein-phase2-reference-frame-design.md)
> 上游：[阶段 1 报告](2026-06-30-klein-video-ab-phase1.md)（裁决点）
> Harness：`scripts/poc/klein_ab/run_phase2.py` ｜ 产物：`output/poc/klein-phase2/`（gitignored）

## 0. 结论先行
（X 是否把 drop-in 的剧烈漂移压到可用；N12 vs N25 哪个好；是否需进 C）

## 1. 实验设置
（复用阶段 1 fixture 250 帧 896×496 / 冻结 prompt / seed=0；X@N12、X@N25；baseline=阶段 1 drop-in）

## 2. 时间一致性（决定性指标）
| 指标 | baseline(drop-in) | X@N12 | X@N25 | 解读 |
|---|---|---|---|---|
| 相邻帧 MAE（交付）| | | | |
| 相邻帧 MAE（生成帧间）| | | | |
| warp-error（交付）| | | | |
| warp-error（生成帧间）| | | | |
| 近静止 120-127 MAE | | | | 原始≈ __ ，纯闪烁读数 |

## 3. 质量指标（两栏）
| 指标 | 栏 | baseline | X@N12 | X@N25 |
|---|---|---|---|---|
| CLIP / PSNR / SSIM / LPIPS | 全帧交付 / 仅生成帧同下标 | | | |

## 4. 目视
（120-127 条带；关键帧 pop / 过度冻结观察）

## 5. 速度 / 显存
（avg_s_per_generated、peak_vram_gb；smoke 锁定分辨率）

## 6. 对 klein 主线决策的影响 + 下一步
（据设计 §8 口径：压住→进阶段 3 productionize；压不住→是否上 C 消融，再不行回退 Z-Image）

## 7. 验收
（时序 MAE/warp-error 下降？目视闪烁缓解？未过度冻结？）
```

- [ ] **Step 6: Commit 报告 + 暂停待定 C**

```bash
git add docs/test-reports/2026-07-01-klein-video-phase2.md
git commit -m "docs: klein 阶段 2 X 方案（参考帧补偿）结论报告

X@N12 / X@N25 相对阶段 1 drop-in 的时间一致性 + 质量对比，含近静止段闪烁读数。
据设计 §4/§8 口径：跑完暂停，与负责人据本报告定是否上 C（prev_keyframe）消融。"
```

> **暂停点**（设计 §4/§8）：X 结果复盘后再决定是否跑 C（`--reference-mode prev_keyframe`，harness 已支持，无需改码）。C 不在本计划自动执行范围。

---

## Self-Review

**1. Spec coverage：**
- 设计 §3.1 接收端 reference_images 能力 → Task 1 ✅
- 设计 §3.2 TemporalPolicyConfig / reference_mode / is_keyframe / build_refs → Task 3 ✅
- 设计 §4 实验矩阵（先 X@N12/N25 后 C）→ Task 4 harness + Task 5 运行；C 留暂停点 ✅
- 设计 §5.1 质量两栏 + 同下标对比 baseline → Task 3 `split_summary` + Task 4 baseline 段 ✅
- 设计 §5.2 时序 MAE + warp-error 两读 + 原始对照 + 近静止窗口 → Task 2 + Task 4 `temporal`/`static_window_mae` ✅
- 设计 §5.3 目视网格（orig｜canny｜drop-in｜X）+ 近静止条带 → Task 4 `make_grid`（4 列）+ `_static_strip` ✅
- 设计 §5.4 复用资产 + 多参考 smoke 有界回退 + **归一化 fixture/透传/baseline 到 R + 尺寸断言 fail-fast** → Task 4 `smoke_probe` + `_fit_all` + main 尺寸断言 ✅（对抗审核缺陷 A 已修）
- 设计 §6 长 GPU 任务 Start-Process + Monitor → Task 4 Step 4、Task 5 Step 1/2 ✅
- 设计 §8 验收/决策口径 → Task 5 报告骨架 §6/§7 ✅
- 设计 §7 不动 VideoPipeline/relay/CLI → 计划无相关改动 ✅

**2. Placeholder scan：** 无 TBD/TODO；报告骨架为待填数值（明确标"从 results.json 取、勿编造"），属运行后产物非代码占位。

**3. Type consistency：**
- `TemporalPolicyConfig` 字段（keyframe_interval/reference_mode/keyframe_passthrough）Task 3 定义、Task 4 一致使用 ✅
- `build_reference_images(mode, prev_output, last_keyframe) -> list`、`is_keyframe(index, config)`、`split_summary(frames, keyframe_indices)` Task 3 定义、Task 4 调用签名一致 ✅
- `temporal_report(restored, original, keyframe_indices)`、`frame_mae_series`、`warp_error_series` Task 2 定义、Task 4 调用一致 ✅
- `KleinReceiver.process(..., reference_images=None)` Task 1 定义、Task 4 `smoke_probe`/`run_policy` 调用一致 ✅
- 复用 `run_ab` 的 `log/_empty_cache/_reset_peak/_peak_vram_gb/_is_oom` 均为阶段 1 已存在函数 ✅
- `fit_working_size` 从 `klein_receiver` 导入（阶段 1 `run_ab` 同款用法）；`_fit_all(images, R)`、
  `make_grid(orig, canny, restored, baseline, out_dir, static_window, n)`、`_static_strip(...)` 定义与 main 调用签名一致 ✅
- Task 2 warp 恒等测试更名 `test_warp_error_near_zero_for_identical`、阈值 `<0.05`（1e-6 恒失败已修）✅
```
