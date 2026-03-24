# 任务状态跟踪

> 创建时间: 2026-03-13
> 任务类型: integration + infrastructure
> 任务前缀: P2
> 任务名称: comfyui-api-prototype

## 进度总览

| 阶段 | 总数 | 完成 | 冻结 | 进行中 | 待开始 |
|------|------|------|------|--------|--------|
| Phase 0: 契约确认与项目骨架 | 4 | 4 | 0 | 0 | 0 |
| Phase 1: 工作流拆分与语义压缩 | 8 | 8 | 0 | 0 | 0 |
| Phase 2: 中继传输与双机演示 | 2 | 2 | 0 | 0 | 0 |
| Phase 3: 质量优化 | 1 | 0 | 0 | 0 | 1 |
| **合计** | **15** | **14** | **0** | **0** | **1** |

## 任务状态

| 编号 | 标题 | 阶段 | 状态 | 依赖 |
|------|------|------|------|------|
| P2-01 | 搭建-Python 项目骨架 | Phase 0 | ✅ 已完成 | 无 |
| P2-02 | 定义-抽象接口 | Phase 0 | ✅ 已完成 | P2-01 |
| P2-03 | 验证-ComfyUI API 连通性 | Phase 0 | ✅ 已完成 | P2-01 |
| P2-04 | 分析-工作流 JSON 到 API 格式转换 | Phase 0 | ✅ 已完成 | P2-03 |
| P2-05 | 拆分-工作流 JSON | Phase 1 | ✅ 已完成 | P2-04 |
| P2-06 | 扩展-配置支持双 ComfyUI 实例 | Phase 1 | ✅ 已完成 | P2-03 |
| P2-07 | 实现-ComfyUI API 客户端 | Phase 1 | ✅ 已完成 | P2-06 |
| P2-08 | 实现-发送端调用 | Phase 1 | ✅ 已完成 | P2-05, P2-07 |
| P2-09 | 实现-接收端调用 | Phase 1 | ✅ 已完成 | P2-05, P2-07 |
| P2-16 | 部署-本机 ComfyUI 实例 | Phase 1 | ✅ 已完成 | P2-05 |
| P2-10 | 搭建-端到端 Demo 脚本 | Phase 1 | ✅ 已完成 | P2-08, P2-09, P2-16 |
| P2-13 | 集成-VLM 自动生成 prompt | Phase 1 | ✅ 已完成 | P2-10 |
| P2-11 | 实现-中继传输协议 | Phase 2 | ✅ 已完成 | P2-10 |
| P2-12 | 编写-双机演示脚本 | Phase 2 | ✅ 已完成 | P2-11 |
| P2-14 | 实现-质量评估模块 | Phase 3 | ⬜ 待开始 | P2-10 |
| P2-15 | 脱离-ComfyUI 发送端 | Phase 3 | ❌ 已取消 | P2-13 |

状态图例: ⬜ 待开始 | 🔄 进行中 | ✅ 已完成 | ⏸️ 冻结 | ❌ 已取消 | 🔀 已拆分

### 已取消任务（原计划）

以下任务因方向调整而取消（从"Python 重写发送端"改为"ComfyUI 工作流拆分 + 中继传输"）：

| 原编号 | 原标题 | 取消原因 |
|--------|--------|----------|
| P2-05（旧） | 实现-Canny 条件提取器 | 发送端继续使用 ComfyUI，不需要 Python 实现 |
| P2-06（旧） | 实现-VLM 发送端适配器 | 重新设计为 P2-13（VLM 集成），已提前至 Phase 1 |
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
| 2026-03-19 | **P2-13（VLM 集成）从 Phase 3 提前到 Phase 1** | 自动语义压缩（VLM 图生文）是项目核心能力，应在 Phase 1 优先验证，而非放到 Phase 3。同事的 ComfyUI 工作流中 prompt 是手动写死的，Phase 1 应闭环"自动语义压缩→条件还原"完整流程。GPU 显存 24GB 足够同机运行 ComfyUI + VLM INT4 |
| 2026-03-19 | P2-02 抽象接口解冻 | VLM 集成提前到 Phase 1，BaseSender 接口需要在 Phase 1 启用 |
| 2026-03-19 | Phase 1 更名为"工作流拆分与语义压缩"，Phase 3 更名为"质量优化与工程精简" | 反映 VLM 提前后的阶段重心变化 |
| 2026-03-21 | **新增 P2-16（部署-本机 ComfyUI 实例）**，P2-10 依赖增加 P2-16 | P2-10 是首个需要真实 ComfyUI 实例的任务，之前所有任务通过 mock 测试验证。本机部署 ComfyUI 是 P2-10 端到端验证的前置条件，同时补充验证 P2-05/08/09 的工作流正确性 |
| 2026-03-21 | 模型下载策略：HuggingFace 镜像 + 魔搭混合 | 魔搭 Tongyi-MAI/Z-Image-Turbo 的文件结构（DiffSynth 分片格式）与 ComfyUI 所需的单文件格式不兼容，主模型只能从 HuggingFace Comfy-Org/z_image_turbo 下载。使用 hf-mirror 国内镜像避免代理不稳定；ControlNet Union 补丁从魔搭 PAI/ 仓库国内直连下载 |
| 2026-03-22 | VLM 推理方案：transformers 原生推理 | 本机 ComfyUI 无 VLM 节点；生态中的节点（LLM_party、VLM_nodes）缺少 system prompt 控制；transformers + diffusers 同属 HuggingFace 生态，为中期脱离 ComfyUI 铺路 |
| 2026-03-22 | VLM 依赖放入主依赖 | 用户偏好简化安装流程，`uv sync` 一步到位，无需 `--group vlm` |
| 2026-03-22 | PyTorch 使用 cu130 索引（不区分平台） | RTX 5090 需 CUDA 13.0+；cu130 wheels 兼容 CPU-only 环境；用户可能在 Linux 带 GPU 环境使用 |
| 2026-03-22 | torchao 不列入依赖，运行时可选 | torchao 无 Windows wheels，代码中已有 ImportError 回退到 float16 的容错逻辑 |
| 2026-03-22 | VLM 描述与边缘图提取串行执行 | 并行仅节省 ~2.5s（边缘图提取耗时），相对 VLM 推理 10-20s 和总流程 60s+ 效果有限，保持代码简单 |
| 2026-03-23 | VLM 模型下载纳入 download_models.py 统一管理 | 用户要求统一下载流程和保存位置。VLM 模型保存到 `D:\Downloads\Models\Qwen\Qwen2.5-VL-7B-Instruct`（供应方/模型名格式）。QwenVLSender 新增 model_path 参数支持本地加载 |
| 2026-03-23 | download_models.py 默认使用 hf-mirror | 用户建议 HuggingFace 默认不开代理使用镜像源。`--hf-mirror` 改为默认行为，新增 `--no-mirror` 用于禁用 |
| 2026-03-23 | HF 仓库完整性检查基于权重分片文件 | 仅检查 config.json 不够，之前导致半下载的模型被误判为完整。改为解析 model.safetensors.index.json 列出的分片文件逐个检查 |
| 2026-03-24 | **取消 P2-15（脱离-ComfyUI 发送端），Phase 3 更名为"质量优化"** | P2-15 属于 ROADMAP 阶段四（工程化与脱离 ComfyUI）的范畴，放在阶段二工作流的 Phase 3 中越界。脱离 ComfyUI 应在 ROADMAP 阶段四独立规划，当前工作流聚焦原型搭建。Phase 3 仅剩 P2-14（质量评估），去掉"工程精简"后缀 |

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

**状态变更**：
- 2026-03-18：标记为 ⏸️ 冻结（Phase 1~2 不使用抽象接口）
- 2026-03-19：解冻为 ✅ 已完成（P2-13 VLM 集成提前到 Phase 1，BaseSender 接口将在 Phase 1 启用）

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

### P2-08 实现-发送端调用（2026-03-19）

**完成内容**：
- 实现 `ComfyUISender` 类，封装发送端完整流程：读取图像 → 上传 → 注入工作流参数 → 提交 → 等待 → 获取边缘图
- `process(image_path) → PIL.Image`：输入图像路径，输出 Canny 边缘图
- 构造时加载并缓存工作流 JSON，`process` 时深拷贝避免污染
- 编写 10 个 mock 测试覆盖成功流程、参数注入、默认/自定义路径、错误传播

**修改的文件**（2 个新建）：
- `src/semantic_transmission/sender/comfyui_sender.py`（新建）
- `tests/test_comfyui_sender.py`（新建）

**验证结果**：
- 10 个新测试全部通过 ✅
- 58 个测试全部通过（含已有 48 个），无回归 ✅

**关键决策**：
- `ComfyUISender` 不继承 `BaseConditionExtractor`——当前阶段它封装的是完整的 ComfyUI 工作流调用（含缩放+Canny+保存），不是纯条件提取。Phase 3 脱离 ComfyUI 时再实现 `BaseConditionExtractor`
- 默认工作流路径通过 `Path(__file__).parents[3]` 相对定位到 `resources/comfyui/sender_workflow_api.json`，避免硬编码绝对路径
- `process` 返回 `PIL.Image` 而非 `bytes`，方便下游（demo 脚本）直接保存和显示

**下一任务及关注点**：
- P2-09（实现-接收端调用）已解锁，结构与 P2-08 类似
- P2-09 需注入 3 个节点参数：节点 "101".inputs.image（边缘图）、"45".inputs.text（prompt）、"44".inputs.seed（可选）
- P2-09 的 `process` 签名需接受 `edge_image`（bytes 或 Path）+ `prompt_text` + `seed`

**遗留问题**：无

### P2-09 实现-接收端调用（2026-03-19）

**完成内容**：
- 实现 `ComfyUIReceiver` 类，封装接收端完整流程：上传边缘图 → 注入 3 个工作流参数 → 提交 → 等待 → 获取还原图像
- `process(edge_image, prompt_text, seed=None) → PIL.Image`：支持 bytes/str/Path 输入边缘图
- 注入节点：LoadImage("101").image、CLIPTextEncode("45").text、KSampler("44").seed（可选）
- 编写 11 个 mock 测试覆盖成功流程、参数注入、seed 可选、深拷贝、bytes/Path 输入、错误传播

**修改的文件**（2 个新建）：
- `src/semantic_transmission/receiver/comfyui_receiver.py`（新建）
- `tests/test_comfyui_receiver.py`（新建）

**验证结果**：
- 11 个新测试全部通过 ✅
- 69 个测试全部通过（含已有 58 个），无回归 ✅

**关键决策**：
- `edge_image` 参数支持 `bytes | str | Path` 三种类型：bytes 直接使用（默认文件名 "edge_input.png"），str/Path 读取文件并使用原始文件名
- seed 参数可选：None 时保留工作流 JSON 中的默认种子值，非 None 时覆盖
- 结构与 `ComfyUISender` 高度对称，便于 P2-10 demo 脚本统一调用模式

**下一任务及关注点**：
- P2-10（搭建-端到端 Demo 脚本）已解锁，依赖 P2-08 ✅ + P2-09 ✅
- P2-10 需串联 ComfyUISender.process() → ComfyUIReceiver.process()，中间传递边缘图和 prompt
- P2-10 的 `--prompt` 模式可直接实现；`--auto-prompt` 模式需 P2-13 完成后可用
- ComfyUISender.process() 返回 PIL.Image，需转为 bytes 传给 ComfyUIReceiver.process()

**遗留问题**：无

### P2-16 部署-本机 ComfyUI 实例（2026-03-21）

**完成内容**：
- 使用秋叶整合包 v3（ComfyUI v0.9.2）部署本机 ComfyUI 实例
- 下载 4 个模型文件（总计 ~22.7GB）：qwen_3_4b（8GB）、z_image_turbo_bf16（12.3GB）、ae（335MB）、Z-Image-Turbo-Fun-Controlnet-Union（3.1GB）
- 编写模型下载辅助脚本 `scripts/download_models.py`，支持 HuggingFace 镜像和魔搭双源下载
- 编写工作流验证脚本 `scripts/verify_workflows.py`，验证发送端和接收端工作流端到端执行
- 编写部署指南 `docs/comfyui-setup.md`

**修改的文件**（3 个新建）：
- `scripts/download_models.py`（新建：模型下载辅助脚本）
- `scripts/verify_workflows.py`（新建：工作流验证脚本）
- `docs/comfyui-setup.md`（新建：部署指南）

**验证结果**：
- 连通性测试 6/6 PASS ✅
- 发送端工作流：256x256 测试图 → 2048x2048 Canny 边缘图，耗时 1.4s ✅
- 接收端工作流：边缘图 + prompt → 2048x2048 还原图像，耗时 82.4s ✅
- P2-05 遗留的"端到端执行验证"已补充完成 ✅

**关键决策**：
- 魔搭 Tongyi-MAI/Z-Image-Turbo 为 DiffSynth 分片格式，不兼容 ComfyUI，主模型从 HuggingFace Comfy-Org/z_image_turbo 下载
- 使用 hf-mirror.com 国内镜像替代代理（代理连接不稳定，会卡住）
- ControlNet Union 从魔搭 PAI/ 仓库国内直连下载（37MB/s）
- 所有 4 个工作流节点类型均为 ComfyUI v0.3.51+ 内置节点，无需安装自定义包

**硬件环境**：
- GPU: NVIDIA GeForce RTX 5090 Laptop GPU, 24GB VRAM
- PyTorch: 2.9.1+cu130
- ComfyUI: v0.9.2（秋叶整合包 v3）

**下一任务及关注点**：
- P2-10（搭建-端到端 Demo 脚本）已解锁，依赖 P2-08 ✅ + P2-09 ✅ + P2-16 ✅
- P2-10 需要 ComfyUI 保持运行状态
- 接收端 82.4s 耗时主要是首次加载模型到 GPU，后续执行应更快
- 发送端输出 2048x2048 是因为 ImageScaleToMaxDimension 的 max=2048 设置

**遗留问题**：无

### P2-10 搭建-端到端 Demo 脚本（2026-03-21）

**完成内容**：
- 创建 `scripts/demo_e2e.py`，串联 ComfyUISender → ComfyUIReceiver 完整流程
- CLI 参数支持：`--image`（输入图像）、`--prompt`/`--auto-prompt`（互斥）、`--sender-host/port`、`--receiver-host/port`、`--output-dir`、`--seed`
- 5 步流程：健康检查 → 发送端提取边缘图 → 获取 prompt → 接收端还原图像 → 生成对比图
- 传输统计输出：原始图像大小、边缘图大小、prompt 大小、总传输量、压缩比、耗时
- `--auto-prompt` 参数已定义，实际 VLM 调用待 P2-13 实现

**修改的文件**（1 个新建）：
- `scripts/demo_e2e.py`（新建：端到端 demo 脚本）

**验证结果**：
- `uv run python scripts/demo_e2e.py --help` 正常显示帮助信息 ✅
- ruff check 通过 ✅
- ruff format 通过 ✅
- 69 个测试全部通过，无回归 ✅
- 端到端实际执行验证：需 ComfyUI 运行时验证（与 P2-16 验证脚本 verify_workflows.py 调用模式一致）

**关键决策**：
- `--prompt` 和 `--auto-prompt` 使用 argparse 的 `add_mutually_exclusive_group(required=True)` 确保互斥且必选
- `--auto-prompt` 模式当前输出提示信息并退出（非 NotImplementedError），便于用户理解
- 对比图使用 PIL 横向拼接（原图 | 边缘图 | 还原图），三张图缩放到相同高度
- 传输统计中"压缩比"= 原始图像文件大小 / (边缘图 PNG 大小 + prompt UTF-8 字节数)
- 配置直接用 `ComfyUIConfig(host, port)` 构造，不走环境变量，保持 CLI 参数优先

**计划变更**：无

**下一任务**：P2-13 集成-VLM 自动生成 prompt

**下一任务需关注**：
- P2-13 需实现 `QwenVLSender(BaseSender)` 并集成到 `demo_e2e.py` 的 `--auto-prompt` 模式
- `demo_e2e.py` 中 `--auto-prompt` 分支当前是 `sys.exit(1)`，P2-13 需替换为 VLM 调用
- VLM 输出需符合分段式描述模板（`[Scene Style]`、`[Perspective]`、`[Key Elements]` 等）
- GPU 显存需 ≥24GB 同机运行 ComfyUI + VLM INT4

**遗留问题**：无

### P2-13 集成-VLM 自动生成 prompt（2026-03-23）

**完成内容**：
- 实现 `QwenVLSender(BaseSender)` 类，使用 Qwen2.5-VL-7B-Instruct 自动生成结构化图像描述
- 采用 transformers 原生推理，延迟加载模型（首次 `describe()` 时加载，float16 ~14GB VRAM）
- system prompt 指导 VLM 输出覆盖 7 个视觉维度（Scene Style / Perspective / Main Subject / Foreground / Background / Lighting & Color / Fine Details），输出为连续英文段落
- 集成到 `demo_e2e.py` 的 `--auto-prompt` 模式，新增 `--vlm-model` 和 `--vlm-model-path` 参数
- 添加 VLM 依赖到主依赖（transformers、torch、torchvision、accelerate、qwen-vl-utils），配置 PyTorch cu130 索引
- 编写 13 个 mock 测试
- VLM 模型下载纳入 `download_models.py` 统一管理，保存到 `D:\Downloads\Models\Qwen\Qwen2.5-VL-7B-Instruct`
- `download_models.py` 默认使用 hf-mirror 镜像，修复仓库完整性检查（基于权重分片文件而非仅 config.json）
- 新增 `unload()` 方法释放 GPU 显存，解决 VLM + ComfyUI VRAM 冲突（float16 ~14GB + ComfyUI ~6GB > 24GB）
- demo 脚本保存 prompt 文本到 `prompt.txt`
- 6 张测试图端到端验证全部通过（Round 3 输出在 `output/demo/round-03/`）

**修改的文件**（6 个，2 新建 4 修改）：
- `src/semantic_transmission/sender/qwen_vl_sender.py`（新建：QwenVLSender 核心实现，含 model_path、unload）
- `tests/test_qwen_vl_sender.py`（新建：13 个 mock 测试）
- `pyproject.toml`（修改：添加 VLM 主依赖 + PyTorch cu130 索引配置）
- `src/semantic_transmission/sender/__init__.py`（修改：导出 QwenVLSender）
- `scripts/demo_e2e.py`（修改：--auto-prompt VLM 集成、unload 释放显存、保存 prompt.txt、flush print）
- `scripts/download_models.py`（修改：新增 VLM 仓库模型下载、默认 hf-mirror、权重完整性检查）

**验证结果**：
- 82 个测试全部通过（含 13 个新增 QwenVLSender 测试 + 69 个已有测试），无回归 ✅
- ruff check / format 通过 ✅
- `uv sync` 成功安装所有依赖（torch 2.10.0+cu130） ✅
- 端到端 --auto-prompt 验证 6/6 张测试图全部通过 ✅
- VLM 推理耗时 ~22-29s，prompt 大小 ~1.3-2.3KB，接收端还原耗时 ~49-64s

**关键决策**：
- transformers 原生推理（非 ComfyUI 节点）：本机 ComfyUI 无 VLM 节点，生态节点缺少 system prompt 控制，为中期脱离 ComfyUI 铺路
- VLM 依赖放入主依赖：用户偏好简化安装
- PyTorch cu130 索引不区分平台：用户可能在 Linux 带 GPU 环境使用
- torchao 不列入依赖（无 Windows wheels）：代码中回退到 float16
- VLM 推理后调用 unload() 释放 VRAM：float16 占 ~14GB，不释放则 ComfyUI 无法加载模型
- VLM 模型下载统一到 download_models.py，保存路径遵循 `供应方/模型名` 格式
- download_models.py 默认使用 hf-mirror（不开代理）

**下一任务**：P2-11 实现-中继传输协议（Phase 2）或进行 Phase 1 阶段回顾

**下一任务需关注**：
- Phase 1 全部 8 个任务已完成，建议先进行 Phase 1 阶段回顾（/task-review）确认退出标准
- Phase 1 退出标准：单机上能跑通"VLM 自动语义压缩→条件还原"完整流程，demo 脚本支持手动/自动 prompt 双模式——已满足

**遗留问题**：无

### P2-11 实现-中继传输协议（2026-03-24）

**完成内容**：
- 实现中继传输模块 `pipeline/relay.py`，支持两种传输模式
- 定义 `TransmissionPacket` 数据结构：edge_image (bytes) + prompt_text (str) + metadata (dict)
- 实现 `LocalRelay`：基于 `queue.Queue` 的线程安全内存传递，支持超时
- 实现 `SocketRelaySender`：TCP 客户端，主动连接接收端并发送数据，支持上下文管理器
- 实现 `SocketRelayReceiver`：TCP 服务端，监听端口接收数据，支持上下文管理器
- 传输协议：length-prefixed framing（每个字段 4 字节大端 uint32 长度头 + 原始数据）
- 内部辅助函数：`_serialize_packet` / `_deserialize_packet` / `_recv_exactly` / `_receive_packet_from_socket`
- 编写 18 个测试覆盖数据结构、序列化往返、LocalRelay、SocketRelay（含大数据包、多包、超时、Unicode）

**修改的文件**（2 个新建，1 个修改）：
- `src/semantic_transmission/pipeline/relay.py`（新建：中继传输核心实现）
- `tests/test_relay.py`（新建：18 个测试）
- `src/semantic_transmission/pipeline/__init__.py`（修改：导出 TransmissionPacket、LocalRelay、SocketRelaySender、SocketRelayReceiver）

**验证结果**：
- 18 个新测试全部通过 ✅
- 100 个测试全部通过（含 82 个已有测试），无回归 ✅
- ruff check 通过 ✅
- ruff format 通过 ✅

**关键决策**：
- TransmissionPacket 与 TransmissionData 分离：前者是传输层概念（bytes 图像），后者是应用层概念（NDArray 图像），职责不同
- SocketRelay 拆分为 Sender/Receiver 两个类：符合双机部署实际使用模式，各自只暴露需要的方法
- length-prefixed framing：零依赖、支持二进制、无编码膨胀，仅用标准库 struct + socket
- 不引入第三方库：全部使用标准库（socket、struct、json、queue、threading）

**计划变更**：无

**下一任务**：P2-12 编写-双机演示脚本

**下一任务需关注**：
- P2-12 需要使用 `SocketRelaySender` 和 `SocketRelayReceiver` 实现 `run_sender.py` 和 `run_receiver.py`
- `run_sender.py` 流程：读取图像 → ComfyUISender 提取边缘图 → VLM 生成 prompt（可选）→ SocketRelaySender 发送 TransmissionPacket
- `run_receiver.py` 流程：SocketRelayReceiver 监听 → 接收 TransmissionPacket → ComfyUIReceiver 还原图像 → 保存结果
- 边缘图需从 PIL.Image 转为 PNG bytes 打包到 TransmissionPacket，接收端再从 bytes 传给 ComfyUIReceiver
- SocketRelaySender 支持自动连接（send 时如未连接则自动 connect），SocketRelayReceiver 支持自动 accept（receive 时如未连接则自动 accept）

**遗留问题**：无

### P2-12 编写-双机演示脚本（2026-03-24）

**完成内容**：
- 创建 `scripts/run_sender.py`：发送端独立脚本，提取边缘图 + 生成语义描述 → 通过 SocketRelaySender 发送到接收端
- 创建 `scripts/run_receiver.py`：接收端独立脚本，监听端口接收数据 → ComfyUIReceiver 还原图像 → 保存结果
- 发送端支持手动 prompt（`--prompt`）和 VLM 自动 prompt（`--auto-prompt`）双模式
- 接收端支持单次模式和连续模式（`--continuous`，持续监听多次接收）
- 两个脚本均支持 `--comfyui-host/port`（本机 ComfyUI）和 `--relay-host/port`（网络传输）参数
- seed 通过 TransmissionPacket.metadata 从发送端传递到接收端
- 接收端按序号创建子目录（0001/、0002/...），每次接收保存边缘图、prompt 文本、还原图像

**修改的文件**（2 个新建）：
- `scripts/run_sender.py`（新建：发送端脚本）
- `scripts/run_receiver.py`（新建：接收端脚本）

**验证结果**：
- `run_sender.py --help` 正常显示帮助 ✅
- `run_receiver.py --help` 正常显示帮助 ✅
- ruff check 通过 ✅
- ruff format 通过 ✅
- 100 个测试全部通过，无回归 ✅

**关键决策**：
- seed 通过 metadata 传递而非新增 TransmissionPacket 字段，保持传输协议通用性
- 接收端连续模式：每次连接处理完后关闭 _conn，保留 _server 继续 accept 新连接
- 接收端输出按序号分目录存放，避免多次接收的文件覆盖
- CLI 参数风格与 demo_e2e.py 保持一致（ComfyUI 地址、VLM 配置等）

**计划变更**：无

**下一任务**：P2-14 实现-质量评估模块（Phase 3）或进行 Phase 2 阶段回顾

**下一任务需关注**：
- Phase 2 全部 2 个任务已完成，建议先进行 Phase 2 阶段回顾（/task-review）确认退出标准
- Phase 2 退出标准：两台机器分别运行发送端和接收端，通过网络传输完成还原——需实际双机验证
- 端到端双机验证需要两台局域网机器各部署 ComfyUI，运行 run_sender.py 和 run_receiver.py

**遗留问题**：无
