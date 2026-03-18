# 任务状态跟踪

> 创建时间: 2026-03-13
> 任务类型: integration + infrastructure
> 任务前缀: P2
> 任务名称: comfyui-api-prototype

## 进度总览

| 阶段 | 总数 | 完成 | 冻结 | 进行中 | 待开始 |
|------|------|------|------|--------|--------|
| Phase 0: 契约确认与项目骨架 | 4 | 3 | 1 | 0 | 0 |
| Phase 1: 工作流拆分与双端 ComfyUI 调用 | 6 | 0 | 0 | 0 | 6 |
| Phase 2: 中继传输与双机演示 | 2 | 0 | 0 | 0 | 2 |
| Phase 3: VLM 集成与质量优化 | 3 | 0 | 0 | 0 | 3 |
| **合计** | **15** | **3** | **1** | **0** | **11** |

## 任务状态

| 编号 | 标题 | 阶段 | 状态 | 依赖 |
|------|------|------|------|------|
| P2-01 | 搭建-Python 项目骨架 | Phase 0 | ✅ 已完成 | 无 |
| P2-02 | 定义-抽象接口 | Phase 0 | ⏸️ 冻结 | P2-01 |
| P2-03 | 验证-ComfyUI API 连通性 | Phase 0 | ✅ 已完成 | P2-01 |
| P2-04 | 分析-工作流 JSON 到 API 格式转换 | Phase 0 | ✅ 已完成 | P2-03 |
| P2-05 | 拆分-工作流 JSON | Phase 1 | ⬜ 待开始 | P2-04 |
| P2-06 | 扩展-配置支持双 ComfyUI 实例 | Phase 1 | ⬜ 待开始 | P2-03 |
| P2-07 | 实现-ComfyUI API 客户端 | Phase 1 | ⬜ 待开始 | P2-06 |
| P2-08 | 实现-发送端调用 | Phase 1 | ⬜ 待开始 | P2-05, P2-07 |
| P2-09 | 实现-接收端调用 | Phase 1 | ⬜ 待开始 | P2-05, P2-07 |
| P2-10 | 搭建-端到端 Demo 脚本 | Phase 1 | ⬜ 待开始 | P2-08, P2-09 |
| P2-11 | 实现-中继传输协议 | Phase 2 | ⬜ 待开始 | P2-10 |
| P2-12 | 编写-双机演示脚本 | Phase 2 | ⬜ 待开始 | P2-11 |
| P2-13 | 集成-VLM 自动生成 prompt | Phase 3 | ⬜ 待开始 | P2-10 |
| P2-14 | 实现-质量评估模块 | Phase 3 | ⬜ 待开始 | P2-10 |
| P2-15 | 脱离-ComfyUI 发送端 | Phase 3 | ⬜ 待开始 | P2-13 |

状态图例: ⬜ 待开始 | 🔄 进行中 | ✅ 已完成 | ⏸️ 冻结 | ❌ 已取消 | 🔀 已拆分

### 已取消任务（原计划）

以下任务因方向调整而取消（从"Python 重写发送端"改为"ComfyUI 工作流拆分 + 中继传输"）：

| 原编号 | 原标题 | 取消原因 |
|--------|--------|----------|
| P2-05（旧） | 实现-Canny 条件提取器 | 发送端继续使用 ComfyUI，不需要 Python 实现 |
| P2-06（旧） | 实现-VLM 发送端适配器 | 移至 Phase 3（P2-13），当前阶段用手动 prompt |
| P2-07（旧） | 实现-ComfyUI 接收端适配器 | 重新设计为 P2-07（通用客户端）+ P2-09（接收端调用） |
| P2-08（旧） | 搭建-端到端 Pipeline | 重新设计为 P2-10（demo 脚本），不依赖抽象接口 |
| P2-09（旧） | 编写-端到端 Demo 脚本 | 合并到新 P2-10 |
| P2-10（旧） | 实现-质量评估模块 | 移至 Phase 3（P2-14） |
| P2-11（旧） | 添加-异常处理与日志 | 延后，在各模块实现时按需添加 |
| P2-12（旧） | 执行-初步质量评估 | 移至 Phase 3，依赖 P2-14 |

## 已知问题

（执行过程中发现的问题记录在此）

## 决策日志

| 日期 | 决策 | 理由 |
|------|------|------|
| 2026-03-13 | 采用适配器模式 | ROADMAP 阶段三/四要求渐进替换模型和脱离 ComfyUI，适配器天然支持组件切换 |
| 2026-03-13 | 任务类型为 integration + infrastructure | 核心工作是接入 ComfyUI API 和部署 VLM，非自研功能 |
| 2026-03-17 | 子图展开策略：两遍遍历 | 先展开子图修改 link lookup，再转换普通节点，避免节点处理顺序导致连接错误 |
| 2026-03-17 | Widget 隐藏值检测：基于数量对比 | 当 widgets_values 数量 > widget inputs 数量且当前为 seed 类型时，跳过下一个值（control_after_generate） |
| 2026-03-17 | Phase 0 阶段回顾通过 | 4/4 任务完成，退出标准全部满足，20 个测试通过，无遗留问题 |
| 2026-03-18 | **任务计划重构：从"Python 重写"改为"ComfyUI 工作流拆分"** | 原计划偏离了用户意图。用户原始需求是最快速度打通 demo：将同事的 ComfyUI 工作流拆分为发送端和接收端，两端都用 ComfyUI API，中间加中继传输。原计划直接跳到了用 Python 重写发送端（Canny+VLM），这属于后续阶段。重构后 Phase 1 聚焦工作流拆分和双端调用，VLM 集成移至 Phase 3 |
| 2026-03-18 | 不做 git revert | P2-01+P2-02 同一 commit 无法单独 revert；P2-02 代码量极少不构成负担，留待 Phase 3 启用；P2-03/P2-04 直接可复用 |
| 2026-03-18 | P2-02 抽象接口标记为"冻结" | 当前阶段两端都用 ComfyUI API，不需要 Python 层的 VLM/Canny 抽象。接口留待 Phase 3"渐进替换"时启用 |

## 交接记录

### P2-01 搭建-Python 项目骨架（2026-03-13）

**完成内容**：
- 创建 `pyproject.toml`（hatchling 构建、Python ≥3.10、5 个核心依赖）
- 建立 `src/semantic_transmission/` 包及 sender、receiver、pipeline、common 四个子包
- 建立 `tests/` 目录

**修改的文件**（7 个新建）：
- `pyproject.toml`
- `src/semantic_transmission/__init__.py`
- `src/semantic_transmission/sender/__init__.py`
- `src/semantic_transmission/receiver/__init__.py`
- `src/semantic_transmission/pipeline/__init__.py`
- `src/semantic_transmission/common/__init__.py`
- `tests/__init__.py`

**验证结果**：
- `uv sync` 成功安装 10 个包 ✅
- `import semantic_transmission` 正常 ✅
- 四个子包均可导入 ✅

**关键决策**：
- build-backend 使用 hatchling（轻量、src 布局原生支持）
- 初始 build-backend 路径 `hatchling.backends` 有误，修正为 `hatchling.build`

**下一任务及关注点**：
- P2-02（定义-抽象接口）和 P2-03（验证-ComfyUI API 连通性）均已解锁，可并行推进
- P2-02 需在 sender/base.py、receiver/base.py、common/types.py 中定义抽象基类
- P2-03 需创建 common/config.py 和连通性测试脚本

**遗留问题**：无

### P2-02 定义-抽象接口（2026-03-13）

**完成内容**：
- 在 `common/types.py` 定义 3 个 dataclass：`SenderOutput`、`TransmissionData`、`ReceiverOutput`
- 在 `sender/base.py` 定义 `BaseSender`（ABC，`describe` 方法）和 `BaseConditionExtractor`（ABC，`extract` 方法）
- 在 `receiver/base.py` 定义 `BaseReceiver`（ABC，`reconstruct` 方法）

**修改的文件**（3 个新建）：
- `src/semantic_transmission/common/types.py`
- `src/semantic_transmission/sender/base.py`
- `src/semantic_transmission/receiver/base.py`

**验证结果**：
- BaseSender、BaseConditionExtractor、BaseReceiver 导入正常 ✅
- 三个类均为 ABC，不可直接实例化 ✅
- SenderOutput、TransmissionData、ReceiverOutput 均为 dataclass ✅

**关键决策**：
- 数据类型使用 `NDArray[np.uint8]` 类型注解，与 opencv/numpy 生态一致
- metadata 字段统一使用 `dict[str, Any]`，保留扩展灵活性

**状态变更（2026-03-18）**：
- 标记为 ⏸️ 冻结。原因：任务计划重构后，Phase 1~2 两端都用 ComfyUI API，不需要 Python 层的抽象接口。接口留待 Phase 3 启用（VLM 集成、脱离 ComfyUI 发送端）。

**遗留问题**：无

### P2-03 验证-ComfyUI API 连通性（2026-03-13）

**完成内容**：
- 创建 `ComfyUIConfig` 配置类，支持环境变量 `COMFYUI_HOST` / `COMFYUI_PORT` / `COMFYUI_TIMEOUT`
- 创建连通性测试脚本，覆盖 6 个端点：健康检查、上传图像、提交工作流、WebSocket、查询历史、下载图像
- 脚本使用最简工作流（LoadImage + SaveImage）验证 `/prompt` 端点，不依赖完整工作流转换

**修改的文件**（2 个新建）：
- `src/semantic_transmission/common/config.py`
- `scripts/test_comfyui_connection.py`

**验证结果**：
- `ComfyUIConfig.from_env()` 正常工作，`base_url` / `ws_url` 属性正确 ✅
- ComfyUI 不可用时脚本优雅失败，输出明确错误信息，不崩溃 ✅
- 脚本支持 `--host` / `--port` 命令行参数覆盖 ✅

**关键决策**：
- 采用方案 (b)：硬编码最简工作流用于连通性测试，避免依赖 P2-04 的工作流转换逻辑
- 配置类使用 dataclass + classmethod `from_env()`，保持与 `types.py` 一致的代码风格

**下一任务及关注点**：
- P2-04（分析-工作流 JSON 到 API 格式转换）已解锁
- P2-06（扩展-配置支持双 ComfyUI 实例）依赖本任务的 ComfyUIConfig

**遗留问题**：无

### P2-04 分析-工作流 JSON 到 API 格式转换（2026-03-17）

**完成内容**：
- 实现 `WorkflowConverter` 类，支持 UI 格式到 API 格式的完整转换
- 支持子图展开：将嵌套的子图节点（虚拟输入 -10、虚拟输出 -20）展开为扁平节点结构
- 支持 widget 值映射：自动处理 control_after_generate 等隐藏 widget
- 支持参数注入：`set_prompt()` 和 `set_condition_image()` 动态替换工作流参数
- 编写 20 个单元测试覆盖结构、连接、内容和注入

**修改的文件**（2 个新建，1 个修改）：
- `src/semantic_transmission/receiver/workflow_converter.py`（新建）
- `tests/test_workflow_converter.py`（新建）
- `pyproject.toml`（修改：添加 pytest 开发依赖）

**验证结果**：
- 20 个单元测试全部通过 ✅
- API 格式包含 16 个节点（4 个外层 + 12 个子图内部） ✅
- 子图边界连接正确（Canny→QwenImageDiffsynthControlnet, VAEDecode→SaveImage） ✅
- KSampler 的 control_after_generate 隐藏 widget 被正确跳过 ✅
- set_prompt / set_condition_image 参数注入正常 ✅

**关键决策**：
- 采用两遍遍历策略：先展开子图（修改 outer_link_lookup），再转换普通节点，避免节点处理顺序问题
- 子图虚拟输入的值来源判断：有外部 link 则用外部源连接，否则用子图引用节点的 widget 值
- 隐藏 widget 检测基于 widgets_values 数量与 widget inputs 数量的对比，结合 seed 名称匹配
- 跳过 PreviewImage 和 MarkdownNote 类型节点（仅用于 UI 展示）

**下一任务及关注点**：
- P2-05（拆分-工作流 JSON）已解锁，可利用 WorkflowConverter 辅助生成拆分后的 API JSON
- WorkflowConverter 的 `to_api_format()` 输出可作为拆分的起点

**遗留问题**：无

### 任务计划重构（2026-03-18）

**完成内容**：
- 重构任务计划方向：从"Python 重写发送端"改为"ComfyUI 工作流拆分 + 中继传输"
- 取消原 P2-05~P2-12（8 个任务），新增 P2-05~P2-15（11 个任务）
- P2-02 标记为 ⏸️ 冻结（留待 Phase 3 启用）
- 更新 workflow.json phases、TASK_PLAN.md、TASK_STATUS.md

**修改的文件**：
- `docs/workflow/workflow.json`
- `docs/workflow/TASK_PLAN.md`
- `docs/workflow/TASK_STATUS.md`

**关键决策**：
- 不做 git revert（P2-01+P2-02 同一 commit，P2-03/P2-04 可复用）
- Phase 1 聚焦"两端 ComfyUI API + demo 脚本"
- Phase 2 聚焦"中继传输 + 双机演示"
- Phase 3 才做 VLM 集成和脱离 ComfyUI

**下一任务及关注点**：
- P2-05（拆分-工作流 JSON）和 P2-06（扩展-配置）已解锁，可并行推进
- P2-05 是关键路径：需要理解完整工作流的节点拓扑，正确拆分为发送端（4节点）和接收端（~14节点）
- P2-06 相对简单，扩展 ComfyUIConfig 支持双实例

**遗留问题**：无
