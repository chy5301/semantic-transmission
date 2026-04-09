# 语义传输项目路线图

## 阶段零：目标定义

实现一个视频语义压缩传输的端到端 demo：

- 发送端：视频 → 逐帧/关键帧语义描述（文本） + 结构化条件（边缘图/关键帧等）
- 传输层：仅传输文本描述和轻量条件信息（极低码率）
- 接收端：文本 + 条件 → 生成还原图像/视频

---

## 阶段一：调研与方案选型 ✅ 已完成

**目标**：了解领域现状，确定技术路线

### 任务

- [x] 收集语义传输/语义通信领域核心论文（6 篇：GVSC、GVC、GSC、M3E-VSC、CPSGD、HFCVD）
- [x] 调研开源项目和可复用的实现（6 个：OpenSemanticComm、DiffEIC、CDM-JSCC、ComfyUI API、WanVideoWrapper、CogVideoXWrapper）
- [x] 分析现有 ComfyUI 工作流（Z-Image-Turbo + ControlNet Union 节点拓扑、数据流、模型依赖）
- [x] 调研关键模型能力
  - 视觉理解：Qwen2.5-VL（3B/7B/72B）、InternVL2.5、LLaVA-OV、GPT-4o、Gemini 2.0 Flash
  - 图像生成：Z-Image-Turbo、FLUX.1、SD 3.5、SDXL Lightning
  - 视频生成：Wan2.1/2.2、CogVideoX、HunyuanVideo 1.5、SVD-XT
  - ControlNet 条件：Canny、Depth、Normal、语义分割、Lineart、HED、OpenPose、Tile（8 种）
- [x] 形成调研报告和选型建议

### 关键选型结论

| 维度 | 主选 | 备选 |
|------|------|------|
| 发送端 VLM | Qwen2.5-VL-7B | InternVL2.5-8B |
| 图像生成 | Z-Image-Turbo（8 步，6GB） | FLUX.1 schnell（高质量模式） |
| 视频生成 | Wan2.1（VBench 第一） | HunyuanVideo 1.5 |
| 条件控制 | Canny → Canny+Depth（渐进） | 长期：GSC 编码潜在通道 |
| 集成框架 | ComfyUI REST API + WebSocket | — |

### 交付物

- `docs/research/` 下的调研报告（详见 [selection-report.md](research/selection-report.md)）

---

## 阶段二：原型搭建（ComfyUI API → Diffusers 本地推理）

**目标**：打通端到端流程，验证可行性，最终脱离外部 ComfyUI 依赖

**状态**：已完成。原基于 ComfyUI API 实现，后由 `receiver-decouple-comfyui` workflow（2026-04）迁移到 Diffusers 本地推理，ComfyUI 运行时代码已完全清除并归档至 `docs/archive/comfyui-prototype/`。

### 任务

- [x] 确认 ComfyUI 部署环境（远程服务器或本地安装）
- [x] 搭建 ComfyUI API 调用环境
  - ComfyUI 以 `--listen` 模式启动
  - Python 封装 REST API 客户端（POST /prompt、GET /history、WebSocket 监听）
- [x] 集成发送端 VLM：Qwen2.5-VL-7B（Transformers 原生推理，INT4 量化）
- [x] 封装发送端模块
  - 输入：图像/视频文件
  - 处理：ComfyUI 工作流 Canny 边缘提取 + VLM 自动生成语义描述
  - 输出：Canny 条件图 + 文本描述
- [x] 封装接收端模块
  - 输入：文本描述 + 条件图像
  - 处理：动态构建工作流 JSON → ComfyUI API 提交 → 获取结果
  - 输出：Z-Image-Turbo + ControlNet Union 还原的图像
- [x] 搭建端到端 pipeline
  - 图像 → 发送端 → 序列化传输数据 → 接收端 → 还原图像
- [x] 实现中继传输协议（LocalRelay + SocketRelay）
- [x] 双机部署：`semantic-tx sender` / `semantic-tx receiver` CLI 子命令（原 run_sender.py / run_receiver.py 已归档）
- [x] 初步评估还原质量
  - 质量评估模块：PSNR、SSIM、LPIPS、CLIP Score
  - 批量评估脚本：逐样本指标 + 汇总统计 + JSON 报告
- [x] CLI 正规化：click 框架统一入口 `semantic-tx`（sender/receiver/demo/batch-demo/check/download/gui）
- [x] Gradio GUI 开发：6 个功能面板（配置 / 单张发送 / 批量发送 / 接收端 / 端到端演示 / 批量端到端）
- [x] **接收端迁移到 Diffusers 本地推理**（2026-04）：`DiffusersReceiver` 使用 Z-Image-Turbo GGUF Q8_0 transformer + ControlNet Union 分组件加载；删除 `common/comfyui_client.py` / `receiver/comfyui_receiver.py` / `sender/comfyui_sender.py`；CLI `check` 子命令重写为 `check vlm` / `check diffusers` / `check relay`；GUI 接收端 Tab 改为队列模式，批量端到端 Tab 改为 Accordion 展示 + 可选质量评估

### 交付物

- 可运行的发送端/接收端 Python 模块
- VLM 自动语义描述生成（QwenVLSender）
- 中继传输模块（LocalRelay + SocketRelay）
- 端到端 demo 脚本 + 双机演示脚本
- 端到端测试报告（`docs/test-reports/`）
- 质量评估模块和批量评估脚本
- 完整文档体系（开发指南、架构文档、使用指南、演示手册、项目总览）
- CLI 工具 `semantic-tx`（接收端完全脱离 ComfyUI，check 子命令重写为 vlm/diffusers/relay 三个独立角色）
- Gradio GUI（`semantic-tx gui`，6 个功能面板）
- ComfyUI 原型历史归档（`docs/archive/comfyui-prototype/`）

---

## 阶段三：方案迭代与优化

**目标**：提升还原质量，优化压缩效率

### 任务

- [ ] 优化语义描述策略
  - 设计结构化 prompt 模板：[场景风格]/[视角]/[主体元素]/[空间关系]/[背景]/[光照]
  - 关键帧选取策略优化（场景切换检测、运动估计等）
  - 多帧间语义一致性维护（差分描述，参考 M3E-VSC）
- [ ] 升级条件控制
  - 增加 Depth 条件（Depth Anything V2），实现 Canny+Depth 双条件融合
  - 对比单条件 vs 双条件的还原质量提升
  - 探索低分辨率图像条件（保留颜色信息，参考 HFCVD）
- [ ] 集成视频生成
  - 通过 WanVideoWrapper 集成 Wan2.1 I2V 模式
  - 实现"首帧+文本描述 → 视频序列"流程（参考 GVSC）
  - 评估 1.3B 版本（快速原型）vs 14B 版本（质量上限）
- [ ] 替换/升级核心模型
  - 测试 FLUX.1 schnell 作为高质量图像生成备选
  - 评估 InternVL2.5-8B 作为发送端 VLM 备选
- [ ] 质量评估体系完善
  - 多组对比实验：不同条件 × 不同模型 × 不同码率
  - 码率-质量曲线绘制

### 交付物

- 优化后的 pipeline（支持图像+视频、多条件）
- 多组对比实验数据和分析

---

## 阶段四：工程化与部署

**目标**：构建独立可部署的系统

**状态**：阶段二已完成接收端脱离 ComfyUI（Diffusers 本地推理），本阶段聚焦部署形态和模块化

### 任务

- [x] 脱离 ComfyUI，接收端使用 Diffusers 直接推理（阶段二已完成）
- [ ] 模块化架构设计
  - 发送端 SDK / 接收端 SDK
  - 可插拔的模型后端
  - 传输协议抽象层
- [ ] 性能优化
  - 模型量化与加速
  - 批处理和并行推理
  - 端到端延迟优化
- [ ] 构建演示系统
  - 可视化对比界面（原始 vs 还原）
  - 压缩率和质量的可调参数

### 交付物

- 独立部署的语义传输 demo 系统
- 技术文档和演示材料
