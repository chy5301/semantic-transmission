# CLAUDE.md

## 常用命令

```bash
uv sync                  # 安装依赖
uv run pytest            # 运行全部测试
uv run pytest tests/test_comfyui_client.py  # 运行单个测试文件
uv run ruff check .      # 代码检查（与 CI 一致，覆盖 src/ scripts/ tests/）
uv run ruff format .     # 代码格式化
uv run ruff format --check .  # 格式化检查（与 CI 一致，仅检查不修改）
uv run python scripts/demo_e2e.py  # 运行端到端 demo（需 ComfyUI 服务运行中）
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
├── pipeline/        # 端到端管道编排（含 relay 中继转发）
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
  - `selection-report.md` — 模型/方案选型报告
  - `skill-evaluation.md` — 技能评估文档
- `docs/comfyui-setup.md` — ComfyUI 部署指南（模型下载、自定义节点安装、验证步骤）
- `docs/test-reports/` — 测试报告
  - `01-e2e-manual-prompt-test.md` — Round 1：简短 prompt 测试（6 张越野车场景）
  - `02-e2e-detailed-prompt-test.md` — Round 2：详细 prompt 测试 + 两轮对比分析
- `docs/workflow/` — 结构化工作流管理（workflow.json、TASK_STATUS.md 等）
- `docs/collaboration/` — Git/GitHub 协作指南（分支管理、PR 流程、Issue 管理等）
- `scripts/` — 工具脚本
  - `demo_e2e.py` — 端到端 demo 脚本（发送端→接收端完整流程）
  - `run_sender.py` — 双机演示发送端脚本（提取边缘图 + 语义描述 → 网络发送）
  - `run_receiver.py` — 双机演示接收端脚本（监听接收 → 还原图像）
  - `verify_workflows.py` — 工作流验证脚本
  - `test_comfyui_connection.py` — ComfyUI API 连通性测试
  - `download_models.py` — 模型下载辅助脚本

## CI 注意事项

- 推送前务必在本地运行 `uv run ruff check .` 和 `uv run ruff format --check .` 确认通过
- CI 检查范围是整个项目（`.`），不仅限于 `src/`

## 文档规范

- 文档中的流程图、拓扑图等使用 Mermaid 格式（```mermaid），不使用 ASCII art

## 环境前置条件

- ComfyUI 服务需在本地运行（默认地址 `127.0.0.1:8188`），配置见 `src/semantic_transmission/common/config.py`
- PyTorch 使用 CUDA 13.0 索引源安装（`pyproject.toml` 中已配置 `pytorch-cu130`）

## 技术栈

- **工作流管理**：使用 structured-workflow 系统管理任务，状态见 `docs/workflow/TASK_STATUS.md`
- **ComfyUI API 模式**：通过 HTTP API 调用 ComfyUI 工作流
- **Python**：主要开发语言，使用 uv 管理依赖
- **生成模型**：Stable Diffusion 系列、Wan2.x 等扩散模型
- **视觉理解模型**：Qwen-VL 等多模态大模型用于图像/视频描述生成
