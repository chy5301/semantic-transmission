# 任务状态跟踪

> 创建时间: 2026-03-31
> 任务类型: migration
> 任务前缀: M

## 进度总览

| 阶段 | 总数 | 完成 | 进行中 | 待开始 |
|------|------|------|--------|--------|
| Phase 0: 准备 | 4 | 2 | 0 | 2 |
| Phase 1: 核心实施 | 2 | 0 | 0 | 2 |
| Phase 2: 完善 | 3 | 0 | 0 | 3 |
| Phase 3: 验证 | 1 | 0 | 0 | 1 |
| **合计** | **10** | **2** | **0** | **8** |

## 任务状态

| 编号 | 标题 | 阶段 | 状态 | 依赖 |
|------|------|------|------|------|
| M-01 | 修复-seed=0 误判 bug | Phase 0 | ✅ 已完成 | 无 |
| M-1A | 决策-PR #14 合并后计划调整 | Phase 0 | ✅ 已完成 | M-01 |
| M-02 | 添加-diffusers 依赖与模型配置 | Phase 0 | ⬜ 待开始 | M-1A |
| M-03 | 设计-接收端后端切换接口 | Phase 0 | ⬜ 待开始 | M-02 |
| M-04 | 实现-DiffusersReceiver 单帧生成 | Phase 1 | ⬜ 待开始 | M-02, M-03 |
| M-05 | 更新-工厂函数支持 Diffusers 后端 | Phase 1 | ⬜ 待开始 | M-03, M-04 |
| M-06 | 实现-批量连续帧图像生成 | Phase 2 | ⬜ 待开始 | M-04 |
| M-07 | 集成-GUI 接收端面板适配 | Phase 2 | ⬜ 待开始 | M-05 |
| M-08 | 集成-CLI 接收端命令适配 | Phase 2 | ⬜ 待开始 | M-05 |
| M-09 | 验证-端到端测试与质量对比 | Phase 3 | ⬜ 待开始 | M-06, M-07, M-08 |

状态图例: ⬜ 待开始 | 🔄 进行中 | ✅ 已完成 | ⏸️ 暂停 | ❌ 已取消 | 🔀 已拆分

## 已知问题

- 遗留 issue: #16（timeout 倍数需确认）、#17（量化依赖按平台条件安装）

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
