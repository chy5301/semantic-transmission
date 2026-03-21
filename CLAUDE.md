# CLAUDE.md

## 常用命令

```bash
uv sync                  # 安装依赖
uv run pytest            # 运行全部测试
uv run pytest tests/test_comfyui_client.py  # 运行单个测试文件
uv run ruff check .      # 代码检查（与 CI 一致，覆盖 src/ scripts/ tests/）
uv run ruff format .     # 代码格式化（与 CI 一致）
```

## 项目概述

本项目是一个"语义传输"（Semantic Transmission / Semantic Communication）预研项目。核心思路是用 AI 模型实现视频的语义级压缩传输：

- **发送端**：通过视频理解模型（视频生文/图生文）将视频帧压缩为文本描述 + 结构化条件（关键帧、边缘图等）
- **接收端**：通过生成模型（文生图/文生视频）从文本和条件信息还原出视觉内容

目标是实现极低码率下的视频传输 demo。

## 项目阶段

1. **调研阶段**（已完成）：收集语义传输相关论文和项目（GVSC、GVC、GSC 等），形成调研报告
2. **ComfyUI API 集成**：基于同事已有的 ComfyUI 工作流，将发送端和接收端封装为 API 打通流程
3. **逐步替换优化**：用更优实现替换 ComfyUI 工作流节点，最终可能完全脱离 ComfyUI

## 源码结构

```
src/semantic_transmission/
├── common/          # 公共模块：ComfyUI 客户端、配置、类型定义
├── pipeline/        # 端到端管道编排
├── sender/          # 发送端：图像/视频 → 语义描述 + 条件信息
└── receiver/        # 接收端：语义描述 → 图像/视频还原
```

## 当前资源

- `resources/comfyui/` — 同事构建的 ComfyUI 工作流文件（JSON）及界面截图
  - 当前工作流使用 Z-Image-Turbo + ControlNet Union 实现图像到图像的 Canny 边缘控制生成
  - 模型：qwen_3_4b (text encoder)、z_image_turbo_bf16 (diffusion)、ae (VAE)、Z-Image-Turbo-Fun-Controlnet-Union (controlnet)
- `docs/ROADMAP.md` — 项目路线图
- `docs/research/` — 调研产出文档
  - `papers/` — 论文综述（语义通信核心论文综述已完成）
  - `projects/` — 开源项目评估（ComfyUI API 集成路径已确定）
  - `models/` — 模型对比
  - `comfyui-workflow-analysis.md` — ComfyUI 工作流技术基线分析
- `docs/QUICK_START.md` — 快速开始指南（ComfyUI 部署、模型下载、环境验证）
- `docs/workflow/` — 结构化工作流管理（workflow.json、TASK_STATUS.md 等）

## CI 注意事项

- 推送前务必在本地运行 `uv run ruff check .` 和 `uv run ruff format --check .` 确认通过
- CI 检查范围是整个项目（`.`），不仅限于 `src/`

## 文档规范

- 文档中的流程图、拓扑图等使用 Mermaid 格式（```mermaid），不使用 ASCII art

## 技术栈（规划中）

- **工作流管理**：使用 structured-workflow 系统管理任务，状态见 `docs/workflow/TASK_STATUS.md`
- **ComfyUI API 模式**：通过 HTTP API 调用 ComfyUI 工作流
- **Python**：主要开发语言，使用 uv 管理依赖
- **生成模型**：Stable Diffusion 系列、Wan2.x 等扩散模型
- **视觉理解模型**：Qwen-VL 等多模态大模型用于图像/视频描述生成
