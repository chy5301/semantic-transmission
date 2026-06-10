# 任务分析报告

> Workflow: `unify-config-and-loader` (refactor + bugfix + infrastructure)
> 分析日期: 2026-04-12
> 基准 commit: `b369a71`

## 项目概述

语义传输预研项目：用 AI 模型实现视频的语义级压缩传输。发送端用 VLM（Qwen2.5-VL）将图像压缩为文本描述 + Canny 边缘图，接收端用 Diffusers（Z-Image-Turbo + ControlNet）从文本和边缘图还原视觉内容。

**技术栈**：Python / uv / Diffusers 0.37 + GGUF 量化 / Qwen2.5-VL / Click CLI / Gradio 5.x GUI / Socket 中继

**本次重构目标**：统一"参数配置 + 模型加载 + 生命周期"核心链 + 修复 P0 demo 缺陷（11 个 GitHub issue）。

---

## 架构扫描

### 模块结构与职责

```
src/semantic_transmission/
├── common/          # config.py (DiffusersReceiverConfig + 2 个 helper) / model_check.py / types.py
├── cli/             # 8 个子命令：sender / batch_sender / receiver / demo / batch_demo / check / download / gui
├── gui/             # 6 个面板：config / sender / batch_sender / pipeline(端到端) / batch(批量端到端) / receiver
├── pipeline/        # relay.py (SocketRelaySender/Receiver) / batch_processor.py (BatchImageDiscoverer + BatchResult)
├── sender/          # qwen_vl_sender.py + local_condition_extractor.py
├── receiver/        # base.py (ABC) + diffusers_receiver.py
└── evaluation/      # metrics.py + semantic_metrics.py + utils.py
```

### 当前配置体系（四套并存）

| 层 | 载体 | 覆盖字段 | 消费者 |
|---|---|---|---|
| ① Dataclass 默认 | `DiffusersReceiverConfig` (7 字段) | 模型路径/device/dtype/steps/cfg | DiffusersReceiver |
| ② 环境变量 | `DIFFUSERS_*` (7 个) + `MODEL_CACHE_DIR` | 与 ① 同 + VLM 路径 | `from_env()` / `get_default_*()` |
| ③ CLI click options | 每命令 9-13 个 options | Canny 阈值 / VLM 路径 / relay / seed / output | CLI 入口 |
| ④ GUI textbox | `config_panel` 传递到下游面板 | VLM model name/path | GUI 面板 |

**问题**：VLM 没有对应的 dataclass（QwenVLSender 只用构造函数参数），CLI 4 个命令各自重复定义相同 options，GUI 的 receiver 配置不可调（走死默认）。

### 当前模型加载体系

| 模型 | 加载代码位置 | 配置来源 | unload 实现 |
|---|---|---|---|
| Diffusers pipeline | `diffusers_receiver.py:35-67` | `DiffusersReceiverConfig` | `unload()` ✓ (pipeline=None + empty_cache + gc) |
| QwenVL | `qwen_vl_sender.py:59-110` | 构造函数参数 | `unload()` ✓ (model=None + empty_cache + gc) |

**关键发现**：两者各自有 `load()/unload()/is_loaded`，行为模式相同，但没有公共接口 — 调用方需要知道具体类型才能管理生命周期。

### CLI 子命令重叠分析

| 维度 | sender.py | batch_sender.py | demo.py | batch_demo.py |
|---|---|---|---|---|
| Canny 阈值 | ✓ 100/200 | ✓ 100/200 | ✓ 100/200 | ✓ 100/200 |
| VLM 选项 | ✓ --vlm-model/path | ✓ --vlm-model/path | ✓ --vlm-model/path | ✓ --vlm-model/path |
| Prompt 选项 | ✓ --prompt/--auto-prompt | ✓ --prompt/--auto-prompt | ✓ --prompt/--auto-prompt | ✓ --prompt/--auto-prompt |
| Relay 选项 | ✓ --relay-host/port | ✓ --relay-host/port | ✗ | ✗ |
| Seed | ✓ --seed | ✓ --seed | ✓ --seed | ✓ --seed |
| **VLM 加载** | **每次加载+卸载** | **一次加载+卸载** | **每次加载+卸载** | **一次加载+卸载** |
| **Receiver** | 远端 | 远端 | 本地 create_receiver | 本地 create_receiver |

**重复**：prompt 校验逻辑 4 处相同、VLM 初始化逻辑 4 处相同、默认路径解析 4 处相同。

---

## 接口契约清单

### DiffusersReceiver 公共接口

```python
class DiffusersReceiver(BaseReceiver):
    def __init__(self, config: DiffusersReceiverConfig | None = None)
    @property
    def is_loaded(self) -> bool
    def load(self) -> None                                           # 幂等
    def unload(self) -> None                                         # pipeline=None + empty_cache + gc
    def process(self, edge_image, prompt_text, seed=None) -> Image   # 内部调 load()
    def process_batch(self, frames: list[FrameInput]) -> BatchOutput # 调 load() + super()
```

**隐式契约**：
- `process()` 内部调用 `load()`，幂等。调用方不需要显式 `load()`
- Pipeline 输出尺寸由 pipeline 默认决定（当前写死，**#24 根因**）
- `guidance_scale=1.0` + `num_inference_steps=9` 硬编码在 `DiffusersReceiverConfig` 默认值中

### QwenVLSender 公共接口

```python
class QwenVLSender:
    def __init__(self, model_name=..., model_path=None, quantization="int4", max_new_tokens=512, system_prompt=None)
    def describe(self, image: np.ndarray | Image.Image, text: str = "") -> SenderOutput  # 内部 lazy load
    def unload(self) -> None
```

**隐式契约**：
- `describe()` 首次调用时触发 lazy load（`_load_model()`）
- 量化策略 cascade：torchao INT4 → bitsandbytes 4bit → float16 fallback
- 无 `is_loaded` 属性（要检查 `_model is not None`）
- 无 `load()` 公共方法（只有 `_load_model()` 私有）

### BaseReceiver.process_batch vs pipeline/batch_processor

- `BaseReceiver.process_batch(frames)` (base.py:55-80)：通用循环，逐帧调 `self.process()`，收集 SampleResult → BatchResult
- `pipeline/batch_processor.py`：`BatchImageDiscoverer` 扫描目录 + `SampleResult`/`BatchResult` 数据结构
- **重叠**：base.py 的循环和 CLI `batch_sender.py`/`batch_demo.py` 各自写了一遍"遍历图片 → 处理 → 收集结果"的循环。base.py 的循环仅供 receiver_panel GUI 使用。

### create_receiver 工厂

```python
# receiver/__init__.py
def create_receiver(config: DiffusersReceiverConfig | None = None) -> BaseReceiver:
    return DiffusersReceiver(config or DiffusersReceiverConfig())
```

所有调用方（CLI receiver/demo/batch_demo, GUI receiver_panel/pipeline_panel/batch_panel）均用此工厂，传 None 走默认配置。

---

## 耦合风险点

### 1. CLI receiver.py 缺少 unload（高风险）

CLI `receiver.py` 的 finally block 只关 relay，**不调 `receiver.unload()`**。长时间运行或连续调用会 VRAM 泄漏。

### 2. GUI pipeline_panel + batch_panel receiver 不 unload（P0）

| 面板 | VLM unload | Receiver unload | LPIPS unload |
|---|---|---|---|
| pipeline_panel | ✓ | **✗ 缺失** | N/A |
| batch_panel | ✓ | **✗ 缺失** | **✗ 缺失** |
| receiver_panel | N/A | ✓ (按钮) | N/A |
| sender_panel | ✓ | N/A | N/A |
| batch_sender_panel | ✓ | N/A (远端) | N/A |

**实测复现**：连续 3 次后第 3 次推理慢 16×（51.54s/it vs 3.17s/it），批量端到端双模型同驻 312s/it。

### 3. Pipeline 输出尺寸写死（P0，#24 根因）

`diffusers_receiver.py` 的 `process()` 方法没有从 `control_image` 读取 H/W，pipeline 使用默认尺寸。竖版原图被 resize 成更矮更宽。

**定位**：`process()` 方法 (lines 78-111) 调用 pipeline 时未传 `height`/`width` 参数。

### 4. 采样器参数与 ComfyUI 不对齐（#25）

当前 `DiffusersReceiverConfig` 默认：`guidance_scale=1.0`, `num_inference_steps=9`。
ComfyUI 基线使用：`AuraFlow shift=3.0`, `res_multistep` sampler, `simple` scheduler。

**风险**：`res_multistep` 和 `AuraFlow shift` 在 diffusers 中的等价 API 需要在 Phase 1 实际验证。seed 文件中写的 `guidance_scale=3.5` 和 `num_inference_steps=20` 是建议值，**实际默认值需要在 #25 对齐过程中通过逼眼对比确定**。

### 5. download.py 硬编码模型清单

`COMFYUI_MODELS` (lines 23-52) 和 `HF_REPO_MODELS` (lines 54-56) 写死在源码。COMFYUI 相关路径已过时（ComfyUI 已脱离），仍在下载列表中占位。

### 6. 全局状态：无

未发现模块级全局状态（singleton / module-level cache / class-level state）。所有状态在实例级管理（`_pipeline`、`_model`、`_processor`）。

---

## 重构范围建议

### 迁移面清单（按 phase）

**Phase 0 新增文件**（不动旧代码）：
| 文件 | 说明 |
|---|---|
| `src/semantic_transmission/common/config.py` | 扩展现有，增加 `ProjectConfig` + `config.toml` loader |
| `src/semantic_transmission/common/model_loader.py` | 新建 `ModelLoader` ABC |
| `config.toml` | 仓库根，默认值 |
| `tests/test_project_config.py` | 新建 |
| `tests/test_model_loader.py` | 新建 |

**Phase 1 修改文件**（receiver 侧）：
| 文件 | 改动 |
|---|---|
| `receiver/diffusers_receiver.py` | 加载逻辑迁移到 DiffusersModelLoader，process() 加 height/width 参数 |
| `receiver/base.py` | process_batch() 可能简化（配合 #31） |
| `common/config.py` | 新增 `DiffusersLoaderConfig` dataclass |
| `tests/test_diffusers_receiver.py` | 补 dynamic size / sampler / lifecycle 测试 |

**Phase 2 修改文件**（sender/CLI 侧）：
| 文件 | 改动 |
|---|---|
| `sender/qwen_vl_sender.py` | 加载逻辑迁移到 QwenVLModelLoader |
| `cli/sender.py` | 吸收 batch_sender 功能，改读 config |
| `cli/batch_sender.py` | **删除** |
| `cli/main.py` | 移除 batch_sender 注册 |
| `cli/demo.py` | 改读 config |
| `cli/batch_demo.py` | 改读 config |
| `cli/download.py` | 从 config 读模型清单 |
| `cli/receiver.py` | 加 finally unload |
| `common/config.py` | 新增 `VLMLoaderConfig` dataclass |

**Phase 3 修改文件**（GUI 侧）：
| 文件 | 改动 |
|---|---|
| `gui/pipeline_panel.py` | try/finally + receiver.unload() |
| `gui/batch_panel.py` | try/finally + receiver.unload() + lpips cleanup |
| `gui/config_panel.py` | 评估是否读 ProjectConfig 填控件 |
| `gui/sender_panel.py` | 评估是否需要 lifecycle 修改 |

**Phase 4 修改文件**（横切 cleanup）：
| 文件 | 改动 |
|---|---|
| `common/image_io.py` | **新建** load_as_rgb() helper |
| 散落的 16+ 文件 | 替换 Image.open().convert("RGB") 为 load_as_rgb() |
| `common/relay.py` 或类似 | 删除 LocalRelay dead code |
| `docs/cli-reference.md` | 更新 CLI 合并 |
| `docs/user-guide.md` | 更新 CLI 合并 |

### 总改动面估计

- **新建文件**：~5 个
- **修改文件**：~20 个
- **删除文件**：~2 个（batch_sender.py、LocalRelay）
- **影响测试文件**：~5 个

---

## 与 brainstorm seed 的一致性/差异

| 维度 | seed 假设 | 代码实际 | 差异影响 |
|---|---|---|---|
| guidance_scale 默认 | 3.5 | **1.0** | 实际值需 Phase 1 实验确定，seed 的 3.5 只是建议 |
| num_inference_steps 默认 | 20 | **9** | 同上 |
| sampler "res_multistep" | 直接写 config | **diffusers 中无同名 scheduler** | Phase 1 需查找 diffusers 等价 API（可能是 `FlowMatchEulerDiscreteScheduler` + shift 参数） |
| process_batch #31 | "删 BaseReceiver.process_batch 循环" | 循环实际在 base.py 且被 DiffusersReceiver.process_batch 调用 | 不能简单删，需要重新设计 receiver_panel 的 queue 处理入口 |
| batch_panel LPIPS | seed 未提及 | **batch_panel 加载 LPIPS 模型但不 unload** | Phase 3 需补 LPIPS cleanup |
| CLI receiver.py unload | seed 未提及 | **CLI receiver 缺 unload** | Phase 2 需在 finally block 加 receiver.unload() |
| QwenVLSender 无 load() | seed 假设有 load/unload 对称 | **只有 _load_model() 私有 + unload() 公共** | QwenVLModelLoader 需包装 lazy load 为显式 load() |
| QwenVLSender 无 is_loaded | seed 假设有 | **无此属性** | QwenVLModelLoader 需实现 |
| demo.py / batch_demo.py | seed 未显式提及 | **与 sender/batch_sender 共享大量逻辑** | Phase 2 CLI 合并需一并处理这两个命令的 config 迁移 |

---

## 补充检查项（Secondary Tags）

### bugfix 标签
- [x] 根因已定位：#23 = GUI 面板缺 receiver unload；#24 = pipeline 未传 H/W；#25 = 采样器参数不对齐
- [x] 回归测试策略已规划：CI fixture `device="cpu"` + 本地 RTX 5090 手工验收 + 连续 3 次跑测

### infrastructure 标签
- [x] CI 影响评估：新增 tomllib（stdlib）无额外 CI 依赖；测试仍走 `device="cpu"`
- [x] 部署兼容：config.toml 是新增文件，不影响现有部署

---

## 待确认问题

1. **demo.py / batch_demo.py CLI 合并范围**：seed 只提到 sender + batch_sender 合并为 sender，但 demo + batch_demo 也有大量重复 options。是否也合并为单一 `demo` 命令？**建议**：本 workflow 不合并 demo/batch_demo（范围已经够大），但 Phase 2 改 config 读取时需同步改 demo 和 batch_demo 的 options。

2. **diffusers 采样器 API 验证**：`res_multistep` + `AuraFlow shift=3` 的 diffusers 等价 API 需在 Phase 1 实际验证。如果 diffusers 没有直接等价，需要讨论替代方案。

3. **LPIPS unload 方式**：batch_panel 的 LPIPS 模型（`lpips` 库）是否有标准 unload/del 方法？需在 Phase 3 确认。
