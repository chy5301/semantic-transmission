# receiver-decouple-comfyui — 待提交 issue 清单

> 本文件是 **workflow 显式维护的交付物**，作为 M-16 批量提交 GitHub issue 前的对账单，也给下次会话/负责人做进度提醒。
>
> **归属**：本 workflow 归档时随 `docs/workflow/` 整体移入 `docs/workflow/archive/receiver-decouple-comfyui/`，不单独归档到其它位置。
>
> **相关记忆**：`memory/project_pending_issues.md`（跨会话索引，提交后同步更新）
> **原始出处**：`docs/workflow/HANDOFF.md` §4（13 项原清单） + `TASK_STATUS.md` 决策日志 2026-04-08 / 2026-04-09 条目（新增项出处）
>
> **最后更新**：2026-04-09（Phase 2.5 复审后）

---

## 总计 22 项

| 来源 | 数量 |
|------|------|
| HANDOFF §4 原清单有效项（14 - #12） | 13 |
| 2026-04-08 brainstorming 新增 | 4 |
| 2026-04-09 Phase 2.5 回顾/复审新增 | 3 |
| 2026-04-09 `/simplify` 复审新增 | 6 |
| 小计 | 26 |
| 2026-04-09 合并整理（见下） | −4 |
| **合计** | **22** |

**编号约定**：
- `#N` 来自 HANDOFF §4 原清单
- `新-N` 来自 2026-04-08 brainstorming
- `审-N` 来自 2026-04-09 phase-review 发现
- `简-N` 来自 2026-04-09 `/simplify` 复审发现
- 编号 #6 / #12 已移除（#6 描述错误并入 #1；#12 ComfyUIReceiver 继承问题在 M-10 后自然消失），保留编号避免混淆

**2026-04-09 合并整理记录**（保留原编号占位，正文指向合并后条目）：
- #2 + #13 → 合并为 **#2**（ModelLoader 策略 + 统一量化策略），#13 条目作为占位指向 #2
- #3 + #10 → 合并为 **#3**（项目级 config.toml + 合并 CLI 四套配置体系），#10 条目作为占位指向 #3
- #7 → 并入 **新-1**（VRAM 临界本属综合议题的子场景）
- 简-3 + 简-4 → 合并为 **简-3**（GUI 资源生命周期不完整），简-4 条目作为占位指向简-3
- 简-7 候选（`check relay` 内联 socket 探测）未独立成项，作为 bullet 写入 **新-1**

---

## 提交状态

| # | 状态 | GitHub issue 编号 | 提交日期 |
|---|------|------|------|
| 全部 20 项 | ⬜ 未提交 | — | — |

（提交后在此处填写 `gh-#N` 并更新 TASK_STATUS.md 决策日志）

---

## 清单总览

> **标题写法约定**：issue 标题使用自然语言描述问题本身，不加 `refactor(xxx):` 这类 conventional-commit 前缀；分类全部靠 labels 承载。优先级也由 label 承载（`priority-high/medium/low`），当前仓库 label 系统中可能尚未创建相应标签，批量提交时用 `gh label create` 一并补齐。

### 🔴 高优先级（5 项）

| # | 标题 | 标签 |
|---|------|------|
| #1 | CLI sender / batch_sender 子命令语义重叠，且单图模式每次调用都重新加载 VLM | refactor, cli, priority-high |
| #2 | DiffusersReceiver 模型加载缺乏抽象，Diffusers 与 QwenVL 量化策略不统一 | refactor, architecture, priority-high |
| #3 | 缺乏项目级配置持久化，CLI 四套配置体系并存 | feature, config, priority-high |
| 新-1 | 统一 socket 通信架构 + 批量 VRAM 临界 + 双端演示能力综合议题（**不预设方案**） | discussion, architecture, priority-high |
| 简-1 | 图像加载 / RGB 转换逻辑在 CLI、GUI、evaluation 三层散落 10+ 处 | refactor, dx, priority-high |

### 🟡 中优先级（8 项）

| # | 标题 | 标签 |
|---|------|------|
| #8 | ComfyUI 特有采样器配置未在 Diffusers 端对齐（AuraFlow shift=3、res_multistep） | enhancement, quality, priority-medium |
| #9 | HF 工具链下载层不稳定（xet CDN 超时），需替换为镜像直链或 modelscope | bug, network, priority-medium |
| #11 | `cli/download.py` 模型清单硬编码，目录布局与 Diffusers 运行时不一致 | refactor, cli, priority-medium |
| #14 | 输出路径管理无统一设计，5+ 默认路径散落且无清理策略 | enhancement, dx, priority-medium |
| 新-5 | GUI 缺少独立的"接收端监听" Tab，双机演示不便 | enhancement, gui, priority-medium |
| 审-1 | 4 篇文档仍含过时 ComfyUI 文案（`user-guide.md` / `project-overview.md` / `development-guide.md` / `gui-design.md`） | docs, priority-medium |
| 简-2 | `BaseReceiver.process_batch` 重复实现了 `pipeline/batch_processor` 的逐样本循环 | refactor, architecture, priority-medium |
| 简-3 | GUI 批量 / 队列流程资源生命周期不完整：异常路径显存未释放 + tmp PNG 累积 | bug, gui, vram, priority-medium |

### 🟢 低优先级（9 项）

| # | 标题 | 标签 |
|---|------|------|
| #4 | timeout 倍数需确认（M-02 遗留，原 issue #16） | enhancement, priority-low |
| #5 | 量化依赖按平台条件安装（M-02 遗留，原 issue #17） | enhancement, dependencies, priority-low |
| #15 | `LocalRelay` 是 dead code，无业务调用方 | cleanup, priority-low |
| 新-3 | `SocketRelaySender` 不支持指定源端口（防火墙场景） | enhancement, network, priority-low |
| 新-4 | `SocketRelayReceiver` 不做来源白名单过滤 | enhancement, security, priority-low |
| 审-2 | `evaluation` 模块 PSNR 在 identical 输入时 skimage 抛 `divide by zero` RuntimeWarning | bug, evaluation, priority-low |
| 审-3 | `test_diffusers_receiver.py::test_load_creates_pipeline` 在 Windows 下 subprocess reader 线程 UnicodeDecodeError | test, windows, priority-low |
| 简-5 | GUI `run_batch_process` 参数 sprawl（10 参数 + 多处重复 yield），PSNR/SSIM/LPIPS 格式化代码复制 3 处 | refactor, gui, priority-low |
| 简-6 | `SampleResult.status` 与 `DiffusersReceiverConfig.torch_dtype` 使用裸字符串而非枚举 | refactor, priority-low |

---

## 详细描述

> 每项仅记录与 `gh issue create` 文案最相关的信息。更详细的背景请回查 HANDOFF.md §4 / TASK_STATUS.md 决策日志。

### #1 — CLI 代码重复

`cli/sender.py`（单图）和 `cli/batch_sender.py`（批量）逻辑大量重复；`cli/batch_demo.py` 与 `cli/batch_sender.py` 也重复。`sender.py` 单图模式每次调用都重新加载 VLM（5 GB / ~30s），连续发送 10 张图需重载 10 次。

**方案**：合并两命令支持 `--image` / `--input-dir` 双模式，或废弃 `sender.py`。同时梳理 `batch_demo.py` 的复用关系。

### #2 — DiffusersReceiver 模型加载缺乏抽象，Diffusers 与 QwenVL 量化策略不统一

**合并自**：原 #2 + 原 #13（2026-04-09 合并整理）

两者是同一件事的一体两面：
- `DiffusersReceiver.load()` 写死 transformer / controlnet / pipeline 三段加载逻辑，更换量化格式（fp8/awq/gptq）需要改 `config.py` + `diffusers_receiver.py` + `tests` 三处。
- QwenVL 端有三层量化 fallback（bnb-4bit → bnb-8bit → fp16），Diffusers 端直接写死 GGUF Q8_0，缺乏统一的"量化后备策略"抽象。

ModelLoader 抽象的主要动机就是吸收不同模型的加载/量化差异，分开实施会导致方案冲突。

**方案**：引入 `ModelLoader` 策略抽象，统一 Diffusers 与 QwenVL 的加载入口和量化 fallback 机制。

### #3 — 缺乏项目级配置持久化，CLI 四套配置体系并存

**合并自**：原 #3 + 原 #10（2026-04-09 合并整理）

两者是同一件事的两面：
- 需要 `MODEL_CACHE_DIR` + `HF_HOME` + `HF_ENDPOINT` 三个环境变量，每次新 shell 手动 export，无项目级持久化。
- CLI 侧 ComfyUI 配置 / Diffusers 配置 / QwenVL 配置 / download 配置四套并存，无统一入口。四套并存的根因就是没有项目级配置承载。

**方案**：引入 `config.toml`（gitignored）+ `config.toml.example`（committed）+ `common/project_config.py` 加载层，兼容旧 env var fallback；同时以此为载体合并 CLI 四套配置体系。

### #4 — timeout 倍数需确认

M-02 遗留，详见原 workflow archive 的 issue #16。

### #5 — 量化依赖按平台条件安装

M-02 遗留，详见原 workflow archive 的 issue #17。

### #7 — 组合 3 VRAM 临界 → 已并入 **新-1**

2026-04-09 合并整理：`batch-demo --auto-prompt --backend diffusers` 在 24 GB 单卡上的 VRAM 临界问题，本质是新-1 综合议题的一个具体触发场景。完整描述和候选方案见新-1。

### #8 — ComfyUI 特有采样器配置未对齐

ComfyUI 原型使用 AuraFlow shift=3、res_multistep 等采样器配置，Diffusers 端尚未完全对齐。跨后端 PSNR/SSIM/LPIPS 对比不可比的主要原因。归档在 `docs/archive/comfyui-prototype/workflows/*.json` 可参考。

### #9 — HF 工具链下载层不稳定

HuggingFace xet CDN 在国内经常超时。当前靠 `HF_ENDPOINT=https://hf-mirror.com` 镜像站兜底，但仍有 intermittent failure。考虑替换为 modelscope 或直接镜像下载链接。

### #10 — CLI 配置体系四套并存 → 已合并入 **#3**

2026-04-09 合并整理：四套并存的根因是缺乏项目级配置承载，与 #3 的 `config.toml` 方案是同一件事，合并到 #3 统一处理。

### #11 — `cli/download.py` 硬编码

`cli/download.py` 的 `--comfyui-dir` 参数 + `models/{unet,controlnet,text_encoders,vae}/` 子目录布局还是 ComfyUI 约定，与 Diffusers 运行时使用的 HF cache + `$MODEL_CACHE_DIR/Z-Image-Turbo/*.gguf` 布局**完全不一致**。实际上已是 dead code（下载位置 receiver 不读），需要按新布局重构。

### #13 — 量化策略未统一 → 已合并入 **#2**

2026-04-09 合并整理：QwenVL 三层 fallback vs Diffusers 写死 GGUF 的量化差异，本质是 ModelLoader 抽象要吸收的差异，合并到 #2 统一处理。

### #14 — 输出路径管理无统一设计

`output/demo/` / `output/batch/` / `output/frames/` / `output/evaluation/` 等 5+ 默认路径散落在各 CLI / GUI 代码里，没有清理策略，demo 跑完会累积大量文件。

### #15 — `LocalRelay` 是 dead code

`common/relay.py` 中的 `LocalRelay` 类无任何业务调用方（发送端用 `SocketRelaySender`，单机 demo 不用 relay）。可安全删除。

### 新-1 — 统一 socket 通信架构 + VRAM 临界 + 双端演示综合议题

**这是下次 workflow 的核心开放议题**，issue 正文**只描述问题本身不预设方案**：
- 单机 24 GB 下 VLM + Diffusers 共存 VRAM 临界（吸收原 #7：`batch-demo --auto-prompt --backend diffusers` 在 24 GB 上 VLM 5 GB + Diffusers 18 GB ≈ 23 GB，激活值无空间触发 swap/OOM）
- 批量场景下模型生命周期（load/unload/复用）缺乏统一策略
- 双机部署演示能力（GUI 需独立的"接收端监听" Tab，见新-5）
- 当前通信架构（SocketRelay 单向 + 单机跨模块直接调用）不统一
- `cli/check.py` 的 `check relay` 子命令内联裸 socket 探测（`connect_ex`），未来 relay 协议若加握手/TLS/鉴权会谎报"可达"；正确归宿是在 `pipeline/relay` 提供 `probe(host, port, timeout)` API，供 CLI 和 GUI 共用（参考 `common/model_check.py` 模式）

**候选方案**（仅在 issue 正文里作为"历史讨论参考"列出，不作为决定）：
- 方案 A：Phase-Separated Batch（原 HANDOFF §5 种子）
- 方案 B：统一 socket 通信架构（单机/双机都走 SocketRelay）
- 方案 C：ModelStore / ModelLoader 抽象
- 方案 D：三者组合

**强约束**：下次 workflow 启动时必须**重新 brainstorm**，不复用本次结论。

### 新-3 — `SocketRelaySender` 不支持指定源端口

防火墙场景下需要固定源端口便于白名单放行。

### 新-4 — `SocketRelayReceiver` 不做来源白名单过滤

安全边界问题：接收端接受任意来源的连接。

### 新-5 — GUI 缺少独立"接收端监听" Tab

当前 GUI 的接收端 Tab 是基于队列的"人工触发生成"模式，没有独立的"监听 TCP 端口、收到即处理"的 daemon-like Tab。双机演示场景下需要补充。与新-1 相关但可独立讨论。

### 审-1 — 4 篇文档仍含过时 ComfyUI 文案

M-16 按"最小变更范围"原则只更新了入口/运行时相关文档（ROADMAP / cli-reference / demo-handbook / architecture / CLAUDE.md）。以下 4 篇故意未动，需作为独立的"文档整体刷新"议题处理：
- `docs/user-guide.md` — 部署说明含 ComfyUI 后端备选
- `docs/project-overview.md` — 阶段二描述含 ComfyUI 原型（作为历史陈述保留是准确的，但需与新架构描述对齐）
- `docs/development-guide.md` — 开发环境章节含 ComfyUI 部署
- `docs/gui-design.md` — 早期 GUI 设计备忘录含 ComfyUI backend radio 的界面描述

### 审-2 — PSNR 在 identical 输入时 skimage 抛 divide by zero 警告

**触发路径**：`skimage.metrics.simple_metrics.py:171` 的 `10 * log10(data_range² / err)`，当 `err=0`（两张图完全相同）时除零，NumPy 抛 RuntimeWarning。
**出现测试**：`test_evaluate_script.py::test_identical_images` / `test_evaluation.py::TestPSNR::test_identical_images_inf` + `test_pil_input` + `test_different_sizes` / `test_gui_batch_panel.py::TestComputeSampleMetrics::test_identical_images_high_psnr` + `test_lpips_included_when_model_passed`。
**本质**：测试场景是**我们主动测的**（期望 inf），功能正确，只是 skimage 内部没短路。
**方案**：在 `src/semantic_transmission/evaluation/` 中 PSNR 调用前 `np.errstate(divide="ignore"):` 或 identical 短路。

### 审-3 — Windows 下 subprocess reader 线程 UnicodeDecodeError

**触发路径**：`tests/test_diffusers_receiver.py::TestLoadUnload::test_load_creates_pipeline` 的 subprocess mock 场景，reader 线程用 UTF-8 解码 Windows 默认 GBK 输出（`0xb2`）→ `UnicodeDecodeError` → 被 pytest 捕获为 `PytestUnhandledThreadExceptionWarning`。
**影响**：测试本身 passed（mock 屏蔽了逻辑），只是清理阶段 reader 线程炸了。
**方案**：测试中 subprocess mock 传 `encoding="utf-8", errors="replace"`，或设 `PYTHONIOENCODING=utf-8`。

### 简-1 — 图像加载 / RGB 转换逻辑在 CLI、GUI、evaluation 三层散落 10+ 处

`Image.open(x).convert("RGB")` 及 `PIL | ndarray | Path` 分支判断在以下位置反复出现：`gui/batch_panel.py`、`gui/pipeline_panel.py`、`gui/receiver_panel.py`、`gui/sender_panel.py`、`gui/batch_sender_panel.py`、`cli/demo.py`、`cli/sender.py`、`cli/batch_sender.py`、`cli/batch_demo.py`；`evaluation/utils.py:21` 和 `receiver/diffusers_receiver.py::_load_condition_image` 已各自实现一份。

**方案**：把 `_load_condition_image` 上提到 `common/`（或与 `evaluation/utils` 合并），所有调用点统一引用。

### 简-2 — `BaseReceiver.process_batch` 重复实现了 `pipeline/batch_processor` 的逐样本循环

`receiver/base.py:53-79` 手写 try/except + timing + `SampleResult` 累积；而 `pipeline/batch_processor` 已封装同一模式，`base.py` 仅从中 import dataclass 使用，未复用其 per-sample runner。

**方案**：`BaseReceiver.process_batch` 委托给 `batch_processor` 的 per-sample runner，消除重复脚手架。

### 简-3 — GUI 批量 / 队列流程资源生命周期不完整

**合并自**：简-3 + 简-4（2026-04-09 合并整理）

同一层级（GUI 资源生命周期）的两个问题：
- **异常路径显存未释放**：`gui/batch_panel.py::run_batch_process` 中 `vlm_sender.unload()` 只在正常 fallthrough 时执行（~line 349）。外层循环 `break` 或未捕获异常时，VLM / LPIPS / receiver 均不释放，长会话 GUI 会累积 GPU 内存。
- **tmp PNG 文件累积**：`gui/receiver_panel.py::_persist_edge` 用 `NamedTemporaryFile(delete=False)` 持久化每次 `add_to_queue` / `append_external_item` 的边缘图，`clear_queue` / `unload_model` / 会话结束均不 unlink。

**方案**：用 try/finally 或 context manager 统一包裹批量流程的资源释放；在 state 里跟踪 tmp 文件路径，clear/unload 时清理。

### 简-4 — GUI 队列 tmp PNG 文件无清理 → 已合并入 **简-3**

2026-04-09 合并整理：同属 GUI 资源生命周期问题，合并到简-3 统一处理。

### 简-5 — GUI `run_batch_process` 参数 sprawl + 指标格式化代码复制

- `gui/batch_panel.py::run_batch_process` 10 个位置参数；早退路径重复 `yield log, results, overall_rows` ≥ 8 次。
- PSNR/SSIM/LPIPS 格式化（`f"{v:.2f} dB"` / `f"{v:.4f}"`）在 `batch_panel.py` 的 aggregate / sample render / Accordion title 三处复制。

**方案**：抽取 state dataclass 封装流式状态，把指标格式化提取为 helper。

### 简-6 — `SampleResult.status` 与 `torch_dtype` 使用裸字符串而非枚举

- `sample.status = "failed"` / `"success"` 字面量散落于 `receiver/base.py` 与 `gui/batch_panel.py`，`SampleResult.status` 无 enum 约束。
- `DiffusersReceiverConfig.torch_dtype: str` 通过模块级 `_TORCH_DTYPE_MAP` 映射到 `torch.dtype`。

**方案**：引入 `SampleStatus` 字符串枚举；`torch_dtype` 改为枚举或直接使用 `torch.dtype`。

---

## 提交动作

### 批量提交命令模板

```bash
# 仓库 label 系统中可能尚未创建优先级与分类标签，批量提交前先补齐：
gh label create priority-high --color d73a4a --force
gh label create priority-medium --color fbca04 --force
gh label create priority-low --color 0e8a16 --force
# ... 其他 label 按需 create

# 逐项提交（标题使用自然语言，不加 conventional-commit 前缀）：
gh issue create --title "CLI sender / batch_sender 子命令语义重叠，且单图模式每次调用都重新加载 VLM" --label "refactor,cli,priority-high" --body-file -
# ... 逐项

# 提交后：
# 1. 在本文件"提交状态"表中填入 gh-#N
# 2. 在 TASK_STATUS.md M-16 交接记录追加 issue 编号
# 3. 更新 memory/project_pending_issues.md（标记为已提交或删除）
```

### 提交后的去向

- **审-1（4 篇文档）**：如采纳为"文档刷新 workflow"种子，与新-1 合并讨论下次 workflow 范围
- **审-2 / 审-3 / 简-5 / 简-6**：低优先级清理，独立 PR 修复即可，不需要 workflow
- **简-1 / 简-2 / 简-3**：中-高优先级清理，可合并进相关重构 PR 或独立 PR
- **新-1 / 新-5**：作为下次 workflow 的启动议题（新-1 已吸收原 #7 与简-7 候选）
- **#2 / #3**（合并后）：属于下次重构 workflow 的主干议题，优先级 high
- **其余项**：按优先级单独处理或合并到相关重构 PR
