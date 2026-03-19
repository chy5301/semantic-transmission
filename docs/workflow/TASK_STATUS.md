# 任务状态跟踪

> 创建时间: 2026-03-13
> 任务类型: integration + infrastructure
> 任务前缀: P2
> 任务名称: comfyui-api-prototype

## 进度总览

| 阶段 | 总数 | 完成 | 冻结 | 进行中 | 待开始 |
|------|------|------|------|--------|--------|
| Phase 0: 契约确认与项目骨架 | 4 | 3 | 1 | 0 | 0 |
| Phase 1: 工作流拆分与双端 ComfyUI 调用 | 6 | 3 | 0 | 0 | 3 |
| Phase 2: 中继传输与双机演示 | 2 | 0 | 0 | 0 | 2 |
| Phase 3: VLM 集成与质量优化 | 3 | 0 | 0 | 0 | 3 |
| **合计** | **15** | **6** | **1** | **0** | **8** |

## 任务状态

| 编号 | 标题 | 阶段 | 状态 | 依赖 |
|------|------|------|------|------|
| P2-01 | 搭建-Python 项目骨架 | Phase 0 | ✅ 已完成 | 无 |
| P2-02 | 定义-抽象接口 | Phase 0 | ⏸️ 冻结 | P2-01 |
| P2-03 | 验证-ComfyUI API 连通性 | Phase 0 | ✅ 已完成 | P2-01 |
| P2-04 | 分析-工作流 JSON 到 API 格式转换 | Phase 0 | ✅ 已完成 | P2-03 |
| P2-05 | 拆分-工作流 JSON | Phase 1 | ✅ 已完成 | P2-04 |
| P2-06 | 扩展-配置支持双 ComfyUI 实例 | Phase 1 | ✅ 已完成 | P2-03 |
| P2-07 | 实现-ComfyUI API 客户端 | Phase 1 | ✅ 已完成 | P2-06 |
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
| 2026-03-18 | 记录同事技术建议：接收端模型选型与条件特征扩展 | 同事指出：(1) 接收端模型需具备图片编辑或 ControlNet 参考能力，推荐 Z-Image-Turbo 和 FLUX.2-klein-9B；(2) 条件特征不限于 Canny 边缘，深度图也是可选方案。这些影响 Phase 3 的模型替换和条件提取器扩展，当前阶段不影响实现 |
| 2026-03-19 | wait_for_completion 采用轮询 /history 而非 WebSocket | WebSocket 需在 submit 前建连否则有竞态，轮询更简单且 test_comfyui_connection.py 已验证可行 |
| 2026-03-19 | get_result_images 接受 history_entry 而非 prompt_id | 避免重复请求 /history，wait_for_completion 已返回完整条目 |
| 2026-03-19 | 自定义异常层级：ComfyUIError → ConnectionError / TimeoutError | P2-08/P2-09 需按异常类型做差异化处理（连接问题 vs 超时 vs 工作流错误） |

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

### P2-06 扩展-配置支持双 ComfyUI 实例（2026-03-18）

**完成内容**：
- 扩展 `ComfyUIConfig.from_env()` 支持可选的 `prefix` 参数，带前缀时优先读取 `COMFYUI_{PREFIX}_HOST` 等环境变量，未设置则回退到 `COMFYUI_HOST`
- 新增 `SemanticTransmissionConfig` dataclass，组合 `sender: ComfyUIConfig` 和 `receiver: ComfyUIConfig`
- 编写 12 个单元测试覆盖默认值、环境变量读取、前缀回退、单机/双机模式

**修改的文件**：
- `src/semantic_transmission/common/config.py`（修改：扩展 from_env + 新增 SemanticTransmissionConfig）
- `tests/test_config.py`（新建：12 个测试用例）

**验证结果**：
- 12 个新测试全部通过 ✅
- 20 个已有测试全部通过，无回归 ✅
- 单机模式：未设置 SENDER/RECEIVER 环境变量时，两端使用相同地址 ✅
- 双机模式：设置不同的 SENDER/RECEIVER 地址后，两端配置独立 ✅
- 向后兼容：无前缀的 `from_env()` 行为不变 ✅

**关键决策**：
- `from_env(prefix)` 采用三级回退策略：`COMFYUI_{PREFIX}_{KEY}` → `COMFYUI_{KEY}` → 默认值
- `SemanticTransmissionConfig` 为单机编排场景（demo_e2e.py）的便利封装；双机场景各端直接用 `ComfyUIConfig` 即可

**下一任务及关注点**：
- P2-07（实现-ComfyUI API 客户端）已解锁，依赖 P2-06
- P2-05（拆分-工作流 JSON）与 P2-07 无依赖关系，可并行推进
- P2-07 需参考 `scripts/test_comfyui_connection.py` 的 API 调用模式

**遗留问题**：无

### P2-05 拆分-工作流 JSON（2026-03-18）

**完成内容**：
- 将完整 ComfyUI 工作流拆分为发送端和接收端两个独立的 API 格式 JSON
- 发送端 4 节点：LoadImage(58) → ImageScaleToMaxDimension(62) → Canny(57) → SaveImage(100，新增)
- 接收端 14 节点：LoadImage(101，新增) + 12 个子图展开节点(39/46/40/64/45/42/60/69/41/47/44/43) + SaveImage(9)
- 关键改动：节点 60/69 的 image 输入从 ["57",0]（Canny）改为 ["101",0]（新 LoadImage）

**修改的文件**（2 个新建）：
- `resources/comfyui/sender_workflow_api.json`
- `resources/comfyui/receiver_workflow_api.json`

**验证结果**：
- 发送端 4 个节点，接收端 14 个节点 ✅
- 引用完整性：所有节点引用均指向同一 JSON 内的有效节点，无悬空引用 ✅
- 参数一致性：原有节点的参数与 WorkflowConverter 完整输出完全一致 ✅
- 关键改动：节点 60/69 的 image 正确指向新 LoadImage(101) ✅
- 端到端验证（需 ComfyUI 环境）：未执行，记录为后续验证项

**关键决策**：
- 采用手工编写方式（非 WorkflowConverter 自动生成），因为 converter 只能生成完整 API，无法直接拆分
- 新增节点 ID 选择 100/101，远离现有 ID 范围（9-69），避免冲突
- 发送端 LoadImage.image 使用占位符 "input_image.jpg"，运行时由 P2-08 动态注入
- 接收端 LoadImage.image 使用占位符 "canny_edge_00001_.png"，运行时由 P2-09 动态注入

**下一任务及关注点**：
- P2-07（实现-ComfyUI API 客户端）已解锁，与 P2-05 无依赖关系
- P2-08（实现-发送端调用）和 P2-09（实现-接收端调用）待 P2-07 完成后解锁
- P2-08 需注入发送端 JSON 的节点 "58".inputs.image（上传后的文件名）
- P2-09 需注入接收端 JSON 的节点 "101".inputs.image（边缘图文件名）、"45".inputs.text（prompt）、"44".inputs.seed（可选）
- 端到端验证需等 ComfyUI 环境可用后补充（P2-08/P2-09 实现时自然覆盖）

**遗留问题**：
- 端到端执行验证尚未完成（需 ComfyUI 实例运行），将在 P2-08/P2-09 实现时验证

### P2-07 实现-ComfyUI API 客户端（2026-03-19）

**完成内容**：
- 实现 `ComfyUIClient` 类，封装 ComfyUI REST API 的完整调用流程
- 四个核心方法：`upload_image`（上传图像）、`submit_workflow`（提交工作流）、`wait_for_completion`（轮询等待完成）、`get_result_images`（下载输出图像）
- 辅助方法：`check_health`（健康检查）、`_request`（统一 HTTP 封装）
- 三个自定义异常：`ComfyUIError`（基类）、`ComfyUIConnectionError`（连接失败）、`ComfyUITimeoutError`（等待超时）
- 编写 16 个 mock 测试覆盖成功路径、错误处理、超时、集成流程

**修改的文件**（2 个新建，1 个修改）：
- `src/semantic_transmission/common/comfyui_client.py`（新建）
- `tests/test_comfyui_client.py`（新建）
- `src/semantic_transmission/common/__init__.py`（修改：导出 ComfyUIClient 和异常类）

**验证结果**：
- 16 个新测试全部通过 ✅
- 48 个测试全部通过（含 20 个 workflow_converter + 12 个 config），无回归 ✅

**关键决策**：
- `wait_for_completion` 采用轮询 `/history` 而非 WebSocket（避免竞态，简化实现）
- `get_result_images` 接受 `history_entry` 参数而非 `prompt_id`（避免重复请求）
- `upload_image` 接受 `bytes` 而非文件路径或 PIL Image（保持客户端层职责纯粹）
- `submit_workflow` 接受 `dict` 而非 WorkflowConverter（保持通用性）
- 使用 `requests.Session()` 复用 TCP 连接

**下一任务及关注点**：
- P2-08（实现-发送端调用）和 P2-09（实现-接收端调用）已解锁，可并行推进
- P2-08 使用 `ComfyUIClient` 调用发送端工作流，注入节点 "58".inputs.image
- P2-09 使用 `ComfyUIClient` 调用接收端工作流，注入节点 "101".inputs.image、"45".inputs.text、"44".inputs.seed
- 两者都需要：读取工作流 JSON → 修改参数 → client.upload_image → client.submit_workflow → client.wait_for_completion → client.get_result_images

**遗留问题**：无
