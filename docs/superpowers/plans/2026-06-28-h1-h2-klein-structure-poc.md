# H1+H2 PoC：klein 结构遵循度 + 速度三档 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用数据裁决目标版关键帧主线选 FLUX.2-klein-9B 还是 Qwen-Image+InstantX——产出逐帧边缘 IoU、目视对比产物、klein 速度三档，给出 go/no-go。

**Architecture:** 在隔离 worktree 内、不碰 `src/` 主线代码；PoC 脚本独立放 `scripts/poc/h1_h2/`，纯逻辑（IoU/抽帧/报告）走 TDD，GPU 模型加载走「smoke 关卡 + 回退梯度」的 spike 方式。klein 与 Qwen 两臂串行（单卡 24GB 装不下两套），同一组帧横向比 IoU。

**Tech Stack:** diffusers（git main，含 `Flux2KleinPipeline`）、transformers（Qwen3 文本编码器）、InstantX 自定义 Qwen-Image ControlNet pipeline（本地导入）、OpenCV Canny、imageio、numpy。uv 管理依赖。

## Global Constraints

- 所有 Python 操作走 `uv run`，禁止直接 `python`/`pip`/`pytest`/`ruff`。
- 不修改 `src/semantic_transmission/` 主线代码；PoC 全部落 `scripts/poc/h1_h2/` 与 `tests/poc/`。
- 推送前 `uv run ruff check .` + `uv run ruff format --check .` 必须通过（CI 覆盖全仓库 `.`）。
- 模型根 `MODEL_CACHE_DIR=D:\Downloads\Models`，模型已就位（见 spec §3.1），depth 暂不用。
- 单卡 RTX 5090 Laptop 24GB；klein 必须 fp8 transformer + CPU offload；显存触顶即按回退梯度降级。
- 判据（spec §4.2）：边缘 IoU>0.4 且目视几何跟随 → 保 klein；klein 不过而 Qwen 过 → 切 Qwen；Canny 阈值复用 config 100/200。
- 测试视频：`resources/test_videos/prepared/`（gitignored，仅本地）；CI 不可见，抽帧测试须用合成视频。
- 上游 spec：`docs/superpowers/specs/2026-06-28-h1-h2-klein-structure-poc-design.md`。
- Commit message 中文、Angular 规范，不含工具生成标记/Co-Authored-By。

---

### Task 1: PoC 脚手架 + 边缘 IoU 度量

**Files:**
- Create: `scripts/poc/h1_h2/__init__.py`
- Create: `scripts/poc/h1_h2/iou.py`
- Test: `tests/poc/__init__.py`, `tests/poc/test_iou.py`

**Interfaces:**
- Produces:
  - `edge_iou(canny_a: NDArray[uint8], canny_b: NDArray[uint8], dilation: int = 0) -> float` —— 两张二值 Canny 边缘图（0/255 或 0/1，shape (H,W)）的交并比；`dilation>0` 时对两张 mask 各做 `dilation`×`dilation` 椭圆核膨胀后再算，容忍 1px 错位；返回 [0,1]，并集为空时返回 0.0。
  - `recanny_iou(generated_rgb: NDArray[uint8], input_canny: NDArray[uint8], low: int = 100, high: int = 200, dilation: int = 0) -> float` —— 对生成图重提 Canny（同阈值），与输入 Canny 算 `edge_iou`。

- [ ] **Step 1: 建脚手架空文件**

```bash
mkdir -p scripts/poc/h1_h2 tests/poc
printf '"""H1+H2 PoC 包。"""\n' > scripts/poc/h1_h2/__init__.py
printf '' > tests/poc/__init__.py
```

- [ ] **Step 2: 写失败测试**

`tests/poc/test_iou.py`:

```python
import numpy as np

from scripts.poc.h1_h2.iou import edge_iou, recanny_iou


def _mask(coords, shape=(10, 10)):
    m = np.zeros(shape, dtype=np.uint8)
    for y, x in coords:
        m[y, x] = 255
    return m


def test_identical_masks_iou_is_one():
    m = _mask([(1, 1), (2, 2), (3, 3)])
    assert edge_iou(m, m) == 1.0


def test_disjoint_masks_iou_is_zero():
    a = _mask([(1, 1)])
    b = _mask([(8, 8)])
    assert edge_iou(a, b) == 0.0


def test_partial_overlap_known_value():
    # 交集 1 像素，并集 3 像素 → 1/3
    a = _mask([(1, 1), (2, 2)])
    b = _mask([(2, 2), (5, 5)])
    assert abs(edge_iou(a, b) - 1 / 3) < 1e-9


def test_empty_union_returns_zero():
    z = np.zeros((10, 10), dtype=np.uint8)
    assert edge_iou(z, z) == 0.0


def test_dilation_recovers_one_pixel_offset():
    a = _mask([(5, 5)])
    b = _mask([(5, 6)])  # 错位 1px
    assert edge_iou(a, b) == 0.0
    assert edge_iou(a, b, dilation=3) > 0.0


def test_recanny_iou_of_solid_image_runs():
    img = np.zeros((32, 32, 3), dtype=np.uint8)
    img[8:24, 8:24] = 255  # 一个方块 → 有边缘
    canny_in = np.zeros((32, 32), dtype=np.uint8)
    val = recanny_iou(img, canny_in)
    assert 0.0 <= val <= 1.0
```

- [ ] **Step 3: 运行确认失败**

Run: `uv run pytest tests/poc/test_iou.py -v`
Expected: FAIL（`ModuleNotFoundError: scripts.poc.h1_h2.iou`）

- [ ] **Step 4: 实现 `iou.py`**

```python
"""边缘 IoU 度量：H1 结构遵循度的量化判据。"""

import cv2
import numpy as np
from numpy.typing import NDArray


def _binarize(mask: NDArray[np.uint8]) -> NDArray[np.bool_]:
    return mask > 0


def edge_iou(
    canny_a: NDArray[np.uint8],
    canny_b: NDArray[np.uint8],
    dilation: int = 0,
) -> float:
    """两张二值边缘图的交并比。

    Args:
        canny_a, canny_b: 二值边缘图 (H, W)，非零视为边缘。
        dilation: >0 时对两图各做该尺寸椭圆核膨胀，容忍 1px 错位。

    Returns:
        IoU ∈ [0, 1]；并集为空返回 0.0。
    """
    a = _binarize(canny_a)
    b = _binarize(canny_b)
    if dilation > 0:
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (dilation, dilation))
        a = cv2.dilate(a.astype(np.uint8), kernel).astype(bool)
        b = cv2.dilate(b.astype(np.uint8), kernel).astype(bool)
    union = np.logical_or(a, b).sum()
    if union == 0:
        return 0.0
    inter = np.logical_and(a, b).sum()
    return float(inter / union)


def recanny_iou(
    generated_rgb: NDArray[np.uint8],
    input_canny: NDArray[np.uint8],
    low: int = 100,
    high: int = 200,
    dilation: int = 0,
) -> float:
    """对生成图重提 Canny，与输入 Canny 算 IoU。"""
    gray = cv2.cvtColor(generated_rgb, cv2.COLOR_RGB2GRAY)
    gen_canny = cv2.Canny(gray, low, high)
    return edge_iou(gen_canny, input_canny, dilation=dilation)
```

- [ ] **Step 5: 运行确认通过**

Run: `uv run pytest tests/poc/test_iou.py -v`
Expected: PASS（6 passed）

- [ ] **Step 6: ruff + 提交**

```bash
uv run ruff check scripts/poc tests/poc && uv run ruff format scripts/poc tests/poc
git add scripts/poc/h1_h2/__init__.py scripts/poc/h1_h2/iou.py tests/poc/__init__.py tests/poc/test_iou.py
git commit -m "feat: H1 PoC 边缘 IoU 度量"
```

---

### Task 2: 抽帧工具

**Files:**
- Create: `scripts/poc/h1_h2/frames.py`
- Test: `tests/poc/test_frames.py`

**Interfaces:**
- Consumes: 无（独立）。
- Produces:
  - `extract_frames(video_path: str | Path, indices: Sequence[int]) -> list[NDArray[uint8]]` —— 读视频，返回指定帧号的 RGB 帧 (H,W,3)；越界帧号抛 `IndexError`。
  - `resize_frame(frame: NDArray[uint8], size: int) -> NDArray[uint8]` —— 等比缩放并中心裁剪到 `size`×`size`。

- [ ] **Step 1: 写失败测试（用合成视频，CI 安全）**

`tests/poc/test_frames.py`:

```python
import imageio.v3 as iio
import numpy as np
import pytest

from scripts.poc.h1_h2.frames import extract_frames, resize_frame


def _make_video(path, n=10, h=48, w=64):
    frames = []
    for i in range(n):
        f = np.full((h, w, 3), i * 20, dtype=np.uint8)  # 每帧亮度不同，便于辨认
        frames.append(f)
    iio.imwrite(path, np.stack(frames), fps=6, codec="libx264")


def test_extract_specific_indices(tmp_path):
    vid = tmp_path / "synthetic.mp4"
    _make_video(vid, n=10)
    out = extract_frames(vid, [0, 5, 9])
    assert len(out) == 3
    assert out[0].shape[2] == 3
    # 帧 5 应比帧 0 亮
    assert out[1].mean() > out[0].mean()


def test_out_of_range_raises(tmp_path):
    vid = tmp_path / "synthetic.mp4"
    _make_video(vid, n=5)
    with pytest.raises(IndexError):
        extract_frames(vid, [99])


def test_resize_to_square():
    f = np.zeros((48, 64, 3), dtype=np.uint8)
    r = resize_frame(f, 512)
    assert r.shape == (512, 512, 3)
```

- [ ] **Step 2: 运行确认失败**

Run: `uv run pytest tests/poc/test_frames.py -v`
Expected: FAIL（`ModuleNotFoundError`）

- [ ] **Step 3: 实现 `frames.py`**

```python
"""从视频抽取指定帧并预处理到方形。"""

from collections.abc import Sequence
from pathlib import Path

import cv2
import imageio.v3 as iio
import numpy as np
from numpy.typing import NDArray


def extract_frames(
    video_path: str | Path, indices: Sequence[int]
) -> list[NDArray[np.uint8]]:
    """读取视频指定帧号（RGB）。越界帧号抛 IndexError。"""
    frames = iio.imread(video_path, index=None)  # (N, H, W, 3) RGB
    n = len(frames)
    out: list[NDArray[np.uint8]] = []
    for idx in indices:
        if idx < 0 or idx >= n:
            raise IndexError(f"帧号 {idx} 越界（视频共 {n} 帧）")
        out.append(np.asarray(frames[idx], dtype=np.uint8))
    return out


def resize_frame(frame: NDArray[np.uint8], size: int) -> NDArray[np.uint8]:
    """等比缩放后中心裁剪到 size×size。"""
    h, w = frame.shape[:2]
    scale = size / min(h, w)
    nh, nw = round(h * scale), round(w * scale)
    resized = cv2.resize(frame, (nw, nh), interpolation=cv2.INTER_AREA)
    top = (nh - size) // 2
    left = (nw - size) // 2
    return resized[top : top + size, left : left + size]
```

- [ ] **Step 4: 运行确认通过**

Run: `uv run pytest tests/poc/test_frames.py -v`
Expected: PASS（3 passed）

- [ ] **Step 5: ruff + 提交**

```bash
uv run ruff check scripts/poc tests/poc && uv run ruff format scripts/poc tests/poc
git add scripts/poc/h1_h2/frames.py tests/poc/test_frames.py
git commit -m "feat: H1 PoC 抽帧工具"
```

---

### Task 3: 环境关卡——升级 diffusers + klein fp8 加载 smoke

> **spike 任务**：无单元测试，以「能否加载 klein 并生成一张图」为关卡。失败本身是有价值的负面结论（→ 上报 / 切 Qwen）。

**Files:**
- Create: `scripts/poc/h1_h2/klein_loader.py`
- Create: `scripts/poc/h1_h2/smoke_klein.py`
- Modify: worktree 的 `.venv`（仅本 worktree，不影响主仓库）

**Interfaces:**
- Produces:
  - `load_klein() -> Flux2KleinPipeline` —— 用 fp8 transformer + CPU offload 装好的 klein pipeline。
  - 常量 `KLEIN_DIR`、`KLEIN_FP8_PATH`（从 `MODEL_CACHE_DIR` 派生）。

- [ ] **Step 1: 在 worktree venv 升级 diffusers 到 git main**

klein 的 `model_index.json` 要求 `_diffusers_version=0.37.0.dev0`（含 `Flux2KleinPipeline`）。先验证当前是否已有：

```bash
uv run python -c "from diffusers import Flux2KleinPipeline; print('ok')"
```

若报 ImportError，安装 git main（仅本 worktree venv）：

```bash
uv pip install "git+https://github.com/huggingface/diffusers.git"
uv run python -c "from diffusers import Flux2KleinPipeline; print('ok')"
```

Expected: 最终打印 `ok`。
（若 transformers 因 Qwen3 文本编码器报错，同法 `uv pip install -U transformers`，记录最终版本号到提交信息。）

- [ ] **Step 2: 写 `klein_loader.py`**

fp8 dir 只有单文件 transformer，其余组件（vae/文本编码器/scheduler/tokenizer）从 klein-9B 完整目录取；用 `enable_model_cpu_offload` 适配 24GB。

```python
"""klein-9B 加载：fp8 transformer + 完整 pipeline 组件 + CPU offload。"""

import os
from pathlib import Path

import torch
from diffusers import Flux2KleinPipeline, Flux2Transformer2DModel

_CACHE = Path(os.environ.get("MODEL_CACHE_DIR", "D:/Downloads/Models"))
KLEIN_DIR = _CACHE / "black-forest-labs" / "FLUX.2-klein-9B"
KLEIN_FP8_PATH = (
    _CACHE / "black-forest-labs" / "FLUX.2-klein-9b-fp8" / "flux-2-klein-9b-fp8.safetensors"
)


def load_klein() -> Flux2KleinPipeline:
    """加载 klein pipeline：fp8 transformer 替换 + CPU offload。"""
    transformer = Flux2Transformer2DModel.from_single_file(
        str(KLEIN_FP8_PATH), torch_dtype=torch.bfloat16
    )
    pipe = Flux2KleinPipeline.from_pretrained(
        str(KLEIN_DIR), transformer=transformer, torch_dtype=torch.bfloat16
    )
    pipe.enable_model_cpu_offload()
    return pipe
```

> **回退梯度（OOM 时按序加码，记录到最终报告）**：
> 1. `pipe.enable_sequential_cpu_offload()`（更激进，慢但省显存）；
> 2. 文本编码器单独量化/offload；
> 3. 分辨率降到 512²；
> 4. 仍 OOM → 记为「24GB 装不下 klein」负面结论，H2 显存点同时证伪。
>
> **fp8 单文件若 `from_single_file` 不认**：改用完整 bf16 transformer + `enable_sequential_cpu_offload`；若 bf16 也 OOM，则记录 fp8 加载为待解工程点。

- [ ] **Step 3: 写 `smoke_klein.py`**

```python
"""klein 加载 + 单图生成 smoke。通过 = 出一张非空 512² 图。"""

from pathlib import Path

import imageio.v3 as iio
import numpy as np
import torch

from scripts.poc.h1_h2.klein_loader import load_klein

OUT = Path("output/poc/h1-h2/smoke")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    pipe = load_klein()
    img = pipe(
        prompt="a desert road with a vehicle, clear daylight",
        guidance_scale=1.0,
        num_inference_steps=4,
        height=512,
        width=512,
        generator=torch.Generator("cpu").manual_seed(0),
    ).images[0]
    arr = np.asarray(img)
    assert arr.shape == (512, 512, 3), f"意外尺寸 {arr.shape}"
    assert arr.std() > 1.0, "输出近乎纯色，生成可能失败"
    iio.imwrite(OUT / "smoke_klein.png", arr)
    print(f"smoke OK → {OUT / 'smoke_klein.png'}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 运行 smoke 关卡**

Run: `uv run python -m scripts.poc.h1_h2.smoke_klein`
Expected: 打印 `smoke OK → ...`，`output/poc/h1-h2/smoke/smoke_klein.png` 是一张可辨认的图（目视）。若 OOM 按 Step 2 回退梯度处理并记录。

- [ ] **Step 5: ruff + 提交**

```bash
uv run ruff check scripts/poc && uv run ruff format scripts/poc
git add scripts/poc/h1_h2/klein_loader.py scripts/poc/h1_h2/smoke_klein.py
git commit -m "feat: klein fp8 加载与 smoke 关卡（含 OOM 回退梯度）"
```

---

### Task 4: klein H1 runner——Canny 当参考图逐帧生成

> **spike 任务**：关卡为「逐帧出图 + IoU 落表」。

**Files:**
- Create: `scripts/poc/h1_h2/klein_runner.py`

**Interfaces:**
- Consumes: `load_klein()`(Task3)、`extract_frames`/`resize_frame`(Task2)、`recanny_iou`(Task1)。
- Produces:
  - `run_klein_h1(pipe, frames: list[NDArray], prompts: list[str], size: int, out_dir: Path) -> list[dict]` —— 每帧返回 `{"index", "iou", "input_canny_path", "output_path", "output_canny_path"}`，并落盘原图/输入Canny/输出/输出重提Canny。

- [ ] **Step 1: 实现 `klein_runner.py`**

klein 无 ControlNet，按 H1 假设把 Canny（转 3 通道 RGB）当参考图塞进 `image=[...]`：

```python
"""klein H1：Canny 当参考图，逐帧生成并算 IoU。"""

from pathlib import Path

import cv2
import imageio.v3 as iio
import numpy as np
import torch
from numpy.typing import NDArray

from scripts.poc.h1_h2.iou import recanny_iou

_CANNY_LOW, _CANNY_HIGH = 100, 200
_IOU_DILATION = 3


def _canny_rgb(frame: NDArray[np.uint8]) -> tuple[NDArray[np.uint8], NDArray[np.uint8]]:
    gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
    edges = cv2.Canny(gray, _CANNY_LOW, _CANNY_HIGH)
    rgb = cv2.cvtColor(edges, cv2.COLOR_GRAY2RGB)
    return edges, rgb


def run_klein_h1(pipe, frames, prompts, size, out_dir: Path) -> list[dict]:
    out_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict] = []
    for i, (frame, prompt) in enumerate(zip(frames, prompts, strict=True)):
        edges, edges_rgb = _canny_rgb(frame)
        from PIL import Image

        cond = Image.fromarray(edges_rgb)
        gen = pipe(
            prompt=prompt,
            image=[cond],
            guidance_scale=1.0,
            num_inference_steps=4,
            height=size,
            width=size,
            generator=torch.Generator("cpu").manual_seed(0),
        ).images[0]
        gen_arr = np.asarray(gen, dtype=np.uint8)
        iou = recanny_iou(gen_arr, edges, _CANNY_LOW, _CANNY_HIGH, _IOU_DILATION)

        ip = out_dir / f"frame{i:02d}_input.png"
        cp = out_dir / f"frame{i:02d}_input_canny.png"
        op = out_dir / f"frame{i:02d}_klein.png"
        ocp = out_dir / f"frame{i:02d}_klein_canny.png"
        iio.imwrite(ip, frame)
        iio.imwrite(cp, edges)
        iio.imwrite(op, gen_arr)
        iio.imwrite(ocp, cv2.Canny(cv2.cvtColor(gen_arr, cv2.COLOR_RGB2GRAY), _CANNY_LOW, _CANNY_HIGH))
        results.append(
            {
                "index": i,
                "iou": iou,
                "input_canny_path": str(cp),
                "output_path": str(op),
                "output_canny_path": str(ocp),
            }
        )
        print(f"[klein] frame {i}: IoU={iou:.3f}")
    return results
```

- [ ] **Step 2: 关卡——临时 driver 跑 2 帧验证**

临时在 REPL/脚本跑（不提交 driver，正式编排在 Task 6）：

```bash
uv run python -c "
from pathlib import Path
from scripts.poc.h1_h2.klein_loader import load_klein
from scripts.poc.h1_h2.frames import extract_frames, resize_frame
from scripts.poc.h1_h2.klein_runner import run_klein_h1
import os
v=os.path.join(os.environ['MODEL_CACHE_DIR'] if False else 'resources/test_videos/prepared','C1X_20250721112728_10s_640x480_6fps.mp4')
fr=[resize_frame(f,512) for f in extract_frames(v,[28,29])]
r=run_klein_h1(load_klein(), fr, ['a desert runway with vehicles']*2, 512, Path('output/poc/h1-h2/klein_smoke'))
print(r)
"
```

Expected: 打印两帧 IoU（[0,1] 内），`output/poc/h1-h2/klein_smoke/` 下有 4×2 张产物图。目视检查 klein 输出是否跟随道路/车辆几何。

- [ ] **Step 3: ruff + 提交**

```bash
uv run ruff check scripts/poc && uv run ruff format scripts/poc
git add scripts/poc/h1_h2/klein_runner.py
git commit -m "feat: klein H1 runner——Canny 参考图逐帧生成与 IoU"
```

---

### Task 5: Qwen+InstantX H1 runner（GGUF transformer spike + 回退）

> **spike 任务**：最高不确定度——Qwen-Image 本地无 transformer 子目录，只有 GGUF；InstantX 自定义 transformer 类能否吃 GGUF 是 spec §6 标的待解工程点。

**Files:**
- Create: `scripts/poc/h1_h2/qwen_loader.py`
- Create: `scripts/poc/h1_h2/qwen_runner.py`

**Interfaces:**
- Consumes: `recanny_iou`(Task1)、InstantX 自定义 pipeline（从模型目录本地导入）。
- Produces:
  - `load_qwen_controlnet() -> pipe`
  - `run_qwen_h1(pipe, frames, prompts, size, out_dir) -> list[dict]`（结构同 Task4，键名 `output_path` 等前缀用 `qwen`）。

- [ ] **Step 1: 写 `qwen_loader.py`（含 GGUF 主路径 + bf16 回退）**

InstantX 自定义文件在 `$MODEL_CACHE_DIR/InstantX/Qwen-Image-ControlNet-Union/`，示例要求本地导入。把该目录加进 `sys.path`：

```python
"""Qwen-Image + InstantX ControlNet 加载。

主路径：GGUF transformer（24GB 唯一可行）；失败回退见 docstring。
"""

import os
import sys
from pathlib import Path

import torch
from diffusers import GGUFQuantizationConfig

_CACHE = Path(os.environ.get("MODEL_CACHE_DIR", "D:/Downloads/Models"))
QWEN_BASE = _CACHE / "Qwen" / "Qwen-Image"
INSTANTX_DIR = _CACHE / "InstantX" / "Qwen-Image-ControlNet-Union"
GGUF_PATH = _CACHE / "QuantStack" / "Qwen-Image-GGUF" / "Qwen_Image-Q4_K_M.gguf"

sys.path.insert(0, str(INSTANTX_DIR))


def load_qwen_controlnet():
    from controlnet_qwenimage import QwenImageControlNetModel  # type: ignore
    from pipeline_qwenimage_controlnet import QwenImageControlNetPipeline  # type: ignore
    from transformer_qwenimage import QwenImageTransformer2DModel  # type: ignore

    controlnet = QwenImageControlNetModel.from_pretrained(
        str(INSTANTX_DIR), torch_dtype=torch.bfloat16
    )
    # 主路径：GGUF transformer 塞进自定义类
    transformer = QwenImageTransformer2DModel.from_single_file(
        str(GGUF_PATH),
        quantization_config=GGUFQuantizationConfig(compute_dtype=torch.bfloat16),
        torch_dtype=torch.bfloat16,
    )
    pipe = QwenImageControlNetPipeline.from_pretrained(
        str(QWEN_BASE),
        controlnet=controlnet,
        transformer=transformer,
        torch_dtype=torch.bfloat16,
    )
    pipe.enable_model_cpu_offload()
    return pipe
```

> **回退梯度（按序，记录到报告）**：
> 1. `from_single_file` 不认自定义类 → 试 `QwenImageTransformer2DModel.from_single_file` 不带 quantization、或用 diffusers 原生 `QwenImageTransformer2DModel`（非 InstantX 版）配 InstantX controlnet；
> 2. GGUF 完全不通 → 下 Qwen-Image bf16 transformer（~40GB，配 `enable_sequential_cpu_offload`，慢但验功能）；
> 3. 仍不通 → **记 Qwen 臂为「待解工程点」，H1 以 klein 单臂结论交付**，并在报告显式标注 Qwen 对照缺失。

- [ ] **Step 2: 写 `qwen_runner.py`**

InstantX 走 `control_image=` + `controlnet_conditioning_scale`（Canny 用 1.0），`num_inference_steps=30`、`true_cfg_scale=4.0`（按官方示例）：

```python
"""Qwen+InstantX H1：Canny 走 ControlNet，逐帧生成并算 IoU。"""

from pathlib import Path

import cv2
import imageio.v3 as iio
import numpy as np
import torch
from PIL import Image

from scripts.poc.h1_h2.iou import recanny_iou

_CANNY_LOW, _CANNY_HIGH, _IOU_DILATION = 100, 200, 3
_CN_SCALE = 1.0


def run_qwen_h1(pipe, frames, prompts, size, out_dir: Path) -> list[dict]:
    out_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict] = []
    for i, (frame, prompt) in enumerate(zip(frames, prompts, strict=True)):
        gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        edges = cv2.Canny(gray, _CANNY_LOW, _CANNY_HIGH)
        cond = Image.fromarray(cv2.cvtColor(edges, cv2.COLOR_GRAY2RGB))
        gen = pipe(
            prompt=prompt + ", TEXT",  # 官方建议 Canny prompt 含 'TEXT'
            negative_prompt=" ",
            control_image=cond,
            controlnet_conditioning_scale=_CN_SCALE,
            width=size,
            height=size,
            num_inference_steps=30,
            true_cfg_scale=4.0,
            generator=torch.Generator(device="cuda").manual_seed(42),
        ).images[0]
        gen_arr = np.asarray(gen, dtype=np.uint8)
        iou = recanny_iou(gen_arr, edges, _CANNY_LOW, _CANNY_HIGH, _IOU_DILATION)
        op = out_dir / f"frame{i:02d}_qwen.png"
        ocp = out_dir / f"frame{i:02d}_qwen_canny.png"
        iio.imwrite(op, gen_arr)
        iio.imwrite(ocp, cv2.Canny(cv2.cvtColor(gen_arr, cv2.COLOR_RGB2GRAY), _CANNY_LOW, _CANNY_HIGH))
        results.append({"index": i, "iou": iou, "output_path": str(op), "output_canny_path": str(ocp)})
        print(f"[qwen] frame {i}: IoU={iou:.3f}")
    return results
```

- [ ] **Step 3: 关卡——临时 driver 跑 2 帧**

```bash
uv run python -c "
from pathlib import Path
from scripts.poc.h1_h2.qwen_loader import load_qwen_controlnet
from scripts.poc.h1_h2.frames import extract_frames, resize_frame
from scripts.poc.h1_h2.qwen_runner import run_qwen_h1
fr=[resize_frame(f,512) for f in extract_frames('resources/test_videos/prepared/C1X_20250721112728_10s_640x480_6fps.mp4',[28,29])]
r=run_qwen_h1(load_qwen_controlnet(), fr, ['a desert runway with vehicles']*2, 512, Path('output/poc/h1-h2/qwen_smoke'))
print(r)
"
```

Expected: 两帧 IoU + 产物图；InstantX 是原生 ControlNet，IoU 预期明显高于 klein。**若加载失败，按 Step 1 回退梯度处理，记录结论。**

- [ ] **Step 4: ruff + 提交**

```bash
uv run ruff check scripts/poc && uv run ruff format scripts/poc
git add scripts/poc/h1_h2/qwen_loader.py scripts/poc/h1_h2/qwen_runner.py
git commit -m "feat: Qwen+InstantX H1 runner（GGUF transformer spike 含回退）"
```

---

### Task 6: H1 编排 + 对比产物组装

**Files:**
- Create: `scripts/poc/h1_h2/report.py`
- Create: `scripts/poc/h1_h2/run_h1.py`
- Test: `tests/poc/test_report.py`

**Interfaces:**
- Consumes: 上述 runner 结果 `list[dict]`。
- Produces:
  - `comparison_grid(frame, input_canny, klein_img, klein_canny, qwen_img, qwen_canny, iou_klein, iou_qwen) -> NDArray` —— 六联图，IoU 数值叠字。
  - `consecutive_strip(images: list[NDArray]) -> NDArray` —— 横向拼接连续帧。
  - `write_iou_table(klein_res, qwen_res, out_dir) -> dict` —— 落 `iou_table.json` + `iou_table.md`，返回含均值的汇总。
  - `run_h1.py`：`main()` 端到端编排（抽帧 → klein → qwen → 组装产物）。

- [ ] **Step 1: 写 `report.py` 纯函数的失败测试**

`tests/poc/test_report.py`:

```python
import numpy as np

from scripts.poc.h1_h2.report import comparison_grid, consecutive_strip, write_iou_table


def test_consecutive_strip_concatenates_width():
    imgs = [np.zeros((32, 32, 3), np.uint8) for _ in range(4)]
    strip = consecutive_strip(imgs)
    assert strip.shape == (32, 128, 3)


def test_comparison_grid_runs_and_shapes():
    f = np.zeros((64, 64, 3), np.uint8)
    c = np.zeros((64, 64), np.uint8)
    grid = comparison_grid(f, c, f, c, f, c, 0.31, 0.55)
    assert grid.ndim == 3 and grid.shape[2] == 3


def test_write_iou_table_means(tmp_path):
    klein = [{"index": 0, "iou": 0.2}, {"index": 1, "iou": 0.4}]
    qwen = [{"index": 0, "iou": 0.5}, {"index": 1, "iou": 0.7}]
    summary = write_iou_table(klein, qwen, tmp_path)
    assert abs(summary["klein_mean"] - 0.3) < 1e-9
    assert abs(summary["qwen_mean"] - 0.6) < 1e-9
    assert (tmp_path / "iou_table.json").exists()
    assert (tmp_path / "iou_table.md").exists()
```

- [ ] **Step 2: 运行确认失败**

Run: `uv run pytest tests/poc/test_report.py -v`
Expected: FAIL（`ModuleNotFoundError`）

- [ ] **Step 3: 实现 `report.py`**

```python
"""H1 对比产物组装：六联图、连续帧条、IoU 表。"""

import json
from pathlib import Path

import cv2
import numpy as np
from numpy.typing import NDArray


def _to_rgb(img: NDArray) -> NDArray[np.uint8]:
    if img.ndim == 2:
        return cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)
    return img.astype(np.uint8)


def _label(img: NDArray[np.uint8], text: str) -> NDArray[np.uint8]:
    out = img.copy()
    cv2.putText(out, text, (4, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1, cv2.LINE_AA)
    return out


def consecutive_strip(images: list[NDArray]) -> NDArray[np.uint8]:
    return np.concatenate([_to_rgb(im) for im in images], axis=1)


def comparison_grid(
    frame, input_canny, klein_img, klein_canny, qwen_img, qwen_canny, iou_klein, iou_qwen
) -> NDArray[np.uint8]:
    panels = [
        _label(_to_rgb(frame), "input"),
        _label(_to_rgb(input_canny), "in-canny"),
        _label(_to_rgb(klein_img), f"klein {iou_klein:.2f}"),
        _label(_to_rgb(klein_canny), "klein-canny"),
        _label(_to_rgb(qwen_img), f"qwen {iou_qwen:.2f}"),
        _label(_to_rgb(qwen_canny), "qwen-canny"),
    ]
    h = min(p.shape[0] for p in panels)
    panels = [cv2.resize(p, (p.shape[1] * h // p.shape[0], h)) for p in panels]
    return np.concatenate(panels, axis=1)


def write_iou_table(klein_res: list[dict], qwen_res: list[dict], out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    k_mean = float(np.mean([r["iou"] for r in klein_res])) if klein_res else 0.0
    q_mean = float(np.mean([r["iou"] for r in qwen_res])) if qwen_res else 0.0
    summary = {"klein_mean": k_mean, "qwen_mean": q_mean, "klein": klein_res, "qwen": qwen_res}
    (out_dir / "iou_table.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["| frame | klein IoU | qwen IoU |", "|---|---|---|"]
    qmap = {r["index"]: r["iou"] for r in qwen_res}
    for r in klein_res:
        lines.append(f"| {r['index']} | {r['iou']:.3f} | {qmap.get(r['index'], float('nan')):.3f} |")
    lines.append(f"| **均值** | **{k_mean:.3f}** | **{q_mean:.3f}** |")
    (out_dir / "iou_table.md").write_text("\n".join(lines), encoding="utf-8")
    return summary
```

- [ ] **Step 4: 运行确认通过**

Run: `uv run pytest tests/poc/test_report.py -v`
Expected: PASS（3 passed）

- [ ] **Step 5: 写 `run_h1.py` 端到端编排**

```python
"""H1 端到端：抽帧 → klein → qwen → 组装对比产物。

抽帧方案见 spec §4.1：主测 C1X_112728 连续 8 帧 + C104_093008 多样性 2 帧。
"""

from pathlib import Path

import imageio.v3 as iio

from scripts.poc.h1_h2.frames import extract_frames, resize_frame
from scripts.poc.h1_h2.klein_loader import load_klein
from scripts.poc.h1_h2.klein_runner import run_klein_h1
from scripts.poc.h1_h2.qwen_loader import load_qwen_controlnet
from scripts.poc.h1_h2.qwen_runner import run_qwen_h1
from scripts.poc.h1_h2.report import comparison_grid, consecutive_strip, write_iou_table

_VID_DIR = Path("resources/test_videos/prepared")
_PRIMARY = _VID_DIR / "C1X_20250721112728_10s_640x480_6fps.mp4"
_DIVERSITY = _VID_DIR / "C104_20260115093008_10s_640x480_6fps.mp4"
_SIZE = 512
_OUT = Path("output/poc/h1-h2/h1")


def _gather_frames():
    primary = [resize_frame(f, _SIZE) for f in extract_frames(_PRIMARY, list(range(26, 34)))]
    diversity = [resize_frame(f, _SIZE) for f in extract_frames(_DIVERSITY, [25, 35])]
    return primary + diversity


def main() -> None:
    frames = _gather_frames()
    prompts = ["a real driving scene, road and vehicles, daylight"] * len(frames)

    # klein 臂（跑完卸载再上 qwen，单卡串行）
    klein_pipe = load_klein()
    klein_res = run_klein_h1(klein_pipe, frames, prompts, _SIZE, _OUT / "klein")
    del klein_pipe
    import torch

    torch.cuda.empty_cache()

    # qwen 臂（加载失败则记空，报告标注对照缺失）
    try:
        qwen_pipe = load_qwen_controlnet()
        qwen_res = run_qwen_h1(qwen_pipe, frames, prompts, _SIZE, _OUT / "qwen")
    except Exception as e:  # noqa: BLE001 —— spike，记录失败结论而非中断
        print(f"[qwen] 加载/运行失败，H1 以 klein 单臂交付：{e}")
        qwen_res = []

    summary = write_iou_table(klein_res, qwen_res, _OUT)
    print(f"klein 均值 IoU={summary['klein_mean']:.3f} / qwen 均值 IoU={summary['qwen_mean']:.3f}")

    # 对比网格 + 连续帧条
    grids = []
    for i, kr in enumerate(klein_res):
        qr = qwen_res[i] if i < len(qwen_res) else {"iou": float("nan"), "output_path": None, "output_canny_path": None}
        frame = iio.imread(_OUT / "klein" / f"frame{i:02d}_input.png")
        in_canny = iio.imread(kr["input_canny_path"])
        k_img = iio.imread(kr["output_path"])
        k_canny = iio.imread(kr["output_canny_path"])
        q_img = iio.imread(qr["output_path"]) if qr["output_path"] else frame * 0
        q_canny = iio.imread(qr["output_canny_path"]) if qr["output_canny_path"] else in_canny * 0
        grid = comparison_grid(frame, in_canny, k_img, k_canny, q_img, q_canny, kr["iou"], qr["iou"])
        iio.imwrite(_OUT / f"grid_frame{i:02d}.png", grid)
        grids.append(grid)

    # 主测连续 8 帧的 klein vs qwen 对比条
    iio.imwrite(_OUT / "strip_klein.png", consecutive_strip([iio.imread(r["output_path"]) for r in klein_res[:8]]))
    if qwen_res:
        iio.imwrite(_OUT / "strip_qwen.png", consecutive_strip([iio.imread(r["output_path"]) for r in qwen_res[:8]]))
    print(f"产物落盘 → {_OUT}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: 端到端运行（GPU，主线让卡时跑）**

Run: `uv run python -m scripts.poc.h1_h2.run_h1`
Expected: 打印 klein/qwen 均值 IoU；`output/poc/h1-h2/h1/` 下有 `iou_table.{json,md}`、每帧 `grid_frameNN.png`、`strip_klein.png`(+`strip_qwen.png`)、klein/ 与 qwen/ 子目录逐帧产物。

- [ ] **Step 7: ruff + 提交**

```bash
uv run ruff check scripts/poc tests/poc && uv run ruff format scripts/poc tests/poc
git add scripts/poc/h1_h2/report.py scripts/poc/h1_h2/run_h1.py tests/poc/test_report.py
git commit -m "feat: H1 编排与对比产物组装（六联图/连续帧条/IoU 表）"
```

---

### Task 7: H2 速度三档

**Files:**
- Create: `scripts/poc/h1_h2/run_h2.py`

**Interfaces:**
- Consumes: `load_klein()`(Task3)。
- Produces: `output/poc/h1-h2/h2/speed.json` + `speed.md`（512/768/1024 各档稳态 ms/帧 + 显存峰值）。

- [ ] **Step 1: 实现 `run_h2.py`**

排除冷加载首帧，每档跑若干次取稳态中位数；`torch.cuda.max_memory_allocated` 记峰值显存。

```python
"""H2：klein-9b-fp8 速度三档（512/768/1024）+ 显存峰值。"""

import json
import time
from pathlib import Path

import torch

from scripts.poc.h1_h2.klein_loader import load_klein

_RESOLUTIONS = [512, 768, 1024]
_WARMUP, _RUNS = 1, 5
_OUT = Path("output/poc/h1-h2/h2")


def main() -> None:
    _OUT.mkdir(parents=True, exist_ok=True)
    pipe = load_klein()
    rows = []
    for size in _RESOLUTIONS:
        torch.cuda.reset_peak_memory_stats()
        times = []
        for r in range(_WARMUP + _RUNS):
            t0 = time.perf_counter()
            pipe(
                prompt="a desert road with vehicles",
                guidance_scale=1.0,
                num_inference_steps=4,
                height=size,
                width=size,
                generator=torch.Generator("cpu").manual_seed(r),
            )
            torch.cuda.synchronize()
            dt = time.perf_counter() - t0
            if r >= _WARMUP:  # 排冷加载
                times.append(dt)
        times.sort()
        median = times[len(times) // 2]
        peak_gb = torch.cuda.max_memory_allocated() / 1e9
        rows.append({"resolution": size, "median_s": median, "peak_vram_gb": peak_gb})
        print(f"[H2] {size}²: 中位 {median:.2f}s/帧, 峰值显存 {peak_gb:.1f}GB")

    (_OUT / "speed.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["| 分辨率 | 中位 s/帧 | 峰值显存 GB |", "|---|---|---|"]
    lines += [f"| {r['resolution']}² | {r['median_s']:.2f} | {r['peak_vram_gb']:.1f} |" for r in rows]
    (_OUT / "speed.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"产物 → {_OUT}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 运行**

Run: `uv run python -m scripts.poc.h1_h2.run_h2`
Expected: 三档各打印中位 s/帧 + 峰值显存；`output/poc/h1-h2/h2/speed.{json,md}` 生成。对照判据 ≤1.5s（512–768），并验官方「<1s」是否成立。

- [ ] **Step 3: ruff + 提交**

```bash
uv run ruff check scripts/poc && uv run ruff format scripts/poc
git add scripts/poc/h1_h2/run_h2.py
git commit -m "feat: H2 klein-9b-fp8 速度三档与显存峰值"
```

---

### Task 8: 裁决报告

**Files:**
- Create: `docs/test-reports/2026-06-28-h1-h2-klein-structure-poc-report.md`
- Modify: `output/poc/.gitignore`（确保运行产物不进 git）

**Interfaces:**
- Consumes: Task6 的 `iou_table.md`、Task7 的 `speed.md`、各对比图。

- [ ] **Step 1: 确认运行产物 gitignored**

```bash
grep -q "^output/" .gitignore || echo "output/" >> .gitignore
git check-ignore output/poc/h1-h2/h1/iou_table.json && echo "ignored ok"
```

Expected: 打印 `ignored ok`（产物目录不进 git，报告里引用关键图时手动拷贝到 `docs/test-reports/assets/` 或附路径）。

- [ ] **Step 2: 写裁决报告**

把实跑得到的 IoU 表、速度表、目视结论、回退记录（klein OOM 梯度、Qwen GGUF 是否通）填入，模板：

```markdown
# H1+H2 PoC 裁决报告（2026-06-28）

> 上游 spec：docs/superpowers/specs/2026-06-28-h1-h2-klein-structure-poc-design.md
> 运行产物：output/poc/h1-h2/（gitignored，本地留存）

## 结论先行（go/no-go）

- **主线建议**：保 klein / 切 Qwen（择一，附一句理由）。
- klein 均值边缘 IoU = X.XX（判据 >0.4）；Qwen 均值 = X.XX。
- klein 速度（fp8 4 步）：512² = X.Xs，768² = X.Xs，1024² = X.Xs；官方「<1s」是否成立：是/否。

## H1 结构遵循度

- IoU 表：见 output/.../iou_table.md（粘贴于此）。
- 目视：klein 是否跟随道路/车辆几何（连续帧条 strip_klein.png）；Qwen 对照。
- HUD 坑影响：C1X_112728 绝对 IoU 偏低说明；C104_093008 overlay-free 旁证值。

## H2 速度与显存

- 速度三档表（粘贴 speed.md）；显存峰值 vs 24GB。

## 工程记录（回退是否触发）

- klein 加载：fp8+offload 是否一次通过 / 触发哪级回退。
- Qwen 臂：GGUF transformer 接 InstantX 是否成功 / 回退到哪 / 是否记为待解工程点。

## 对后续的影响

- 解锁 ROADMAP D4 关键帧主线落地（按本裁决选模型）。
- depth 补测、H3 帧间一致性留作后续会话。
```

- [ ] **Step 3: 提交报告**

```bash
git add docs/test-reports/2026-06-28-h1-h2-klein-structure-poc-report.md .gitignore
git commit -m "docs: H1+H2 PoC 裁决报告"
```

---

## 完成后

全部任务后：在 worktree 上 `uv run ruff check .` + `uv run ruff format --check .` 通过，开 PR（`feature/poc-h1-h2-klein-structure`）。报告里的 go/no-go 即目标版主线裁决输入。
