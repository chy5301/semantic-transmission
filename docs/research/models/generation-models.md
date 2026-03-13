# 图像与视频生成模型对比（接收端模型选型）

> 更新时间：2026-03-13
> 用途：语义传输项目接收端——从文本描述+结构条件还原图像/视频

## 模型总览对比表

### 图像生成模型

| 维度 | Z-Image-Turbo | FLUX.1 schnell | FLUX.1 dev | SD 3.5 Large/Turbo | SD 3.5 Medium | SDXL Lightning |
|------|--------------|----------------|------------|--------------------|--------------:|----------------|
| 开发者 | 阿里巴巴通义 | Black Forest Labs | Black Forest Labs | Stability AI | Stability AI | ByteDance |
| 参数量 | 6B | 12B DiT + 4.5B 文本编码器 | 同左 | 8B | 2.6B | ~3.5B (基于 SDXL) |
| 许可证 | Apache 2.0 | Apache 2.0 | 非商用 | 社区许可证 | 社区许可证 | 开放权重 |
| 最少采样步数 | 8 步 | 4 步 | 20-50 步 | Turbo: 4 步 | 4 步 | 1-4 步 |
| 显存 (FP16) | ~6GB | ~24GB | ~24GB | ~18-24GB | ~6-8GB | ~8-12GB |
| ControlNet | Union (多模态统一) | 官方 Canny/Depth | 同左 | 官方 Canny/Depth/Blur | 同左 | 社区验证 |
| ComfyUI 集成 | 原生支持 | 原生支持 | 原生支持 | 原生支持 | 原生支持 | 原生支持 |

### 视频生成模型

| 维度 | Wan2.1 (14B/1.3B) | Wan2.2 A14B | CogVideoX (2B/5B) | HunyuanVideo 1.5 | SVD-XT |
|------|-------------------|-------------|--------------------|--------------------|--------|
| 开发者 | 阿里巴巴 | 阿里巴巴 | 智谱 AI | 腾讯混元 | Stability AI |
| 参数量 | 14B / 1.3B | MoE 27B 总 / 14B 激活 | 2B / 5B | 8.3B | 1.5B |
| 许可证 | Apache 2.0 | Apache 2.0 | CogVideoX License | Apache 2.0 (地域限制) | 研究/非商用 |
| 帧数/时长 | 可变，支持长视频 | 同左 | 48 帧 / 6 秒 | 121 帧 / 720p | 25 帧 (XT) |
| 分辨率 | 最高 8K，常用 720p/1080p | 同左 | 720×480 | 720p | 1024×576 |
| 显存需求 | 1.3B: 8GB; 14B: 24-80GB | 14B 激活: 24-80GB | 2B: 18GB; 5B: 26GB | 最低 14GB（优化后 6GB） | 8-10GB |
| 推理速度 | ~9 分/5 秒片段 (4090, 14B) | 更快 (MoE 优化) | ~90 秒/视频 (A100, 5B) | ~75 秒/视频 (4090) | 秒级/帧 |
| ControlNet | Fun-Control + 8 步快速 LoRA | 同左 | 社区 HED/Canny | 社区 Depth | 社区支持 |
| ComfyUI | 原生 + WanVideoWrapper | 原生支持 | CogVideoXWrapper | 原生支持 | 插件支持 |
| VBench | 86.22%（第一） | 更高 | 较高 | 较高 | 中等 |

---

## 1. Z-Image-Turbo

### 基本信息

- **开发者 / 机构**：阿里巴巴通义实验室 (Tongyi-MAI)
- **参数量**：6B
- **发布时间**：2025 年 11 月
- **许可证**：Apache 2.0
- **HuggingFace**：[Tongyi-MAI/Z-Image-Turbo](https://huggingface.co/Tongyi-MAI/Z-Image-Turbo)
- **GitHub**：[Tongyi-MAI/Z-Image](https://github.com/Tongyi-MAI/Z-Image)

### 能力概述

Z-Image-Turbo 是通过 Decoupled-DMD（解耦分布匹配蒸馏）从大模型蒸馏而来的快速扩散模型。核心特点是仅需 8 步采样即可生成高质量 1024×1024 图像，实现亚秒级延迟。**当前 ComfyUI 工作流已在使用此模型**，迁移成本为零。

关键特性：
- ControlNet Union 模型支持 Canny/HED/Depth/Pose 等多模态统一控制
- 中英文文字渲染能力强
- ComfyUI 官方原生支持，有完整教程

### 部署要求

| 项目 | 要求 |
|------|------|
| 显存 | ~6GB（最低），16GB 流畅 |
| 推理框架 | ComfyUI / Diffusers |
| 推理速度 | 亚秒级（8 步采样） |
| 量化支持 | FP16 |

### 与本项目的适配性

**优势：**
- 当前工作流已在使用，零迁移成本
- 8 步采样低延迟，极适合语义传输实时场景
- ControlNet Union 支持多种条件类型统一控制
- 显存仅需 6GB，消费级 GPU 即可部署
- Apache 2.0 许可，无商用限制

**劣势：**
- 模型较新（2025.11），社区生态仍在建设
- 在极高保真度场景可能略逊于 FLUX.1

**推荐：** 继续作为图像接收端主力模型，零迁移成本 + 低延迟 + 低显存。

---

## 2. FLUX.1 系列

### 基本信息

- **开发者 / 机构**：Black Forest Labs（Stable Diffusion 原创团队）
- **参数量**：12B DiT + 4.5B 文本编码器
- **发布时间**：2024 年 8 月
- **许可证**：schnell: Apache 2.0; dev: 非商用
- **HuggingFace**：[FLUX.1-schnell](https://huggingface.co/black-forest-labs/FLUX.1-schnell) / [FLUX.1-dev](https://huggingface.co/black-forest-labs/FLUX.1-dev)
- **GitHub**：[black-forest-labs/flux](https://github.com/black-forest-labs/flux)

### 能力概述

FLUX.1 是当前开源图像生成质量最高的模型之一，在多项评测中超越 SD3 Ultra 和 Midjourney V6。架构为 DiT（Diffusion Transformer）。GSC 论文已验证 FLUX 在语义通信场景的有效性。

- **schnell**：4 步采样，适合实时场景
- **dev**：20-50 步，质量最高但速度较慢
- 官方 Flux Tools 提供 Canny/Depth ControlNet
- FLUX.1 Kontext 支持结构化视觉提示

### 部署要求

| 项目 | 要求 |
|------|------|
| 显存 (BF16) | ~24GB+ |
| 显存 (FP8 量化) | ~12GB |
| 推荐 GPU | RTX 4090 24GB / A100 |
| 推理框架 | ComfyUI / Diffusers |
| 推理速度 | schnell: 4 步; dev: 20-50 步 |

### 与本项目的适配性

**优势：**
- 图像质量天花板最高
- GSC 论文已验证在语义通信场景的效果
- schnell 版本 4 步采样，Apache 2.0 许可
- 官方 ControlNet 支持

**劣势：**
- 模型极大（12B），显存需求高
- FP8 量化可降至 12GB 但有质量损失
- dev 版本非商用许可

**推荐：** 作为"高质量模式"备选方案，在资源充足时使用。

---

## 3. Stable Diffusion 3.5

### 基本信息

- **开发者 / 机构**：Stability AI
- **参数量**：Large: 8B; Medium: 2.6B
- **发布时间**：2024 年 10 月
- **许可证**：社区许可证（年营收 <$1M 免费商用）
- **HuggingFace**：[stabilityai/stable-diffusion-3.5-large](https://huggingface.co/stabilityai/stable-diffusion-3.5-large)

### 能力概述

SD 3.5 使用 MMDiT（Multimodal Diffusion Transformer）架构，三个预训练文本编码器，前 12 个 transformer 层采用双注意力块。Turbo 变体通过对抗扩散蒸馏（ADD）实现 4 步快速采样。

- 官方 ControlNet 支持 Canny/Depth/Blur
- Medium 版本仅 2.6B 参数，6-8GB 显存即可运行
- 文字渲染能力和提示词遵循度强

### 部署要求

| 项目 | Large | Medium |
|------|-------|--------|
| 显存 | 18-24GB | 6-8GB |
| 推荐 GPU | RTX 4090 | RTX 3060 12GB+ |
| 推理速度 | Turbo: 4 步 | 4 步 |

### 与本项目的适配性

**优势：**
- Medium 版本轻量（2.6B，6GB 显存），适合资源受限场景
- 官方 ControlNet 支持完善
- 提示词遵循度高，有利于结构化描述还原

**劣势：**
- 社区许可证有营收限制
- 生态成熟度不如 SDXL 系列
- Large 版本显存需求高

**推荐：** Medium 版本可作为 Z-Image-Turbo 的轻量替代测试。

---

## 4. SDXL Lightning

### 基本信息

- **开发者 / 机构**：ByteDance
- **参数量**：~3.5B（基于 SDXL）
- **发布时间**：2024 年 2 月
- **许可证**：开放权重

### 能力概述

基于 SDXL 的渐进式对抗蒸馏模型，实现 1-4 步极速采样。通过 LoRA 适配器应用于 SDXL 基础模型。在潜空间操作，比 SDXL Turbo 更高效。

### 与本项目的适配性

**优势：**
- 1-4 步极速采样，延迟极低
- 显存中等（8-12GB）
- ControlNet 兼容性已验证

**劣势：**
- 基于 SDXL 架构，质量上限低于 FLUX.1 和 SD3.5
- 不支持负提示词
- 架构较旧，未来发展前景有限

**推荐：** 仅在对延迟极度敏感且质量要求不高时考虑。

---

## 5. Wan2.1 / Wan2.2（万相）

### 基本信息

- **开发者 / 机构**：阿里巴巴
- **参数量**：Wan2.1: 14B / 1.3B; Wan2.2: MoE 27B 总 / 14B 激活
- **发布时间**：Wan2.1: 2025 年 2 月; Wan2.2: 2025 年 7 月
- **许可证**：Apache 2.0
- **GitHub**：[Wan-Video/Wan2.1](https://github.com/Wan-Video/Wan2.1) / [Wan-Video/Wan2.2](https://github.com/Wan-Video/Wan2.2)
- **HuggingFace**：[Wan-AI](https://huggingface.co/Wan-AI)

### 能力概述

Wan2.1 在 VBench 排行榜排名第一（86.22%），超过 Sora（84.28%）。支持 T2V（文生视频）、I2V（图生视频）、视频编辑等多任务。Wan2.2 引入 MoE 架构，双专家设计（高噪声专家 + 低噪声专家），总参 27B 但每步仅激活 14B。

关键特性：
- 1.3B 轻量版仅需 8GB 显存
- Fun-Control 支持 ControlNet + 8 步快速 LoRA
- 最高支持 8K 分辨率
- ComfyUI 原生支持 + WanVideoWrapper

### 部署要求

| 项目 | Wan2.1-1.3B | Wan2.1-14B | Wan2.2 A14B |
|------|-------------|------------|-------------|
| 显存 | ~8GB | 24-80GB | 24-80GB |
| 推荐 GPU | RTX 3060+ | A100 80GB | A100 80GB |
| 推理速度 | 较快 | ~9 分/5 秒片段 (4090) | 更快（MoE 优化） |

### 与本项目的适配性

**优势：**
- VBench 第一，视频质量最高
- 1.3B 轻量版可在消费级 GPU 运行
- Apache 2.0 许可，完全开源
- Fun-Control ControlNet 特别适合语义传输的条件控制需求
- 8 步快速 LoRA 支持低延迟生成
- G-04 已确认 WanVideoWrapper 为核心技术路径

**劣势：**
- 14B 版本推理速度慢（分钟级）
- 显存需求高（14B 版本）

**推荐：** 视频接收端首选。1.3B 版本用于原型开发，14B/A14B 用于质量上限测试。

---

## 6. CogVideoX

### 基本信息

- **开发者 / 机构**：智谱 AI (THUDM)
- **参数量**：2B / 5B
- **发布时间**：2024 年 8 月
- **许可证**：CogVideoX License（自定义，非标准开源）
- **GitHub**：[zai-org/CogVideo](https://github.com/zai-org/CogVideo)
- **HuggingFace**：[zai-org/CogVideoX-5b](https://huggingface.co/zai-org/CogVideoX-5b)

### 能力概述

基于扩散 Transformer 的视频生成模型，支持 3D 因果 VAE。2B 版本门槛较低，CogKit 微调框架支持定制化训练。

### 与本项目的适配性

**优势：**
- 2B 版本门槛较低（18GB 显存）
- CogKit 微调框架可定制化
- ComfyUI-CogVideoXWrapper 较成熟

**劣势：**
- 分辨率低（720×480）、时长短（6 秒）
- 自定义许可证，非标准开源
- 推理较慢（A100 约 90 秒）
- 社区 ControlNet 支持有限

**推荐：** 作为 Wan2.x 的备选方案，适合需要微调定制的场景。

---

## 7. HunyuanVideo 1.5

### 基本信息

- **开发者 / 机构**：腾讯混元
- **参数量**：8.3B
- **发布时间**：2025 年初
- **许可证**：Apache 2.0（EU/UK/韩国除外）
- **GitHub**：[Tencent-Hunyuan/HunyuanVideo-1.5](https://github.com/Tencent-Hunyuan/HunyuanVideo-1.5)

### 能力概述

8.3B 参数扩散 Transformer + 3D 因果 VAE，使用选择性和滑动瓦片注意力（SSTA）减少计算开销。支持 121 帧 720p 生成，时序一致性优秀。

### 与本项目的适配性

**优势：**
- 消费级 GPU 可运行（最低 14GB，优化后 6GB）
- 时序一致性优秀，支持复杂镜头运动
- 121 帧生成能力
- ComfyUI 原生支持

**劣势：**
- 许可证有地域限制（EU/UK/韩国除外）
- ControlNet 主要通过社区支持（Depth 为主）
- 80GB GPU 为最佳配置

**推荐：** 视频接收端的第二备选，时序一致性突出。

---

## 8. Stable Video Diffusion (SVD-XT)

### 基本信息

- **开发者 / 机构**：Stability AI
- **参数量**：1.5B
- **发布时间**：2023 年 11 月
- **许可证**：研究/非商用
- **HuggingFace**：[stabilityai/stable-video-diffusion-img2vid-xt](https://huggingface.co/stabilityai/stable-video-diffusion-img2vid-xt)

### 与本项目的适配性

**优势：**
- 参数最小（1.5B），显存低（8-10GB），推理最快
- 生态最成熟，社区资源丰富

**劣势：**
- 非商用许可
- 帧数少（25 帧，约 4 秒），分辨率固定（1024×576）
- 只支持 I2V，不支持 T2V
- 已被 Wan2.x/HunyuanVideo 全面超越

**推荐：** 仅适合快速原型验证，不推荐作为最终方案。

---

## 语义传输场景适用性综合分析

### 接收端核心需求

1. **条件控制能力**：从文本+结构条件（边缘图/深度图）精确还原，ControlNet 支持是刚需
2. **推理速度**：语义传输追求低延迟，少步采样至关重要
3. **显存效率**：部署端可能资源有限
4. **生成保真度**：重建质量直接影响传输系统体验
5. **ComfyUI 集成**：当前工作流基于 ComfyUI

### 适用性评级

| 模型 | 条件控制 | 推理速度 | 显存效率 | 生成质量 | ComfyUI | 综合 |
|------|---------|---------|---------|---------|---------|------|
| Z-Image-Turbo | A（Union） | A（8 步） | A（6GB） | B+ | A | **A** |
| FLUX.1 schnell | B+（官方） | A（4 步） | C（12-24GB） | A | A | **A-** |
| SD 3.5 Medium | B+（官方） | A（4 步） | A（6GB） | B+ | A | **B+** |
| SDXL Lightning | B（社区） | A+（1-4 步） | A-（8-12GB） | B | A | **B** |
| Wan2.1/2.2 | A-（Fun-Control） | C（分钟级） | B-（24GB+） | A | A | **B+** |
| HunyuanVideo 1.5 | B（社区） | B（75 秒） | B（14GB+） | A | A | **B+** |
| CogVideoX | B-（社区） | C+（90 秒） | B（18GB+） | B+ | B+ | **B-** |
| SVD-XT | B-（社区） | A-（秒级） | A（8GB） | B- | B+ | **C+** |

### 模型推荐排序

#### 图像生成（接收端）

**首选：Z-Image-Turbo**
- 理由：当前工作流已使用，零迁移成本；8 步采样 + ControlNet Union + 6GB 显存，语义传输低延迟场景最优选择

**备选 1：FLUX.1 schnell**
- 理由：质量天花板最高，4 步采样，GSC 论文已验证效果；适合资源充足时的"高质量模式"

**备选 2：SD 3.5 Medium**
- 理由：2.6B 参数，6GB 显存，4 步采样，兼具轻量和质量

#### 视频生成（接收端）

**首选：Wan2.1（1.3B 版本原型 / 14B 版本生产）**
- 理由：VBench 第一，Apache 2.0，Fun-Control ControlNet 适合条件控制，G-04 已确认为核心技术路径

**备选：HunyuanVideo 1.5**
- 理由：时序一致性突出，消费级 GPU 可运行；注意地域许可限制

### 阶段性部署建议

| 阶段 | 图像接收端 | 视频接收端 |
|------|-----------|-----------|
| 短期（ComfyUI API 集成） | Z-Image-Turbo（维持现有） | Wan2.1-1.3B |
| 中期（逐步替换优化） | + FLUX.1 schnell（高质量模式） | Wan2.2 / HunyuanVideo 1.5 |
| 长期（脱离 ComfyUI） | 按资源选择 | 按资源选择 |
