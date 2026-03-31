# 任务状态跟踪

> 创建时间: 2026-03-31
> 任务类型: migration
> 任务前缀: M

## 进度总览

| 阶段 | 总数 | 完成 | 进行中 | 待开始 |
|------|------|------|--------|--------|
| Phase 0: 准备 | 3 | 1 | 0 | 2 |
| Phase 1: 核心实施 | 2 | 0 | 0 | 2 |
| Phase 2: 完善 | 3 | 0 | 0 | 3 |
| Phase 3: 验证 | 1 | 0 | 0 | 1 |
| **合计** | **9** | **1** | **0** | **8** |

## 任务状态

| 编号 | 标题 | 阶段 | 状态 | 依赖 |
|------|------|------|------|------|
| M-01 | 修复-seed=0 误判 bug | Phase 0 | ✅ 已完成 | 无 |
| M-02 | 添加-diffusers 依赖与模型配置 | Phase 0 | ⬜ 待开始 | 无 |
| M-03 | 设计-接收端后端切换接口 | Phase 0 | ⬜ 待开始 | M-02 |
| M-04 | 实现-DiffusersReceiver 单帧生成 | Phase 1 | ⬜ 待开始 | M-02, M-03 |
| M-05 | 更新-工厂函数支持 Diffusers 后端 | Phase 1 | ⬜ 待开始 | M-03, M-04 |
| M-06 | 实现-批量连续帧图像生成 | Phase 2 | ⬜ 待开始 | M-04 |
| M-07 | 集成-GUI 接收端面板适配 | Phase 2 | ⬜ 待开始 | M-05 |
| M-08 | 集成-CLI 接收端命令适配 | Phase 2 | ⬜ 待开始 | M-05 |
| M-09 | 验证-端到端测试与质量对比 | Phase 3 | ⬜ 待开始 | M-06, M-07, M-08 |

状态图例: ⬜ 待开始 | 🔄 进行中 | ✅ 已完成 | ⏸️ 暂停 | ❌ 已取消 | 🔀 已拆分

## 已知问题

（执行过程中发现的问题记录在此）

## 决策日志

- 2026-03-31: 迁移策略选择 Strangler Fig，保留 ComfyUI 后端作为备选
- 2026-03-31: 继续使用 Z-Image-Turbo + ControlNet Union，通过 diffusers ZImageControlNetPipeline 加载
- 2026-03-31: 双机接收端也改为直接推理，同时支持后端切换

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
