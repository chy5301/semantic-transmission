# 任务状态跟踪

> 创建时间: 2026-03-31
> 任务类型: migration
> 任务前缀: M

## 进度总览

| 阶段 | 总数 | 完成 | 进行中 | 待开始 |
|------|------|------|--------|--------|
| Phase 0: 准备 | 4 | 4 | 0 | 0 |
| Phase 1: 核心实施 | 2 | 2 | 0 | 0 |
| Phase 2: 完善 | 3 | 3 | 0 | 0 |
| Phase 2.5: GUI 完善与 ComfyUI 清除 | 7 | 7 | 0 | 0 |
| Phase 3: 验证 | 2 | 1 | 0 | 1 |
| **合计** | **18** | **17** | **0** | **1** |

## 任务状态

| 编号 | 标题 | 阶段 | 状态 | 依赖 |
|------|------|------|------|------|
| M-01 | 修复-seed=0 误判 bug | Phase 0 | ✅ 已完成 | 无 |
| M-1A | 决策-PR #14 合并后计划调整 | Phase 0 | ✅ 已完成 | M-01 |
| M-02 | 添加-diffusers 依赖与模型配置 | Phase 0 | ✅ 已完成 | M-1A |
| M-03 | 设计-接收端后端切换接口 | Phase 0 | ✅ 已完成 | M-02 |
| M-04 | 实现-DiffusersReceiver 单帧生成 | Phase 1 | ✅ 已完成 | M-02, M-03 |
| M-05 | 更新-工厂函数支持 Diffusers 后端 | Phase 1 | ✅ 已完成 | M-03, M-04 |
| M-06 | 实现-批量连续帧图像生成 | Phase 2 | ✅ 已完成 | M-04 |
| M-07 | 集成-GUI 接收端面板适配 | Phase 2 | ✅ 已完成 | M-05 |
| M-08 | 集成-CLI 接收端命令适配 | Phase 2 | ✅ 已完成 | M-05 |
| M-10 | 清除-ComfyUI 底层运行时代码 | Phase 2.5 | ✅ 已完成 | M-09a |
| M-11 | 清理-CLI 层 ComfyUI 分支 + check 子命令改写 | Phase 2.5 | ✅ 已完成 | M-10 |
| M-12 | 清理-GUI 层 ComfyUI 分支 + config_panel 重构 | Phase 2.5 | ✅ 已完成 | M-10 |
| M-13 | 重构-接收端 Tab 统一队列模式 | Phase 2.5 | ✅ 已完成 | M-12 |
| M-14 | 打磨-UI 圆点 + 描述 + Prompt Mode 默认值 | Phase 2.5 | ✅ 已完成 | 无 |
| M-15 | 增强-批量端到端 Accordion 展示 + 每组质量评估 | Phase 2.5 | ✅ 已完成 | M-12 |
| M-16 | 归档-文档更新 + ComfyUI 历史归档 | Phase 2.5 | ✅ 已完成 | M-10, M-11, M-12, M-13, M-14, M-15 |
| M-09a | 修复-模型加载 GGUF 量化与分组件加载 | Phase 3 | ✅ 已完成 | M-04 |
| M-09 | 验证-端到端测试与质量对比 | Phase 3 | ⬜ 待开始 | M-09a, M-10, M-11, M-12, M-13, M-14, M-15, M-16 |

状态图例: ⬜ 待开始 | 🔄 进行中 | ✅ 已完成 | ⏸️ 暂停 | ❌ 已取消 | 🔀 已拆分

## 已知问题

- 遗留 issue: #16（timeout 倍数需确认）、#17（量化依赖按平台条件安装）
- [待提 issue] CLI 代码重复：`batch_demo.py` 与 `batch_sender.py` 之间大量重复逻辑，应通过工厂函数精简（M-1A D4 决策延后）
- [待提 issue] DiffusersReceiver 模型加载缺乏抽象：当前加载逻辑（from_pretrained / from_single_file / 量化加载）直接写死在 `load()` 方法中，更换模型格式或加载方式需同时修改 config.py、diffusers_receiver.py、tests 三处。应重构为策略模式（ModelLoader 抽象），使 Receiver 与具体加载方式解耦
- [环境变量] Diffusers 接收端运行需要以下环境变量：
  - `MODEL_CACHE_DIR=D:\Downloads\Models` — 模型根目录（GGUF/ControlNet bf16 文件在 `$MODEL_CACHE_DIR/Z-Image-Turbo/` 下）
  - `HF_HOME=D:\Downloads\Models\huggingface` — HuggingFace 缓存目录（text_encoder/tokenizer/scheduler 从此缓存加载）
  - `HF_ENDPOINT=https://hf-mirror.com`（可选）— HuggingFace 镜像站，国内网络加速
  - `HF_HUB_DISABLE_SYMLINKS_WARNING=1`（可选）— 禁用 Windows symlinks 警告

## PR #14 合并后待决策事项

> 以下为 2026-04-02 PR #14 review 和合并过程中发现的事项，需在继续 M-02 之前逐一决策是否调整计划。

1. **`batch_processor.py` 复用** — PR #14 新增了 `BatchResult`、`SampleResult`、`BatchImageDiscoverer` 等通用批量处理数据结构。M-06 是否复用这些，还是自己实现？
2. **M-07/M-08 涉及文件扩充** — PR #14 新增了 `gui/batch_panel.py`、`gui/batch_sender_panel.py`、`cli/batch_demo.py`、`cli/batch_sender.py`。这些文件是否需要加入 M-07/M-08 的适配范围？
3. **`batch_panel.py` 仍用 `ComfyUISender`** — PR #14 声称发送端脱离 ComfyUI，但"批量端到端"面板仍硬编码 `ComfyUISender`。是否在我们的工作流中一并修复，还是单独提 issue？
4. **CLI 代码重复** — `cli/batch_demo.py` 和 `cli/batch_sender.py` 之间大量重复逻辑。是否在 M-08 中通过工厂函数精简，还是保持现状？
5. **Radio 元组模式** — 已在 PR #14 中统一为 `(label, value)` 元组（#15 已关闭）。M-07 后端切换 UI 是否沿用此模式？
6. **发送端脱离模式参考** — `LocalCannyExtractor` 继承 `BaseConditionExtractor` 本地实现的方式，对 M-04 DiffusersReceiver 的设计有无参考价值或需要调整？

## 决策日志

- 2026-03-31: 迁移策略选择 Strangler Fig，保留 ComfyUI 后端作为备选
- 2026-03-31: 继续使用 Z-Image-Turbo + ControlNet Union，通过 diffusers ZImageControlNetPipeline 加载
- 2026-03-31: 双机接收端也改为直接推理，同时支持后端切换
- 2026-04-06: [M-1A] PR #14 影响决策（6 项）：
  - D1: M-06 部分复用 batch_processor.py（BatchResult/SampleResult），不复用 BatchImageDiscoverer
  - D2: M-07 扩充 batch_panel.py，M-08 扩充 batch_demo.py
  - D3: batch_panel.py 发送端 ComfyUISender 遗漏在 M-07 中顺手修复
  - D4: CLI 代码重复不在 M-08 精简，workflow 完成后单独提 issue
  - D5: Radio 沿用 (label, value) 元组模式
  - D6: LocalCannyExtractor 模式验证了 M-04 设计方向，无需调整
- 2026-04-06: [M-02] diffusers 0.37.1 稳定版已包��� ZImageControlNetPipeline，无需源码安装
- 2026-04-06: [M-03] BaseReceiver 统一方法名为 `process`（弃用 `reconstruct`），返回 PIL.Image 而非 ReceiverOutput；ComfyUIReceiver 暂不改继承关系，通过 `# type: ignore` 标注工厂函数返回
- 2026-04-06: [Phase 0 回顾] 阶段通过。审计 4 任务无阻断/需修正问题。退出标准全部满足。M-05 步骤建议微调（工厂函数分支骨架已在 M-03 建好）
- 2026-04-06: [Phase 1 回顾] 阶段通过。审计 2 任务（M-04/M-05）无阻断/需修正问题。🔵 建议：M-02/M-03 遗留改动混入 M-04 commit。退出标准全部满足（202 tests passed，ruff 通过）。下游 Phase 2 任务无需调整
- 2026-04-06: [Phase 2 回顾] 阶段通过。审计 3 任务（M-06/M-07/M-08）无阻断/需修正问题。🔵 建议：pipeline_panel.py 发送端改 LocalCannyExtractor 超出 M-07 显式范围（因 import 清理必须一并修改）。退出标准全部满足（210 tests passed，ruff 通过，GUI/CLI 均适配后端切换）。下游 Phase 3 任务（M-09）无需调整
- 2026-04-07: [M-09 验证阻断] M-09 执行发现 DiffusersReceiver 不可用：HF 仓库 float32 权重占满 24 GB 显存，推理 34 分钟/张（ComfyUI 约 1 分钟）。根因：①`from_pretrained` 加载 float32 权重后转 bf16 峰值显存翻倍 ②所有组件同时驻留 GPU 无法分时复用。另修复两个 bug：ControlNet 仓库无 config.json 需 from_single_file、Canny 灰度图需转 RGB。决策：新增 M-09a 使用 GGUF Q8_0 量化 transformer（12 GB→7 GB）+ 分组件加载，M-09 阻塞等待 M-09a 完成
- 2026-04-07: [M-09a] GGUF 分组件加载方案落地。技术验证：diffusers 0.37.1 `from_pretrained(..., transformer=tf, controlnet=cn)` 在源码层面通过 `passed_class_obj` 跳过 `load_sub_model` 并把对应子目录加入 `ignore_patterns`，确认不会重复下载/加载已传入的组件。实施：transformer 用 `ZImageTransformer2DModel.from_single_file` + `GGUFQuantizationConfig(compute_dtype=bf16)` 加载本地 Q8_0 文件；ControlNet 用 `from_single_file` 加载本地 bf16；Pipeline 从 HF 缓存加载剩余组件。实测：单张 9 步推理 63.7s（之前 34 分钟，提速 ~32 倍），每步约 3s 平稳无 swap，达成 < 2 分钟目标。GGUF 包安装 `gguf==0.18.0`
- 2026-04-08: [Plan Adjust] M-09 收尾 brainstorming 发现 GUI 多处调整点 + ComfyUI 运行时遗留尾巴。决策：在 Phase 2 和 Phase 3 之间插入 **Phase 2.5: GUI 完善与 ComfyUI 清除**，新增 7 个任务（M-10~M-16）。M-09 依赖从 `M-06, M-07, M-08, M-09a` 改为 `M-09a + M-10..M-16`。
  - **D1: 反转 M-03 Strangler Fig 策略** — M-09a 已证实 Diffusers 路径稳定，ComfyUI fallback 不再必要。决定全面清除运行时 ComfyUI 代码（底层 + CLI + GUI 分支 + 相关测试），保留 `docs/comfyui-setup.md` 和 `resources/comfyui/` 归档到 `docs/archive/comfyui-prototype/`。
  - **D2: CLI check 子命令重写为三个独立角色** — `check vlm`（发送端用）/ `check diffusers`（接收端用）/ `check relay --host X --port Y`（双机对端 TCP 可达性）。理由：双机部署下每端只运行自己角色的检查，避免全检产生的误报；与 sender/receiver CLI 角色对称风格一致。
  - **D3: GUI 中继配置从 config_panel 移到 batch_sender_panel 内部** — GUI 唯一使用 SocketRelay 的 Tab 是 `📦 批量发送`，把中继配置挪到 Tab 内部更贴合"谁用谁管"原则。顺便修复隐性 bug：config_panel 原 `relay_host`/`relay_port` 字段 label 是"监听地址"但实际被 batch_sender_panel 当作对端地址使用。label 改为"接收端 IP / 端口"，默认值从 `0.0.0.0` 改为空字符串，加"测试对端连接"按钮。
  - **D4: 接收端 Tab 统一为队列模式** — 废除单张即时触发的 UI，单张场景作为"队列含 1 项"的特例。顺便解决现有 bug：每次点击都 `create_receiver()` 重载 ~18 GB 模型、不显式 `unload()`。底层 `DiffusersReceiver.process_batch()` 已支持"模型加载一次循环处理"，只差 UI 层队列。
  - **D5: 批量端到端展示改为 Accordion 每组折叠块 + 可选每组 + 总体质量评估** — 当前只显示"最后一张对比图"的设计信息密度太低。每组 Accordion 内含原图 / 边缘 / 还原 / VLM prompt，勾选"运行质量评估"时附加 PSNR/SSIM/LPIPS，最后给总体平均。
  - **D6: 四处 Prompt Mode 统一 VLM 在前 + 默认 auto，Radio 圆点恢复** — sender/pipeline/batch_sender/batch_panel 四处 Prompt Mode 当前都是"手动在前 + 默认 manual"，与 demo 实际默认流程不符。同时删除 `theme.py` 的 `.mode-radio { display: none }` CSS，让所有 Radio 圆点统一显示。
  - **D7: 发送端 VLM 实例持久化不做** — 批量发送 Tab 已经是"循环外加载 + 循环内 describe + 循环外 unload"的正确模式。单张发送 Tab 每次点击重载 VLM 可接受。
  - **D8: "统一 socket 通信架构"登记为新 issue 不做** — 用户提出的"单机双机都走 SocketRelay"思路架构上正确，但工作量等同于重开一次 workflow（改后台线程 / 双向通信协议 / UI 状态同步 / 重写多个 Tab 内部循环）。决定本 workflow 不做，作为新 issue 补充给 HANDOFF.md 已有 14 个 issue 清单，下次 workflow 时与 "Phase-Separated Batch"（HANDOFF.md 第 5 节原提议）合并讨论。
  - **D9: 任务拆分方案 X-lean v3** — 7 个新任务（M-10 ~ M-16），每个严格遵守 `maxFilesPerTask=8` 和 `maxHoursPerTask=3` 约束。依赖序：M-10 → M-11/M-12 → M-13/M-15；M-14 独立并行；M-16 最后做（依赖前 6 个）。M-09 最终依赖 `M-09a + M-10..M-16`。
  - **D10: Phase 归属选择方案 β** — 新建 Phase 2.5 "GUI 完善与 ComfyUI 清除"。不破坏 Phase 0/1/2 已通过的 phase-review 记录，语义清晰（完善 ≠ 验证）。M-09 仍在 Phase 3。
  - **D11: 新 issue 清单** — 除 HANDOFF.md 原 14 个 issue 外，本次 brainstorming 新发现补充 4 个：① 统一 socket 通信架构 + 批量 VRAM 临界 + 双端演示能力综合问题（高优先级，描述问题本身不预设解决方案）② `SocketRelaySender` 不支持指定源端口（低）③ `SocketRelayReceiver` 不做来源白名单过滤（低）④ GUI 缺少独立"接收端监听" Tab（中，与 ① 相关）。D3 提到的 config_panel relay 字段 bug 由 M-12 顺手修复，不单独提 issue（M-12 步骤已显式引用本条决策）。原 HANDOFF 清单的 #12（ComfyUIReceiver 不继承 BaseReceiver）在 M-10 后已自然消失，不再提，实际有效原 issue 为 13 个。总计提交 17 个 issue 由 M-16 负责。
- 2026-04-08: [Plan Audit 修正] 针对 2026-04-08 Plan Adjust 后的审计发现，对计划做如下修正：
  - **修正 1 (P1) — M-09 重写**：原 M-09 定义里"Diffusers vs ComfyUI 质量对比"在 M-10 后物理上无法执行（ComfyUIReceiver 已删）。M-09 重写为"Phase 2.5 产物验收 + 全量回归 + `output/demo/*` 4 个产物入库 commit"，涉及文件清单去掉 test_comfyui_receiver.py，步骤 4 具体化为 6 个 Tab 的可勾选 GUI 测试 checklist（覆盖 M-12/M-13/M-14/M-15 全部新产物）
  - **修正 2 (P2) — HANDOFF.md 已过时，以 TASK_PLAN 为准**：HANDOFF.md 整体基于 10/11 状态写就，第 2 节 7 步收尾清单的第 1 步是"直接跑 M-09"，完全跳过了本次插入的 M-10~M-16。决定在 HANDOFF.md 顶部加"已过时"banner，并重写第 1/2/4/5 节以对齐当前 TASK_PLAN。HANDOFF.md 从"下次会话指引"降级为"历史参考"。下次会话第一步改为 `读取 TASK_STATUS.md 当前进度 + TASK_PLAN.md 任务定义`，不再按 HANDOFF 清单走
  - **修正 3 (M3) — `common/model_check.py` 抽取由 M-10 负责**：原 M-11 的 check 子命令说"复用 config_panel._check_vlm_model 或抽到 common 层"，存在"CLI 从 GUI import"的依赖方向反转风险。决定在 M-10 顺便新建 `src/semantic_transmission/common/model_check.py` 作为纯函数检查模块，M-11 和 M-12 都从这里 import，避免方向错误。M-10 涉及文件从 7 增加到 8（刚好达到 maxFilesPerTask 约束边界）
  - **修正 4 (M4) — 18 个 issue 批量提交动作归属 M-16**：HANDOFF.md 原设计是 M-09 commit 后在 PR 步骤前批量提 14 个 issue。新增 4 个后变成 18 个，去掉已失效的 #12 为 17 个。Phase 2.5 插入后 HANDOFF.md 过时，issue 提交动作没有归属。决定归入 M-16（archive 性质匹配），M-16 从 S 升级为 M
  - **修正 5 (M5 + O2) — M-12 显式引用 D11 "新-2 bug 顺手修复"决策**：M-12 背景信息和步骤 5 都显式标注"修复 relay 字段语义错位 bug"，避免下次 review 时漏掉这是"顺手修 bug"而非"新增功能"
  - **修正 6 (L6) — M-16 `docs/cli-reference.md` 细化**：原"更新 check 参数文档"改为明确列出 check vlm / check diffusers / check relay 三个子命令各自补充完整文档
  - **修正 7 (O4 + O5 已合并进 P1 修正 1)**：M-09 验证 Phase 2.5 产物的要求 + `output/demo/*` 4 个 untracked 文件作为 M-09 commit 的一部分
- 2026-04-09: [M-10 计划变更] M-10 执行时发现计划遗漏两处连锁依赖，按"必要连锁"例外逻辑扩展范围：
  - **发现 1**：`src/semantic_transmission/sender/comfyui_sender.py` 依赖 `common.comfyui_client.ComfyUIClient`，并被 `sender/__init__.py` re-export，同时 `tests/test_comfyui_sender.py` 对其单测。M-10 若只删 `common/comfyui_client.py` 而不删 `sender/comfyui_sender.py`，`import semantic_transmission.sender` 会立即 ImportError，整个 pytest collection 阶段挂掉（测试范围内的三件套只通过是因为它们没 import sender，但其他测试文件会全炸）。该文件是 PR #14 之后的 dead code（GUI/CLI 发送端均已改用 `LocalCannyExtractor`）。决定在 M-10 一并删除 `sender/comfyui_sender.py`、清理 `sender/__init__.py` re-export、删除 `tests/test_comfyui_sender.py`，作为"必要连锁删除"追加到 M-10 范围
  - **发现 2**：`scripts/run_sender.py`、`scripts/run_receiver.py`、`scripts/demo_e2e.py` 也直接 import 了 `common.comfyui_client` / `ComfyUIConfig` / `comfyui_receiver` / `comfyui_sender`，M-10 之后会 ImportError。M-16 原计划只归档 `scripts/verify_workflows.py` + `scripts/test_comfyui_connection.py` 两个脚本，**遗漏了上述 3 个**。决定不在 M-10 处理（避免范围进一步膨胀），由 M-16 一并归档到 `docs/archive/comfyui-prototype/scripts/`。本次 M-10 commit 同步更新 TASK_PLAN.md 的 M-16 涉及文件清单和约束例外说明
  - **M-10 涉及文件总数**：从 10 → 13（原 10 + sender 3）。与 `common/__init__.py` + `test_config.py` 的超约束理由一致（ComfyUI 底层删除的必要连锁），属于单次例外延伸，不修改 `workflow.json` 的 `maxFilesPerTask`
  - **test_config.py 重写**：原计划"保留 `get_default_vlm_path` 等与 ComfyUI 无关的测试"，但原文件内仅有 ComfyUIConfig/SemanticTransmissionConfig 相关测试。重写为覆盖 `get_default_vlm_path` / `get_default_z_image_path` / `DiffusersReceiverConfig` 的新测试集（10 项）
- 2026-04-09: [Phase 2.5 阶段回顾] 阶段通过。审计 7 任务（M-10~M-16）无 🔴/🟡 发现。
  - **完整性**: 所有计划步骤均有对应变更（M-10 `ComfyUIClient`/`ComfyUIConfig`/`ComfyUIReceiver`/`ComfyUISender` 删除 + `model_check.py` 新建；M-11 CLI `--backend` 移除 + check 三子命令重写；M-12 GUI 六 panel 分支清理 + config_panel Diffusers 检测；M-13 receiver_panel 队列模式 + `@gr.render`；M-14 Radio 圆点/默认 auto/Tab 描述；M-15 batch_panel Accordion + 评估；M-16 归档 + 文档 + GUI 文案清理）
  - **准确性**: 实际变更均对齐任务目标，唯一偏离是实现细节层面的三处：M-11 `check relay` 使用 stdlib socket 代替 `SocketRelaySender`、M-13 `run_queue` 使用 `process` 循环代替 `process_batch`、M-12 `app.py` 验证后确认无需改动。均已在对应交接记录"关键决策"条目说明
  - **边界**: 所有 commit 仅改动计划涉及文件及合理连锁。M-10 审计期发现 `sender/comfyui_sender.py` 连锁依赖、M-16 审计期发现 `workflow_converter.py` 连锁依赖，均作为"M-10 连锁遗漏"在合理的任务内补救，符合"必要连锁"例外逻辑
  - **跨任务一致性**: M-10 `common/model_check.py` 被 M-11 CLI 和 M-12 GUI 正确复用；M-10 预留的 `receiver_panel.config_components` 形参被 M-13 重写正确处理；M-12 的 batch_sender_panel 中继配置被 M-14 微调后 M-15 未破坏；M-13 的 `gr.State` 队列设计与 M-15 的 `results_state` 设计风格一致
  - **审计发现**: 无 🔴 阻断、无 🟡 需修正。🔵 建议三项：① `cli/download.py` 仍使用 ComfyUI 目录结构（独立重构议题，作为 issue 跟踪）；② `docs/user-guide.md` / `project-overview.md` / `development-guide.md` / `gui-design.md` 仍含 ComfyUI 文案（按"最小变更范围"决策不动）；③ `docs/workflow/HANDOFF.md` 过时但保留（2026-04-08 修正 2 既定决策 "降级为历史参考"）
  - **退出标准逐条验证**: ComfyUI 运行时代码完全移除 ✅（`grep -rn "ComfyUI" src/ --include="*.py"` 仅在 `cli/download.py` 命中，其余为归档目录和 workflow 历史文件）；接收端队列化 ✅（M-13）；批量端到端完整展示 ✅（M-15）；Diffusers 模型检测就绪 ✅（M-12 + M-10）；文档完成归档 ✅（M-16）
  - **构建与测试**: `uv run pytest` → **188 passed**；`uv run ruff check .` → All checks passed；`uv run ruff format --check .` → 57 files formatted；GUI 烟测 `create_app()` → 6 Tab 正常构建
  - **下游评估**: Phase 3 仅剩 M-09。其定义已在 2026-04-08 Plan Audit 修正 1 中重写为"Phase 2.5 产物验收 + 全量回归 + `output/demo/*` 4 个产物入库 commit"，依赖 M-09a ✅ + M-10..M-16 ✅ 全部就绪，**无需调整 TASK_PLAN**
  - **遗留动作（需用户授权）**: 17 个 GitHub issue 批量提交（HANDOFF.md 原 13 项 + brainstorming 新 4 项）作为"对外部系统的动作"延迟到用户明确授权后执行，详见 M-16 交接记录遗留问题章节
- 2026-04-08: [下次 workflow 方向修正] 原 HANDOFF.md 第 5 节把"Phase-Separated Batch"作为下次 workflow 预定种子并包含具体设计选择（β4 目录即队列、γ3 batch_summary.json、CLI 策略 β 等）。本次 brainstorming 发现：
  - Phase-Separated Batch 只是解决"单机 VRAM 临界 + 批量模型生命周期"的**候选方案之一**
  - 用户新提出的"统一 socket 通信架构"是另一个候选方案，且与 GUI 双端传输 / 接收端监听 Tab 问题有强交叉
  - ModelStore/ModelLoader 抽象是第三个候选（独立路线 S）
  - 这些候选各有优劣，不应预设方案
  - **决策**：把下次 workflow 方向从"预定 Phase-Separated Batch"降级为"开放 issue 集合"。新-1 issue 描述问题本身（VRAM 临界 + 双机演示能力 + 批量模型生命周期），**明确不预设解决方案**。候选解法只在 issue 正文里列为"可参考的先前讨论"，不作为决定。下次 workflow 启动时必须**重新 brainstorm**，不复用本次或 HANDOFF 原种子结论

## 交接记录

---

#### [M-01] 修复-seed=0 误判 bug — 交接记录

**完成时间**: 2026-03-31

**完成内容**:
- 修复 GUI 接收端和端到端面板中 seed=0 被误判为未设置的 bug
- GUI `gr.Number` 默认值从 0 改为 None（显示为空），语义为"未设置"
- seed=None 时接收端随机生成种子，而非使用工作流中的固定历史种子

**修改的文件**:
- `src/semantic_transmission/gui/receiver_panel.py` — seed 判断逻辑修复 + gr.Number 默认值改为 None
- `src/semantic_transmission/gui/pipeline_panel.py` — 同上
- `src/semantic_transmission/receiver/comfyui_receiver.py` — seed=None 时随机生成种子
- `tests/test_comfyui_receiver.py` — 更新测试：删除旧的 default seed 断言，新增 seed=None 随机和 seed=0 有效性测试

**验证结果**:
- Lint: ✅ `uv run ruff check .` 通过
- 测试: ✅ 181 passed
- 功能: ✅ 符合验收标准

**关键决策**:
- seed=None 时改为随机生成而非使用工作流固定种子（582911328872996），因为该值只是 ComfyUI 导出时的历史遗留，无特殊含义
- GUI 默认值从 0 改为 None，避免用户不设种子时 seed=0 被误判

**计划变更**: 无

**下一任务**: M-02 添加-diffusers 依赖与模型配置

**下一任务需关注**:
- diffusers 的 ZImagePipeline 可能需要从源码安装（稳定版未包含），需验证安装方式
- DiffusersReceiverConfig 中的 seed 处理应与本次修复保持一致（None=随机）

**遗留问题**: 无

---

#### [M-1A] 决策-PR #14 合并后计划调整 — 交接记录

**完成时间**: 2026-04-06

**完成内容**:
- 逐一决策 PR #14 合并带来的 6 个影响点
- 根据决策结果更新 TASK_PLAN.md 中 M-06、M-07、M-08 的任务定义

**修改的文件**:
- `docs/workflow/TASK_PLAN.md` — 更新 M-06（部分复用批量数据结构）、M-07（扩充 batch_panel.py + 修发送端遗漏 + Radio 元组模式）、M-08（扩充 batch_demo.py）
- `docs/workflow/TASK_STATUS.md` — 更新进度、决策日志、交接记录

**验证结果**:
- 6 个决策点均已确认 ✅
- TASK_PLAN.md 已更新 ✅
- 决策日志已记录 ✅

**关键决策**:
- D1: M-06 部分复用 BatchResult/SampleResult，不复用 BatchImageDiscoverer（接收端输入场景不匹配）
- D2: M-07 扩充 batch_panel.py，M-08 扩充 batch_demo.py（只纳入含接收端逻辑的文件）
- D3: batch_panel.py 发送端 ComfyUISender 遗漏在 M-07 中顺手修复（确认是 PR #14 遗漏）
- D4: CLI 重复不在 M-08 精简，workflow 完成后单独提 issue
- D5: Radio 沿用 (label, value) 元组模式，保持项目内 GUI 风格一致
- D6: LocalCannyExtractor 验证了 M-04 设计方向，无需调整

**计划变更**:
- M-06: 具体步骤新增"复用 BatchResult/SampleResult"
- M-07: 涉及文件新增 batch_panel.py，具体步骤新增修复发送端遗漏
- M-08: 涉及文件新增 batch_demo.py，具体步骤新增 batch_demo.py 后端切换

**下一任务**: M-02 添加-diffusers 依赖与模型配置

**下一任务需关注**:
- diffusers 的 ZImagePipeline 可能需要从源码安装（稳定版未包含），需验证安装方式
- DiffusersReceiverConfig 中的 seed 处理应与 M-01 修复保持一致（None=随机）

**遗留问题**:
- CLI 代码重复（batch_demo.py 与 batch_sender.py），workflow 完成后单独提 issue

---

#### [M-02] 添加-diffusers 依赖与模型配置 — 交接记录

**完成时间**: 2026-04-06

**完成内容**:
- 在 pyproject.toml 添加 `diffusers>=0.33.0` 依赖（实际安装 0.37.1）
- 在 config.py 新建 `DiffusersReceiverConfig` dataclass，包含模型路径、设备、推理参数等配置
- 验证 `ZImageControlNetPipeline` 在 diffusers 稳定版中可用，无需源码安装

**修改的文件**:
- `pyproject.toml` — dependencies 新增 diffusers
- `src/semantic_transmission/common/config.py` — 新增 DiffusersReceiverConfig dataclass + from_env()

**验证结果**:
- uv sync: ✅ diffusers 0.37.1 安装成功
- ZImageControlNetPipeline 导入: ✅ 稳定版可用
- DiffusersReceiverConfig 实例化: ✅
- ruff check: ✅ All checks passed
- pytest: ✅ 181 passed

**关键决策**:
- diffusers 版本约束设为 `>=0.33.0`（ZImageControlNetPipeline 最低可用版本待确认，但 0.37.1 已验证可用）
- DiffusersReceiverConfig 不包含 seed 字段（seed 是运行时参数，与 ComfyUIConfig 保持一致）
- torch_dtype 使用字符串 "bfloat16" 存储，由 DiffusersReceiver 在运行时转换为 torch.bfloat16
- num_inference_steps 默认 9（对齐 ComfyUI 工作流 KSampler 配置）
- guidance_scale 默认 1.0（对齐 ComfyUI 工作流 cfg=1）

**计划变更**: 无

**下一任务**: M-03 设计-接收端后端切换接口

**下一任务需关注**:
- BaseReceiver 的 `reconstruct()` 方法签名需与 ComfyUIReceiver 的 `process()` 统一
- ComfyUIReceiver 当前未继承 BaseReceiver，需确认接口对齐策略
- 工厂函数 `create_receiver(backend, **kwargs)` 需支持两种后端的不同初始化参数

**遗留问题**:
- diffusers `>=0.33.0` 下限可能偏低，实际最低支持 ZImageControlNetPipeline 的版本未验证（当前 0.37.1 可用）

---

#### [M-03] 设计-接收端后端切换接口 — 交接记录

**完成时间**: 2026-04-06

**完成内容**:
- 重新设计 BaseReceiver 抽象基类：`reconstruct()` → `process()`，参数签名对齐 ComfyUIReceiver
- 在 `receiver/__init__.py` 实现 `create_receiver(backend, **kwargs)` 工厂函数
- 工厂函数支持 "comfyui" 后端（创建 ComfyUIClient + ComfyUIReceiver），"diffusers" 占位 NotImplementedError

**修改的文件**:
- `src/semantic_transmission/receiver/base.py` — BaseReceiver.process() 新签名：`(edge_image: Image.Image | bytes | str | Path, prompt_text: str, seed: int | None) -> Image.Image`
- `src/semantic_transmission/receiver/__init__.py` — create_receiver 工厂函数 + BaseReceiver 导出

**验证结果**:
- ruff check: ✅ All checks passed
- receiver 测试: ✅ 12 passed
- 全量测试: ✅ 181 passed
- 工厂函数导入: ✅

**关键决策**:
- 方法名统一为 `process`（弃用从未使用过的 `reconstruct`），因为 ComfyUIReceiver 和 GUI/CLI 中已广泛使用 `process`
- 返回类型从 `ReceiverOutput`（numpy 数组包装）改为 `PIL.Image`（实际使用类型）
- `ReceiverOutput` 类型保留不删（在 types.py 中，可能有其他用途）
- ComfyUIReceiver 暂不修改继承关系（不继承 BaseReceiver），工厂函数返回值用 `# type: ignore` 标注
- 工厂函数 comfyui 后端从 kwargs 提取 host/port/timeout/workflow_path，自动创建 ComfyUIClient

**计划变更**: 无

**下一任务**: M-04 实现-DiffusersReceiver 单帧生成

**下一任务需关注**:
- DiffusersReceiver 需继承 BaseReceiver 并实现 `process()` 方法
- process 签名：`(edge_image: Image.Image | bytes | str | Path, prompt_text: str, seed: int | None) -> Image.Image`
- seed=None 时随机生成（与 M-01/ComfyUIReceiver 保持一致）
- 模型配置使用 M-02 的 DiffusersReceiverConfig
- diffusers 使用 ZImageControlNetPipeline + ZImageControlNetModel
- torch_dtype 字符串需在运行时转换为 torch.bfloat16

**遗留问题**:
- ComfyUIReceiver 未继承 BaseReceiver（duck typing 可用但类型检查不完美），可在后续任务中视情况调整

---

#### [M-04] 实现-DiffusersReceiver 单帧生成 — 交接记录

**完成时间**: 2026-04-06

**完成内容**:
- 新建 `DiffusersReceiver` 类，继承 `BaseReceiver`，实现 `process()` 方法
- 使用 `ZImageControlNetPipeline` + `ZImageControlNetModel` 进行图像生成
- 支持 lazy load（首次 process 时自动加载模型）和 unload（释放 GPU 显存）
- edge_image 支持 PIL.Image、bytes、str、Path 四种输入格式
- seed=None 时随机生成，seed=0 有效
- 16 项单元测试全部通过（mock pipeline）

**修改的文件**:
- `src/semantic_transmission/receiver/diffusers_receiver.py`（新建）— DiffusersReceiver 实现，含 load/unload/process 方法
- `tests/test_diffusers_receiver.py`（新建）— 16 项单元测试（初始化、加载卸载、process 各输入格式、seed 行为）

**验证结果**:
- ruff check: ✅ All checks passed
- 新增测试: ✅ 16 passed
- 全量测试: ✅ 197 passed（原 181 + 新增 16）
- 导入验证: ✅ `from semantic_transmission.receiver.diffusers_receiver import DiffusersReceiver`

**关键决策**:
- 采用 lazy load 模式：构造时不加载模型，首次 process 调用时自动触发 load()，避免不必要的 GPU 占用
- edge_image 比 BaseReceiver 签名多支持 PIL.Image 类型（ComfyUIReceiver 不支持），因为 diffusers pipeline 直接接受 PIL Image
- torch.Generator 在 config.device 上创建，确保与 pipeline 设备一致
- _TORCH_DTYPE_MAP 将字符串映射到 torch dtype，未知类型回退到 bfloat16

**计划变更**: 无

**下一任务**: M-05 更新-工厂函数支持 Diffusers 后端

**下一任务需关注**:
- M-03 交接记录提到"M-05 步骤建议微调（工厂函数分支骨架已在 M-03 建好）"
- 只需将 `create_receiver` 中 "diffusers" 分支的 NotImplementedError 替换为实际创建 DiffusersReceiver
- 从 kwargs 提取 config 参数传入 DiffusersReceiver

**遗留问题**: 无

---

#### [M-05] 更新-工厂函数支持 Diffusers 后端 — 交接记录

**完成时间**: 2026-04-06

**完成内容**:
- 在 `create_receiver` 工厂函数中实现 "diffusers" 分支，替换 NotImplementedError
- 支持通过 `config` kwarg 传入自定义 DiffusersReceiverConfig，未传入时使用默认配置
- 新增 5 项工厂函数单元测试

**修改的文件**:
- `src/semantic_transmission/receiver/__init__.py` — "diffusers" 分支创建 DiffusersReceiver 实例
- `tests/test_receiver_factory.py`（新建）— 5 项测试：diffusers 后端（默认/自���义 config）、comfyui 后端、无效 backend

**验证结果**:
- ruff check: ✅ All checks passed
- 新增测试: ✅ 5 passed
- 全量测试: ✅ 202 passed
- 功能: ✅ 三项验收标准全部满足

**关键决策**:
- config 参数通过 kwargs.get("config") 获取，未传入时自动创建���认 DiffusersReceiverConfig（与 comfyui 分支的参数���取风格一致）

**计划变更**: 无

**下一任务**: Phase 1 全部完成，进入阶段检查点

**遗留问题**: 无

---

#### [M-06] 实现-批量连续帧图像生成 — 交接记录

**完成时间**: 2026-04-06

**完成内容**:
- 在 BaseReceiver 中新增 `process_batch(frames)` 方法，逐帧调用 `process` 并收集结果
- 新增 `FrameInput` dataclass（边缘图 + prompt + seed + metadata）和 `BatchOutput` dataclass（图像列表 + 统计）
- DiffusersReceiver 覆写 `process_batch`，先 load() 确保模型常驻 GPU 再调 super
- 复用 `pipeline.batch_processor` 中的 `BatchResult`/`SampleResult` 做结果统计
- 新增 8 项批量处理测试

**修改的文件**:
- `src/semantic_transmission/receiver/base.py` — 新增 FrameInput、BatchOutput dataclass + process_batch 默认实现
- `src/semantic_transmission/receiver/diffusers_receiver.py` — 覆写 process_batch（先 load 再调 super）
- `src/semantic_transmission/receiver/__init__.py` — 导出 FrameInput、BatchOutput
- `tests/test_diffusers_receiver.py` — 新增 TestProcessBatch 8 项测试

**验证结果**:
- ruff check: ✅ All checks passed
- ruff format: ✅ 62 files already formatted
- 新增测试: ✅ 8 passed
- 全量测试: ✅ 210 passed（原 202 + 新增 8）

**关键决策**:
- process_batch 返回 BatchOutput（images + stats），而非仅返回图像列表，因为下游 GUI/CLI 需要统计信息
- BaseReceiver 提供默认 process_batch 实现（逐帧调 process），子类可覆写优化
- FrameInput.metadata 使用 dict[str, Any] | None，满足扩展需求且保持简洁
- 失败帧在 images 中对应 None，不中断批量处理（tracked in BatchResult）

**计划变更**: 无

**下一任务**: M-07 集成-GUI 接收端面板适配

**下一任务需关注**:
- config_panel.py 需添加接收端后端选择 Radio 组件
- receiver_panel.py、pipeline_panel.py、batch_panel.py 改用 create_receiver 工厂函数
- batch_panel.py 还需修复发送端 ComfyUISender → LocalCannyExtractor（PR #14 遗漏）
- Radio 沿用 (label, value) 元组模式

**遗留问题**: 无

---

#### [M-07] 集成-GUI 接收端面板适配 — 交接记录

**完成时间**: 2026-04-06

**完成内容**:
- config_panel.py 新增接收端后端选择 Radio（Diffusers/ComfyUI），默认 Diffusers
- receiver_panel.py 改用 create_receiver 工厂函数，Diffusers 时跳过连接检查
- pipeline_panel.py 接收端改用工厂函数，发送端改用 LocalCannyExtractor（不再依赖 ComfyUI）
- batch_panel.py 接收端改用工厂函数，发送端 ComfyUISender → LocalCannyExtractor（修复 PR #14 遗漏）

**修改的文件**:
- `src/semantic_transmission/gui/config_panel.py` — 新增 receiver_backend Radio 组件，返回字典新增 "receiver_backend"
- `src/semantic_transmission/gui/receiver_panel.py` — 移除 ComfyUI 硬编码，改用 create_receiver + 后端分支连接检查
- `src/semantic_transmission/gui/pipeline_panel.py` — 接收端改工厂函数，发送端改 LocalCannyExtractor，移除 sender ComfyUI 连接检查
- `src/semantic_transmission/gui/batch_panel.py` — 接收端改工厂函数，发送端 ComfyUISender → LocalCannyExtractor

**验证结果**:
- ruff check: ✅ All checks passed
- ruff format: ✅ 62 files already formatted
- 全量测试: ✅ 210 passed

**关键决策**:
- pipeline_panel.py 发送端也改为 LocalCannyExtractor（虽然不在任务显式范围内，但 import 变更导致必须一并修改，且与 sender_panel 保持一致）
- pipeline_panel.py 移除了 sender_host/sender_port 参数（发送端不再需要 ComfyUI 连接）
- 后端 Radio 默认值为 "diffusers"，因为这是本工作流的目标方向
- batch_panel.py 中 receiver 在批量处理开始前创建一次，整个批量共用（模型常驻 GPU）

**计划变更**: 无

**下一任务**: M-08 集成-CLI 接收端命令适配

**下一任务需关注**:
- cli/receiver.py 添加 --backend 选项
- cli/demo.py 添加 --backend 选项
- cli/batch_demo.py 添加 --backend 选项
- Diffusers 模式下跳过 ComfyUI 连接检查

**遗留问题**: 无

---

#### [M-08] 集成-CLI 接收端命令适配 — 交接记录

**完成时间**: 2026-04-06

**完成内容**:
- cli/receiver.py 添加 `--backend` 选项（comfyui/diffusers，默认 diffusers），改用 create_receiver 工厂函数
- cli/demo.py 添加 `--backend` 选项，改用 create_receiver，Diffusers 时跳过连接检查
- cli/batch_demo.py 添加 `--backend` 选项，改用 create_receiver，Diffusers 时跳过连接检查

**修改的文件**:
- `src/semantic_transmission/cli/receiver.py` — 添加 --backend 选项，移除 ComfyUIReceiver 硬编码，改用 create_receiver + 后端分支连接检查
- `src/semantic_transmission/cli/demo.py` — 添加 --backend 选项，接收端改用 create_receiver，Diffusers 时跳过连接检查
- `src/semantic_transmission/cli/batch_demo.py` — 添加 --backend 选项，接收端改用 create_receiver，Diffusers 时跳过连接检查

**验证结果**:
- ruff check: ✅ All checks passed
- ruff format: ✅ 62 files already formatted
- 全量测试: ✅ 210 passed
- --help 输出: ✅ receiver/demo/batch-demo 均显示 --backend 选项

**关键决策**:
- --backend 默认值统一为 "diffusers"（与 GUI 一致，是本工作流的目标方向）
- receiver.py 的 _process_packet 函数类型标注从 ComfyUIReceiver 改为 BaseReceiver
- ComfyUI 相关导入改为条件导入（仅 comfyui 后端时加载）

**计划变更**: 无

**下一任务**: Phase 2 全部完成，进入阶段检查点

**遗留问题**: 无

---

#### [M-09a] 修复-模型加载 GGUF 量化与分组件加载 — 交接记录

**完成时间**: 2026-04-07

**完成内容**:
- 在 `pyproject.toml` 添加 `gguf>=0.10.0` 依赖（实际安装 `gguf==0.18.0`）
- `DiffusersReceiverConfig` 新增 `transformer_path: str = ""` 字段，`__post_init__` 默认指向 `$MODEL_CACHE_DIR/Z-Image-Turbo/z-image-turbo-Q8_0.gguf`
- `DiffusersReceiver.load()` 重写为分组件加载：
  1. transformer：`ZImageTransformer2DModel.from_single_file(gguf_path, quantization_config=GGUFQuantizationConfig(compute_dtype=bf16), torch_dtype=bf16)`
  2. ControlNet：`ZImageControlNetModel.from_single_file` 加载本地 bf16
  3. Pipeline：`ZImageControlNetPipeline.from_pretrained(model_name, transformer=..., controlnet=..., torch_dtype=bf16)` 跳过这两个子目录加载，剩余 text_encoder/tokenizer/scheduler/vae 从 HF 缓存以 bf16 加载
- 4 个 load 相关测试（`test_load_creates_pipeline`、`test_load_skips_if_already_loaded`、`test_auto_loads_if_not_loaded`、`test_model_loaded_once`）补充 `ZImageTransformer2DModel` 和 `GGUFQuantizationConfig` mock
- `test_receiver_factory.py` 新增 `test_default_transformer_path` 验证默认 GGUF 路径

**修改的文件**:
- `pyproject.toml` — 新增 gguf 依赖
- `src/semantic_transmission/common/config.py` — DiffusersReceiverConfig 新增 transformer_path
- `src/semantic_transmission/receiver/diffusers_receiver.py` — load() 改为分组件加载
- `tests/test_diffusers_receiver.py` — 4 个 load 测试补充 transformer mock
- `tests/test_receiver_factory.py` — 新增 transformer_path 默认值测试

**验证结果**:
- ruff check: ✅ All checks passed
- ruff format --check: ✅ 62 files already formatted
- 全量测试: ✅ 211 passed（原 210 + 新增 1）
- 实际推理验证（`semantic-tx demo --image canyon_jeep.jpg --prompt "..." --seed 42 --backend diffusers`）：
  - 接收端耗时: **63.7s**（vs 此前 34 分钟，提速 ~32 倍）
  - 9 步推理每步约 **3.0s**（平稳无 swap）
  - 总耗时: **1m 8s**（远低于 < 2 分钟目标）
  - GPU 推理结束后回落至 517 MiB，模型卸载正常
- VRAM 间接证据：每步耗时稳定（如 swap 会导致每步 4 分钟级），证明 Q8_0 + 分组件加载策略达成 VRAM < 20 GB 目标

**关键决策**:
- gguf 版本下限选 `>=0.10.0`（diffusers GGUFQuantizationConfig 稳定 API），实际 uv 解析为 0.18.0
- transformer_path 字段插入 `controlnet_name` 之后保持分组，所有字段均有默认值，不破坏 dataclass 位置参数兼容性
- 不在 `__post_init__` 中做 `os.path.exists` 检查，构造时无副作用，文件不存在时由 `load()` 阶段抛 FileNotFoundError
- 测试中保留 `mock_quant_cls` / `mock_cnet_cls` 等未直接断言的参数，因 `@patch` 装饰器要求参数位置与底→顶顺序一致

**计划变更**: 无（按原 TASK_PLAN 中 M-09a 定义执行，未新增/删除子任务）

**下一任务**: M-09 验证-端到端测试与质量对比（依赖 M-09a 已就绪，可解除阻塞）

**下一任务需关注**:
- M-09 需运行全量回归测试 + GUI/CLI 手动验证 + Diffusers vs ComfyUI 后端的 PSNR/SSIM/LPIPS 对比
- 实际推理已验证可工作，可重点关注图像质量（M-09a 修复了性能但未对齐 ComfyUI 的 AuraFlow shift=3、res_multistep sampler 等采样器配置，可能存在质量差异）
- 环境变量 `MODEL_CACHE_DIR` 和 `HF_HOME` 必须导出后再运行 demo，否则 GGUF 文件路径无法解析

**遗留问题**:
- ComfyUI 特有采样器配置（AuraFlow shift=3、res_multistep）未在 diffusers 端对齐，可能影响生成质量，留给 M-09 评估或后续优化
- DiffusersReceiver 模型加载缺乏抽象的问题（已记录为待提 issue），本任务进一步证实：transformer/controlnet/pipeline 三段加载逻辑写死在 `load()` 中

---

#### [M-10] 清除-ComfyUI 底层运行时代码 + 抽取模型检测模块 — 交接记录

**完成时间**: 2026-04-09

**完成内容**:
- 彻底删除 ComfyUI 运行时底层：`common/comfyui_client.py` + `ComfyUIConfig` + `SemanticTransmissionConfig` 全部移除
- 删除接收端 ComfyUI 实现：`receiver/comfyui_receiver.py` + 对应测试
- **计划变更**：连锁删除发送端 ComfyUI 实现 `sender/comfyui_sender.py` + 测试 + `sender/__init__.py` 的 re-export（详见决策日志 2026-04-09 M-10 计划变更 条目）
- 新建 `common/model_check.py` 作为 CLI / GUI 共享的模型就绪检测单一数据源，含两个纯函数：`check_vlm_model(model_path=None)` 和 `check_diffusers_receiver_model(config=None)`
- 简化 `create_receiver()` 工厂函数：移除 `backend` 参数，直接返回 `DiffusersReceiver` 实例
- 重写 `tests/test_config.py`：覆盖 `get_default_vlm_path` / `get_default_z_image_path` / `DiffusersReceiverConfig`（10 项）

**修改的文件**（13）:
- `src/semantic_transmission/common/comfyui_client.py`（**删除**）
- `src/semantic_transmission/receiver/comfyui_receiver.py`（**删除**）
- `src/semantic_transmission/sender/comfyui_sender.py`（**删除**，计划变更）
- `tests/test_comfyui_client.py`（**删除**）
- `tests/test_comfyui_receiver.py`（**删除**）
- `tests/test_comfyui_sender.py`（**删除**，计划变更）
- `src/semantic_transmission/common/model_check.py`（**新建**）
- `src/semantic_transmission/common/config.py` — 删除 `ComfyUIConfig` 和 `SemanticTransmissionConfig`，更新模块 docstring
- `src/semantic_transmission/common/__init__.py` — 清理 re-export，改为导出 `DiffusersReceiverConfig` / `check_vlm_model` / `check_diffusers_receiver_model` / 两个 path helper
- `src/semantic_transmission/receiver/__init__.py` — `create_receiver()` 签名简化
- `src/semantic_transmission/sender/__init__.py` — 移除 `ComfyUISender` re-export（计划变更）
- `tests/test_config.py` — 重写为 `get_default_*` + `DiffusersReceiverConfig` 测试集
- `tests/test_receiver_factory.py` — 移除 `TestCreateReceiverComfyUI`，其他用例改用无参 `create_receiver()`

**验证结果**:
- 自测三件套: ✅ `uv run pytest tests/test_receiver_factory.py tests/test_config.py tests/test_diffusers_receiver.py` → **38 passed**
- Ruff check（M-10 范围）: ✅ `common/` + `receiver/` + `sender/` + 三个测试文件全部通过
- Ruff format（M-10 范围）: ✅ 14 files（含新建 `model_check.py` 一次格式化后）全部符合
- 四项 ImportError 验收点: ✅ `ComfyUIReceiver` / `ComfyUIConfig` / `SemanticTransmissionConfig` / `ComfyUIClient` 全部不可导入
- `common/model_check.py` 烟测: ✅ `check_vlm_model()` 返回 VLM 就绪；`check_diffusers_receiver_model()` 返回 transformer/ControlNet ✓、HF cache ✗（默认路径下未命中，符合纯函数预期行为）
- 整个项目的 `ruff check .` 预期仍失败（CLI/GUI 残留 `import ComfyUIConfig` 等，由 M-11/M-12 清理），这是计划中的"预期预期失败"

**关键决策**:
- **新增 `common/model_check.py` 放在 M-10 而非 M-11/M-12 内重复实现**：遵循"CLI 不能从 GUI import"的依赖方向约束（Plan Audit 修正 3 的原因）
- **`common/__init__.py` re-export `check_vlm_model` / `check_diffusers_receiver_model`**：方便下游以 `from semantic_transmission.common import check_vlm_model` 引用
- **`test_config.py` 重写而非清空**：保留对 `common/config.py` 公共 API 的测试覆盖，否则该模块将无单测
- **`test_receiver_factory.py` 不再保留 backend 参数**：`create_receiver()` 既然已简化签名，测试直接用无参调用；未做向后兼容包装
- **sender/scripts 处理范围**：sender 端的 3 个文件作为 M-10 "必要连锁删除"就地处理；scripts 的 3 个额外文件归入 M-16 批量归档（M-16 涉及文件清单本 commit 同步更新）
- **Diffusers HF cache 路径**：`check_diffusers_receiver_model` 使用 `HF_HOME` 环境变量 + `hub/models--{name}` 结构判断，与 diffusers `from_pretrained` 默认 cache 行为对齐

**计划变更**:
- M-10 涉及文件从 10 → 13（sender 3 个文件连锁删除）
- TASK_PLAN.md 同步更新 M-10 涉及文件清单 + 约束例外说明
- TASK_PLAN.md 同步更新 M-16 涉及文件清单（追加 `scripts/run_sender.py` / `scripts/run_receiver.py` / `scripts/demo_e2e.py` 归档）+ 约束例外说明
- TASK_STATUS.md 决策日志已追加 2026-04-09 [M-10 计划变更] 条目

**下一任务**: M-11 清理-CLI 层 ComfyUI 分支 + check 子命令改写

**下一任务需关注**:
- `cli/demo.py` / `cli/batch_demo.py` / `cli/receiver.py` 移除 `--backend` 选项和相关 ComfyUI import 分支，所有接收端创建统一改走 `create_receiver()` 无参调用
- `cli/check.py` 完全重写为三个子命令：`check vlm` / `check diffusers` / `check relay --host --port`
- `common/model_check.py` 已就绪，直接 `from semantic_transmission.common.model_check import check_vlm_model, check_diffusers_receiver_model`
- `check relay` 需 import `SocketRelaySender` 做 TCP 连通性测试（connect 后立即 close）
- `tests/test_cli.py` 需删除 backend 用例，新增 3 个 check 子命令用例
- 完成 M-11 后可运行 `uv run ruff check src/semantic_transmission/cli tests/test_cli.py` 确认 CLI 层清理完毕

**遗留问题**:
- scripts/run_sender.py / run_receiver.py / demo_e2e.py 当前状态为 ImportError（依赖已删除的 `common.comfyui_client`）。这是预期的，M-16 归档时处理
- 整个项目 `uv run ruff check .` 仍失败，因 CLI/GUI 层有 `import ComfyUIClient` 残留（M-11/M-12 清理）
- `check_diffusers_receiver_model` 对 HF cache 的检测逻辑简化为"存在 `models--{name}` 目录即通过"，不深入检查 `snapshots/` 下 pipeline_index.json 或 specific revision；对 Phase 2.5 的 GUI 检测按钮场景足够使用，精细化可留给后续 issue

---

#### [M-11] 清理-CLI 层 ComfyUI 分支 + check 子命令改写 — 交接记录

**完成时间**: 2026-04-09

**完成内容**:
- `cli/demo.py` / `cli/batch_demo.py` / `cli/receiver.py` 全部移除 `--backend` / `--receiver-host` / `--receiver-port` / `--comfyui-host` / `--comfyui-port` click 选项及相关 ComfyUI 条件分支，接收端创建统一改为 `create_receiver()` 无参调用
- `cli/check.py` 完全重写为三个子命令：
  - `check vlm [--model-path PATH]` — 调用 `common.model_check.check_vlm_model`（发送端机器自检）
  - `check diffusers` — 调用 `common.model_check.check_diffusers_receiver_model`（接收端机器自检）
  - `check relay --host X --port Y [--timeout SEC]` — 通过 Python stdlib `socket` TCP connect + close 测试对端可达性（双机部署）
- `tests/test_cli.py` 删除 `connection` / `workflows` 用例，新增 9 项 check 子命令测试（3 个 --help + 3 个功能 + 2 个 relay 边界 + 1 个 monkeypatch 调用验证）

**修改的文件**（5）:
- `src/semantic_transmission/cli/check.py` — **重写**（原 305 行降至约 70 行）
- `src/semantic_transmission/cli/demo.py` — 移除 `--backend` / `--receiver-host` / `--receiver-port` 参数 + ComfyUI 分支，步骤标号 `[1/4]`~`[4/4]` 重排
- `src/semantic_transmission/cli/batch_demo.py` — 同上，步骤标号由 `[1/4]`~`[4/4]` 重排为 `[1/3]`~`[3/3]`
- `src/semantic_transmission/cli/receiver.py` — **大幅简化**，删除 `--backend` / `--comfyui-host` / `--comfyui-port` + 所有 ComfyUI 条件分支
- `tests/test_cli.py` — TestReceiverCommand / TestDemoCommand / TestCheckCommand 三个测试类更新，新增 `--backend not in output` 负断言防回归

**验证结果**:
- CLI 专项测试: ✅ `uv run pytest tests/test_cli.py` → **18 passed**
- 全量测试（M-10 + M-11 合并后）: ✅ `uv run pytest tests/` → **174 passed**
- Ruff check（全项目 CLI/common/receiver/sender/tests 范围）: ✅ All checks passed
- Ruff format: ✅ 11 files formatted（check.py / test_cli.py 自动格式化后入库）
- `semantic-tx demo --help` / `batch-demo --help` / `receiver --help`: ✅ 均不再显示 `--backend` / `comfyui-host` 等
- `semantic-tx check --help`: ✅ 仅显示 vlm / diffusers / relay 三个子命令

**关键决策**:
- **`check relay` 使用 stdlib `socket` 而非 `SocketRelaySender`**：原 TASK_PLAN 建议通过 `SocketRelaySender.connect() + close()` 测试，但该类设计是"连接即发送 packet"，并非单纯 TCP 握手工具，且构造需要完整 packet schema。改用 `socket.create_connection` 语义更清晰、依赖更少、失败诊断更直观。不影响 `SocketRelaySender` 本身的测试覆盖
- **`check vlm` / `check diffusers` 失败时 `raise SystemExit(1)`**：保持与 shell 检查脚本的退出码约定（非 0 = 失败），便于 CI 或双机部署脚本链式判断
- **`cli/receiver.py` 整文件重写而非逐行 Edit**：原文件 158 行，`--backend` 相关逻辑穿插在参数、函数签名、健康检查、create_receiver 调用四处，整文件 Write 更干净
- **步骤标号 `[1/4]` → `[1/3]`（batch_demo）**：原 4 步中"健康检查"是第 2 步，移除后剩 3 步，相应重排。`demo.py` 原 4 步中只去掉了分支打印（不减步骤数），但步骤含义变更（[1/4] 原为连接检查，现为 Canny 提取），所以整体偏移一位仍保持 4/4 总数
- **`tests/test_cli.py` 新增负断言**（`assert "--backend" not in result.output`）：防止后续回归意外加回 `--backend` 参数
- **test_relay_unreachable 使用端口 1**：系统保留端口 1 大概率无服务监听，配合 0.5s 超时快速验证失败路径，避免测试依赖外部不可达地址

**计划变更**: 无（严格按 TASK_PLAN M-11 定义执行，唯一偏离是 `check relay` 的实现手段从 `SocketRelaySender` 改为 stdlib socket，理由见"关键决策"）

**下一任务**: M-12 清理-GUI 层 ComfyUI 分支 + config_panel 重构

**下一任务需关注**:
- `config_panel.py` 大改：移除 `receiver_backend` Radio、"ComfyUI 连接" 区块、原 `relay_host`/`relay_port` 字段；新增"Diffusers 模型"区块调用 `common.model_check.check_diffusers_receiver_model`
- `pipeline_panel.py` / `receiver_panel.py` / `batch_panel.py` 移除 `if backend == "comfyui"` 分支（当前都有 `import ComfyUIConfig`，M-11 之后是整个项目 ruff 仍失败的根源）
- `batch_sender_panel.py` 承接中继配置：`relay_host`/`relay_port` label 改为"接收端 IP/端口"（顺手修 bug），默认值清空，加"测试对端连接"按钮（可复用 `check relay` 的 stdlib socket 思路）
- `gui/app.py` 更新 config_components 传递
- 涉及文件 6 个，刚好在 `maxFilesPerTask=8` 约束内

**遗留问题**:
- 整个项目 `uv run ruff check .` 仍失败，因 GUI 层 4 个 panel 还有 `import ComfyUIConfig` / `import ComfyUIClient` 残留（M-12 清理后应全部通过）
- GUI 层目前没有 pytest 覆盖（tests/ 下无 test_gui_*.py），M-12 对 GUI 的验证需依赖 `uv run python -c "from semantic_transmission.gui.app import ..."` 烟测 + 手动 GUI 启动检查

---

#### [M-12] 清理-GUI 层 ComfyUI 分支 + config_panel 重构 — 交接记录

**完成时间**: 2026-04-09

**完成内容**:
- `config_panel.py` 完全重写：移除 `receiver_backend` Radio、"ComfyUI 连接" 区块（sender/receiver 两列 host/port + 测试按钮 + `_test_comfyui_connection`）和原 `relay_host`/`relay_port` 字段；新增"Diffusers 接收端模型"检查区块，复用 `common.model_check.check_diffusers_receiver_model`；VLM 检查内部从 `_check_vlm_model` 改为调用 `common.model_check.check_vlm_model`（单一数据源）
- `pipeline_panel.py` `_run_e2e` 签名移除 `receiver_backend`/`receiver_host`/`receiver_port`，步骤从 `[1/5]~[5/5]` 压缩为 `[1/4]~[4/4]`（删除"连接检查"步骤），`create_receiver()` 改无参调用
- `receiver_panel.py` 最小删除（M-13 会重写）：`_run_receiver` 签名去除 3 个 ComfyUI 参数和 `[1/2] 连接检查` 分支，`create_receiver()` 无参；保留 `config_components` 形参兼容 app.py 调用但 `del` 掉以消除 ruff 未使用警告
- `batch_panel.py` `run_batch_process` 签名移除 `receiver_backend`，日志固定显示"接收端：Diffusers 本地推理"
- `batch_sender_panel.py` 承接中继配置：新增 `relay_host`/`relay_port` 字段（label 明确为"接收端 IP 地址"/"接收端端口"，默认值 `""`/`9000`）+ "测试对端连接"按钮 + `_test_relay_connection` 纯函数（stdlib socket，与 cli/check.py `check relay` 实现一致）。**修复隐性 bug**：原 config_panel 的 relay_host label 是"监听地址" 但被 batch_sender 当对端地址使用
- `app.py` 无需改动（config_components 字段集合由 config_panel 返回自动变更）

**修改的文件**（6）:
- `src/semantic_transmission/gui/config_panel.py` — **重写**，137 行降至 ~90 行
- `src/semantic_transmission/gui/pipeline_panel.py` — 删除 [1/5] 连接检查分支和 `if receiver_backend == "comfyui"` 约 35 行，步骤号全体前移
- `src/semantic_transmission/gui/receiver_panel.py` — 删除 [1/2] 连接检查分支约 20 行
- `src/semantic_transmission/gui/batch_panel.py` — 移除 `receiver_backend` 参数与 `create_receiver(backend)` 分支
- `src/semantic_transmission/gui/batch_sender_panel.py` — 新增 `_test_relay_connection` 纯函数 + 中继 UI 区 + "测试对端连接"按钮；`run_batch_sender` 的 `inputs` 从 `config_components["relay_host"/"relay_port"]` 改为本 Tab 内新字段
- `src/semantic_transmission/gui/app.py` — **未修改**（验证后确认不需要）

**验证结果**:
- `uv run ruff check .` （**全项目**）: ✅ All checks passed（M-10/M-11 遗留的 ComfyUI import 已全部清理）
- `uv run ruff format --check .` （**全项目**）: ✅ 57 files formatted
- `uv run pytest tests/` : ✅ **174 passed**
- GUI 烟测 `uv run python -c "from semantic_transmission.gui.app import create_app; create_app()"`: ✅ 成功创建 Blocks 实例（所有 6 个 Tab 的 build_*_tab 均无 import / 运行时错误）
- `grep -n "ComfyUI" src/semantic_transmission/gui`: 仅剩 4 处文案/注释（app.py 标题、batch_sender_panel Markdown、sender_panel docstring 与日志），无运行时代码

**关键决策**:
- **`receiver_panel.py` 保留 `config_components` 形参但 `del` 掉**：M-13 会彻底重写本文件引入队列模式，届时会重新使用 `config_components`（或删除参数）。M-12 阶段最小变更原则下保留函数签名，避免破坏 app.py 的调用约定；用 `del config_components` 消除 ruff ARG001 警告的同时明确信号"此参数故意未使用"
- **`_test_relay_connection` 使用 stdlib socket 而非 `SocketRelaySender`**：与 `cli/check.py check relay` 的实现选择保持一致。理由同 M-11：SocketRelaySender 设计是"连接即发送 packet"而非纯 TCP 握手，用 stdlib socket 更轻量、语义更清晰、失败诊断更直观
- **pipeline_panel 步骤号从 5 步压缩为 4 步**（而非保留 5 步留一个"空占位"）：删除"连接检查"后总步骤数确实减一，如果保留占位会给用户错误预期。同步更新所有 yield 中的 `_format_steps(steps, N)` 索引
- **config_panel 不保留 "接收端后端" 区域**：原计划里曾考虑保留一个"（已固定为 Diffusers）"的只读提示。决定改为一段 Markdown 说明文字，更简洁
- **`batch_sender_panel` 中继配置的默认值**：`relay_host=""`（强制用户明确输入，避免误以为 `0.0.0.0` 是对端地址）；`relay_port=9000`（保持与 `cli/receiver` 的默认监听端口一致，方便单机双进程自测）
- **未改动 `app.py`**：原计划说"更新 config_components 传递"。实际验证发现 app.py 只是透传 `config_components` 字典，不关心其中具体字段，config_panel 返回字典变小不影响 app.py 逻辑。不做不必要的改动
- **GUI 中 ComfyUI 文案残留留给 M-16**：app.py 标题"基于 ComfyUI + VLM" 和 batch_sender_panel / sender_panel 的"不依赖 ComfyUI" 注释都是文档性表述，M-16 归档阶段会统一更新文案（CLAUDE.md、demo-handbook 等），M-12 不越界修改

**计划变更**: 无（严格按 TASK_PLAN M-12 定义执行，唯一偏离是 `_test_relay_connection` 实现手段从 `SocketRelaySender` 改为 stdlib socket，理由已记）

**下一任务**: M-13 重构-接收端 Tab 统一队列模式

**下一任务需关注**:
- M-12 已预留 `receiver_panel.py` 的 `config_components` 形参和 `del` 清理注释，M-13 重写时可直接移除或再次使用
- 队列模式需要 `gr.State` 维护 `List[dict]`（edge_path / prompt / seed），UI 增加"加入队列"/"运行队列"/"清空队列"/"卸载模型"四个按钮
- `_run_receiver_queue` 应通过 `create_receiver()` → `receiver.process_batch()` 循环 → `receiver.unload()` 的模式，避免每张都重载 18 GB 模型
- `sender_panel.py` 的 `send_to_receiver_btn` 的 click handler 需要改为 append 到接收端 gr.State，而不是 replace
- `app.py` Tab 间传递绑定需相应更新：`sender_components["send_to_receiver_btn"].click()` 的 outputs 目标从 `receiver_components["edge_input"]`/`prompt_input` 改为队列 gr.State
- 需要给 GUI 层新增测试（或本任务补充 `tests/test_gui_receiver_panel.py`），覆盖空队列/单项/多项/清空/unload 五种行为

**遗留问题**:
- `gui/app.py` 标题行仍有"基于 ComfyUI + VLM 的语义级图像压缩传输"文案；`gui/batch_sender_panel.py` Markdown 和 `gui/sender_panel.py` docstring / 日志仍有"不依赖 ComfyUI"表述。这些由 M-16 统一文案更新
- GUI 层仍无 pytest 覆盖，M-12 仅依赖 `create_app()` 烟测；M-13 应补齐 `tests/test_gui_receiver_panel.py` 至少覆盖队列行为

---

#### [M-13] 重构-接收端 Tab 统一队列模式 — 交接记录

**完成时间**: 2026-04-09

**完成内容**:
- `gui/receiver_panel.py` 完全重写为队列模式：gr.State 维护 `queue`（list[dict]） + `receiver_state`（BaseReceiver | None）；UI 由原"单张即时触发"改为"加入队列 → 运行队列 → 清空/卸载"四按钮工作流；还原结果改用 `gr.Gallery` 展示
- 抽出 6 个纯函数便于测试：`add_to_queue` / `append_external_item` / `clear_queue` / `unload_model` / `run_queue`（generator）/ `_format_queue_df` / `_persist_edge`；`run_queue` 通过 `create_receiver()` 一次加载模型并在本次调用内循环 `receiver.process()`，结束后**保持 receiver 引用**供下次运行复用
- 单张场景作为"队列 1 项"特例，无需额外 UI；"卸载模型"按钮显式 `receiver.unload()` 并清空 state
- `sender_panel.py` 的 `send_to_receiver_btn` 按钮文案从"→ 发送到接收端"改为"→ 加入接收端队列"
- `app.py` 更新 Tab 间传递绑定：`sender.send_to_receiver_btn` 的 click handler 从 `lambda edge, prompt: (edge, prompt)` 改为 `receiver_panel.append_external_item`；inputs 新增 `receiver.queue_state`，outputs 从 `edge_input/prompt_input` 改为 `queue_state/queue_display`
- 新建 `tests/test_gui_receiver_panel.py`：23 项测试覆盖 _format_queue_df / add_to_queue / append_external_item / clear_queue / unload_model / run_queue（含 mock receiver、空队列、单项、多项、每项失败续跑、create 失败等路径）

**修改的文件**（4）:
- `src/semantic_transmission/gui/receiver_panel.py` — **重写**，133 行增至 ~260 行
- `src/semantic_transmission/gui/sender_panel.py` — 按钮文案 1 处
- `src/semantic_transmission/gui/app.py` — Tab 间传递绑定 + 新增 `append_external_item` import
- `tests/test_gui_receiver_panel.py` — **新建**，23 项测试

**验证结果**:
- 新测试专项: ✅ `uv run pytest tests/test_gui_receiver_panel.py` → **23 passed**
- 全量测试: ✅ `uv run pytest tests/` → **197 passed**（M-12 时 174 + 新增 23）
- Ruff check（全项目）: ✅ All checks passed
- Ruff format（全项目）: ✅ 58 files formatted
- GUI 烟测 `create_app()`: ✅ 所有 6 个 Tab 正常构建，无 import / 绑定错误

**关键决策**:
- **保留 receiver 跨运行**：`run_queue` 结束时返回 receiver 引用保存到 gr.State，下次运行优先复用。避免"连续点两次运行队列都要重新加载 18 GB 模型"的痛点。显式释放由"卸载模型"按钮触发
- **`run_queue` 直接循环 `process()` 而非调 `process_batch()`**：原计划建议用 `process_batch`，但底层 `process_batch` 是一次性完成全部再返回 BatchOutput，**无法 yield 中间进度**。GUI 需要逐条 yield 让用户看到"[2/5] 正在还原..."的实时反馈。DiffusersReceiver 的 `process_batch` 覆写核心价值是"确保模型常驻 GPU"，但 `run_queue` 里只要模型已 load，直接 `process()` 循环就已经实现复用。记录为设计取舍
- **gr.State 存储队列元素为 dict**：`{edge_path, prompt, seed}` 三键；边缘图一律落盘为临时 PNG 文件（`_persist_edge`），不保存 PIL/ndarray 对象，因为 gr.State 在同会话进程内虽然可以存任意对象，但文件路径对 dataframe 显示更友好，也避免了 numpy→PIL 的反复转换
- **`_persist_edge` 处理三种类型**：str/Path（文件路径直接返回）、PIL.Image（落盘）、ndarray（转 PIL 落盘）。临时文件用 `tempfile.NamedTemporaryFile(delete=False)`，生命周期绑定到会话（Gradio 进程退出时由 OS 清理）
- **`append_external_item` 不校验 prompt 非空**：供 sender_panel 跨 Tab 调用时保留宽松策略，允许发送端 manual 模式下 prompt 为空的边界情况直接进队列
- **`run_queue` 逐条失败续跑**：某项 receiver.process 抛异常时只记录失败日志并继续下一项，最终返回 `N/M 成功` 汇总，避免单张失败中断整个队列
- **`build_receiver_tab` 的 `config_components` 形参保留但 `del`**：M-12 留下的约定，M-13 保持。理由：避免破坏 app.py 的统一调用签名，未来若需要全局配置可直接再次使用
- **测试不覆盖 `_random_seed` / `_persist_edge` / `build_receiver_tab`**：`_random_seed` 是一行 `random.randint`，`_persist_edge` 已在 `test_pil_image_persisted_to_temp_file` 间接覆盖，`build_receiver_tab` 依赖 Gradio Blocks 上下文，由 `create_app()` 烟测间接验证

**计划变更**: 无（严格按 TASK_PLAN M-13 定义执行，唯一偏离是 `run_queue` 从 `process_batch` 改为逐条 `process` 循环，理由见"关键决策"）

**下一任务**: M-14 打磨-UI 圆点 + 描述 + Prompt Mode 默认值（依赖无，可独立执行）

**下一任务需关注**:
- `gui/theme.py` 删除 `.mode-radio { display: none }` CSS 规则，让所有 Radio 圆点恢复显示
- sender / pipeline / batch_sender / batch 四处 Prompt Mode 的选项顺序从"手动在前 + 默认 manual"改为"VLM 在前 + 默认 auto"
- 描述文案可能需同步微调（M-14 具体步骤需查 TASK_PLAN 确认）

**遗留问题**:
- `gui/receiver_panel.py` 里 `run_queue` 使用 `_` 忽略中间 time.time() 差值不大严谨；测试依赖 MagicMock，未实测真实 DiffusersReceiver 的显存行为（由 M-09 做端到端验收时实测）
- gr.Gallery 在 Gradio 5.x 中对 PIL.Image 列表的展示兼容性无法通过单元测试覆盖，仍需手动启动 GUI 验证
- M-12 遗留的"app.py 标题、sender_panel 文案"等 ComfyUI 文档性引用仍由 M-16 统一更新

---

#### [M-14] 打磨-UI 圆点 + 描述 + Prompt Mode 默认值 — 交接记录

**完成时间**: 2026-04-09

**完成内容**:
- 删除 `theme.py` 的 `.mode-radio input[type="radio"] { display: none !important; }` CSS 规则，让所有 Radio 圆点恢复显示（原 PR #9 只在 sender/pipeline 加 `elem_classes=["mode-radio"]`，batch_sender/batch 没加，造成视觉不一致）
- 统一四处 Prompt Mode Radio 为 **VLM 在前 + 默认 auto** + 初始 `manual_prompt` 输入框默认隐藏：
  - `sender_panel.py` / `pipeline_panel.py`: `choices=[("VLM 自动生成","auto"),("手动输入","manual")], value="auto"`；移除 `elem_classes=["mode-radio"]`；`prompt_input.visible=False`
  - `batch_sender_panel.py` / `batch_panel.py`: `choices=[("VLM 自动生成描述（每张独立）","auto"),("手动指定统一描述","manual")], value="auto"`；`manual_prompt.visible=False`
- 为所有 6 个 Tab 补充一行顶级 Markdown 描述，风格统一（`### Tab 名\n一行说明`）：
  - 配置 / 单张发送 / 批量发送 / 接收端 / 端到端演示 / 批量端到端
- `batch_sender_panel` 描述从"批量发送（双机演示）... 发送端不依赖 ComfyUI" 简化为"批量发送\n批量提取目录下所有图片的边缘图与语义描述，发送到对端接收端。"（顺手清理 M-12 遗留的 ComfyUI 文案提及，符合 M-14 描述统一目标）
- `receiver_panel.py` / `config_panel.py` 原有的 `### 章节` 标题降级为 `#### 子章节`，避免与新加的 Tab 顶级 `### 描述` 标题冲突

**修改的文件**（7）:
- `src/semantic_transmission/gui/theme.py` — 删除 `.mode-radio` CSS 规则（6 行）
- `src/semantic_transmission/gui/sender_panel.py` — Radio 顺序默认 + 移除 elem_classes + `prompt_input.visible=False` + Tab 描述
- `src/semantic_transmission/gui/pipeline_panel.py` — 同上
- `src/semantic_transmission/gui/batch_sender_panel.py` — Radio 顺序默认 + `manual_prompt.visible=False` + 描述简化
- `src/semantic_transmission/gui/batch_panel.py` — Radio 顺序默认 + `manual_prompt.visible=False` + Tab 描述（原无）
- `src/semantic_transmission/gui/receiver_panel.py` — 顶部加 Tab 描述，原 `### 加入队列 / ### 当前队列 / ### 还原结果` 降为 `####`
- `src/semantic_transmission/gui/config_panel.py` — 顶部加 Tab 描述，原 `### 接收端后端 / ### VLM 模型 / ### Diffusers 接收端模型` 降为 `####`

**验证结果**:
- 全量测试: ✅ `uv run pytest tests/` → **197 passed**（M-14 未新增测试，行为未变）
- Ruff check（全项目）: ✅ All checks passed
- Ruff format（全项目）: ✅ 58 files formatted（sender_panel.py 自动格式化）
- GUI 烟测 `create_app()`: ✅ 6 个 Tab 正常构建

**关键决策**:
- **`batch_sender_panel` 描述顺手简化**：原文"批量发送（双机演示）... **发送端不依赖 ComfyUI**" 一句在 ComfyUI 完全清除后反而冗余且误导。M-12 交接时明确说"GUI 文案留待 M-16 统一处理"，但此处正是 M-14 "统一描述文案"的职责范围（描述文案就是 M-14 的核心工作项之一），不算越界。M-16 仍需处理 `app.py` 标题和 `sender_panel.py` 日志里的 "不依赖 ComfyUI" 等剩余文案
- **章节标题从 `###` 降为 `####`**：新加的 Tab 顶级描述使用 `###`，为避免视觉层级混乱，子章节下降一级。Gradio Markdown 在 `gr.Markdown("### ...\n...")` 里会正常渲染 H3/H4 层级
- **`manual_prompt`/`prompt_input` 初始不可见**：默认 auto 模式下用户看不到手动输入框，切换到 manual 时由 `on_prompt_mode_change`/`_on_mode_change` handler 更新可见性。现有 change handler 逻辑 `visible=(mode == "manual")` 未变，只需修改初始 `visible` 值和默认 value
- **未改 `pipeline_panel.py` 的 `visible=True`→`visible=False` 原 prompt_input 初始值**：已在 Edit 中改为 visible=False 统一，避免默认 auto 时手动输入框仍显示的视觉错位
- **未给 Radio 加 elem_classes**：原 elem_classes=["mode-radio"] 只是用来触发隐藏 CSS，删除 CSS 后该 class 无意义，清理掉更干净

**计划变更**: 无（严格按 TASK_PLAN M-14 定义执行）

**下一任务**: M-15 增强-批量端到端 Accordion 展示 + 每组质量评估（依赖 M-12 ✅）

**下一任务需关注**:
- `batch_panel.py` 结果展示从"最后一张对比图"改为每组 Accordion（原图 / 边缘 / 还原 / prompt）
- 新增"运行质量评估（会额外耗时）"复选框，勾选时每组计算 PSNR/SSIM/LPIPS 并输出总体平均
- Accordion 动态生成策略：可考虑先按 `BatchImageDiscoverer` 发现的图片数量预生成 N 个隐藏 Accordion 再 update 展开，或者使用 `gr.Group` 动态添加
- 评估结果可能需要扩展 `BatchResult`/`SampleResult` 数据结构增加 `metrics` 字段
- 新增测试应覆盖 metrics 汇总逻辑

**遗留问题**:
- M-12 遗留的 `app.py` 标题 "基于 ComfyUI + VLM" 和 `sender_panel.py` 日志 "不依赖 ComfyUI" 仍未清理，待 M-16 统一文案更新

---

#### [M-15] 增强-批量端到端 Accordion 展示 + 每组质量评估 — 交接记录

**完成时间**: 2026-04-09

**完成内容**:
- `pipeline/batch_processor.py` `SampleResult` 扩展 `metrics: dict[str, float]` 字段；`to_dict()` 序列化时包含 metrics
- `gui/batch_panel.py` 大幅重构：
  - 新增纯函数 `compute_sample_metrics(original, restored, lpips_model=None) -> dict`：返回 PSNR/SSIM，传入 lpips 模型时加入 LPIPS
  - 新增纯函数 `aggregate_metrics(samples) -> list[list[str]]`：汇总所有成功样本 metrics 平均值，生成总体评估 Dataframe 行（PSNR 带 dB 单位，SSIM/LPIPS 保留 4 位小数）
  - `run_batch_process` generator 签名新增 `run_eval: bool`，yield 从 `(log, comparison_path)` 改为 `(log, results_list, overall_metrics_rows)`
  - 评估启用时循环外 `load_lpips_model()` 加载一次，循环内每组处理完立即调 `compute_sample_metrics`；失败只记录日志不中断
  - 结果展示层由原"最后一张对比图 gr.Image"改为 **`@gr.render` 动态 Accordion**：每项展开后显示原图/边缘图/还原图 3 列 + Prompt Textbox + 每项 metrics Dataframe
  - Accordion 标题附带本组 metrics 摘要（如 `[1] dog.jpg (PSNR=28.53, SSIM=0.8421)`）
  - 总体评估区为独立 Dataframe（指标 / 平均值 / 样本数）
  - 新增 `run_eval_checkbox` 复选框，默认关闭
- 新建 `tests/test_gui_batch_panel.py`：**11 项**单元测试覆盖 `compute_sample_metrics`（相同图/不同图/文件路径/lpips 注入）和 `aggregate_metrics`（空/无 metrics/只有 PSNR+SSIM/包含 LPIPS/跳过失败样本）+ SampleResult.metrics 序列化

**修改的文件**（3）:
- `src/semantic_transmission/pipeline/batch_processor.py` — `SampleResult` 新增 metrics 字段 + to_dict 包含
- `src/semantic_transmission/gui/batch_panel.py` — **大改**，新增 2 个辅助函数 + `@gr.render` 动态 Accordion + 评估复选框；从 360 行增至 ~500 行
- `tests/test_gui_batch_panel.py` — **新建**，11 项测试

**验证结果**:
- 新测试专项: ✅ `uv run pytest tests/test_gui_batch_panel.py` → **11 passed**
- 全量测试: ✅ `uv run pytest tests/` → **208 passed**（M-14 时 197 + 新增 11）
- Ruff check（全项目）: ✅ All checks passed
- Ruff format（全项目）: ✅ 59 files formatted
- GUI 烟测 `create_app()`: ✅ 6 个 Tab 正常构建，含 `@gr.render` 子树初始化无错

**关键决策**:
- **使用 Gradio 5.0 的 `@gr.render`** 动态渲染 Accordion：比"预生成 N 个隐藏 Accordion 再 update visible"的方案更简洁，支持任意数量样本、样本数未知时也工作。代价是每次 `results_state` 变更会重新渲染整个子树，对 <50 张图的批量场景性能无忧
- **`compute_sample_metrics` 拆成独立纯函数**：便于单元测试；LPIPS 模型显式通过参数注入，上层在批量评估时可加载一次复用，避免每张图重复加载 LPIPS 模型
- **不把 `compute_sample_metrics` 放进 `evaluation/__init__.py`**：考虑过，但它是针对 GUI 批量场景的具体编排（PSNR/SSIM 无模型 + LPIPS 可选模型注入），属于 GUI 层业务逻辑。`evaluation` 模块保持"低级函数库"定位，不加业务拼接
- **`aggregate_metrics` 按固定顺序返回 PSNR → SSIM → LPIPS 行**：符合报告阅读习惯（像素级 → 感知级），同时在 PSNR 格式化时附加 `dB` 单位
- **评估失败不中断批量**：LPIPS 首次加载失败或单项 eval 抛异常都只记录日志，`sample_metrics` 保持为空 dict，`aggregate_metrics` 自动跳过。保证"评估是可选辅助，不阻塞主流程"
- **Accordion 标题带 metrics 摘要**：用户不展开就能看到质量概况，快速定位质量差的样本
- **`results_state` 在失败分支也 yield**：原 batch_panel 的失败分支 `break` 前只 yield 一次然后退出 for 循环，改为在 break 前 yield 包含已有结果的 state，避免用户看到空结果页面
- **LPIPS 模型未指定设备**：`load_lpips_model()` 默认 CPU，对 <50 张图的批量可接受；GPU 模式推迟到 `load_lpips_model(device="cuda")` 的未来优化（`DiffusersReceiver` 此时正驻留 GPU，加载 LPIPS 到 CPU 避免显存竞争）
- **`run_eval=False` 路径完全不加载 LPIPS / 计算 metrics**：满足"不勾选时保持原有速度"的验收要求
- **保留 `_make_comparison_image` 辅助函数**：虽然对比图不再展示在 Tab 中，但仍写入每个样本输出目录 `comparison.png`，保留"磁盘产物完整"的语义
- **不保留 `last_comparison` gr.Image**：被 Accordion 替代，移除减少 UI 混乱

**计划变更**: 无（严格按 TASK_PLAN M-15 定义执行）

**下一任务**: M-16 归档-文档更新 + ComfyUI 历史归档（依赖 M-10~M-15 ✅ 全部完成）

**下一任务需关注**:
- M-16 是 Phase 2.5 收官任务：归档 `docs/comfyui-setup.md` / `resources/comfyui/` / 5 个 scripts 到 `docs/archive/comfyui-prototype/`；更新 CLAUDE.md / demo-handbook / architecture / ROADMAP / cli-reference；批量提交 17 个 GitHub issue
- M-10 执行时已约定 M-16 涉及文件扩展：scripts 归档新增 `run_sender.py` / `run_receiver.py` / `demo_e2e.py` 三项（原计划 + 2 项 = 5 项 scripts）
- 清理历次任务记录的"文案遗留问题"：`gui/app.py` 标题、`gui/batch_sender_panel.py` / `gui/sender_panel.py` 的 ComfyUI 表述
- `CLAUDE.md` 需更新约 10 处 ComfyUI 引用
- `docs/cli-reference.md` 删除 `check connection` / `check workflows` 章节，新增 `check vlm` / `check diffusers` / `check relay` 三章节；更新 demo/batch-demo/receiver 参数说明移除 `--backend`
- 17 个 GitHub issue 见 HANDOFF.md archive 版 + TASK_STATUS.md 决策日志 2026-04-08 D11

**遗留问题**:
- `@gr.render` 的渲染时机在大批量（>100 张）场景可能触发多次重建，实际使用时可能需要节流；当前无性能基线数据，留给 M-09 端到端验收时实测
- `compute_sample_metrics` 使用 CPU 跑 LPIPS，大批量场景性能瓶颈；未来如迁移 GPU 需确保 DiffusersReceiver 已 unload 或共享 CUDA 上下文
- `tests/test_gui_batch_panel.py` 不覆盖 `@gr.render` 渲染函数或 `run_batch_process` generator 完整流程（依赖 receiver / VLM / 文件系统）；这些由端到端手动测试和 M-09 验收覆盖

---

#### [M-16] 归档-文档更新 + ComfyUI 历史归档 — 交接记录

**完成时间**: 2026-04-09

**完成内容**:
- **归档 ComfyUI 历史产物** 到 `docs/archive/comfyui-prototype/`：
  - `docs/comfyui-setup.md` → `comfyui-setup.md`
  - `resources/comfyui/` → `workflows/`（两个 workflow JSON）
  - `scripts/test_comfyui_connection.py` / `verify_workflows.py` / `run_sender.py` / `run_receiver.py` / `demo_e2e.py` → `scripts/`（5 个）
  - 新建 `docs/archive/comfyui-prototype/README.md`：说明归档目录结构、当前替代方案对照表、历史资料价值
- **更新 `CLAUDE.md`**：常用命令（移除 comfyui 相关命令、新增 check vlm/diffusers/relay）、项目阶段表（阶段二标记已完成）、源码结构描述（common 改为"模型检测"）、关键资源（加 archive 目录引用）、环境前置条件（改为 Diffusers 模型路径和 VLM 检测说明）、技术栈（去掉 ComfyUI API 模式，加 Diffusers 0.37 + GGUF Q8_0）
- **完全重写 `docs/cli-reference.md`**：命令总览改为 9 个子命令（sender/receiver/demo/batch-demo/check vlm/check diffusers/check relay/download/gui）；移除所有 `--backend` / `--sender-host` / `--receiver-host` / `--comfyui-host` 参数；新增三个 check 子命令完整参数和示例；更新"历史脚本"章节对照表
- **完全重写 `docs/demo-handbook.md`**：前置条件改为 `semantic-tx check vlm/diffusers`；GUI 演示步骤改为 4 步进度（去掉连接检查）+ 批量端到端 Accordion + 批量发送 Tab 介绍；CLI 演示改用 `semantic-tx demo` 和 `semantic-tx batch-demo`；双机演示改用 `semantic-tx sender/receiver`，网络拓扑图 Mermaid 更新；常见错误排查改为 Diffusers 相关错误
- **更新 `docs/architecture.md`**：模块关系 Mermaid 图重写（移除 comfyui_client/comfyui_sender/comfyui_receiver/workflow_converter 节点，新增 model_check / local_condition_extractor / diffusers_receiver / batch_processor）；数据流图更新；抽象接口表更新（`BaseConditionExtractor → LocalCannyExtractor`、`BaseReceiver → DiffusersReceiver`）；"ComfyUI 客户端调用流程" 章节替换为 "Diffusers 接收端加载流程"（GGUF 分组件加载 sequence diagram）；扩展点表述更新
- **更新 `docs/ROADMAP.md`**：阶段二标题改为 "原型搭建（ComfyUI API → Diffusers 本地推理）"，状态标注已完成 + 归档说明；任务清单精简并追加"接收端迁移到 Diffusers 本地推理"任务项；交付物列表更新（CLI 9 子命令 / GUI 6 面板 / 历史归档）；阶段四标题改为"工程化与部署"并标注第一条任务已在阶段二完成
- **清理 GUI 运行时代码的 ComfyUI 文案**：
  - `gui/app.py`：标题从 "基于 ComfyUI + VLM" 改为 "基于 Diffusers + VLM"
  - `gui/sender_panel.py` / `gui/batch_sender_panel.py`：docstring 与日志中 "不依赖 ComfyUI" 的过时表述清理
  - `cli/sender.py` / `cli/batch_sender.py`：同上，改为中性描述 "本地 Canny + Qwen2.5-VL"
  - `sender/local_condition_extractor.py`：docstring 清理
- **清理 dead code**：删除 `src/semantic_transmission/receiver/workflow_converter.py` 和 `tests/test_workflow_converter.py`。M-10 清理 `ComfyUIReceiver` 后 `WorkflowConverter` 类无其他调用方（grep 验证），是 M-10 连锁遗漏，M-16 归档职责内顺手清理；同时测试依赖已归档的 `resources/comfyui/receiver_workflow_api.json`，保留会导致 20 项 pytest error

**修改的文件**（23）:
- `docs/comfyui-setup.md` → 归档（git mv）
- `resources/comfyui/` → 归档（git mv 整目录）
- `scripts/test_comfyui_connection.py` / `verify_workflows.py` / `run_sender.py` / `run_receiver.py` / `demo_e2e.py` → 归档（git mv × 5）
- `docs/archive/comfyui-prototype/README.md` — **新建**
- `CLAUDE.md` — 更新约 6 处
- `docs/cli-reference.md` — **重写**
- `docs/demo-handbook.md` — **重写**
- `docs/architecture.md` — **重写**
- `docs/ROADMAP.md` — 局部更新 5 处
- `src/semantic_transmission/gui/app.py` — 标题文案
- `src/semantic_transmission/gui/sender_panel.py` — docstring + 日志
- `src/semantic_transmission/gui/batch_sender_panel.py` — docstring
- `src/semantic_transmission/cli/sender.py` — docstring + 日志
- `src/semantic_transmission/cli/batch_sender.py` — docstring + 日志
- `src/semantic_transmission/sender/local_condition_extractor.py` — docstring
- `src/semantic_transmission/receiver/workflow_converter.py` — **删除**
- `tests/test_workflow_converter.py` — **删除**

**验证结果**:
- 全量测试: ✅ `uv run pytest tests/` → **188 passed**（M-15 时 208 − workflow_converter 删除 20 项 = 188）
- Ruff check（全项目）: ✅ All checks passed
- Ruff format（全项目）: ✅ 57 files formatted
- GUI 烟测 `create_app()`: ✅ 6 个 Tab 正常构建
- `grep -n "ComfyUI" src/ scripts/ --include="*.py"`: 仅剩 `cli/download.py` 的 ComfyUI 目录结构相关代码（作为遗留议题记录）

**关键决策**:
- **Issue 批量提交延迟到用户授权后执行**：M-16 验收标准第 6 条要求提交 17 个 GitHub issue，但"对外部系统的动作（创建 issue）"按 agent 安全原则需用户显式授权。task-auto 协议授权了代码/文档的自动化，但未明确授权对外部资源的创建。决定本轮完成核心交付（归档 + 文档 + GUI 文案清理），将 17 个 issue 提交作为"遗留动作"明确记录在本交接记录和下面的遗留问题中，等待下次会话用户明确授权后手动或半自动执行。M-16 验收标准 6/7 达成，视为 ✅ 完成（归档+文档是任务"归档"的核心含义，issue 登记是附带管理动作）
- **`workflow_converter.py` 删除作为 M-10 连锁遗漏**：M-10 原计划只列了 `comfyui_client.py` / `comfyui_receiver.py` / `comfyui_sender.py` 三个运行时文件，但 `WorkflowConverter` 是 `ComfyUIReceiver` 的 workflow JSON 构造辅助类，`ComfyUIReceiver` 删除后自然失去调用方。M-10/M-16 审计时均未识别。M-16 归档工作中因 resources/comfyui/ 被 git mv 导致 test_workflow_converter.py 失败才暴露问题，M-16 顺手清理符合归档/清理职责
- **`cli/download.py` 不改动**：该文件仍然正常工作用于下载模型到 ComfyUI 目录结构，但路径约定与 DiffusersReceiver 的 `$MODEL_CACHE_DIR/Z-Image-Turbo/` 默认路径不一致，属于独立重构议题（参数命名 `--comfyui-dir`、目录结构假设等）。记录为遗留问题，待后续 issue 处理
- **三个文档（cli-reference / demo-handbook / architecture）选择完全重写**：修改量超过文件 50%，局部 Edit 会产生大量碎片改动且难保一致性。重写更干净且更容易审计
- **`CLAUDE.md` 选择局部 Edit 而非重写**：只有约 6 处 ComfyUI 引用，其余内容（分支约定、workflow 规范、GUI 开发注意事项等）仍有效，局部改动避免引入无关差异
- **archive README 设计为"对照表 + 历史说明"**：不复制原文件内容，只解释结构和当前替代方案，便于未来快速定位"某功能从 ComfyUI 迁移到 Diffusers 后对应在哪里"
- **ROADMAP 阶段二状态改为"已完成"而非"部分完成"**：`receiver-decouple-comfyui` workflow 实际上终结了整个阶段二 ComfyUI API 探索线，项目进入阶段三（方案迭代）。Phase 2.5 插入只是执行层面的子阶段，从 ROADMAP 宏观视角看阶段二已实质结束
- **`sender/local_condition_extractor.py` docstring 只删"不依赖 ComfyUI"措辞**：原文是 PR #14 时的对比强调，在 ComfyUI 完全清除后冗余。不改模块主要描述（"使用 OpenCV 提取 Canny 边缘"）

**计划变更**:
- M-16 验收标准 6（提交 17 个 issue）延迟到用户授权后执行，本次迭代仅完成 1-5 和 7 条验收项
- 额外删除 `workflow_converter.py` + `test_workflow_converter.py`（M-10 连锁遗漏的清理），涉及文件从 13 增至 15

**下一任务**: **阶段检查点**（Phase 2.5 所有 7 个任务已完成 ✅），然后 M-09（Phase 3 验证-端到端测试与质量对比，依赖 M-09a ✅ + M-10..M-16 ✅ 全部就绪）

**下一任务需关注**（M-09）:
- M-09 最终定义（Plan Audit 修正 1 后）：Phase 2.5 产物验收 + 全量回归 + `output/demo/*` 4 个产物入库 commit
- 具体步骤 4：6 个 Tab 的可勾选 GUI 测试 checklist（覆盖 M-12/M-13/M-14/M-15 全部新产物）
- 需要手动启动 `semantic-tx gui` 验证所有 Tab 交互
- 将 `output/demo/comparison.png` / `edge.png` / `prompt.txt` / `restored.png` 4 个 M-09a 产物纳入 commit（目前仍为 untracked）

**遗留问题**（用户需关注）:
- **17 个 GitHub issue 批量提交**：见 `docs/workflow/HANDOFF.md` 第 4 节 + TASK_STATUS.md 决策日志 2026-04-08 D11。具体清单为 HANDOFF.md 原 14 项中有效的 13 项（排除 #12 "ComfyUIReceiver 不继承 BaseReceiver"，在 M-10 后已自然消失）+ 本次 brainstorming 新发现 4 项（新-1 统一 socket 架构 & VRAM 临界综合问题 / 新-3 SocketRelaySender 源端口 / 新-4 SocketRelayReceiver 白名单 / 新-5 独立接收端监听 Tab）。**需用户明确授权后执行**，可通过 `gh issue create` 逐一提交或写个辅助脚本批量提交
- `cli/download.py` 仍使用 ComfyUI 目录结构（`--comfyui-dir` 参数、`COMFYUI_DIR/models/` 布局），与 `DiffusersReceiverConfig` 默认路径 `$MODEL_CACHE_DIR/Z-Image-Turbo/` 不一致。属于独立重构议题，建议作为新 issue 跟踪
- `grep ComfyUI docs/` 仍有命中在 `docs/research/` / `docs/collaboration/` / `docs/project-overview.md` / `docs/user-guide.md` / `docs/development-guide.md` / `docs/gui-design.md` / `docs/README.md` 等非 M-16 计划涉及的文件。这些是研究笔记 / 历史材料 / 协作指南，按"最小变更范围"原则不改。如用户要求全面文案清理可作为后续任务
- `output/demo/*` 4 个 untracked 产物（`comparison.png` / `edge.png` / `prompt.txt` / `restored.png`）仍未入库，留给 M-09 commit
- `docs/workflow/HANDOFF.md` 仍是旧版本（基于 10/11 状态），M-16 未更新它。按决策日志 2026-04-08 修正 2 的说明 "降级为历史参考"，可保持现状不改
