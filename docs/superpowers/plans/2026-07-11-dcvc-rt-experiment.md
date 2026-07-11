# DCVC-RT 神经编解码实验实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 验证 DCVC-RT 神经编解码在驾驶视频素材上的实际表现，与 H.265 做头对头对比（延迟、码率、质量）。

**Architecture:** 独立实验脚本放 `experiments/dcvc-rt/`，subprocess 调用 DCVC-RT CLI，import 项目现有 `evaluation` 模块做 PSNR-Y/SSIM/LPIPS。两条管线（DCVC-RT vs H.265）共享同一组 PNG 帧序列作为输入，各自编码→解码→评估，结果 JSON 汇总对比。

**Tech Stack:** DCVC-RT (microsoft/DCVC), PyTorch 2.10+cu130, CUDA Toolkit 13.3, ffmpeg (imageio-ffmpeg), uv, 项目 evaluation 模块

## Global Constraints

- Python >= 3.12，所有操作通过 `uv` 执行
- 单卡 RTX 4090 24GB，CUDA 13.3，GCC 11.4
- PSNR 仅计算 Y 通道（亮度），与 DCVC-RT 论文口径一致。注意：项目 `evaluation` 模块的 `compute_psnr` 默认在 RGB 上计算，需要先将帧转换到 YCbCr 取 Y 通道
- H.265 基线使用 ABR 码率控制（非 CRF），GOP 对齐 DCVC-RT（全 P 帧）
- 测试素材：`resources/test_videos/prepared/C104_20260115121711_10s_640x480_6fps.mp4`
- 实验产物（results/、frames/）不入库，加 .gitignore
- DCVC-RT 在 PNG 模式下自身的 PSNR 在 RGB 域计算（`src/utils/metrics.py:calc_psnr`），与我们的 Y-only PSNR 口径不同；两条管线均使用我们的 Y-only PSNR 保证对比公平

---

## 文件结构

| 文件 | 职责 |
|------|------|
| `experiments/dcvc-rt/README.md` | 实验说明、使用步骤、结论（留空待填写） |
| `experiments/dcvc-rt/.gitignore` | 忽略 results/ 和 frames/ |
| `experiments/dcvc-rt/prepare_frames.py` | 从 mp4 提取 PNG 帧序列到 frames/original/ |
| `experiments/dcvc-rt/run_dcvc.py` | DCVC-RT 编解码 + 延迟/码率/质量测量 |
| `experiments/dcvc-rt/compare_h265.py` | H.265 编解码 + 同码率对比评估 |
| `experiments/dcvc-rt/results/` | 输出 JSON + 解码帧（.gitignore） |

---

### Task 1: 环境准备——DCVC 仓库与 CUDA 扩展编译

**Files:**
- Create: (无新文件，操作在外部目录)

**Interfaces:**
- Produces: DCVC 仓库 clone 路径，两个编译产物可 import

- [ ] **Step 1: Clone DCVC 仓库**

```bash
cd /home/ws-009/chy/Projects
git clone https://github.com/microsoft/DCVC.git
cd DCVC
git log --oneline -1  # 记录 commit hash
```

- [ ] **Step 2: 安装 DCVC-RT Python 依赖**

```bash
cd /home/ws-009/chy/Projects/DCVC
uv pip install numpy scipy matplotlib tqdm bd-metric pillow pybind11
```

- [ ] **Step 3: 编译 ANS 熵编码器扩展（纯 C++）**

```bash
cd /home/ws-009/chy/Projects/DCVC/src/cpp
uv pip install -e . --no-build-isolation
```

Expected: 成功安装 `MLCodec_extensions_cpp`。

- [ ] **Step 4: 编译 CUDA 推理扩展**

```bash
cd /home/ws-009/chy/Projects/DCVC/src/layers/extensions/inference
CUDA_HOME=/usr/local/cuda uv pip install -e . --no-build-isolation
```

Expected: 成功安装 `inference_extensions_cuda`。若失败，检查 nvcc 版本和 PyTorch CUDA 版本是否对齐。

- [ ] **Step 5: 验证扩展可 import**

```bash
uv run python -c "
import MLCodec_extensions_cpp
print('ANS extension OK')
import inference_extensions_cuda
print('CUDA extension OK')
"
```

Expected: 两条 "OK" 输出。若 CUDA extension import 失败，DCVC-RT 会回退到纯 PyTorch 实现（性能大幅下降）。

- [ ] **Step 6: 下载预训练权重**

从 OneDrive 下载 I-frame 和 P-frame checkpoint：
- https://1drv.ms/f/c/2866592d5c55df8c/Esu0KJ-I2kxCjEP565ARx_YB88i0UnR6XnODqFcvZs4LcA?e=by8CO8

```bash
mkdir -p /home/ws-009/chy/Projects/DCVC/checkpoints
# 手动下载 ckpt_i.pth 和 ckpt_p.pth 到此目录
ls -la /home/ws-009/chy/Projects/DCVC/checkpoints/
```

- [ ] **Step 7: 跑通最小示例**

准备一个最简 JSON 配置，用单张图或几帧测试编解码流程：

```bash
cd /home/ws-009/chy/Projects/DCVC

# 创建最简测试配置（用 prepared mp4 的前几帧）
uv run python -c "
import json
config = {
    'root_path': '/home/ws-009/chy/Projects/semantic-transmission/resources/test_videos/prepared',
    'test_classes': {
        'C104': {
            'base_path': '.',
            'src_type': 'png',
            'test': 1,
            'sequences': {
                'C104_20260115121711_10s_640x480_6fps': {
                    'height': 480, 'width': 640, 'frames': 10, 'intra_period': -1
                }
            }
        }
    }
}
with open('test_config_quick.json', 'w') as f:
    json.dump(config, f, indent=2)
print('Config written')
"

# 用前 10 帧快速测试
uv run python test_video.py \
    --test_config test_config_quick.json \
    --model_path_i checkpoints/ckpt_i.pth \
    --model_path_p checkpoints/ckpt_p.pth \
    --cuda True \
    --write_stream True \
    --save_decoded_frame True \
    --stream_path /tmp/dcvc_test_bin \
    --output_path /tmp/dcvc_test_result.json \
    --rate_num 1 \
    --qp_i 4 \
    --qp_p 4 \
    --force_intra_period -1 \
    --force_frame_num 10 \
    --verbose 2
```

Expected: 成功输出 JSON 结果文件，包含 PSNR 和编码时间。记录 fps 数字作为后续参考基线。

- [ ] **Step 8: 记录门禁结果**

将检查结果写入实验 README 或临时备忘，标注：
- DCVC commit hash
- CUDA extension 编译是否成功（是/否 + 耗时）
- 最小示例 fps（编码/解码分开记录，若 test_video.py 输出中有）
- 是否有警告或异常

---

### Task 2: 项目配置——pyproject.toml 与实验目录

**Files:**
- Modify: `pyproject.toml`（添加 `no-build-isolation-package` 配置）
- Create: `experiments/dcvc-rt/.gitignore`

**Interfaces:**
- Produces: uv 可正确编译 DCVC-RT 相关扩展，实验目录结构就绪

- [ ] **Step 1: 在 pyproject.toml 中添加 uv 构建隔离配置**

在 `pyproject.toml` 末尾追加：

```toml
[tool.uv]
no-build-isolation-package = ["dcvc-rt"]
```

注意：如果项目已有 `[tool.uv]` section，需要合并而非重复创建。

- [ ] **Step 2: 创建实验目录和 .gitignore**

```bash
mkdir -p experiments/dcvc-rt/results/frames
```

创建 `experiments/dcvc-rt/.gitignore`：

```
results/
frames/
__pycache__/
*.pyc
```

- [ ] **Step 3: 创建实验 README 骨架**

创建 `experiments/dcvc-rt/README.md`：

```markdown
# DCVC-RT 神经编解码实验

> 对应设计文档: `docs/superpowers/specs/2026-07-11-dcvc-rt-experiment-design.md`

## 使用步骤

1. 确认 DCVC 仓库已 clone 并编译（见 Task 1）
2. 准备帧序列: `uv run python experiments/dcvc-rt/prepare_frames.py`
3. 跑 DCVC-RT: `uv run python experiments/dcvc-rt/run_dcvc.py`
4. 跑 H.265 对照: `uv run python experiments/dcvc-rt/compare_h265.py`
5. 查看结果: `cat experiments/dcvc-rt/results/comparison.json`

## 结论

（待填写）
```

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml experiments/dcvc-rt/
git commit -m "chore: 初始化 DCVC-RT 实验目录与 uv 构建配置"
```

---

### Task 3: 帧序列准备脚本

**Files:**
- Create: `experiments/dcvc-rt/prepare_frames.py`

**Interfaces:**
- Consumes: `resources/test_videos/prepared/C104_20260115121711_10s_640x480_6fps.mp4`
- Produces: `experiments/dcvc-rt/results/frames/original/im00001.png` ... `im00060.png`（6fps × 10s = 60 帧）

- [ ] **Step 1: 编写 prepare_frames.py**

```python
"""从 prepared mp4 提取 PNG 帧序列，供 DCVC-RT 和 H.265 两条管线共用。"""

from __future__ import annotations

import shutil
from pathlib import Path

from semantic_transmission.common.video_io import read_frames

# ── 配置 ──────────────────────────────────────────────
INPUT_MP4 = Path("resources/test_videos/prepared/C104_20260115121711_10s_640x480_6fps.mp4")
OUTPUT_DIR = Path("experiments/dcvc-rt/results/frames/original")
# ─────────────────────────────────────────────────────


def main() -> None:
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True)

    frames, meta = read_frames(str(INPUT_MP4))
    print(f"读取 {len(frames)} 帧，分辨率 {meta.width}x{meta.height}，fps={meta.fps}")

    for i, frame in enumerate(frames, start=1):
        # DCVC-RT PNG 模式要求 im{i}.png 或 im{i:05d}.png 命名
        out_path = OUTPUT_DIR / f"im{i:05d}.png"

        from PIL import Image
        Image.fromarray(frame).save(out_path)

    print(f"已保存 {len(frames)} 帧到 {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 运行验证**

```bash
cd /home/ws-009/chy/Projects/semantic-transmission/.claude/worktrees/experiment+dcvc-rt-neural-codec
uv run python experiments/dcvc-rt/prepare_frames.py
ls experiments/dcvc-rt/results/frames/original/ | head -5
# Expected: im00001.png im00002.png ... 共 60 个文件
```

- [ ] **Step 3: Commit**

```bash
git add experiments/dcvc-rt/prepare_frames.py
git commit -m "feat: DCVC-RT 实验——帧序列准备脚本"
```

---

### Task 4: DCVC-RT 编解码脚本

**Files:**
- Create: `experiments/dcvc-rt/run_dcvc.py`

**Interfaces:**
- Consumes: `results/frames/original/im*.png`（来自 Task 3）
- Consumes: DCVC 仓库路径、checkpoint 路径（脚本顶部常量配置）
- Produces: `results/dcvc_metrics.json`（每帧 PSNR/SSIM/LPIPS + 码率 + 延迟）
- Produces: `results/frames/dcvc/im*.png`（DCVC-RT 还原帧）

- [ ] **Step 1: 编写 run_dcvc.py**

```python
"""DCVC-RT 编解码 + 质量/码率/延迟测量。

通过 subprocess 调用 DCVC-RT 的 test_video.py，解析输出 JSON，
再用项目 evaluation 模块计算 PSNR-Y/SSIM/LPIPS。
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

from PIL import Image

from semantic_transmission.common.video_io import read_frames
from semantic_transmission.evaluation.perceptual_metrics import (
    compute_lpips,
    load_lpips_model,
)
from semantic_transmission.evaluation.pixel_metrics import compute_psnr, compute_ssim
from semantic_transmission.evaluation.video_eval import evaluate_video


def rgb_to_y_channel(frame: np.ndarray) -> np.ndarray:
    """RGB uint8 帧转 Y 通道（亮度），返回单通道 uint8 ndarray。"""
    # BT.601 公式: Y = 0.299R + 0.587G + 0.114B
    r, g, b = frame[:, :, 0].astype(np.float32), frame[:, :, 1].astype(np.float32), frame[:, :, 2].astype(np.float32)
    y = (0.299 * r + 0.587 * g + 0.114 * b).clip(0, 255).astype(np.uint8)
    return y


def compute_psnr_y(original: np.ndarray, reconstructed: np.ndarray) -> float:
    """计算 Y 通道 PSNR（与 DCVC-RT 论文口径一致）。"""
    y_orig = rgb_to_y_channel(original)
    y_recon = rgb_to_y_channel(reconstructed)
    from skimage.metrics import peak_signal_noise_ratio
    return float(peak_signal_noise_ratio(y_orig, y_recon, data_range=255))

# ── 配置 ──────────────────────────────────────────────
DCVC_DIR = Path("/home/ws-009/chy/Projects/DCVC")
CKPT_I = DCVC_DIR / "checkpoints" / "ckpt_i.pth"
CKPT_P = DCVC_DIR / "checkpoints" / "ckpt_p.pth"
INPUT_MP4 = Path("resources/test_videos/prepared/C104_20260115121711_10s_640x480_6fps.mp4")
FRAMES_DIR = Path("experiments/dcvc-rt/results/frames/original")
DCVC_OUT_DIR = Path("experiments/dcvc-rt/results/frames/dcvc")
STREAM_DIR = Path("experiments/dcvc-rt/results/dcvc_bin")
RESULT_JSON = Path("experiments/dcvc-rt/results/dcvc_metrics.json")
QP_I = 4  # I-frame QP（0=最高质量，值越大码率越低）
QP_P = 4  # P-frame QP
# ─────────────────────────────────────────────────────


def build_dcvc_config(frames_dir: Path, width: int, height: int, num_frames: int) -> Path:
    """生成 DCVC-RT 所需的 JSON 配置文件。"""
    config = {
        "root_path": str(frames_dir.parent),  # frames_dir 的父目录（即 results/frames/）
        "test_classes": {
            "experiment": {
                "base_path": frames_dir.name,  # "original"
                "src_type": "png",
                "test": 1,
                "sequences": {
                    "original": {
                        "height": height,
                        "width": width,
                        "frames": num_frames,
                        "intra_period": -1,
                    }
                },
            }
        },
    }
    config_path = frames_dir.parent / "dcvc_config.json"
    config_path.write_text(json.dumps(config, indent=2))
    return config_path


def run_dcvc_encode_decode(config_path: Path) -> dict:
    """subprocess 调用 DCVC-RT test_video.py，返回其输出 JSON 内容。"""
    cmd = [
        sys.executable,
        str(DCVC_DIR / "test_video.py"),
        "--test_config", str(config_path),
        "--model_path_i", str(CKPT_I),
        "--model_path_p", str(CKPT_P),
        "--cuda", "True",
        "--write_stream", "True",
        "--save_decoded_frame", "True",
        "--stream_path", str(STREAM_DIR),
        "--output_path", str(RESULT_JSON.parent / "dcvc_raw_output.json"),
        "--rate_num", "1",
        "--qp_i", str(QP_I),
        "--qp_p", str(QP_P),
        "--force_intra_period", "-1",
        "--verbose", "2",
    ]

    print(f"运行 DCVC-RT: {' '.join(cmd)}")
    t_start = time.perf_counter()
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(DCVC_DIR))
    t_elapsed = time.perf_counter() - t_start

    if result.returncode != 0:
        print(f"DCVC-RT 失败:\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}")
        sys.exit(1)

    # 解析 DCVC-RT 输出 JSON
    raw_json_path = RESULT_JSON.parent / "dcvc_raw_output.json"
    with open(raw_json_path) as f:
        dcvc_output = json.load(f)

    return {"dcvc_output": dcvc_output, "wall_clock_seconds": t_elapsed}


def compute_bitrate(stream_dir: Path, duration_seconds: float) -> float:
    """计算编码输出的实际码率（Mbps）。"""
    total_bytes = 0
    for bin_file in stream_dir.rglob("*.bin"):
        total_bytes += bin_file.stat().st_size
    if total_bytes == 0:
        return 0.0
    return (total_bytes * 8) / (duration_seconds * 1_000_000)


def load_frames_as_ndarray(frames_dir: Path, count: int):
    """加载 PNG 帧为 ndarray 列表。"""
    frames = []
    for i in range(1, count + 1):
        path = frames_dir / f"im{i:05d}.png"
        if path.exists():
            img = Image.open(path)
            import numpy as np
            frames.append(np.array(img))
    return frames


def main() -> None:
    # 读取原始帧信息
    frames, meta = read_frames(str(INPUT_MP4))
    num_frames = len(frames)
    width, height = meta.width, meta.height
    duration = num_frames / meta.fps

    print(f"输入: {num_frames} 帧, {width}x{height}, fps={meta.fps}, 时长={duration:.1f}s")

    # 生成 DCVC 配置
    config_path = build_dcvc_config(FRAMES_DIR, width, height, num_frames)

    # 运行 DCVC-RT 编解码
    dcvc_result = run_dcvc_encode_decode(config_path)
    wall_clock = dcvc_result["wall_clock_seconds"]

    # 计算码率
    bitrate_mbps = compute_bitrate(STREAM_DIR, duration)
    print(f"DCVC-RT 码率: {bitrate_mbps:.3f} Mbps, 墙钟: {wall_clock:.2f}s")

    # 加载原始帧和还原帧
    orig_frames = load_frames_as_ndarray(FRAMES_DIR, num_frames)
    dcvc_frames = load_frames_as_ndarray(DCVC_OUT_DIR, num_frames)

    if len(dcvc_frames) == 0:
        print("警告: 未找到 DCVC-RT 还原帧，跳过质量评估")
        return

    # 质量评估——SSIM 和 LPIPS 用 evaluate_video（RGB 域），PSNR-Y 单独算
    print("运行质量评估...")
    eval_result = evaluate_video(
        orig_frames[:len(dcvc_frames)],
        dcvc_frames,
        with_lpips=True,
        with_clip=False,
        device="cuda",
    )

    # 补充 PSNR-Y（仅 Y 通道，与论文口径一致）
    psnr_y_values = [
        compute_psnr_y(o, d)
        for o, d in zip(orig_frames[:len(dcvc_frames)], dcvc_frames)
    ]
    import statistics
    psnr_y_mean = statistics.mean(psnr_y_values)
    psnr_y_std = statistics.pstdev(psnr_y_values) if len(psnr_y_values) > 1 else 0.0

    # 汇总输出
    output = {
        "codec": "DCVC-RT",
        "source": str(INPUT_MP4),
        "frame_count": len(dcvc_frames),
        "resolution": f"{width}x{height}",
        "duration_seconds": duration,
        "qp_i": QP_I,
        "qp_p": QP_P,
        "bitrate_mbps": round(bitrate_mbps, 4),
        "wall_clock_seconds": round(wall_clock, 3),
        "fps_overall": round(len(dcvc_frames) / wall_clock, 2),
        "summary": {
            "psnr_y": {"mean": round(psnr_y_mean, 4), "std": round(psnr_y_std, 4)},
            "ssim": eval_result["summary"]["ssim"],
            "lpips": eval_result["summary"]["lpips"],
        },
    }

    RESULT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(RESULT_JSON, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\n结果已保存到 {RESULT_JSON}")
    print(f"PSNR-Y: {psnr_y_mean:.2f} dB")
    print(f"SSIM: {eval_result['summary']['ssim']['mean']:.4f}")
    if eval_result['summary']['lpips']['mean'] is not None:
        print(f"LPIPS: {eval_result['summary']['lpips']['mean']:.4f}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 运行验证**

```bash
cd /home/ws-009/chy/Projects/semantic-transmission/.claude/worktrees/experiment+dcvc-rt-neural-codec
uv run python experiments/dcvc-rt/run_dcvc.py
```

Expected: 输出 PSNR-Y/SSIM/LPIPS 数字和码率，结果写入 `results/dcvc_metrics.json`。

- [ ] **Step 3: Commit**

```bash
git add experiments/dcvc-rt/run_dcvc.py
git commit -m "feat: DCVC-RT 实验——编解码与质量评估脚本"
```

---

### Task 5: H.265 对照脚本

**Files:**
- Create: `experiments/dcvc-rt/compare_h265.py`

**Interfaces:**
- Consumes: `results/frames/original/im*.png`（与 DCVC-RT 共用）
- Consumes: `results/dcvc_metrics.json`（读取 DCVC-RT 实际码率用于匹配）
- Produces: `results/h265_metrics.json`
- Produces: `results/comparison.json`（两条管线的头对头对比表）

- [ ] **Step 1: 编写 compare_h265.py**

```python
"""H.265 对照编码 + 与 DCVC-RT 的头对头对比。

从 dcvc_metrics.json 读取 DCVC-RT 实际码率，用 ffmpeg ABR 模式编码 H.265，
评估质量后输出对比表。
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import imageio_ffmpeg
import numpy as np
from PIL import Image

from semantic_transmission.evaluation.perceptual_metrics import (
    compute_lpips,
    load_lpips_model,
)
from semantic_transmission.evaluation.pixel_metrics import compute_psnr, compute_ssim
from semantic_transmission.evaluation.video_eval import evaluate_video


def rgb_to_y_channel(frame: np.ndarray) -> np.ndarray:
    """RGB uint8 帧转 Y 通道（亮度），返回单通道 uint8 ndarray。"""
    r, g, b = frame[:, :, 0].astype(np.float32), frame[:, :, 1].astype(np.float32), frame[:, :, 2].astype(np.float32)
    y = (0.299 * r + 0.587 * g + 0.114 * b).clip(0, 255).astype(np.uint8)
    return y


def compute_psnr_y(original: np.ndarray, reconstructed: np.ndarray) -> float:
    """计算 Y 通道 PSNR（与 DCVC-RT 论文口径一致）。"""
    y_orig = rgb_to_y_channel(original)
    y_recon = rgb_to_y_channel(reconstructed)
    from skimage.metrics import peak_signal_noise_ratio
    return float(peak_signal_noise_ratio(y_orig, y_recon, data_range=255))


# ── 配置 ──────────────────────────────────────────────
FRAMES_DIR = Path("experiments/dcvc-rt/results/frames/original")
H265_OUT_DIR = Path("experiments/dcvc-rt/results/frames/h265")
H265_BIN = Path("experiments/dcvc-rt/results/h265_bin")
DCVC_METRICS = Path("experiments/dcvc-rt/results/dcvc_metrics.json")
RESULT_JSON = Path("experiments/dcvc-rt/results/h265_metrics.json")
COMPARISON_JSON = Path("experiments/dcvc-rt/results/comparison.json")
FPS = 6  # 帧率（与 prepared mp4 一致）
PRESETS = ["medium"]  # 可加 "slow" 作为质量上限参考
# ─────────────────────────────────────────────────────


def load_frames_as_ndarray(frames_dir: Path, count: int) -> list[np.ndarray]:
    """加载 PNG 帧为 ndarray 列表。"""
    frames = []
    for i in range(1, count + 1):
        path = frames_dir / f"im{i:05d}.png"
        if path.exists():
            frames.append(np.array(Image.open(path)))
    return frames


def encode_h265_abr(
    frames_dir: Path,
    output_bin: Path,
    target_bitrate_kbps: float,
    preset: str,
    num_frames: int,
    width: int,
    height: int,
) -> float:
    """用 ffmpeg ABR 模式编码 PNG 帧序列为 H.265，返回编码耗时（秒）。"""
    output_bin.parent.mkdir(parents=True, exist_ok=True)

    ff = imageio_ffmpeg.get_ffmpeg_exe()

    # 输入：PNG 帧序列（image sequence pattern）
    input_pattern = str(frames_dir / "im%05d.png")
    output_path = str(output_bin / f"h265_{preset}_{int(target_bitrate_kbps)}k.mp4")

    cmd = [
        ff, "-y",
        "-framerate", str(FPS),
        "-i", input_pattern,
        "-c:v", "libx265",
        "-preset", preset,
        "-b:v", f"{int(target_bitrate_kbps)}k",
        "-maxrate", f"{int(target_bitrate_kbps * 1.2)}k",
        "-bufsize", f"{int(target_bitrate_kbps * 2)}k",
        "-x265-params", "keyint=9999:min-keyint=9999:scenecut=0",  # 超长 GOP 对齐 DCVC-RT
        "-pix_fmt", "yuv420p",
        "-frames:v", str(num_frames),
        output_path,
    ]

    print(f"  编码 H.265 preset={preset} target={int(target_bitrate_kbps)}kbps...")
    t_start = time.perf_counter()
    result = subprocess.run(cmd, capture_output=True, text=True)
    t_elapsed = time.perf_counter() - t_start

    if result.returncode != 0:
        print(f"  ffmpeg 编码失败:\n{result.stderr}")
        return 0.0

    # 计算实际码率
    bin_path = Path(output_path)
    if bin_path.exists():
        size_bytes = bin_path.stat().st_size
        duration = num_frames / FPS
        actual_bitrate_mbps = (size_bytes * 8) / (duration * 1_000_000)
        print(f"  实际码率: {actual_bitrate_mbps:.4f} Mbps, 耗时: {t_elapsed:.2f}s")
    else:
        actual_bitrate_mbps = 0.0

    return t_elapsed, actual_bitrate_mbps, output_path


def decode_h265_to_frames(mp4_path: str, output_dir: Path, num_frames: int) -> float:
    """用 ffmpeg 解码 H.265 mp4 为 PNG 帧，返回解码耗时。"""
    output_dir.mkdir(parents=True, exist_ok=True)

    ff = imageio_ffmpeg.get_ffmpeg_exe()

    cmd = [
        ff, "-y",
        "-i", mp4_path,
        "-frames:v", str(num_frames),
        str(output_dir / "im%05d.png"),
    ]

    t_start = time.perf_counter()
    result = subprocess.run(cmd, capture_output=True, text=True)
    t_elapsed = time.perf_counter() - t_start

    if result.returncode != 0:
        print(f"  ffmpeg 解码失败:\n{result.stderr}")

    return t_elapsed


def main() -> None:
    # 读取 DCVC-RT 结果获取目标码率
    if not DCVC_METRICS.exists():
        print(f"错误: 找不到 {DCVC_METRICS}，请先运行 run_dcvc.py")
        sys.exit(1)

    with open(DCVC_METRICS) as f:
        dcvc_data = json.load(f)

    target_bitrate_mbps = dcvc_data["bitrate_mbps"]
    target_bitrate_kbps = target_bitrate_mbps * 1000
    num_frames = dcvc_data["frame_count"]
    width, height = dcvc_data["resolution"].split("x")
    width, height = int(width), int(height)
    duration = dcvc_data["duration_seconds"]

    print(f"DCVC-RT 参考码率: {target_bitrate_mbps:.4f} Mbps ({target_bitrate_kbps:.0f} kbps)")
    print(f"目标: {num_frames} 帧, {width}x{height}")

    # 加载原始帧
    orig_frames = load_frames_as_ndarray(FRAMES_DIR, num_frames)

    # 对每个 preset 编码 + 解码 + 评估
    results = []
    for preset in PRESETS:
        print(f"\n--- H.265 preset={preset} ---")

        # 编码
        encode_time, actual_bitrate, mp4_path = encode_h265_abr(
            FRAMES_DIR, H265_BIN, target_bitrate_kbps, preset, num_frames, width, height
        )

        # 解码
        decoded_dir = H265_OUT_DIR / preset
        decode_time = decode_h265_to_frames(mp4_path, decoded_dir, num_frames)

        # 加载还原帧
        h265_frames = load_frames_as_ndarray(decoded_dir, num_frames)
        if len(h265_frames) == 0:
            print(f"  警告: 未找到 H.265 还原帧，跳过")
            continue

        # 质量评估——SSIM 和 LPIPS 用 evaluate_video（RGB 域），PSNR-Y 单独算
        print("  运行质量评估...")
        eval_result = evaluate_video(
            orig_frames[:len(h265_frames)],
            h265_frames,
            with_lpips=True,
            with_clip=False,
            device="cuda",
        )

        # 补充 PSNR-Y（仅 Y 通道，与 DCVC-RT 对齐）
        import statistics
        psnr_y_values = [
            compute_psnr_y(o, h)
            for o, h in zip(orig_frames[:len(h265_frames)], h265_frames)
        ]
        psnr_y_mean = statistics.mean(psnr_y_values)
        psnr_y_std = statistics.pstdev(psnr_y_values) if len(psnr_y_values) > 1 else 0.0

        preset_result = {
            "preset": preset,
            "target_bitrate_mbps": round(target_bitrate_mbps, 4),
            "actual_bitrate_mbps": round(actual_bitrate, 4),
            "bitrate_deviation_pct": round(
                abs(actual_bitrate - target_bitrate_mbps) / target_bitrate_mbps * 100, 2
            ) if target_bitrate_mbps > 0 else None,
            "encode_time_seconds": round(encode_time, 3),
            "decode_time_seconds": round(decode_time, 3),
            "fps_encode": round(num_frames / encode_time, 2) if encode_time > 0 else None,
            "fps_decode": round(num_frames / decode_time, 2) if decode_time > 0 else None,
            "summary": {
                "psnr_y": {"mean": round(psnr_y_mean, 4), "std": round(psnr_y_std, 4)},
                "ssim": eval_result["summary"]["ssim"],
                "lpips": eval_result["summary"]["lpips"],
            },
        }
        results.append(preset_result)

        print(f"  PSNR-Y: {psnr_y_mean:.2f} dB")
        print(f"  SSIM: {eval_result['summary']['ssim']['mean']:.4f}")

    # 保存 H.265 结果
    h265_output = {
        "codec": "H.265/HEVC (libx265)",
        "source": dcvc_data["source"],
        "frame_count": num_frames,
        "resolution": f"{width}x{height}",
        "duration_seconds": duration,
        "results_by_preset": results,
    }

    RESULT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(RESULT_JSON, "w") as f:
        json.dump(h265_output, f, indent=2, ensure_ascii=False)

    print(f"\nH.265 结果已保存到 {RESULT_JSON}")

    # 生成对比表
    if results:
        comparison = {
            "dcvc_rt": {
                "bitrate_mbps": dcvc_data["bitrate_mbps"],
                "psnr_y_db": dcvc_data["summary"]["psnr_y"]["mean"],
                "ssim": dcvc_data["summary"]["ssim"]["mean"],
                "lpips": dcvc_data["summary"]["lpips"]["mean"],
                "fps_overall": dcvc_data["fps_overall"],
            },
            "h265": {},
        }
        for r in results:
            comparison["h265"][r["preset"]] = {
                "bitrate_mbps": r["actual_bitrate_mbps"],
                "bitrate_deviation_pct": r["bitrate_deviation_pct"],
                "psnr_y_db": r["summary"]["psnr_y"]["mean"],
                "ssim": r["summary"]["ssim"]["mean"],
                "lpips": r["summary"]["lpips"]["mean"],
                "fps_encode": r["fps_encode"],
                "fps_decode": r["fps_decode"],
            }

        with open(COMPARISON_JSON, "w") as f:
            json.dump(comparison, f, indent=2, ensure_ascii=False)

        print(f"\n对比表已保存到 {COMPARISON_JSON}")
        print("\n=== 对比汇总 ===")
        print(f"DCVC-RT: {comparison['dcvc_rt']['bitrate_mbps']:.4f} Mbps, "
              f"PSNR-Y={comparison['dcvc_rt']['psnr_y_db']:.2f}dB, "
              f"SSIM={comparison['dcvc_rt']['ssim']:.4f}")
        for preset, h in comparison["h265"].items():
            print(f"H.265-{preset}: {h['bitrate_mbps']:.4f} Mbps "
                  f"(偏差{h['bitrate_deviation_pct']:.1f}%), "
                  f"PSNR-Y={h['psnr_y_db']:.2f}dB, "
                  f"SSIM={h['ssim']:.4f}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 运行验证**

```bash
cd /home/ws-009/chy/Projects/semantic-transmission/.claude/worktrees/experiment+dcvc-rt-neural-codec
uv run python experiments/dcvc-rt/compare_h265.py
```

Expected: 输出 H.265 PSNR-Y/SSIM/LPIPS 数字，与 DCVC-RT 的对比表写入 `results/comparison.json`。

- [ ] **Step 3: Commit**

```bash
git add experiments/dcvc-rt/compare_h265.py
git commit -m "feat: DCVC-RT 实验——H.265 对照与头对头对比脚本"
```

---

### Task 6: 端到端验证与结果审查

**Files:**
- Modify: `experiments/dcvc-rt/README.md`（填写实验结论）

**Interfaces:**
- Consumes: `results/comparison.json`（来自 Task 5）

- [ ] **Step 1: 完整运行流程**

```bash
cd /home/ws-009/chy/Projects/semantic-transmission/.claude/worktrees/experiment+dcvc-rt-neural-codec

# 1. 准备帧
uv run python experiments/dcvc-rt/prepare_frames.py

# 2. 跑 DCVC-RT
uv run python experiments/dcvc-rt/run_dcvc.py

# 3. 跑 H.265 对照
uv run python experiments/dcvc-rt/compare_h265.py
```

- [ ] **Step 2: 审查结果 JSON**

```bash
cat experiments/dcvc-rt/results/comparison.json
```

检查：
- 码率偏差是否 <5%（若 >5%，H.265 需要微调 `-b:v` 重跑）
- PSNR-Y 数字是否合理（>25dB 通常可接受，>30dB 较好）
- DCVC-RT fps 是否在 60-100 范围内（预期校准值）

- [ ] **Step 3: 抽查解码帧质量**

```bash
ls experiments/dcvc-rt/results/frames/dcvc/ | head -3
ls experiments/dcvc-rt/results/frames/h265/medium/ | head -3
```

肉眼对比 DCVC-RT 和 H.265 的还原帧，检查是否有明显伪影或闪烁。

- [ ] **Step 4: 填写实验结论**

更新 `experiments/dcvc-rt/README.md`，填写：
- DCVC-RT 实际 fps（编码/解码）
- 码率-质量对比数据
- 大运动稳定性观察
- 是否推荐继续投入

- [ ] **Step 5: 最终 Commit**

```bash
git add experiments/dcvc-rt/README.md
git commit -m "docs: DCVC-RT 实验结论"
```
