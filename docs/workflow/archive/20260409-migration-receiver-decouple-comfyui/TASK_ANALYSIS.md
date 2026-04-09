# 任务分析报告

## 迁移概述

**源系统**：基于 ComfyUI API 的接收端（通过 HTTP API 调用 ComfyUI 工作流执行图像生成）
**目标系统**：Python 直接调用模型推理的接收端（使用 diffusers 等库直接加载和运行生成模型）
**迁移动机**：脱离 ComfyUI 依赖，实现独立可部署的系统（路线图阶段四目标）；同时支持批量连续帧图像生成（阶段三目标）

**附带修复**：GUI 接收端 seed=0 被误判为未设置（issue #3）

## 系统映射

### 源系统组件（ComfyUI 方案）

| 组件 | 文件 | 职责 |
|------|------|------|
| ComfyUIReceiver | `src/semantic_transmission/receiver/comfyui_receiver.py` | 上传边缘图 → 注入 prompt/seed → 提交工作流 → 等待完成 → 下载结果 |
| ComfyUIClient | `src/semantic_transmission/common/comfyui_client.py` | HTTP API 封装（上传、提交、轮询、下载） |
| WorkflowConverter | `src/semantic_transmission/receiver/workflow_converter.py` | ComfyUI UI 格式 → API 格式转换 |
| BaseReceiver | `src/semantic_transmission/receiver/base.py` | 抽象基类（定义 `reconstruct` 接口） |
| ComfyUIConfig | `src/semantic_transmission/common/config.py` | ComfyUI 连接配置 |
| 工作流 JSON | `resources/comfyui/receiver_workflow_api.json` | Z-Image-Turbo + ControlNet Union 工作流定义 |

### 目标系统组件（Python 直接推理）

| 组件 | 对应关系 | 说明 |
|------|----------|------|
| DiffusersReceiver（新建） | 替代 ComfyUIReceiver | 使用 diffusers 库直接加载 SDXL-Turbo + ControlNet Union |
| BaseReceiver（保留） | 保持不变 | 抽象基类，新实现需继承 |
| 模型加载/卸载逻辑 | 新建 | 管理 GPU 显存，支持模型热加载卸载 |
| ComfyUIReceiver（保留） | 降级为备选 | 不删除，作为备用实现保留 |

### 功能对等性

| 功能 | ComfyUI 方案 | Python 直接推理 |
|------|-------------|-----------------|
| 图像生成 | Z-Image-Turbo 工作流 | diffusers StableDiffusionXLPipeline 或等效 |
| 条件控制 | ControlNet Union 节点 | diffusers ControlNetModel |
| Seed 控制 | KSampler 节点参数 | torch Generator seed |
| 单帧处理 | ✅ | ✅ |
| 批量连续帧 | ❌（需逐次提交） | ✅（循环调用，模型常驻） |

## 数据模型差异

### 现有数据类型（无需变更）

- `TransmissionData`：text + condition_image + metadata — 已有 metadata dict 可扩展
- `ReceiverOutput`：image + metadata
- `TransmissionPacket`（中继）：edge_image + prompt_text + metadata

### 需要新增/调整

- `BaseReceiver.reconstruct` 接口签名：当前只支持单帧，需考虑是否新增批量方法或保持单帧接口由外层循环
- 中继 `metadata` 字段：预留扩展位已存在（`dict[str, Any]`），无需结构变更
- 接收端配置：新增模型路径、设备等配置项（替代 ComfyUIConfig）

## API 兼容性分析

### 公共接口

1. **BaseReceiver.reconstruct(text, condition_image) → ReceiverOutput**
   - 保持不变，新实现需遵循此接口
   - 注意：ComfyUIReceiver 实际上没有继承 BaseReceiver，使用了自己的 `process` 方法

2. **ComfyUIReceiver.process(edge_image, prompt_text, seed) → Image**
   - 新的 DiffusersReceiver 应提供相同签名的 `process` 方法
   - 同时应正确继承 BaseReceiver

3. **GUI/CLI 调用点**：
   - `gui/receiver_panel.py:56-58` — 直接实例化 ComfyUIReceiver
   - `gui/pipeline_panel.py:271` — 直接实例化 ComfyUIReceiver
   - `cli/receiver.py:110` — 直接实例化 ComfyUIReceiver
   - `cli/demo.py:205` — 直接实例化 ComfyUIReceiver

### 不兼容点

- ComfyUIReceiver 的构造函数接受 `ComfyUIClient`，新实现需要不同的初始化参数（模型路径、设备等）
- GUI/CLI 中硬编码了 ComfyUIReceiver 实例化，需要改为工厂函数或配置切换

## 风险评估

### 高风险

1. **模型选型与加载**：当前使用的 Z-Image-Turbo 可能不在 diffusers hub 上直接可用，需确认模型来源和加载方式
2. **ControlNet Union 兼容性**：需确认 diffusers 对 ControlNet Union（promax）的支持程度
3. **GPU 显存管理**：接收端模型常驻 GPU 时的显存占用，与 VLM（发送端）的显存冲突

### 中风险

4. **生成质量一致性**：diffusers 直接推理的输出可能与 ComfyUI 工作流结果存在差异（采样器实现、调度器参数等）
5. **批量处理性能**：连续帧逐帧生成的总耗时可能较长

### 低风险

6. **seed=0 bug**：根因明确（`if seed` 对 0 求值为 False），修复简单
7. **接口兼容**：BaseReceiver 抽象基类设计合理，新实现只需继承

## 迁移策略建议

推荐 **Strangler Fig（绞杀者模式）**：

1. 保留 ComfyUIReceiver 不动，新建 DiffusersReceiver 作为并行实现
2. 通过配置/参数切换使用哪个实现
3. 验证新实现的生成质量与原实现对齐后，GUI/CLI 默认切换到新实现
4. ComfyUI 相关代码暂不删除，作为备用

理由：
- 风险最低，任何时候都可以回退到 ComfyUI 方案
- 便于对比两种实现的生成质量
- 不阻塞其他开发工作

## 补充检查项

### refactor 标签
- [x] 架构耦合点已识别：GUI/CLI 4 处硬编码 ComfyUIReceiver
- [x] 接口变更有兼容方案：保留旧实现，新实现并行

### bugfix 标签
- [x] 根因已定位：`receiver_panel.py:50` 和 `pipeline_panel.py:269` 中 `if seed` 对 0 求值为 False
- [x] 回归测试策略：新增 seed=0 的单元测试用例

## 待确认问题（已确认）

1. **模型选择**：继续使用 Z-Image-Turbo + ControlNet Union ✅
2. **diffusers 可用性**：Z-Image-Turbo 有 diffusers 支持（`ZImageControlNetPipeline`），权重在 `Tongyi-MAI/Z-Image-Turbo`；ControlNet Union 在 `alibaba-pai/Z-Image-Turbo-Fun-Controlnet-Union`。注意可能需要从源码安装 diffusers ✅
3. **单机 vs 双机场景**：双机接收端也改为直接推理，同时加上 ComfyUI/Diffusers 后端切换机制 ✅
