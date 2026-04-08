# 会话交接简报 — receiver-decouple-comfyui workflow 收尾

> ## ⚠️ 本文件已过时（2026-04-08）
>
> 本文档写于 2026-04-07，基于 `10/11` 状态 + Strangler Fig 保留 ComfyUI 策略。**2026-04-08 brainstorming 已反转这些前提**：
> - 插入了 **Phase 2.5**（7 个新任务 M-10~M-16，全面清除 ComfyUI 运行时 + GUI 完善）
> - workflow 进度从 10/11 扩大到 **10/18**
> - 第 2 节 7 步收尾清单**不再有效**（第 1 步直接跳 M-09，跳过了 Phase 2.5）
> - 第 4 节 14 项 issue 清单扩展为 **17 项**（13 原 + 4 新，去除失效的 #12）
> - 第 5 节"下次 workflow 种子 = Phase-Separated Batch"**已降级**为开放 issue（新-1），下次 workflow 必须重新 brainstorm 不复用本种子
>
> **下次会话第一步改为**：
> 1. 读 `docs/workflow/TASK_STATUS.md` 了解当前进度（看任务状态表和最新决策日志）
> 2. 读 `docs/workflow/TASK_PLAN.md` 了解任务定义
> 3. 从当前第一个 ⬜ 待开始任务开始执行（首个是 **M-10**）
>
> **本文件留作历史参考**，特别是第 3 节（关键背景）和第 4 节（原 issue 清单）仍有参考价值。但**不要**按第 2 节的 7 步清单执行。
> 详细修正记录见 `TASK_STATUS.md` 决策日志 2026-04-08 条目。

---

## 0. TL;DR（已过时）

~~当前 `receiver-decouple-comfyui` workflow 已完成 10/11 任务（M-01 ~ M-09a 全部 ✅），剩 M-09 端到端验证待执行。下次会话**不要再 brainstorm 新设计**，按第 2 节 7 步清单走完即可收尾、提 PR、merge。~~

**当前实际状态**（2026-04-08 之后）：workflow 已扩大到 18 个任务。完成 10（M-01~M-08, M-09a），待开始 8（M-10~M-16 + M-09）。收尾路径变长：M-10 → M-11 → M-12 → M-13 → M-14 → M-15 → M-16 → `phase-review`（Phase 2.5）→ M-09 → `phase-review`（Phase 3）→ archive → PR → merge。

---

## 1. 当前状态快照（已更新至 2026-04-08）

- **分支**：`feature/receiver-decouple-comfyui`
- **最近提交**：（以 `git log` 为准，本文档不再自动更新 commit hash）
- **workflow 进度**：10/18（原 M-01~M-08, M-09a 已完成；新增 M-10~M-16 待开始；M-09 依赖全部新任务）
- **未提交文件**：`output/demo/{comparison,edge,prompt,restored}.{png,txt}` 4 个 untracked（M-09a 实测产物，**归属变更**：按本次 Plan Audit 修正，这 4 个文件在 M-09 任务内作为 commit 的一部分提交，不再单独处理）
- **运行环境变量**（跑 Phase 2.5 和 M-09 时需要）：
  ```bash
  export HF_HOME=D:/Downloads/Models/huggingface
  export MODEL_CACHE_DIR=D:/Downloads/Models
  ```

---

## 2. 7 步收尾执行清单（已过时，保留作历史参考）

> ⚠️ **本节清单已失效**。下次会话不要按这个清单执行。新的执行路径：按 TASK_PLAN.md 顺序执行 M-10 → M-11 → M-12 → M-13 → M-14 → M-15 → M-16 → phase-review（Phase 2.5）→ M-09 → phase-review（Phase 3）→ archive → PR → merge。
>
> 原 7 步清单（下面这些）仅用于理解 2026-04-07 时点的计划意图，**不要实际执行**。

### 步骤 1：跑 M-09 验证

```bash
/structured-workflow:task-exec M-09
```

M-09 定义见 `docs/workflow/TASK_PLAN.md`。验收：

- `uv run pytest` 211+ passed
- `uv run ruff check .` 通过
- `uv run ruff format --check .` 通过
- 实测推理 —— **仅测组合 1**（manual prompt + diffusers），命令与 M-09a 验证完全一致：

  ```bash
  uv run semantic-tx demo --image resources/test_images/canyon_jeep.jpg \
    --prompt "A jeep driving through a desert canyon" --seed 42 --backend diffusers
  ```

  预期：~64s/张，VRAM 峰值 < 20 GB，输出 `output/demo/restored.png` + `comparison.png`。

⚠️ **不要测组合 3**（auto-prompt + diffusers + 单机）：已知 VRAM 临界（VLM 5 GB + Diffusers 18 GB ≈ 23/24 GB），是 issue #7 的内容，属于下次 workflow 解决。

### 步骤 2：批量提交 14 项 issue

详见第 4 节。**建议方式**：用 `gh issue create` 命令逐项提交。可以一次性写一个 shell 脚本，也可以手动一项一项做（14 项，预计 15-20 分钟）。

### 步骤 3：M-09 commit 同时提交 output/demo/

`output/demo/*` 4 个文件就是 M-09a 实测产物，应在 M-09 验证 commit 里一并提交，让历史更完整。

### 步骤 4：phase-review

```
/structured-workflow:phase-review
```

确认 Phase 3 退出标准全部满足。

### 步骤 5：archive workflow

按 structured-workflow 标准 archive 流程：

- 把 `docs/workflow/` 下的活跃文件（`TASK_PLAN.md`、`TASK_STATUS.md`、`DEPENDENCY_MAP.md`、`HANDOFF.md` 等）移动到 `docs/workflow/archive/<timestamp>-receiver-decouple-comfyui/`
- **本文档（HANDOFF.md）随 archive 一起归档，不需要保留在 main 分支**

### 步骤 6：提 PR

```bash
gh pr create --title "feat(receiver): 接收端脱离 ComfyUI（receiver-decouple-comfyui workflow）" \
  --body "$(cat <<'EOF'
## 概述

完成 M-01 ~ M-09a + M-09，实现接收端脱离 ComfyUI 的目标。引入 DiffusersReceiver 作为新后端，与 ComfyUIReceiver 通过工厂函数并存（Strangler Fig 模式）。GUI/CLI 入口通过 --backend 参数切换后端。

## 关键变更

- 新增 DiffusersReceiver（GGUF Q8 量化 transformer + 分组件加载）
- 新增接收端工厂函数 create_receiver
- 批量帧处理（process_batch）
- GUI/CLI 适配后端切换
- M-09a 性能修复：从 34min/张 优化到 ~64s/张（提速 ~32 倍），VRAM < 20 GB

## 验证

- 211 tests passed
- ruff check + format --check 全绿
- 实测推理验证（manual prompt + diffusers 组合）

## 待办（已提为 issue）

本 workflow 范围聚焦"接收端脱离 ComfyUI"，下列遗留项已开 issue：
- #X CLI 代码重复
- #X 模型加载缺乏抽象
- #X 配置入口分裂
- ...（共 14 项，详见各 issue）
EOF
)"
```

PR body 中的 issue 编号待第 2 步完成后填入。

### 步骤 7：merge + 删分支

```bash
gh pr merge <number> --squash --delete-branch --admin
```

按项目约定，管理员合并自己的 PR 用 `--admin` 绕过 self-approve 限制。

---

## 3. 关键背景（must preserve across auto-compact）

1. **M-09a 已经验证可工作**：`semantic-tx demo --backend diffusers` + manual prompt 组合稳定，63.7s/张，VRAM < 20 GB，211 tests passed。
2. **本次 workflow 范围严格不包括**：Phase-Separated Batch、ModelStore/ModelLoader 抽象、config.toml 重构。这些是下次 workflow 的内容，已记录为 issue。
3. **不要在收尾会话再起 brainstorming**。brainstorming 已在前一会话做过，结论保存在本文档第 5 节和决策日志里。
4. **环境变量必须 export 才能跑 M-09 实测**（HF_HOME + MODEL_CACHE_DIR）。
5. **GitHub CLI 操作**遵循项目 CLAUDE.md 约定：管理员合并自己的 PR 用 `--admin`。

---

## 4. 14 项待提交 issue 清单（2026-04-08 更新为 17 项）

> **2026-04-08 更新**：本清单仍然有效作为 M-16 批量提 issue 的参考，但有调整：
> - 原 14 项中的 **#12 "ComfyUIReceiver 不继承 BaseReceiver"** 在 M-10 后自然消失（ComfyUIReceiver 已删），**不再提交**。实际有效为 13 项
> - **新增 4 项** issue 来自 2026-04-08 brainstorming：
>   - **新-1**：统一 socket 通信架构 + 批量 VRAM 临界 + 双端演示能力综合问题（**高优先级**，描述问题本身不预设解决方案，是下次 workflow 的开放议题）
>   - **新-3**：`SocketRelaySender` 不支持指定源端口（低）
>   - **新-4**：`SocketRelayReceiver` 不做来源白名单过滤（低）
>   - **新-5**：GUI 缺少独立"接收端监听" Tab（中，与新-1 相关但可独立讨论）
> - **合计 17 项**由 M-16 批量提交（而非原计划的 14 项）
>
> 编号 #6 已删除（原"sender 缺少 batch 模式"描述错误，并入 #1），编号保留避免混淆。

### 概览

| # | 标题 | 优先级 | 来源 |
|---|------|------|------|
| 1 | CLI 代码重复（含 sender.py vs batch_sender.py 语义不清）| 高 | M-1A D4 + brainstorming 修订 |
| 2 | DiffusersReceiver 模型加载缺乏抽象 | 高 | M-09a 会话 |
| 3 | 配置入口分裂（4 套配置体系并存）| 高 | M-09a 会话 |
| 4 | timeout 倍数需确认 | 低 | M-02 遗留（issue #16）|
| 5 | 量化依赖按平台条件安装 | 低 | M-02 遗留（issue #17）|
| 7 | 组合 3（auto-prompt + diffusers + 单机）VRAM 临界 | 高 | brainstorming |
| 8 | ComfyUI 特有采样器配置未对齐 | 中 | M-09a 会话 |
| 9 | HF 工具链下载层不稳定（xet CDN 超时）| 中 | brainstorming |
| 10 | CLI 配置体系四套并存 | 高 | brainstorming |
| 11 | cli/download.py 模型清单硬编码 | 中 | brainstorming |
| 12 | ComfyUIReceiver 不继承 BaseReceiver（leaky abstraction）| 低 | M-03 留下 |
| 13 | 量化策略未统一 | 中 | brainstorming |
| 14 | 输出路径管理无统一设计 | 中 | brainstorming |
| 15 | LocalRelay 是 dead code | 低 | brainstorming |

### 详细描述

#### #1 — CLI 代码重复（含 sender.py vs batch_sender.py 语义不清）

**背景**：项目里有 `cli/sender.py`（单图）和 `cli/batch_sender.py`（批量）两个发送端 CLI，逻辑大量重复。`cli/batch_demo.py` 和 `cli/batch_sender.py` 也有重复。`sender.py` 单图模式每次调用都重新加载 VLM（5 GB，~30s），用户连续发送 10 张图就要重载 10 次。

**建议方案**：
- 选项 a：合并 `sender.py` 和 `batch_sender.py`，让 sender 一个命令支持单图（`--image`）和批量（`--input-dir`）两种模式
- 选项 b：废弃 `sender.py`，让 `batch_sender.py` 成为唯一发送端（包括单图场景）
- 同时考虑 `batch_demo.py` 与 `batch_sender.py` 的复用关系

**优先级**：高（影响双机演示用户体验）

```bash
gh issue create --title "CLI 代码重复：sender/batch_sender 语义不清，单图模式反复加载 VLM" \
  --label "refactor,cli,priority-high"
```

#### #2 — DiffusersReceiver 模型加载缺乏抽象

**背景**：当前 `DiffusersReceiver.load()` 直接写死了 transformer / controlnet / pipeline 三段加载逻辑（GGUF + safetensors + from_pretrained）。更换模型格式（如 fp8 / awq / gptq）或加载方式需要同时修改 `config.py`、`diffusers_receiver.py`、`tests` 三处。

**建议方案**：引入 `ModelLoader` 策略抽象，使 Receiver 与具体加载方式解耦。每种格式一个 loader（GGUFLoader / SafetensorsLoader / HFLoader），Receiver 通过接口组合。

**优先级**：高（影响后续模型迭代成本）

```bash
gh issue create --title "DiffusersReceiver 模型加载缺乏抽象，需引入 ModelLoader 策略模式" \
  --label "refactor,architecture,priority-high"
```

#### #3 — 配置入口分裂（环境变量持久化痛点）

**背景**：DiffusersReceiver 运行需要 `MODEL_CACHE_DIR` + `HF_HOME` + `HF_ENDPOINT` 三个环境变量，每次新 shell 都要手动 export，且没有项目级配置文件持久化。新协作者上手痛点高。

**建议方案**：
- 引入项目级 `config.toml`（gitignored）+ `config.toml.example`（committed）
- 加载层：`common/project_config.py` 工具函数读取 toml + 解析相对路径
- 兼容旧 env var fallback

**优先级**：高

```bash
gh issue create --title "配置入口分裂：环境变量未持久化，需引入项目级 config.toml" \
  --label "feature,config,priority-high"
```

#### #4 — timeout 倍数需确认（M-02 遗留）

来自 M-02 任务遗留，详见原 workflow archive 中的 issue #16。

#### #5 — 量化依赖按平台条件安装（M-02 遗留）

来自 M-02 任务遗留，详见原 workflow archive 中的 issue #17。

#### #7 — 组合 3（auto-prompt + diffusers + 单机）VRAM 临界

**背景**：`batch-demo --auto-prompt --backend diffusers` 在 24 GB 单卡上 VRAM 占用接近上限（VLM 5 GB + Diffusers 18 GB ≈ 23 GB），激活值无空间，会触发 swap 或 OOM。当前只能避开这个组合（用 manual prompt 或 ComfyUI 后端）。

**建议方案**：实现 **Phase-Separated Batch** 模式 —— 把循环重构为两阶段：Phase 1 加载 VLM 跑完所有 prompts → unload → Phase 2 加载 Receiver 跑完所有还原。两个模型永不共存于显存，峰值降到 18 GB。这是下次 workflow 的核心方向，详见本文档第 5 节。

**优先级**：高（auto-prompt 单机当前不可用）

```bash
gh issue create --title "组合 3 VRAM 临界：auto-prompt + diffusers + 单机不可用，需 Phase-Separated Batch" \
  --label "bug,vram,architecture,priority-high"
```

#### #8 — ComfyUI 特有采样器配置未对齐

**背景**：ComfyUI 的 Z-Image-Turbo 工作流使用了 AuraFlow shift=3、res_multistep sampler 等特殊配置，但 DiffusersReceiver 当前用的是 diffusers 默认采样器。M-09 验证可能发现两个后端生成质量有差异。

**建议方案**：对齐 diffusers pipeline 的 scheduler 配置，或文档化差异。M-09 验证完成后根据实际质量对比决定。

**优先级**：中

```bash
gh issue create --title "ComfyUI 特有采样器配置未在 diffusers 端对齐（AuraFlow shift=3、res_multistep）" \
  --label "quality,parity,priority-medium"
```

#### #9 — HF 工具链下载层不稳定

**背景**：HuggingFace 的 xet CDN（cas-bridge.xethub.hf.co）国内访问极不稳定，即使配置 `HF_ENDPOINT=hf-mirror.com` 也只能加速 metadata 请求，实际下载仍走 xet CDN。本次 workflow 中开发者花一整天才下载完模型。

**建议方案**：
- 选项 a：用 modelscope 镜像替代（已在 `cli/download.py` 部分使用）
- 选项 b：直接用 hf-mirror.com 的镜像 URL 通过 curl/wget 下载
- 选项 c：项目内提供下载脚本封装这些细节

**注意**：此问题仅影响"下载层"，不影响"运行时加载层"（`from_pretrained` 读本地缓存完全无问题）。

**优先级**：中

```bash
gh issue create --title "HF 工具链下载层不稳定（xet CDN 超时），需替换为镜像直链或 modelscope" \
  --label "bug,network,priority-medium"
```

#### #10 — CLI 配置体系四套并存

**背景**：项目里 4 个独立的"模型相关"配置体系互不通气：

- `ComfyUIConfig`（host/port，COMFYUI_HOST/PORT 环境变量）
- `DiffusersReceiverConfig`（dataclass + MODEL_CACHE_DIR 环境变量）
- `QwenVLSender`（构造函数参数 + get_default_vlm_path() + MODEL_CACHE_DIR）
- `cli/download.py`（argparse + COMFYUI_DIR + MODEL_CACHE_DIR + HF_ENDPOINT + HTTPS_PROXY）

每套用了不同的 env var 命名空间和不同的默认值策略。

**建议方案**：与 #3 配套解决，统一到 config.toml + 单一加载机制。

**优先级**：高

```bash
gh issue create --title "CLI 配置体系四套并存（ComfyUI/Diffusers/QwenVL/download），需统一" \
  --label "refactor,config,priority-high"
```

#### #11 — cli/download.py 模型清单硬编码

**背景**：`cli/download.py` 中模型清单（COMFYUI_MODELS、HF_REPO_MODELS）写死在文件顶部。每次加新模型都要改这里 + 改运行时使用模型的代码两处。

**建议方案**：把模型清单移到 config.toml 或独立的 `models.toml`，作为单一信息源（"ModelStore" 概念的一部分）。

**优先级**：中

```bash
gh issue create --title "cli/download.py 模型清单硬编码，需 ModelStore 抽象" \
  --label "refactor,priority-medium"
```

#### #12 — ComfyUIReceiver 不继承 BaseReceiver

**背景**：M-03 设计 BaseReceiver 时，ComfyUIReceiver 没法干净地继承（因为它的"加载"是 HTTP 调用而非本地模型），所以工厂函数返回类型用 `# type: ignore` 标注绕过。这是个 leaky abstraction。

**建议方案**：要么让 ComfyUIReceiver 继承 BaseReceiver（接受 dummy load/unload），要么把工厂函数返回类型改为 Protocol。低优先级，不影响功能。

**优先级**：低

```bash
gh issue create --title "ComfyUIReceiver 不继承 BaseReceiver，工厂函数有 # type: ignore" \
  --label "refactor,types,priority-low"
```

#### #13 — 量化策略未统一

**背景**：QwenVLSender 用三层 fallback（torchao INT4 → bitsandbytes 4bit → fp16），DiffusersReceiver 直接写死 GGUF Q8。两个组件的量化选择逻辑完全独立，加新量化方式（如 fp8、awq）要散弹枪修改。

**建议方案**：与 #2 配套，引入统一的 QuantizationConfig + 选择策略。

**优先级**：中

```bash
gh issue create --title "量化策略未统一：QwenVL 三层 fallback vs Diffusers 写死 GGUF" \
  --label "refactor,architecture,priority-medium"
```

#### #14 — 输出路径管理无统一设计

**背景**：项目里有 5+ 个不同的默认输出路径（`output/demo`、`output/batch-demo`、`output/sender`、`output/received`、`output/`），没有清理策略、没有集中配置、没有大小上限。`.gitignore` 里有 `!output/demo/` 例外但理由不明显。

**建议方案**：
- 集中输出路径配置到 config.toml
- 加 size limit 或 cleanup 策略
- 文档化哪些产物入版本管理、哪些是临时

**优先级**：中

```bash
gh issue create --title "输出路径管理无统一设计：5+ 默认路径，无清理策略" \
  --label "refactor,housekeeping,priority-medium"
```

#### #15 — LocalRelay 是 dead code

**背景**：`pipeline/relay.py` 中的 `LocalRelay`（基于 `queue.Queue` 的内存中继）没有任何业务代码使用，只有 `tests/test_relay.py` 覆盖。它是当年规划的"单机调试用"抽象，但实际开发中所有单机调试都直接用了 batch_demo 的内联循环。

**建议方案**：
- 选项 a：删除 LocalRelay 和相关测试
- 选项 b：把 batch_demo 内部的内存循环包装成 LocalRelay 用法（保持抽象一致性）
- 选项 c：保留备用，文档化"未来可能用于流式批处理"

**优先级**：低

```bash
gh issue create --title "LocalRelay 是 dead code，无业务调用方" \
  --label "refactor,cleanup,priority-low"
```

---

## 5. 下次 workflow 的种子（已降级为开放 issue，2026-04-08）

> ## ⚠️ 本节已被 2026-04-08 决策覆盖
>
> 原本节把 "模型加载架构与 Phase-Separated Batch" 作为下次 workflow 的**预定方向**，并包含了具体的设计选择（β4 目录即队列、γ3 batch_summary.json、CLI 策略 β 等）。
>
> **2026-04-08 brainstorming 中发现**：
> 1. Phase-Separated Batch 只是解决"单机 VRAM 临界 + 批量模型生命周期"的**候选方案之一**
> 2. 用户新提出的"**统一 socket 通信架构**"是另一个候选方案（单机 / 双机都走 SocketRelay 本地回环 / 对端地址），且和 GUI 双端传输、接收端监听 Tab 问题有**强交叉**
> 3. **ModelStore / ModelLoader 抽象** 是第三个候选方案（独立路线 S）
> 4. 这些候选方案各有优劣，不应预设方向
>
> **新决策**：
> - 本节原种子（Phase-Separated Batch + 目录即队列 + γ3 状态跟踪）**降级**为"可参考的先前讨论记录"，不作为下次 workflow 的预定方向
> - 这些问题全部归并到**新-1 issue**（"统一 socket 通信架构 + 批量 VRAM 临界 + 双端演示能力综合问题"），issue 正文描述**问题本身**，不预设解决方案
> - 下次 workflow 启动时**必须重新 brainstorm**，不直接复用本节结论
>
> 本节内容保留为历史参考（见下文原始内容），但**不是行动指引**。

### 标题候选

「**模型加载架构与 Phase-Separated Batch**」 或 「**model-loading-and-batching-redesign**」

### 核心洞察

把"批量端到端处理"从单循环 monolithic 重构为**严格串行的两阶段**：

```
Phase 1（发送端工作负载）              Phase 2（接收端工作负载）
─────────────────────────────         ─────────────────────────────
load VLM (~5 GB)                       load Receiver (~18 GB)
for image in input_images:             for sample_dir in batch_dir/*-*/:
  edge = canny(image)                    edge = read(sample_dir/edge.png)
  prompt = vlm.describe(image)           prompt = read(sample_dir/prompt.txt)
  save(sample_dir/edge.png + prompt.txt) restored = receiver.process(edge, prompt)
unload VLM                               save restored.png
                                       unload Receiver

GPU peak: ~5 GB                        GPU peak: ~18 GB
两个模型永不共存于显存
```

### 关键设计选择（已与用户确认的方向）

- **中间介质 = 现有目录结构**（β4 方案，目录即队列），不引入 jsonl 或新临时文件
- **半成品状态跟踪 = 扩展 batch_summary.json**（γ3 方案），不引入新文件类型
- **TransmissionPacket 不动**：它继续服务"双机实时流式 socket"场景，与本设计正交
- **CLI 策略 β**：现有 demo / batch-demo 内部改用阶段分离，新增 prepare-prompts / process-prompts 作为底层 primitive
- **范围排除**：ModelStore/ModelLoader 抽象（独立后续 workflow，路线 S 自下而上）

### 同时解决的问题

- ✅ 组合 3 的 VRAM 矛盾（issue #7）
- ✅ auto-prompt 单机可用性
- ✅ "目录即队列" 自然支持双机离线部署（tar 物理拷贝）
- ✅ 接收端独立调试（同一份 prompts 喂不同 receiver 后端做对比）
- ✅ 数据集复用（跑过 VLM 的目录可重复 replay）

### 不在种子范围

- ModelStore/ModelLoader 抽象（路线 S 自下而上）
- 真实流式接收（违背 VRAM 隔离收益）
- 重写 sender CLI（属于 issue #1）
- config.toml 重构（属于 issue #3，可与下次 workflow 合并或独立）

### 下次启动方式

下次启动新 workflow 时：

1. 读本文档第 5 节 + 已提交的 issues（特别是 #2/#3/#7/#10/#13）
2. **重新 brainstorm 完整设计**（本次未写完整 spec，避免 stale）
3. 用 `workflow-init` 初始化新 workflow
4. **不要直接复用本节内容作为 spec** —— 这只是种子，下次 brainstorm 时可能会调整方向

---

## 6. 自我清理

本文档（HANDOFF.md）生命周期结束于 archive 步骤。archive 时把整个 `docs/workflow/` 下的活跃文件（包括本文档）移动到 archive 子目录，HANDOFF.md 不需要保留在 main 分支。
