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

## 阶段二：基于 ComfyUI API 的原型搭建

**目标**：打通端到端流程，验证可行性

### 前置条件

- ComfyUI 工作流已分析完成（阶段一 G-02），节点拓扑和数据流已明确
- ComfyUI API 端点已记录（阶段一 G-04），7 个核心端点 + WebSocket 调用流程

### 任务

- [x] 确认 ComfyUI 部署环境（远程服务器或本地安装）
- [x] 搭建 ComfyUI API 调用环境
  - ComfyUI 以 `--listen` 模式启动
  - Python 封装 REST API 客户端（POST /prompt、GET /history、WebSocket 监听）
- [ ] 部署发送端 VLM：Qwen2.5-VL-7B（vLLM/Transformers，单卡 RTX 4090）
- [x] 封装发送端模块
  - 输入：图像/视频文件
  - 处理：ComfyUI 工作流 Canny 边缘提取（VLM 生成结构化描述待 P2-13）
  - 输出：Canny 条件图（文本描述待 P2-13）
- [x] 封装接收端模块
  - 输入：文本描述 + 条件图像
  - 处理：动态构建工作流 JSON → ComfyUI API 提交 → 获取结果
  - 输出：Z-Image-Turbo + ControlNet Union 还原的图像
- [x] 搭建端到端 pipeline
  - 图像 → 发送端 → 序列化传输数据 → 接收端 → 还原图像
- [ ] 初步评估还原质量
  - 主要指标：CLIP Score、LPIPS（感知质量）
  - 辅助指标：PSNR、SSIM（像素精确度，生成式方案非强项）
  - 记录传输码率（文本 + 条件图的数据量）

### 交付物

- 可运行的发送端/接收端 Python 模块
- 端到端 demo 脚本
- 初步质量评估数据（含码率-质量权衡分析）

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

## 阶段四：工程化与脱离 ComfyUI

**目标**：构建独立可部署的系统

### 任务

- [ ] 完全脱离 ComfyUI，用 Python 代码直接实现推理流程
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
