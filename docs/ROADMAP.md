# 语义传输项目路线图

## 阶段零：目标定义

实现一个视频语义压缩传输的端到端 demo：

- 发送端：视频 → 逐帧/关键帧语义描述（文本） + 结构化条件（边缘图/关键帧等）
- 传输层：仅传输文本描述和轻量条件信息（极低码率）
- 接收端：文本 + 条件 → 生成还原图像/视频

**目标升级（2026-06）**：由"端到端 demo"升级为**输入视频流、输出生成视频流**的程序，目标场景是替代无人车远程遥操作的视频画面（延迟/清晰度/帧间一致性尽量接近真实遥控）。分层交付——合同基础功能为保底，准实时遥控替代为真实目标。详见 [`docs/superpowers/specs/2026-06-21-video-stream-6day-plan-design.md`](superpowers/specs/2026-06-21-video-stream-6day-plan-design.md) 与技术方案 [`docs/research/2026-06-21-video-stream-tech-scout.md`](research/2026-06-21-video-stream-tech-scout.md)。

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
- [x] 实现中继传输协议（SocketRelaySender / SocketRelayReceiver；早期实验性 LocalRelay 已于 cleanup 阶段删除）
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
- 中继传输模块（SocketRelaySender / SocketRelayReceiver）
- 端到端 demo 脚本 + 双机演示脚本
- 端到端测试报告（`docs/test-reports/`）
- 质量评估模块和批量评估脚本
- 完整文档体系（开发指南、架构文档、使用指南、演示手册、项目总览）
- CLI 工具 `semantic-tx`（接收端完全脱离 ComfyUI，check 子命令重写为 vlm/diffusers/relay 三个独立角色）
- Gradio GUI（`semantic-tx gui`，6 个功能面板）
- ComfyUI 原型历史归档（`docs/archive/comfyui-prototype/`）

---

## 阶段三：视频流语义传输（当前主线，2026-06 启动）

**目标**：交付输入视频流、输出生成视频流的程序，逼近遥控可用的延迟/清晰度/一致性

**状态**：进行中。详细编排、风险兜底、验收口径见 [6 天冲刺规划设计](superpowers/specs/2026-06-21-video-stream-6day-plan-design.md)；技术选型依据见 [视频流技术方案](research/2026-06-21-video-stream-tech-scout.md) 与 [2026-06 综合评估](research/2026-06-reevaluation.md)。

**核心决策（已与负责人确认）**：保底优先+架构预留实时 / 帧生成主线 FLUX.2-klein-9B（Qwen-Image-Edit-2511 对照）/ 图生文 Qwen3-VL-4B（7 月升级）/ 目标版核心 KPI = 压短关键帧周期（接受插帧无法消除的 ~1s 语义滞后）/ 实时帧率靠 DLSS 式分层（关键帧大模型生成 + RIFE 插帧 + 超分）。

### 短期：6 天冲刺（6/22–6/27，激进塞目标版，留 6/28–30 余量）

| 日 | 主线 | ‖ 并行 PoC |
|---|---|---|
| D1 6/22 | `video_io.py` + 保底骨架跑通（video→帧→现有管道→帧→video） | H1：klein vs Qwen+InstantX 结构遵循度 |
| D2 6/23 | 保底接 relay 双机 + evaluation 逐帧/整段 | H2：klein 速度三档 + 下深度权重 |
| D3 6/24 | **保底版完成（M1，合同硬目标）** + 真实行车视频测试 | H3：帧间一致性 → 主线裁决 |
| D4 6/25 | 目标版起步：关键帧主线（512–768 低分常驻）+ 输出契约替换空钩子 | RIFE-TRT 环境 |
| D5 6/26 | 接 RIFE 插帧 → 关键帧+插帧平滑流 | 超分选型实测 |
| D6 6/27 | 接超分 + 流式 I/O 雏形 + 延迟/帧率/一致性测量 + 目标版 PoC 演示 | 写 7 月计划 |

**M1 红线**：D3 保底闭环必达；若 D1–D3 受阻，目标版让位，余量保保底。**保底版用现有 Z-Image 不依赖 klein**，klein 显存/质量风险不影响合同交付。

### 中期：目标版工程化（7 月）

- 主线模型优化打磨；流式 I/O 雏形 → 生产化（相机/RTSP 输入、编码回流、背压）
- 深度图升级 Video-Depth-Anything（时间一致）+ 深度图码率压缩
- Qwen3-VL-4B 升级（结构化/差分描述，transformers≥4.57）
- 压短关键帧周期（低分/TensorRT/激进蒸馏）；双机实时演示；N 按运动幅度自适应
- 质量评估扩展：帧间 LPIPS、光流 warping error、漂移斜率、码率-质量曲线

### 交付物

- 6/30 保底版：离线 video→video 闭环 + 质量指标 + 单/双机演示
- 目标版 PoC：关键帧+插帧+超分平滑流 + 端到端延迟/帧率/一致性测量
- 测试报告（`docs/test-reports/`）

---

## 阶段四：准实时遥控替代（最终，≥8 月）

**目标**：达到尽量替代远程遥控视频的画面输出

### 任务

- [ ] 关键帧周期压到目标 KPI（多卡/更激进蒸馏）
- [ ] 相机实时流端到端闭环（输入实际相机流，输出生成视频流）
- [ ] 鲁棒性：大运动/遮挡/突现物体的安全处理（突现物体靠压短关键帧周期 + 动态降 N，插帧无法"无中生有"）
- [ ] 模块化与可插拔模型后端、传输协议抽象（承接已统一的 ModelLoader / ProjectConfig）
- [ ] 生产化部署与演示材料

### 交付物

- 准实时遥控替代演示系统
- 技术文档和演示材料
