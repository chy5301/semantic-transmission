# KleinReceiver 关键帧主线接收端 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 FLUX.2-klein-9B 落地为 `BaseReceiver` 子类，经 `create_receiver(backend="klein")` 与 `video --backend klein` 接入真实 video→video 流程，与 Z-Image 做 A/B 验证。

**Architecture:** 新增 `KleinReceiver(BaseReceiver)`（自包含持有 `Flux2KleinPipeline`，`image=[Canny]`+prompt 4 步生成），`create_receiver` 增 `backend` 分支，`video` CLI 增 `--backend` 旗标。不动 `BaseReceiver` 接口与 `VideoPipeline`。工作分辨率在 receiver 内部按长边上限降采样，规避大帧 OOM。

**Tech Stack:** Python 3.12 / uv / diffusers 0.37.1（`Flux2KleinPipeline`）/ PyTorch CUDA / click / pytest / ruff。

## Global Constraints

- 所有 Python 操作走 `uv run`（`uv run pytest`、`uv run ruff check .`、`uv run ruff format .`），禁止裸 `python`/`pip`/`pytest`/`ruff`。
- 推送前必过 `uv run ruff check .` 与 `uv run ruff format --check .`（CI 范围是整个项目 `.`）。
- klein 模型目录：`$MODEL_CACHE_DIR/black-forest-labs/FLUX.2-klein-9B`（bf16 全组件）。
- klein 加载固定 `enable_model_cpu_offload`；generator 用 `torch.Generator("cpu")`（offload 下最稳）。
- klein 生成参数：`image=[Canny_rgb]`、`guidance_scale=1.0`、`num_inference_steps=4`。
- 工作分辨率默认长边 `max_side=768`，保宽高比、宽高各向下取 16 的倍数、不放大。
- 长 GPU 任务超后台 2min 限制，必须 PowerShell `Start-Process` 脱离跑 + `Monitor` 守候。
- 提交信息遵循 Angular 约定、中文，不含工具生成标记与 Co-Authored-By。

---

### Task 1: KleinReceiverConfig 配置数据类

**Files:**
- Modify: `src/semantic_transmission/common/config.py`（在 `DiffusersReceiverConfig` 之后新增）
- Test: `tests/test_klein_config.py`

**Interfaces:**
- Produces: `KleinReceiverConfig(model_dir="", device="cuda", num_inference_steps=4, guidance_scale=1.0, torch_dtype="bfloat16", max_side=768, enable_vae_tiling=False, enable_attention_slicing=False)`；`__post_init__` 空 `model_dir` 回退 `load_config().model_cache_dir / "black-forest-labs" / "FLUX.2-klein-9B"`；`from_env()` 读 `KLEIN_*` 环境变量。

- [ ] **Step 1: Write the failing test**

`tests/test_klein_config.py`：

```python
"""KleinReceiverConfig 单元测试。"""

import os

from semantic_transmission.common.config import KleinReceiverConfig


def test_defaults():
    cfg = KleinReceiverConfig(model_dir="/x")  # 传 model_dir 跳过 load_config
    assert cfg.num_inference_steps == 4
    assert cfg.guidance_scale == 1.0
    assert cfg.torch_dtype == "bfloat16"
    assert cfg.max_side == 768
    assert cfg.enable_vae_tiling is False


def test_model_dir_resolves_from_cache(monkeypatch, tmp_path):
    monkeypatch.setenv("MODEL_CACHE_DIR", str(tmp_path))
    cfg = KleinReceiverConfig()
    assert cfg.model_dir.replace("\\", "/").endswith(
        "black-forest-labs/FLUX.2-klein-9B"
    )
    assert str(tmp_path).replace("\\", "/") in cfg.model_dir.replace("\\", "/")


def test_from_env_overrides(monkeypatch):
    monkeypatch.setenv("KLEIN_MAX_SIDE", "1024")
    monkeypatch.setenv("KLEIN_MODEL_DIR", "/custom/klein")
    monkeypatch.setenv("KLEIN_ENABLE_VAE_TILING", "true")
    cfg = KleinReceiverConfig.from_env()
    assert cfg.max_side == 1024
    assert cfg.model_dir == "/custom/klein"
    assert cfg.enable_vae_tiling is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_klein_config.py -v`
Expected: FAIL with `ImportError: cannot import name 'KleinReceiverConfig'`

- [ ] **Step 3: Write minimal implementation**

在 `src/semantic_transmission/common/config.py` 的 `DiffusersReceiverConfig` 类定义之后、`ProjectConfig` 分隔注释之前插入：

```python
@dataclass
class KleinReceiverConfig:
    """FLUX.2-klein-9B 接收端配置。

    支持 ``KLEIN_*`` 环境变量覆盖。``__post_init__`` 中空的 ``model_dir`` 回退到
    ``MODEL_CACHE_DIR``（经 ``load_config`` 解析）下的 klein 模型目录。
    """

    model_dir: str = ""
    device: str = "cuda"
    num_inference_steps: int = 4
    guidance_scale: float = 1.0
    torch_dtype: str = "bfloat16"
    max_side: int = 768
    enable_vae_tiling: bool = False
    enable_attention_slicing: bool = False

    def __post_init__(self):
        if not self.model_dir:
            project_config = load_config()
            self.model_dir = str(
                Path(project_config.model_cache_dir)
                / "black-forest-labs"
                / "FLUX.2-klein-9B"
            )

    @classmethod
    def from_env(cls) -> "KleinReceiverConfig":
        """从 ``KLEIN_*`` 环境变量构造配置实例。"""

        def _to_bool(v: str) -> bool:
            return v.strip().lower() in ("1", "true", "yes", "on")

        _TYPE_MAP = {"int": int, "float": float, "bool": _to_bool}
        kwargs: dict[str, object] = {}
        for f in fields(cls):
            val = os.environ.get(f"KLEIN_{f.name.upper()}")
            if val is None:
                continue
            type_str = f.type if isinstance(f.type, str) else f.type.__name__
            converter = _TYPE_MAP.get(type_str)
            if converter is not None:
                try:
                    kwargs[f.name] = converter(val)
                except (ValueError, TypeError) as e:
                    raise ValueError(
                        f"环境变量 KLEIN_{f.name.upper()}={val!r} 无法转换为 {type_str}"
                    ) from e
            else:
                kwargs[f.name] = val
        return cls(**kwargs)
```

（`dataclass` / `fields` / `os` / `Path` 均已在 `config.py` 顶部导入；`load_config` 虽定义在后，但 `__post_init__` 运行时才调用，与 `DiffusersReceiverConfig` 同样的前向引用，安全。）

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_klein_config.py -v`
Expected: PASS（3 passed）

- [ ] **Step 5: Commit**

```bash
uv run ruff format src/semantic_transmission/common/config.py tests/test_klein_config.py
uv run ruff check src/semantic_transmission/common/config.py tests/test_klein_config.py
git add src/semantic_transmission/common/config.py tests/test_klein_config.py
git commit -m "feat: 新增 KleinReceiverConfig 配置数据类"
```

---

### Task 2: fit_working_size 工作分辨率降采样

**Files:**
- Create: `src/semantic_transmission/receiver/klein_receiver.py`（仅本任务的 `fit_working_size` 函数 + 模块 docstring）
- Test: `tests/test_klein_receiver.py`（仅 `fit_working_size` 用例）

**Interfaces:**
- Produces: `fit_working_size(image: PIL.Image.Image, max_side: int) -> PIL.Image.Image` — 保宽高比把长边压到 `max_side`，宽高各向下取 16 的倍数，不放大；尺寸不变时原样返回。

- [ ] **Step 1: Write the failing test**

`tests/test_klein_receiver.py`：

```python
"""KleinReceiver 单元测试（无 GPU，注入假 pipe）。"""

from PIL import Image

from semantic_transmission.receiver.klein_receiver import fit_working_size


def test_fit_downscales_16x9_to_max_side():
    out = fit_working_size(Image.new("RGB", (1920, 1080)), max_side=768)
    assert out.size == (768, 432)  # 768=48*16, 432=27*16


def test_fit_downscales_4x3_to_max_side():
    out = fit_working_size(Image.new("RGB", (1280, 960)), max_side=768)
    assert out.size == (768, 576)  # 576=36*16


def test_fit_no_upscale_but_rounds_to_16():
    out = fit_working_size(Image.new("RGB", (100, 100)), max_side=768)
    assert out.size == (96, 96)  # 不放大，向下取 16


def test_fit_keeps_exact_multiple_unchanged():
    src = Image.new("RGB", (320, 240))
    out = fit_working_size(src, max_side=768)
    assert out.size == (320, 240)
    assert out is src  # 尺寸已合规则原样返回
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_klein_receiver.py -v`
Expected: FAIL with `ModuleNotFoundError: ... klein_receiver`

- [ ] **Step 3: Write minimal implementation**

`src/semantic_transmission/receiver/klein_receiver.py`：

```python
"""FLUX.2-klein-9B 接收端：image=[Canny]+prompt 4 步生成。"""

from __future__ import annotations

from PIL import Image


def fit_working_size(image: Image.Image, max_side: int) -> Image.Image:
    """保宽高比把长边压到 ``max_side``，宽高各向下取 16 的倍数，不放大。

    klein/Flux 要求尺寸为 16 的倍数；大帧（如 1920×1080）原生分辨率会 OOM，
    故在 receiver 内部降采样到 GPU 可承受的工作分辨率。尺寸已合规则原样返回。
    """
    w, h = image.size
    scale = min(1.0, max_side / max(w, h))
    nw = max(16, int(w * scale) // 16 * 16)
    nh = max(16, int(h * scale) // 16 * 16)
    if (nw, nh) == (w, h):
        return image
    return image.resize((nw, nh), Image.LANCZOS)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_klein_receiver.py -v`
Expected: PASS（4 passed）

- [ ] **Step 5: Commit**

```bash
uv run ruff format src/semantic_transmission/receiver/klein_receiver.py tests/test_klein_receiver.py
uv run ruff check src/semantic_transmission/receiver/klein_receiver.py tests/test_klein_receiver.py
git add src/semantic_transmission/receiver/klein_receiver.py tests/test_klein_receiver.py
git commit -m "feat: 新增 fit_working_size 工作分辨率降采样"
```

---

### Task 3: KleinReceiver 类（load/unload/process）

**Files:**
- Modify: `src/semantic_transmission/receiver/klein_receiver.py`（追加 `KleinReceiver` 类）
- Test: `tests/test_klein_receiver.py`（追加 `KleinReceiver` 用例）

**Interfaces:**
- Consumes: `fit_working_size`（Task 2）；`KleinReceiverConfig`（Task 1）；`BaseReceiver` / `BatchOutput` / `FrameInput`（`receiver.base`）；`load_as_rgb`（`common.image_io`）。
- Produces: `KleinReceiver(config: KleinReceiverConfig | None = None)`，含 `is_loaded` 属性、`load()`、`unload()`、`process(edge_image, prompt_text, seed=None) -> Image`、`process_batch(frames) -> BatchOutput`；内部 `_build_pipeline()` 可被测试 monkeypatch。

- [ ] **Step 1: Write the failing test**

在 `tests/test_klein_receiver.py` 顶部 import 处补充，并追加用例：

```python
from semantic_transmission.common.config import KleinReceiverConfig
from semantic_transmission.receiver.base import BaseReceiver
from semantic_transmission.receiver.klein_receiver import KleinReceiver


class _FakePipe:
    """记录 __call__ 入参的假 pipeline。"""

    def __init__(self):
        self.calls = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        out = type("Out", (), {})()
        out.images = [Image.new("RGB", (kwargs["width"], kwargs["height"]))]
        return out


def _receiver_with_fake_pipe():
    rec = KleinReceiver(KleinReceiverConfig(model_dir="/x", max_side=768))
    fake = _FakePipe()
    rec._pipe = fake
    return rec, fake


def test_is_basereceiver():
    rec = KleinReceiver(KleinReceiverConfig(model_dir="/x"))
    assert isinstance(rec, BaseReceiver)
    assert rec.is_loaded is False


def test_process_passes_klein_kwargs():
    rec, fake = _receiver_with_fake_pipe()
    rec.process(Image.new("RGB", (1920, 1080)), "a desert road", seed=0)
    call = fake.calls[0]
    assert call["image"][0].size == (768, 432)  # 内部已降采样
    assert call["width"] == 768 and call["height"] == 432
    assert call["num_inference_steps"] == 4
    assert call["guidance_scale"] == 1.0
    assert call["prompt"] == "a desert road"
    assert call["generator"].device.type == "cpu"


def test_process_seed_deterministic_generator():
    rec, fake = _receiver_with_fake_pipe()
    rec.process(Image.new("RGB", (512, 512)), "x", seed=123)
    gen = fake.calls[0]["generator"]
    assert gen.initial_seed() == 123


def test_load_idempotent(monkeypatch):
    rec = KleinReceiver(KleinReceiverConfig(model_dir="/x"))
    counter = {"n": 0}

    def fake_build():
        counter["n"] += 1
        return _FakePipe()

    monkeypatch.setattr(rec, "_build_pipeline", fake_build)
    rec.load()
    rec.load()
    assert counter["n"] == 1
    assert rec.is_loaded is True


def test_unload_clears_pipe():
    rec, _ = _receiver_with_fake_pipe()
    assert rec.is_loaded is True
    rec.unload()
    assert rec.is_loaded is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_klein_receiver.py -v`
Expected: FAIL with `ImportError: cannot import name 'KleinReceiver'`

- [ ] **Step 3: Write minimal implementation**

在 `klein_receiver.py` 追加 import 与类（`fit_working_size` 已在文件中）：

```python
import gc
import random

import torch

from semantic_transmission.common.config import KleinReceiverConfig
from semantic_transmission.common.image_io import load_as_rgb
from semantic_transmission.receiver.base import BaseReceiver, BatchOutput, FrameInput


class KleinReceiver(BaseReceiver):
    """接收端：用 ``Flux2KleinPipeline`` 从 Canny 参考图 + prompt 生成图像。"""

    def __init__(self, config: KleinReceiverConfig | None = None) -> None:
        self.config = config or KleinReceiverConfig()
        self._pipe = None

    @property
    def is_loaded(self) -> bool:
        return self._pipe is not None

    def _build_pipeline(self):
        from diffusers import Flux2KleinPipeline

        pipe = Flux2KleinPipeline.from_pretrained(
            self.config.model_dir,
            torch_dtype=getattr(torch, self.config.torch_dtype),
            local_files_only=True,
        )
        pipe.enable_model_cpu_offload()
        if self.config.enable_vae_tiling:
            pipe.enable_vae_tiling()
        if self.config.enable_attention_slicing:
            pipe.enable_attention_slicing()
        return pipe

    def load(self):
        """加载 klein pipeline（幂等）。"""
        if self._pipe is None:
            self._pipe = self._build_pipeline()
        return self._pipe

    def unload(self) -> None:
        """卸载 pipeline，释放显存。"""
        if self._pipe is not None:
            del self._pipe
            self._pipe = None
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

    def process(
        self,
        edge_image,
        prompt_text,
        seed=None,
    ) -> Image.Image:
        """从 Canny 边缘图 + 文本生成还原图像（内部降采样到工作分辨率）。"""
        pipe = self.load()
        cond = fit_working_size(load_as_rgb(edge_image), self.config.max_side)
        width, height = cond.size
        if seed is None:
            seed = random.randint(0, 2**32 - 1)
        generator = torch.Generator("cpu").manual_seed(seed)
        result = pipe(
            prompt=prompt_text,
            image=[cond],
            guidance_scale=self.config.guidance_scale,
            num_inference_steps=self.config.num_inference_steps,
            height=height,
            width=width,
            generator=generator,
        )
        return result.images[0]

    def process_batch(self, frames: list[FrameInput]) -> BatchOutput:
        """批量处理，模型常驻 GPU 不反复加载。"""
        self.load()
        return super().process_batch(frames)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_klein_receiver.py -v`
Expected: PASS（9 passed：4 个 fit + 5 个 receiver）

- [ ] **Step 5: Commit**

```bash
uv run ruff format src/semantic_transmission/receiver/klein_receiver.py tests/test_klein_receiver.py
uv run ruff check src/semantic_transmission/receiver/klein_receiver.py tests/test_klein_receiver.py
git add src/semantic_transmission/receiver/klein_receiver.py tests/test_klein_receiver.py
git commit -m "feat: 新增 KleinReceiver 接收端（load/unload/process）"
```

---

### Task 4: create_receiver 增加 backend 分支

**Files:**
- Modify: `src/semantic_transmission/receiver/__init__.py`
- Test: `tests/test_receiver_factory.py`（追加 klein 分支用例）

**Interfaces:**
- Consumes: `KleinReceiver`（Task 3）。
- Produces: `create_receiver(config=None, *, loader=None, backend="diffusers")`；`backend="klein"` 返回 `KleinReceiver(config)`；未知 backend 抛 `ValueError`。

- [ ] **Step 1: Write the failing test**

在 `tests/test_receiver_factory.py` 末尾追加：

```python
class TestCreateReceiverKlein:
    def test_returns_klein_receiver(self):
        from semantic_transmission.receiver.klein_receiver import KleinReceiver

        receiver = create_receiver(backend="klein")
        assert isinstance(receiver, KleinReceiver)
        assert isinstance(receiver, BaseReceiver)

    def test_klein_accepts_klein_config(self):
        from semantic_transmission.common.config import KleinReceiverConfig

        cfg = KleinReceiverConfig(model_dir="/x", max_side=1024)
        receiver = create_receiver(config=cfg, backend="klein")
        assert receiver.config.max_side == 1024

    def test_unknown_backend_raises(self):
        import pytest

        with pytest.raises(ValueError, match="backend"):
            create_receiver(backend="nope")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_receiver_factory.py::TestCreateReceiverKlein -v`
Expected: FAIL with `TypeError: create_receiver() got an unexpected keyword argument 'backend'`

- [ ] **Step 3: Write minimal implementation**

替换 `src/semantic_transmission/receiver/__init__.py` 的 `create_receiver`：

```python
def create_receiver(
    config: DiffusersReceiverConfig | KleinReceiverConfig | None = None,
    *,
    loader: DiffusersModelLoader | None = None,
    backend: str = "diffusers",
) -> BaseReceiver:
    """创建接收端实例。

    ``backend="diffusers"``（默认/备选）返回 ``DiffusersReceiver``（Z-Image）；
    ``backend="klein"`` 返回 ``KleinReceiver``（FLUX.2-klein-9B 关键帧主线）。
    ``config`` 按 backend 解释为对应的接收端配置；``loader`` 仅 diffusers 适用。
    """
    if backend == "diffusers":
        from semantic_transmission.receiver.diffusers_receiver import DiffusersReceiver

        return DiffusersReceiver(config, loader=loader)
    if backend == "klein":
        from semantic_transmission.receiver.klein_receiver import KleinReceiver

        return KleinReceiver(config)
    raise ValueError(f"未知 backend: {backend!r}（支持 'diffusers' / 'klein'）")
```

并在文件顶部 `TYPE_CHECKING` 块补充 klein 配置类型：

```python
if TYPE_CHECKING:
    from semantic_transmission.common.config import (
        DiffusersReceiverConfig,
        KleinReceiverConfig,
    )
    from semantic_transmission.common.model_loader import DiffusersModelLoader
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_receiver_factory.py -v`
Expected: PASS（原 4 个 diffusers 用例 + 新 3 个 klein 用例全过）

- [ ] **Step 5: Commit**

```bash
uv run ruff format src/semantic_transmission/receiver/__init__.py tests/test_receiver_factory.py
uv run ruff check src/semantic_transmission/receiver/__init__.py tests/test_receiver_factory.py
git add src/semantic_transmission/receiver/__init__.py tests/test_receiver_factory.py
git commit -m "feat: create_receiver 增加 klein backend 分支"
```

---

### Task 5: video CLI 增加 --backend 旗标

**Files:**
- Modify: `src/semantic_transmission/cli/video.py`
- Test: `tests/test_cli_video.py`（更新既有 monkeypatch + 新增 backend 用例）

**Interfaces:**
- Consumes: `create_receiver(backend=...)`（Task 4）。
- Produces: `video` 命令新增 `--backend {diffusers,klein}`（默认 diffusers），透传给 `create_receiver`。

- [ ] **Step 1: Write the failing test**

先**修复**既有测试：`tests/test_cli_video.py` 第 52 行的零参 lambda 改为接受 kwargs（否则 Task 5 改动会让它 `TypeError`）：

```python
    monkeypatch.setattr(video_mod, "create_receiver", lambda *a, **k: _DummyReceiver())
```

再在 `tests/test_cli_video.py` 末尾追加两个用例：

```python
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

    out = tmp_path / "out" / "out.mp4"  # 写到 tmp，避免污染仓库 output/
    result = CliRunner().invoke(
        video,
        ["--input", str(src), "--output", str(out), "--prompt", "a", "--backend", "klein"],
    )
    assert result.exit_code == 0, result.output
    assert captured["backend"] == "klein"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli_video.py -v`
Expected: FAIL — `test_video_rejects_invalid_backend` 与 `test_video_passes_backend_to_factory` 失败（`--backend` 尚不存在，click 报 "no such option"）

- [ ] **Step 3: Write minimal implementation**

在 `src/semantic_transmission/cli/video.py` 的 `--seed` option 之后、`def video(` 之前新增 option：

```python
@click.option(
    "--backend",
    type=click.Choice(["diffusers", "klein"]),
    default="diffusers",
    help="接收端后端（默认 diffusers/Z-Image 备选；klein=FLUX.2-klein-9B 关键帧主线）",
)
```

在 `def video(` 参数列表加入 `backend`（放 `seed` 之后即可，click 按名传参），并把：

```python
    receiver = create_receiver()
```

改为：

```python
    receiver = create_receiver(backend=backend)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli_video.py -v`
Expected: PASS（含既有 4 个 + 新 2 个）

- [ ] **Step 5: Commit**

```bash
uv run ruff format src/semantic_transmission/cli/video.py tests/test_cli_video.py
uv run ruff check src/semantic_transmission/cli/video.py tests/test_cli_video.py
git add src/semantic_transmission/cli/video.py tests/test_cli_video.py
git commit -m "feat: video CLI 增加 --backend 旗标"
```

---

### Task 6: 决策记录（ROADMAP + H1 报告 §0 口径修正）

**Files:**
- Modify: `docs/ROADMAP.md`
- Modify: `docs/test-reports/2026-06-29-h1-klein-structure-poc-report.md`

**Interfaces:** 无代码接口，纯文档。

- [ ] **Step 1: 更新 ROADMAP.md**

先 `Read` `docs/ROADMAP.md`，定位关键帧主线/阶段三选型相关段落，加入决策记录（措辞按上下文调整，要点固定）：

> **2026-06-30 关键帧主线选型决策**：负责人定 **FLUX.2-klein-9B 为关键帧主线、Z-Image-Turbo 为备选**。klein 经 `KleinReceiver` 接入 video→video 流程做 A/B 验证（设计见 `docs/superpowers/specs/2026-06-30-klein-receiver-backend-design.md`）。决策可逆：若 klein 帧间一致性即便加参考帧仍不可用，回退 Z-Image。

- [ ] **Step 2: 修正 H1 报告 §0 口径**

`Read` `docs/test-reports/2026-06-29-h1-klein-structure-poc-report.md` 的 §0，在「结论先行」首段后补一句口径修正（**不删除**原有「单帧 IoU 是低天花板指标、不代表 video→video 表现」的说明）：

> **（2026-06-30 更新）** 负责人已据本 PoC 单帧发现 + klein 视觉质量优势，定 **klein 为关键帧主线、Z-Image 备选**。本报告单帧 IoU 结论维持有效；klein 的 video→video 公平复测在 `feature/klein-receiver-backend` 进行（`KleinReceiver` 接入），含帧间一致性与参考帧补偿验证。

- [ ] **Step 3: 校验改动**

Run: `uv run ruff format --check . && uv run ruff check .`
Expected: PASS（纯文档改动不应影响；若 ruff 报无关历史问题，仅确认本次改动文件不在报错列表）

- [ ] **Step 4: Commit**

```bash
git add docs/ROADMAP.md docs/test-reports/2026-06-29-h1-klein-structure-poc-report.md
git commit -m "docs: 记录 klein 主线/Z-Image 备选决策 + 修正 H1 报告 §0 口径"
```

---

### Task 7: 阶段 1 真实 video→video A/B 验证（手动 GPU）

> **手动任务，需 GPU。** 不是自动化测试——产出是对比观察 + 一份简短测试报告。长推理超后台 2min 限制，**必须** PowerShell `Start-Process` 脱离跑 + `Monitor` 守候。

**Files:**
- Create: `docs/test-reports/2026-06-30-klein-video-ab-phase1.md`（验证结论）
- 产物：`output/video/klein_*/` 与 `output/video/zimage_*/`（gitignored）

**Interfaces:** 无代码接口；消费 Task 1–5 的全部成果。

- [ ] **Step 1: 选定干净测试片段**

优先用容器干净的 `resources/test_videos/视频记录/20251109134829.mp4`（1920×1080）。裸 `.h265` 若 `read_frames` 解码报错（ffprobe 见 missing picture / PPS）则跳过。先 smoke 一条短的：可用 ffmpeg 截 ~3s 子片段降低单次耗时。

- [ ] **Step 2: 后台跑 klein（脱离 + 守候）**

用 PowerShell `Start-Process` 脱离运行，`Monitor` 守候日志直到结束（命令按实际路径调整）：

```powershell
Start-Process -FilePath "uv" -ArgumentList @(
  "run","semantic-tx","video",
  "--input","resources/test_videos/视频记录/20251109134829.mp4",
  "--output","output/video/klein_001/out.mp4",
  "--backend","klein","--auto-prompt"
) -RedirectStandardOutput "output/video/klein_001/run.log" `
  -RedirectStandardError "output/video/klein_001/err.log" -NoNewWindow
```

观察 `err.log`：若 OOM，按 spec §3.3 降 `KLEIN_MAX_SIDE=640` 或设 `KLEIN_ENABLE_VAE_TILING=true` 重试；记录实测能扛的最大 `max_side`。

- [ ] **Step 3: 同片段同分辨率跑 Z-Image baseline**

为公平 A/B，让 Z-Image 用与 klein 相同的工作分辨率（若需要，临时把输入缩到 klein 实测分辨率再喂；记录所用分辨率）：

```powershell
Start-Process -FilePath "uv" -ArgumentList @(
  "run","semantic-tx","video",
  "--input","resources/test_videos/视频记录/20251109134829.mp4",
  "--output","output/video/zimage_001/out.mp4",
  "--backend","diffusers","--auto-prompt"
) -RedirectStandardOutput "output/video/zimage_001/run.log" `
  -RedirectStandardError "output/video/zimage_001/err.log" -NoNewWindow
```

- [ ] **Step 4: 评估对比**

```bash
uv run python scripts/evaluate_video.py --help   # 确认参数
# 对两路输出各算 CLIP Score（PSNR/SSIM 对生成式不作主判据）
```

目视并排两段输出，重点看：klein 帧间闪烁 / 构图漂移程度、单帧视觉质量是否优于 Z-Image。

- [ ] **Step 5: 写验证报告 + Commit**

`docs/test-reports/2026-06-30-klein-video-ab-phase1.md` 记录：实测最大 `max_side`、是否 OOM 及处置、CLIP Score 对比、目视结论（klein 时间一致性现状、是否值得进阶段 2 参考帧）。

```bash
git add docs/test-reports/2026-06-30-klein-video-ab-phase1.md
git commit -m "docs: klein vs Z-Image 阶段1 video A/B 验证报告"
```

- [ ] **Step 6: 停下来与负责人讨论**

按 spec §6：阶段 1 结果出来后**暂停**，与负责人讨论是否进入阶段 2（参考帧补偿）及其细节（间隔 N、参考帧来源、relay 透传）。

---

## 验证全量回归

全部代码任务完成后：

```bash
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
```

Expected: 全绿。
