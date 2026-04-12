# 任务状态跟踪

> 创建时间: 2026-04-12
> Workflow: unify-config-and-loader
> 任务类型: refactor + bugfix + infrastructure
> 任务前缀: R

## 进度总览

| 阶段 | 总数 | 完成 | 进行中 | 待开始 |
|------|------|------|--------|--------|
| Phase 0: 基础设施 | 2 | 1 | 0 | 1 |
| Phase 1: receiver 侧垂直切 | 4 | 0 | 0 | 4 |
| Phase 2: sender/CLI 侧垂直切 | 3 | 0 | 0 | 3 |
| Phase 3: GUI 侧垂直切 | 2 | 0 | 0 | 2 |
| Phase 4: cleanup + 收尾 | 3 | 0 | 0 | 3 |
| **合计** | **14** | **1** | **0** | **13** |

## 任务状态

| 编号 | 标题 | 阶段 | 状态 | 依赖 |
|------|------|------|------|------|
| R-01 | 创建-ProjectConfig 与 config.toml 体系 | Phase 0 | ✅ | 无 |
| R-02 | 创建-ModelLoader 抽象基类 | Phase 0 | ⬜ | 无 |
| R-03 | 实现-DiffusersModelLoader | Phase 1 | ⬜ | R-01, R-02 |
| R-04 | 迁移-DiffusersReceiver + 动态尺寸 #24 | Phase 1 | ⬜ | R-03 |
| R-05 | 简化-BaseReceiver.process_batch #31 | Phase 1 | ⬜ | R-04 |
| R-06 | 对齐-采样器参数 #25 | Phase 1 | ⬜ | R-04 |
| R-07 | 实现-QwenVLModelLoader + 迁移 QwenVLSender | Phase 2 | ⬜ | R-02 |
| R-08 | 合并-CLI sender/batch_sender #19 | Phase 2 | ⬜ | R-01, R-07 |
| R-09 | 重构-download.py + 迁移 demo/batch_demo CLI | Phase 2 | ⬜ | R-01, R-08 |
| R-10 | 修复-GUI 面板生命周期 #23 | Phase 3 | ⬜ | R-04, R-07 |
| R-11 | 迁移-GUI 面板读 ProjectConfig 默认值 | Phase 3 | ⬜ | R-01, R-10 |
| R-12 | 创建-load_as_rgb + 替换 core 模块 #22 | Phase 4 | ⬜ | R-04, R-07 |
| R-13 | 替换-CLI + GUI 模块 RGB 散落 #22 续 | Phase 4 | ⬜ | R-12 |
| R-14 | 删除-LocalRelay #33 + 文档更新 + issue 关闭 | Phase 4 | ⬜ | R-08, R-13 |

状态图例: ⬜ 待开始 | 🔄 进行中 | ✅ 已完成 | ⏸️ 暂停 | ❌ 已取消 | 🔀 已拆分

## 已知问题

（执行过程中发现的问题记录在此）

## 决策日志

| 日期 | 决策 | 原因 |
|------|------|------|
| 2026-04-11 | 选定 L3 深切片（#20 + #21 捆绑） | 两者耦合度高，只做其中一个改动面不减 |
| 2026-04-11 | 按模块垂直切（非架构优先/P0优先） | 每模块改完即稳定，任一 phase 断点可合并 |
| 2026-04-11 | CLI 不保留旧 batch_sender 子命令 | 预研阶段无外部用户 |
| 2026-04-11 | --image 和 --input-dir 保留差异化输出 | 两种心智（快测 vs 数据集），行为可预测 |
| 2026-04-11 | config.toml 扩展集（模型+推理+路径） | 覆盖 ModelLoader 和 CLI 两层需求 |
| 2026-04-11 | ModelLoader 不直接依赖 ProjectConfig | 用 dataclass 子集解耦，config 变 loader 不动 |
| 2026-04-11 | tomllib + 手写 dataclass（不引 pydantic） | stdlib 零依赖成本 |
| 2026-04-11 | 不走 docs/superpowers/ 独立 spec | 与 structured-workflow 合并单一路径，避免两套文档 |
| 2026-04-12 | guidance_scale/steps 默认值待 R-06 实验确定 | 代码分析发现当前值 1.0/9 vs seed 建议 3.5/20 差异大 |
| 2026-04-12 | R-05/R-06 编号互换（原 R-06→R-05, 原 R-05→R-06） | process_batch 审计是确定性工作先做，采样器对齐是实验性任务后做 |
| 2026-04-12 | requires-python 提升到 >=3.12 | 预研项目+CI 3.12+本地 3.12，直接用 stdlib tomllib |

## 交接记录

### R-01 交接（2026-04-12）

**完成内容**：建立 `ProjectConfig` frozen dataclass + `load_config()` 加载器 + `config.toml` 默认配置文件，实现 4 层配置优先级（代码默认 < config.toml < config.local.toml < 环境变量）。

**修改的文件**：
- `src/semantic_transmission/common/config.py` — 新增 `ProjectConfig`、`load_config()`、环境变量展开工具函数；修复 `from_env()` 兼容 `from __future__ import annotations`
- `config.toml` — 新建，仓库根，当前代码实际默认值
- `.gitignore` — 新增 `config.local.toml`
- `tests/test_project_config.py` — 新建，10 个测试用例覆盖默认值/toml 加载/local 覆盖/环境变量展开
- `pyproject.toml` — `requires-python` 从 `>=3.10` 提升到 `>=3.12`（用 stdlib tomllib）

**验证结果**：198 passed / ruff check + format 全绿

**关键决策**：
- `requires-python` 提升到 `>=3.12`：预研项目、CI 3.12、团队均 3.12+，直接用 stdlib tomllib
- `config.toml` 的 inference 默认值用当前代码实际值（`guidance_scale=1.0`, `steps=9`），待 R-06 实验后更新
- `DiffusersReceiverConfig.from_env()` 修复：加了 `from __future__ import annotations` 后 `f.type` 变字符串，改用 `_TYPE_MAP` 字符串查找

**下一任务**：R-02 创建 ModelLoader 抽象基类（无依赖，可直接开始）

**遗留问题**：无
