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

## 总计 20 项

| 来源 | 数量 |
|------|------|
| HANDOFF §4 原清单有效项（14 - #12） | 13 |
| 2026-04-08 brainstorming 新增 | 4 |
| 2026-04-09 Phase 2.5 回顾/复审新增 | 3 |
| **合计** | **20** |

**编号约定**：
- `#N` 来自 HANDOFF §4 原清单
- `新-N` 来自 2026-04-08 brainstorming
- `审-N` 来自 2026-04-09 phase-review 发现
- 编号 #6 / #12 已移除（#6 描述错误并入 #1；#12 ComfyUIReceiver 继承问题在 M-10 后自然消失），保留编号避免混淆

---

## 提交状态

| # | 状态 | GitHub issue 编号 | 提交日期 |
|---|------|------|------|
| 全部 20 项 | ⬜ 未提交 | — | — |

（提交后在此处填写 `gh-#N` 并更新 TASK_STATUS.md 决策日志）

---

## 清单总览

### 🔴 高优先级（6 项）

| # | 标题 | 标签 |
|---|------|------|
| #1 | CLI 代码重复：sender/batch_sender 语义不清 + 单图模式反复加载 VLM | refactor, cli, priority-high |
| #2 | DiffusersReceiver 模型加载缺乏抽象，需引入 ModelLoader 策略 | refactor, architecture, priority-high |
| #3 | 配置入口分裂：环境变量未持久化，需引入项目级 config.toml | feature, config, priority-high |
| #7 | 组合 3（auto-prompt + diffusers + 单机）VRAM 临界不可用 | bug, vram, architecture, priority-high |
| #10 | CLI 配置体系四套并存（ComfyUI / Diffusers / QwenVL / download） | refactor, config, priority-high |
| 新-1 | 统一 socket 通信架构 + 批量 VRAM 临界 + 双端演示能力综合问题（**不预设方案**） | discussion, architecture, priority-high |

### 🟡 中优先级（7 项）

| # | 标题 | 标签 |
|---|------|------|
| #8 | ComfyUI 特有采样器配置未在 Diffusers 端对齐（AuraFlow shift=3、res_multistep） | enhancement, quality, priority-medium |
| #9 | HF 工具链下载层不稳定（xet CDN 超时），需替换为镜像直链或 modelscope | bug, network, priority-medium |
| #11 | `cli/download.py` 模型清单硬编码 + 目录布局与 Diffusers 运行时不一致，需 ModelStore 抽象 | refactor, cli, priority-medium |
| #13 | 量化策略未统一：QwenVL 三层 fallback vs Diffusers 写死 GGUF | refactor, architecture, priority-medium |
| #14 | 输出路径管理无统一设计（5+ 默认路径，无清理策略） | enhancement, dx, priority-medium |
| 新-5 | GUI 缺少独立"接收端监听" Tab（与新-1 相关但可独立讨论） | enhancement, gui, priority-medium |
| 审-1 | 4 篇文档仍含过时 ComfyUI 文案（`user-guide.md` / `project-overview.md` / `development-guide.md` / `gui-design.md`） | docs, priority-medium |

### 🟢 低优先级（7 项）

| # | 标题 | 标签 |
|---|------|------|
| #4 | timeout 倍数需确认（M-02 遗留，原 issue #16） | enhancement, priority-low |
| #5 | 量化依赖按平台条件安装（M-02 遗留，原 issue #17） | enhancement, dependencies, priority-low |
| #15 | `LocalRelay` 是 dead code，无业务调用方 | cleanup, priority-low |
| 新-3 | `SocketRelaySender` 不支持指定源端口（防火墙场景） | enhancement, network, priority-low |
| 新-4 | `SocketRelayReceiver` 不做来源白名单过滤 | enhancement, security, priority-low |
| 审-2 | `evaluation` 模块 PSNR 计算在 identical 输入时 skimage 抛 `divide by zero` RuntimeWarning（本项目代码需用 `np.errstate` 或短路处理） | bug, evaluation, priority-low |
| 审-3 | `test_diffusers_receiver.py::test_load_creates_pipeline` 在 Windows 下 subprocess reader 线程 UnicodeDecodeError（测试 mock 未指定 `encoding="utf-8"`） | test, windows, priority-low |

---

## 详细描述

> 每项仅记录与 `gh issue create` 文案最相关的信息。更详细的背景请回查 HANDOFF.md §4 / TASK_STATUS.md 决策日志。

### #1 — CLI 代码重复

`cli/sender.py`（单图）和 `cli/batch_sender.py`（批量）逻辑大量重复；`cli/batch_demo.py` 与 `cli/batch_sender.py` 也重复。`sender.py` 单图模式每次调用都重新加载 VLM（5 GB / ~30s），连续发送 10 张图需重载 10 次。

**方案**：合并两命令支持 `--image` / `--input-dir` 双模式，或废弃 `sender.py`。同时梳理 `batch_demo.py` 的复用关系。

### #2 — DiffusersReceiver 模型加载缺乏抽象

`DiffusersReceiver.load()` 写死 transformer / controlnet / pipeline 三段加载逻辑。更换量化格式（fp8/awq/gptq）需要改 `config.py` + `diffusers_receiver.py` + `tests` 三处。需引入 `ModelLoader` 策略抽象。

### #3 — 配置入口分裂

需要 `MODEL_CACHE_DIR` + `HF_HOME` + `HF_ENDPOINT` 三个环境变量，每次新 shell 手动 export，无项目级持久化。方案：引入 `config.toml`（gitignored）+ `config.toml.example`（committed）+ `common/project_config.py` 加载层，兼容旧 env var fallback。

### #4 — timeout 倍数需确认

M-02 遗留，详见原 workflow archive 的 issue #16。

### #5 — 量化依赖按平台条件安装

M-02 遗留，详见原 workflow archive 的 issue #17。

### #7 — 组合 3 VRAM 临界

`batch-demo --auto-prompt --backend diffusers` 在 24 GB 单卡上 VLM 5 GB + Diffusers 18 GB ≈ 23 GB，激活值无空间，触发 swap 或 OOM。当前只能避开。方案候选：Phase-Separated Batch（两阶段循环，两模型不共存），但该方案已降级为**新-1** 的候选之一而非既定方案。

### #8 — ComfyUI 特有采样器配置未对齐

ComfyUI 原型使用 AuraFlow shift=3、res_multistep 等采样器配置，Diffusers 端尚未完全对齐。跨后端 PSNR/SSIM/LPIPS 对比不可比的主要原因。归档在 `docs/archive/comfyui-prototype/workflows/*.json` 可参考。

### #9 — HF 工具链下载层不稳定

HuggingFace xet CDN 在国内经常超时。当前靠 `HF_ENDPOINT=https://hf-mirror.com` 镜像站兜底，但仍有 intermittent failure。考虑替换为 modelscope 或直接镜像下载链接。

### #10 — CLI 配置体系四套并存

ComfyUI 配置 / Diffusers 配置 / QwenVL 配置 / download 配置四套并存，无统一入口。与 #3 相关但侧重点不同（#3 解决持久化，#10 解决集约化）。

### #11 — `cli/download.py` 硬编码

`cli/download.py` 的 `--comfyui-dir` 参数 + `models/{unet,controlnet,text_encoders,vae}/` 子目录布局还是 ComfyUI 约定，与 Diffusers 运行时使用的 HF cache + `$MODEL_CACHE_DIR/Z-Image-Turbo/*.gguf` 布局**完全不一致**。实际上已是 dead code（下载位置 receiver 不读），需要按新布局重构。与 #10 可合并考虑。

### #13 — 量化策略未统一

QwenVL 端有三层 fallback（bnb-4bit → bnb-8bit → fp16），Diffusers 端直接写死 GGUF Q8_0。缺乏统一的"量化后备策略"抽象。

### #14 — 输出路径管理无统一设计

`output/demo/` / `output/batch/` / `output/frames/` / `output/evaluation/` 等 5+ 默认路径散落在各 CLI / GUI 代码里，没有清理策略，demo 跑完会累积大量文件。

### #15 — `LocalRelay` 是 dead code

`common/relay.py` 中的 `LocalRelay` 类无任何业务调用方（发送端用 `SocketRelaySender`，单机 demo 不用 relay）。可安全删除。

### 新-1 — 统一 socket 通信架构 + VRAM 临界 + 双端演示综合议题

**这是下次 workflow 的核心开放议题**，issue 正文**只描述问题本身不预设方案**：
- 单机 24 GB 下 VLM + Diffusers 共存 VRAM 临界
- 批量场景下模型生命周期（load/unload/复用）缺乏统一策略
- 双机部署演示能力（GUI 需独立的"接收端监听" Tab，见新-5）
- 当前通信架构（SocketRelay 单向 + 单机跨模块直接调用）不统一

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

---

## 提交动作

### 批量提交命令模板

```bash
# 高优先级
gh issue create --title "CLI 代码重复：sender/batch_sender 语义不清，单图模式反复加载 VLM" --label "refactor,cli,priority-high" --body-file -
# ... 逐项

# 提交后：
# 1. 在本文件"提交状态"表中填入 gh-#N
# 2. 在 TASK_STATUS.md M-16 交接记录追加 issue 编号
# 3. 更新 memory/project_pending_issues.md（标记为已提交或删除）
```

### 提交后的去向

- **审-1（4 篇文档）**：如采纳为"文档刷新 workflow"种子，与新-1 合并讨论下次 workflow 范围
- **审-2 / 审-3**：低优先级 bug，独立 PR 修复即可，不需要 workflow
- **新-1 / 新-5**：作为下次 workflow 的启动议题
- **其余 15 项**：按优先级单独处理或合并到相关重构 PR
