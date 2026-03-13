# 开源项目与框架评估

> 调研时间: 2026-03-13
> 覆盖范围: 语义通信开源项目、ComfyUI 生态、论文配套代码
> 评估项目数: 6 个

## 目录

1. [OpenSemanticComm — 语义通信开源代码合集](#1-opensemantcomm)
2. [DiffEIC — 扩散先验极端图像压缩](#2-diffeic)
3. [CDM-JSCC — 条件扩散模型联合源信道编码](#3-cdm-jscc)
4. [ComfyUI API 模式 — 工作流程序化调用](#4-comfyui-api-模式)
5. [ComfyUI-WanVideoWrapper — Wan2.x 视频生成节点](#5-comfyui-wanvideowrapper)
6. [ComfyUI-CogVideoXWrapper — CogVideoX 视频生成节点](#6-comfyui-cogvideoxwrapper)
7. [项目对比表](#项目对比表)
8. [对本项目的综合建议](#对本项目的综合建议)

---

## 1. OpenSemanticComm

### 语义通信开源代码合集

- **仓库**: [github.com/yang-hsiao/OpenSemanticComm](https://github.com/yang-hsiao/OpenSemanticComm)
- **Star / Fork**: 282 / 27
- **最近更新**: 2024-07
- **许可证**: 未明确标注

#### 功能概述

OpenSemanticComm 是一个语义通信领域的开源代码索引仓库，收录了 50+ 个语义通信相关的开源实现。涵盖 DJSCC（深度联合源信道编码）系列变体、扩散模型方案、Transformer 方案、多模态方案等。

该仓库本身不包含独立可运行的代码，而是作为一个**策展型索引**，汇集了各论文的配套代码链接。收录的关键项目包括：
- DeepJSCC 系列（DeepJSCC、DeepJSCC-f、DeepJSCC-l++）
- 扩散模型方案（CDDM、DiffJSCC、DM4ASC）
- Transformer 方案（SwinJSCC、WITT）
- 视频语义通信（Compression Ratio Learning for Video, Extreme Video Compression with Diffusion）

#### 技术栈

- 语言 / 框架：Python / PyTorch（收录项目的主流技术栈）
- 依赖的模型：各项目独立，涵盖 CNN、Transformer、扩散模型等
- 部署要求：各项目独立

#### 与本项目的关联

作为语义通信领域最全面的开源索引，可从中定位具体可复用的实现。特别是：
- DeepJSCC 系列可作为有信道噪声场景的基线参考
- 扩散模型方案（DiffJSCC、CDM-JSCC）与本项目接收端的生成式重建思路一致
- 视频语义通信项目可提供端到端的参考架构

#### 可复用性评估

| 维度 | 评估 | 说明 |
|------|------|------|
| 功能匹配度 | 中 | 索引型仓库，需跳转到具体项目 |
| 代码质量 | 中 | 各收录项目质量参差不齐 |
| 文档完整度 | 中 | 仅提供项目列表和论文链接 |
| 社区活跃度 | 低 | 2024-07 后未更新 |
| 集成难度 | 中 | 需从具体项目中提取可用组件 |
| **综合可复用性** | **中** | 作为项目发现入口有价值，但不能直接复用 |

#### 备注

建议将此仓库作为持续跟踪的信息源，定期检查新收录的项目。

---

## 2. DiffEIC

### 扩散先验极端图像压缩

- **仓库**: [github.com/huai-chang/DiffEIC](https://github.com/huai-chang/DiffEIC)
- **Star / Fork**: 101 / 12
- **最近更新**: 2024-04
- **许可证**: Apache-2.0

#### 功能概述

DiffEIC（Diffusion-based Extreme Image Compression）实现了基于扩散先验的极端图像压缩。系统分两阶段：第一阶段使用 VAE 将图像压缩为潜在表示作为引导；第二阶段利用预训练的 Stable Diffusion v2.1 在引导下重建图像。通过小型控制模块（类似 ControlNet）注入内容信息，保持 SD 模型固定。

支持 5 个压缩级别：0.12 / 0.09 / 0.06 / 0.04 / 0.02 bpp，在极低码率下显著优于传统方法。

同团队还有后续工作 RDEIC（[github.com/huai-chang/RDEIC](https://github.com/huai-chang/RDEIC)），引入残差扩散加速推理。

#### 技术栈

- 语言 / 框架：Python 3.8 / PyTorch 2.0.1
- 依赖的模型：Stable Diffusion v2.1、ELIC 压缩模型
- 部署要求：GPU（具体显存需求未明确）、预训练权重下载
- 训练数据：LSDIR 数据集
- 推理：支持批处理，50 步扩散采样

#### 与本项目的关联

DiffEIC 的"潜在特征引导 + 扩散重建"架构与本项目接收端的设计目标高度一致。可参考其：
- 控制模块设计（如何将压缩信息注入扩散模型）
- 多码率支持机制（5 级可配置）
- 与 GSC 论文的方法论类似，但 DiffEIC 有完整开源代码

#### 可复用性评估

| 维度 | 评估 | 说明 |
|------|------|------|
| 功能匹配度 | 高 | 极端图像压缩+扩散重建，与接收端需求匹配 |
| 代码质量 | 中 | 基于成熟框架，但文档较简 |
| 文档完整度 | 中 | 有 README 和预训练权重，缺详细使用指南 |
| 社区活跃度 | 低 | 2024-04 后未更新 |
| 集成难度 | 中 | 需要适配到本项目的数据流 |
| **综合可复用性** | **中-高** | 控制模块和压缩管线可直接参考 |

#### 备注

DiffEIC 仅处理图像，不支持视频。但其架构设计可扩展到逐帧处理。

---

## 3. CDM-JSCC

### 条件扩散模型联合源信道编码

- **仓库**: [github.com/zhang-guangyi/cdm-jscc](https://github.com/zhang-guangyi/cdm-jscc)
- **Star / Fork**: 17 / —
- **最近更新**: 2024-11
- **许可证**: 未明确标注

#### 功能概述

CDM-JSCC 实现了基于条件扩散模型的码率自适应生成式语义通信系统。核心创新是将信道噪声和压缩失真统一建模为扩散过程的一部分，使用条件扩散模型同时完成去噪和图像重建。

该项目是少数将**生成式 AI + 联合源信道编码 + 码率自适应**三者结合的开源实现。

#### 技术栈

- 语言 / 框架：Python / PyTorch
- 依赖的模型：扩散模型（自训练）
- 部署要求：GPU

#### 与本项目的关联

- 码率自适应机制对本项目不同带宽场景下的应用有参考价值
- 联合源信道编码的思路在无线传输场景中优于分离式设计
- 如果本项目后续考虑信道噪声（无线传输），CDM-JSCC 是重要的参考实现

#### 可复用性评估

| 维度 | 评估 | 说明 |
|------|------|------|
| 功能匹配度 | 中 | 偏学术研究，与工程实现有距离 |
| 代码质量 | 中 | 论文配套代码，可运行性待验证 |
| 文档完整度 | 低 | 论文配套代码，文档有限 |
| 社区活跃度 | 低 | Star 数少，更新不频繁 |
| 集成难度 | 高 | 需要显著改造才能用于本项目 |
| **综合可复用性** | **低-中** | 适合作为技术参考，不适合直接集成 |

#### 备注

同作者还有 Semantic-MDJCM（20 Stars），是多描述联合编码的扩展实现。

---

## 4. ComfyUI API 模式

### 工作流程序化调用

- **仓库**: [github.com/comfyanonymous/ComfyUI](https://github.com/comfyanonymous/ComfyUI)
- **文档**: [docs.comfy.org](https://docs.comfy.org/development/comfyui-server/comms_routes)
- **Star / Fork**: 80k+ / —
- **最近更新**: 持续活跃
- **许可证**: GPL-3.0

#### 功能概述

ComfyUI 提供完整的 REST API 和 WebSocket 接口，支持工作流的程序化执行。本项目阶段二将基于此 API 集成发送端和接收端。

**核心 API 端点**：

| 端点 | 方法 | 功能 |
|------|------|------|
| `/prompt` | POST | 提交工作流到队列执行，返回 `prompt_id` |
| `/prompt` | GET | 获取当前队列状态 |
| `/queue` | GET | 查看执行队列状态 |
| `/queue` | POST | 管理队列（清空等） |
| `/history/{prompt_id}` | GET | 获取指定任务的执行结果 |
| `/view` | GET | 获取生成的图像（按文件名） |
| `/upload/{image_type}` | POST | 上传图像/掩码 |
| `/interrupt` | POST | 中断当前执行 |
| `/object_info` | GET | 获取节点类型信息 |
| `/ws` | WebSocket | 实时双向通信（进度、状态、预览） |

**WebSocket 消息类型**：`status`、`execution_start`、`execution_cached`、`executing`、`progress`、`executed`

**典型调用流程**：
1. `GET /object_info` — 获取节点目录
2. 构建/加载工作流 JSON
3. `POST /prompt` — 提交工作流，获取 `prompt_id`
4. `ws://host/ws?clientId=xxx` — 监听执行进度
5. `GET /history/{prompt_id}` — 获取执行结果
6. `GET /view?filename=xxx` — 下载生成图像

#### 技术栈

- 语言 / 框架：Python / aiohttp
- 依赖的模型：由工作流定义
- 部署要求：GPU（根据工作流中使用的模型）

#### 与本项目的关联

ComfyUI API 是本项目阶段二的**核心集成点**。通过 API 可以：
- 将现有 ComfyUI 工作流（Z-Image-Turbo + ControlNet Union）封装为接收端服务
- 动态修改工作流参数（prompt 文本、条件图像、采样步数等）
- 实时监控生成进度和获取结果
- 后续可通过 API 灵活替换工作流中的节点/模型

#### 可复用性评估

| 维度 | 评估 | 说明 |
|------|------|------|
| 功能匹配度 | 高 | 直接满足工作流程序化调用需求 |
| 代码质量 | 高 | 成熟的开源项目，80k+ Stars |
| 文档完整度 | 高 | 官方文档完整，社区教程丰富 |
| 社区活跃度 | 高 | 持续活跃开发 |
| 集成难度 | 低 | REST API + WebSocket，标准接口 |
| **综合可复用性** | **高** | 阶段二的核心基础设施 |

#### 备注

- 需要注意 ComfyUI 运行在远程服务器上时的网络配置（`--listen 0.0.0.0`）
- 大文件（图像/视频）的上传下载可能需要优化传输效率
- 第三方封装 [SaladTechnologies/comfyui-api](https://github.com/SaladTechnologies/comfyui-api) 提供了生产级 API 封装

---

## 5. ComfyUI-WanVideoWrapper

### Wan2.x 视频生成节点

- **仓库**: [github.com/kijai/ComfyUI-WanVideoWrapper](https://github.com/kijai/ComfyUI-WanVideoWrapper)
- **Star / Fork**: 6,200 / 598
- **最近更新**: 2025-02（持续活跃）
- **许可证**: 未明确标注

#### 功能概述

kijai 开发的 ComfyUI 自定义节点包，封装了阿里巴巴 Wan2.1/2.2 视频生成模型。支持文生视频（T2V）和图生视频（I2V），提供多种模型尺寸（1.3B / 14B）。

**支持的模型/功能**：
- Wan2.1/2.2 核心模型（T2V、I2V）
- SkyReels、WanVideoFun、ReCamMaster、VACE
- Phantom、ATI、Uni3C、FantasyTalking
- 支持最长 1025 帧的上下文窗口处理
- FP8 量化支持，VRAM 管理和块级 offloading

**依赖节点**：ComfyUI-VideoHelperSuite、ComfyUI-KJNodes

#### 技术栈

- 语言 / 框架：Python / PyTorch / ComfyUI
- 依赖的模型：Wan2.1/2.2（1.3B-14B）、CLIP、VAE
- 部署要求：GPU（14B 模型需大显存，FP8 量化可降低需求）
- 存储路径：`ComfyUI/models/diffusion_models/`、`text_encoders/`、`vae/`

#### 与本项目的关联

Wan2.x 是本项目接收端**视频生成**的重要候选。相比当前工作流仅支持图像生成（Z-Image-Turbo），Wan2.x 可以：
- 从文本描述直接生成视频（T2V 模式）
- 从首帧+文本生成后续帧（I2V 模式，与 GVSC 的 First Frame+Desc 方案吻合）
- 通过 ControlNet 类扩展实现条件控制

#### 可复用性评估

| 维度 | 评估 | 说明 |
|------|------|------|
| 功能匹配度 | 高 | 视频生成能力直接满足接收端需求 |
| 代码质量 | 高 | 活跃维护，6k+ Stars |
| 文档完整度 | 中 | 有 README 和示例工作流，但缺系统文档 |
| 社区活跃度 | 高 | 持续更新，支持最新模型 |
| 集成难度 | 低 | 通过 ComfyUI API 调用即可 |
| **综合可复用性** | **高** | 接收端视频生成的首选方案 |

#### 备注

14B 模型显存需求较高，建议先用 1.3B 模型验证流程，再评估是否需要升级。

---

## 6. ComfyUI-CogVideoXWrapper

### CogVideoX 视频生成节点

- **仓库**: [github.com/kijai/ComfyUI-CogVideoXWrapper](https://github.com/kijai/ComfyUI-CogVideoXWrapper)
- **Star / Fork**: ~3k+ / —
- **最近更新**: 持续活跃
- **许可证**: 未明确标注

#### 功能概述

同为 kijai 开发的 ComfyUI 节点包，封装了智谱 AI 的 CogVideoX 视频生成模型。CogVideoX 采用 3D Causal VAE + Expert Transformer 架构，支持文生视频。

**核心节点**：
- CogVideoTextEncode：文本 prompt 编码（CLIP 模型）
- CogVideoSampler：视频采样
- CogVideoDecode：视频解码
- DownloadAndLoadCogVideoModel：模型加载

CogVideoX-5B 是其主力模型，在文生视频质量和一致性上表现良好。

#### 技术栈

- 语言 / 框架：Python / PyTorch / ComfyUI
- 依赖的模型：CogVideoX-5B（5B 参数）
- 部署要求：GPU，显存需求中等（5B 参数）

#### 与本项目的关联

CogVideoX 是 Wan2.x 之外的视频生成备选方案。如果 Wan2.x 在特定场景下表现不佳（如时序一致性），CogVideoX 的 3D Causal VAE 架构可能提供更好的时序建模。

#### 可复用性评估

| 维度 | 评估 | 说明 |
|------|------|------|
| 功能匹配度 | 高 | 视频生成能力满足接收端需求 |
| 代码质量 | 高 | 活跃维护 |
| 文档完整度 | 中 | 有示例工作流 |
| 社区活跃度 | 高 | 持续更新 |
| 集成难度 | 低 | 通过 ComfyUI API 调用 |
| **综合可复用性** | **高** | 视频生成备选方案 |

#### 备注

CogVideoX 由智谱 AI 开发，模型参数量（5B）比 Wan2.x 14B 更轻量，适合作为快速验证方案。

---

## 项目对比表

| 项目 | 类型 | Star | 活跃度 | 可复用性 | 本项目用途 |
|------|------|------|--------|----------|-----------|
| OpenSemanticComm | 索引合集 | 282 | 低 | 中 | 技术发现入口 |
| DiffEIC | 图像压缩 | 101 | 低 | 中-高 | 接收端架构参考 |
| CDM-JSCC | 联合编码 | 17 | 低 | 低-中 | 信道适应参考 |
| ComfyUI API | 基础设施 | 80k+ | 高 | **高** | 阶段二核心集成 |
| WanVideoWrapper | 视频生成 | 6.2k | 高 | **高** | 接收端视频生成 |
| CogVideoXWrapper | 视频生成 | 3k+ | 高 | **高** | 视频生成备选 |

---

## 对本项目的综合建议

### 1. ComfyUI API 是阶段二的核心路径

ComfyUI 的 REST API + WebSocket 接口成熟可靠，建议阶段二直接基于此搭建原型：
- 用 Python 封装 ComfyUI API 客户端
- 通过 `POST /prompt` 提交工作流
- 通过 WebSocket 监控进度
- 通过 `/history` 和 `/view` 获取结果

### 2. 视频生成节点推荐优先级

1. **Wan2.x**（首选）：生态最活跃（6.2k Stars），支持 I2V（首帧→视频），与 GVSC 论文的 First Frame+Desc 方案匹配
2. **CogVideoX**（备选）：参数更轻量（5B），3D Causal VAE 时序建模可能更优
3. **当前 Z-Image-Turbo**（基线）：仅支持图像，但速度最快（9 步采样）

### 3. 学术项目的参考价值

- **DiffEIC**：潜在特征引导 + 扩散重建的架构设计可借鉴到本项目的接收端
- **CDM-JSCC**：如果后续需要考虑无线信道噪声，其联合编码方案是重要参考
- **OpenSemanticComm**：作为持续跟踪的信息源

### 4. 论文配套代码现状

G-03 调研的 6 篇核心论文均未完全开源。开源生态中可用的实现主要集中在：
- 图像级压缩+重建（DiffEIC、RDEIC）
- DJSCC 基础实现（OpenSemanticComm 收录）
- ComfyUI 生态的生成模型节点

**端到端的视频语义通信开源系统尚不存在**，本项目需要自行组装各组件。

### 5. 建议的技术栈组合

```
发送端                    传输                    接收端
┌─────────────┐     ┌──────────┐     ┌──────────────────┐
│ Qwen-VL     │     │          │     │ ComfyUI API      │
│ (图像描述)   │ ──→ │ 文本     │ ──→ │ ├─ Wan2.x (视频)  │
│             │     │ +        │     │ ├─ Z-Image-Turbo  │
│ Canny/分割   │ ──→ │ 条件图   │ ──→ │ │  (图像, 基线)   │
│ (条件提取)   │     │          │     │ └─ ControlNet     │
└─────────────┘     └──────────┘     └──────────────────┘
                                      通过 REST API 调用
```
