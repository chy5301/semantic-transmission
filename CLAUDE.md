# CLAUDE.md

## 仓库信息

- **主仓库**：Gitee（`chy5301/semantic-transmission`，私有）
- **镜像**：GitHub（`chy5301/semantic-transmission`，私有）
- 日常开发推送到 Gitee（origin），GitHub 镜像按需同步

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

详见 `docs/ROADMAP.md`。

| 阶段 | 目标 | 状态 |
|------|------|------|
| 阶段一：调研与选型 | 论文综述、开源项目评估、技术路线确定 | 已完成 |
| 阶段二：ComfyUI API 原型 | 基于 ComfyUI API 打通端到端流程 | 进行中 |
| 阶段三：方案迭代与优化 | 提升还原质量，优化压缩效率 | 待启动 |
| 阶段四：工程化与脱离 ComfyUI | 构建独立可部署的系统 | 待启动 |

## 源码结构

```
src/semantic_transmission/
├── common/          # 公共模块：ComfyUI 客户端、配置、类型定义
├── pipeline/        # 端到端管道编排（含 relay 中继转发）
├── sender/          # 发送端：图像/视频 → 语义描述 + 条件信息
└── receiver/        # 接收端：语义描述 → 图像/视频还原
```

## 关键资源

- `resources/comfyui/` — ComfyUI 工作流文件（Z-Image-Turbo + ControlNet Union，Canny 边缘控制生成）
- `docs/ROADMAP.md` — 项目路线图
- `docs/research/selection-report.md` — 模型/方案选型报告
- `docs/comfyui-setup.md` — ComfyUI 部署指南
- `docs/workflow/` — structured-workflow 插件产物（agent coding 任务管理，详见"分支与协作约定"）
- `docs/test-reports/` — 端到端测试报告
- `docs/collaboration/` — 团队协作指南
- `resources/test_images/` — 测试用图片集

## CI 注意事项

- 推送前务必在本地运行 `uv run ruff check .` 和 `uv run ruff format --check .` 确认通过
- CI 检查范围是整个项目（`.`），不仅限于 `src/`

## 文档规范

- 文档中的流程图、拓扑图等使用 Mermaid 格式（```mermaid），不使用 ASCII art

## 环境前置条件

- Python >= 3.10（CI 使用 3.12）
- ComfyUI 服务需在本地运行（默认地址 `127.0.0.1:8188`），配置见 `src/semantic_transmission/common/config.py`
- PyTorch 使用 CUDA 13.0 索引源安装（`pyproject.toml` 中已配置 `pytorch-cu130`）

## 技术栈

- **工作流管理**：使用 structured-workflow 系统辅助 agent coding，详见下方"分支与协作约定"
- **ComfyUI API 模式**：通过 HTTP API 调用 ComfyUI 工作流
- **Python**：主要开发语言，使用 uv 管理依赖
- **生成模型**：Z-Image-Turbo + ControlNet Union（当前基线），Wan2.x（规划中）
- **视觉理解模型**：Qwen-VL 等多模态大模型用于图像/视频描述生成

## 分支与协作约定

- 所有变更必须走 feature branch → PR → Squash Merge，禁止直接 push main
- 协作者的 PR 需至少 1 人 approve + CI 通过；管理员的 PR 仅需 CI 通过即可自行合并
- 分支命名规范见 `docs/collaboration/05-project-conventions.md`

### workflow 系统使用规范

`docs/workflow/` 由 [structured-workflow](https://github.com/chy5301/cc-plugins) 插件管理，提供大型工程任务的结构化管理工作流（分析→规划→执行→回顾→归档全生命周期），不是团队协作的任务分配系统：

- 任何安装了 structured-workflow 插件的开发者都可以在自己的 feature branch 上使用
- 在 feature branch 上运行：task-init → 开发 → task-archive 全部在分支上完成
- PR 前清理：archive 后确保 `docs/workflow/` 下无活跃的 TASK_STATUS.md、TASK_PLAN.md 等文件
- GitHub Issues 仅按需创建，用于分配给协作者的任务
