# 工作流完成摘要

## 基本信息

- **任务名称**: research-semantic-transmission
- **任务类型**: generic + integration
- **任务前缀**: G
- **开始时间**: 2026-03-13
- **归档时间**: 2026-03-13

## 总体统计

- 阶段数: 4
- 任务总数: 9
- 已完成: 9
- 已取消: 0
- 未完成: 0

## 各阶段摘要

### Phase 0: 准备（3 任务）

| 编号 | 标题 | 关键成果 |
|------|------|---------|
| G-00 | 搜索评估-调研辅助 Skill | 评估 5 个候选 skill，安装 read-arxiv-paper |
| G-01 | 创建-调研文档框架 | 建立 docs/research/ 目录结构和写作模板 |
| G-02 | 分析-现有 ComfyUI 工作流 | 解析 18 个节点拓扑、4 个模型依赖、9 个改进点 |

### Phase 1: 论文与项目调研（2 任务）

| 编号 | 标题 | 关键成果 |
|------|------|---------|
| G-03 | 调研-语义通信核心论文 | 6 篇论文综述（GVSC/GVC/GSC/M3E-VSC/CPSGD/HFCVD） |
| G-04 | 调研-开源项目与框架 | 6 个项目评估，确定 ComfyUI API + WanVideoWrapper 为核心路径 |

### Phase 2: 模型能力调研（3 任务）

| 编号 | 标题 | 关键成果 |
|------|------|---------|
| G-05 | 调研-视觉理解模型 | 5 模型系列 7 版本对比，首选 Qwen2.5-VL-7B |
| G-06 | 调研-图像与视频生成模型 | 8 模型对比，图像首选 Z-Image-Turbo，视频首选 Wan2.1 |
| G-07 | 调研-条件控制与 ControlNet 方案 | 8 种条件类型对比，短期 Canny → 中期 +Depth → 长期编码潜在 |

### Phase 3: 汇总与选型报告（1 任务）

| 编号 | 标题 | 关键成果 |
|------|------|---------|
| G-08 | 编写-调研汇总与选型建议 | 端到端选型报告，覆盖发送端/接收端/条件控制/框架/路线图 |

## 核心选型结论

| 维度 | 主选 | 备选 | 理由 |
|------|------|------|------|
| 发送端 VLM | Qwen2.5-VL-7B | InternVL2.5-8B | GSC 论文验证同系列，7B 单卡可部署 |
| 图像生成 | Z-Image-Turbo | FLUX.1 schnell | 零迁移成本，8 步低延迟，6GB 显存 |
| 视频生成 | Wan2.1 | HunyuanVideo 1.5 | VBench 第一，Apache 2.0，Fun-Control |
| 条件控制 | Canny → Canny+Depth | 编码潜在通道（长期） | Union ControlNet 同时支持 |
| 集成框架 | ComfyUI REST API | — | 80k+ Stars，文档完整 |

## 关键决策汇总

| 决策 | 原因 |
|------|------|
| 按主题分块调研 | 论文/项目/模型三维度独立，分块效率更高 |
| 仅安装 read-arxiv-paper skill | 其余 4 个候选功能重叠或质量不足 |
| ComfyUI API + WanVideoWrapper 为核心路径 | 端到端视频语义通信开源系统不存在，需自行组装 |
| 首选 Qwen2.5-VL-7B | GSC 论文验证，7B 版本性价比最优 |
| 图像继续用 Z-Image-Turbo | 零迁移成本 + 低延迟 + 低显存 |
| 视频首选 Wan2.1 | VBench 第一 + I2V 模式与论文方案吻合 |
| 评估指标优先 CLIP Score/LPIPS | 生成式方案像素精确度非优势 |

## 遗留问题清单

1. 本机无 ComfyUI 环境，阶段二启动前需确认部署方案（远程调用或本地安装）
2. 各模型在"结构化场景描述→还原"的端到端质量需实测验证
3. LLaVA-OV-1.5（Qwen3 基座）正式发布后可能改变发送端模型排序
4. Z-Image-Turbo Union 不支持语义分割条件，探索需换用 xinsir Union
5. 多条件融合（Canny+Depth）的实际还原质量提升需原型阶段实测
6. Wan2.2 MoE 架构的实际部署稳定性需验证
7. M3E-VSC 的详细量化指标（PSNR/SSIM 数值）在公开材料中不完整

## 产出文件索引

| 文件 | 说明 |
|------|------|
| `docs/research/README.md` | 调研总览和索引 |
| `docs/research/selection-report.md` | 调研汇总与选型报告 |
| `docs/research/skill-evaluation.md` | Skill 评估记录 |
| `docs/research/comfyui-workflow-analysis.md` | ComfyUI 工作流分析 |
| `docs/research/papers/semantic-communication-survey.md` | 论文综述（6 篇） |
| `docs/research/projects/opensource-evaluation.md` | 开源项目评估（6 个） |
| `docs/research/models/visual-understanding-models.md` | 视觉理解模型对比 |
| `docs/research/models/generation-models.md` | 生成模型对比 |
| `docs/research/models/controlnet-conditions.md` | 条件控制方案对比 |
| `docs/ROADMAP.md` | 项目路线图（已更新） |

## 经验教训

1. **分块调研策略有效**：论文/项目/模型三个维度并行推进，各块独立产出文档，最终汇总时交叉对比形成了更有说服力的选型建议。
2. **调研文档框架先行**：G-01 先建立统一模板，后续各任务产出格式一致，降低了汇总难度。
3. **技术基线锚定重要**：G-02 分析现有工作流为后续调研提供了明确的对比基准，每个模型/方案都能与当前方案做直接对比。
4. **端到端开源系统不存在**：需自行组装各组件，这是阶段二的核心挑战。ComfyUI 生态是最可靠的基础设施选择。
