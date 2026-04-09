# 工作流完成摘要 — receiver-decouple-comfyui

## 基本信息

- **任务名称**: receiver-decouple-comfyui
- **任务类型**: migration（兼 refactor / bugfix）
- **任务前缀**: M
- **开始时间**: 2026-03-31
- **归档时间**: 2026-04-09
- **init commit**: `070b6ce`
- **首末 commit**: `6eab1a7`（M-01 首次落地）→ `ee2006c`（M-09 复审合并）

## 总体统计

| 项 | 数 |
|---|---|
| 阶段数 | 5（含中途插入的 Phase 2.5） |
| 任务总数 | 18 |
| 已完成 | 18 |
| 已取消 / 暂停 / 未完成 | 0 |

## 各阶段摘要

### Phase 0: 准备（4/4）
- M-01 修复 seed=0 误判 bug
- M-1A PR #14 合并后计划调整决策（PR14_IMPACT_ANALYSIS.md）
- M-02 添加 diffusers 依赖与模型配置
- M-03 设计接收端后端切换接口

**关键成果**：seed bug 修复、diffusers 依赖落地、Receiver 后端切换接口设计稳定。

### Phase 1: 核心实施（2/2）
- M-04 实现 DiffusersReceiver 单帧生成
- M-05 工厂函数支持 Diffusers 后端

**关键成果**：DiffusersReceiver 单帧生成可工作，与 ComfyUIReceiver 可对比。

### Phase 2: 完善（3/3）
- M-06 实现批量连续帧图像生成
- M-07 GUI 接收端面板适配 Diffusers 后端切换
- M-08 CLI 接收端命令适配 Diffusers 后端切换

**关键成果**：批量、GUI、CLI 三条路径全部支持 Diffusers 后端，与 ComfyUI 后端共存。

### Phase 2.5: GUI 完善与 ComfyUI 清除（7/7，中途插入）
- M-10 清除 ComfyUI 底层运行时代码 + 抽取 `model_check` 模块
- M-11 清理 CLI 层 ComfyUI 分支 + 重写 check 子命令（vlm / diffusers / relay）
- M-12 清理 GUI 层 ComfyUI 分支 + 重构 config_panel
- M-13 接收端 Tab 重构为队列模式
- M-14 统一 UI 圆点 / Prompt Mode 默认值 / Tab 描述
- M-15 批量端到端 Tab 改 Accordion 展示并支持质量评估
- M-16 文档更新 + ComfyUI 历史归档（`docs/archive/comfyui-prototype/`）

**关键成果**：ComfyUI 运行时代码完全移除（Phase 2 共存策略升级为单一 Diffusers 后端），GUI 完成可测试化改造，文档与原型材料完成归档。

### Phase 3: 验证（2/2）
- M-09a 修复模型加载（GGUF Q8_0 + 分组件加载，适配 24GB VRAM）
- M-09 端到端测试 + Phase 2.5 产物验收

**关键成果**：188 tests / ruff / format 全绿；CLI demo 端到端可运行；GUI 6 Tab 结构 + 单张/接收端/批量发送（管理员手动）通过；M-09a demo 产物入库。

## 关键决策汇总

1. **2026-04-02 — 接受 PR #14 改动并调整计划**：M-1A 决策吸收 PR #14 的 `pipeline/batch_processor` / `LocalCannyExtractor` / `gui/batch_panel.py` 等基础设施，M-06/M-07/M-08 task 计划相应调整，CLI 重复代码延后单独提 issue。
2. **2026-04-08 — 插入 Phase 2.5**：原计划 M-09 验证前 brainstorming 发现 GUI 多个调整点 + ComfyUI 运行时未彻底清除，新增 7 个任务（M-10~M-16），把"两后端共存"升级为"单 Diffusers 后端 + ComfyUI 完全清除"。
3. **2026-04-08 — M-09a 拆出独立任务**：原 M-04 留下的 GGUF 量化 + 分组件加载 + ControlNet 通道 bug 不属于"加 Diffusers 支持"范围，独立成 Phase 3 修复任务。
4. **2026-04-09 — Phase 2.5 阶段回顾通过 + `/simplify` 复审追加 6 项 issue**。
5. **2026-04-09 — M-09 真实推理发现 P0 性能缺陷**：◆ 端到端 / ◇ 批量端到端 Tab 模型生命周期泄漏 + DiffusersReceiver 还原图尺寸不等比 + CFG=1.0 step=9 细节丢失。按"验证任务发现并记录"职责处理，登记为 M09-2 / M09-3，**不在本 workflow 内修复**。
6. **2026-04-09 — 复审合并 简-3 + M09-2**：同根因（GUI 缺乏统一 try/finally + unload 治理），合并为单一 priority-high issue。

## 遗留问题清单

详细清单见 `PENDING_ISSUES.md`。**总数 25 项**（最后更新 2026-04-09 复审），按优先级：

- 🔴 **高优先级 7 项**：#1 CLI 重复 / #2 ModelLoader 抽象 / #3 项目级配置 / 新-1 socket+VRAM+双端综合议题 / 简-1 RGB 转换散落 / M09-2 GUI 资源+模型生命周期 / M09-3 还原图尺寸+细节丢失
- 🟡 **中优先级 8 项**：#8 #9 #11 #14 新-5 审-1 简-2 M09-1
- 🟢 **低优先级 10 项**：#4 #5 #15 新-3 新-4 审-2 审-3 简-5 简-6 M09-4

下次 workflow 启动时，**新-1 是开放议题，必须重新 brainstorm，不复用本次方案种子**。

## 经验教训

1. **真实推理验证是必须的** — Phase 2.5 完成的所有结构性改造在自动化测试和 GUI 结构性校验下都通过，但 M-09 真实推理才暴露 P0 级性能缺陷（M09-2 / M09-3）。验证任务不能只靠 mock + Playwright 结构性遍历，必须有"真实模型 + 真实数据"的烟雾测试。
2. **Phase 中途插入新 Phase 是合理的** — Phase 2.5 的插入避免了把 GUI 完善和 ComfyUI 清除这种同质性工作硬塞进 M-09 验证任务里，保持了任务边界清晰。代价是计划文档需要 Plan Audit 二轮修正补连锁文件。
3. **Brainstorming 阶段值得发散** — 2026-04-08 brainstorming 一次性识别出"统一 socket 通信架构 + 模型生命周期 + 双机演示能力"这个综合议题（新-1），后续手测复现的三个症状都在该议题覆盖范围内，证明 brainstorming 的产出有前瞻性。
4. **Issue 合并要做两轮** — 2026-04-09 一次合并整理（4 项）+ 一次复审追加合并（简-3+M09-2 → M09-2）。复审是必要的，能发现"层级不同但根因相同"的合并机会。
5. **CLAUDE.md 约束执行良好** — 全程严格走 feature branch、ruff 三件套、Angular conventional commit；CI 0 失败。
6. **HANDOFF.md 是次优交接载体** — 2026-04-08 创建后很快被 TASK_STATUS / TASK_PLAN 的内容覆盖并过时。下次工作流不再依赖独立的 HANDOFF.md，所有交接信息直接落到 TASK_STATUS 决策日志和交接记录里。
