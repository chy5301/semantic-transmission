# CLAUDE.md

## 常用命令

```bash
uv sync                  # 安装依赖
uv run pytest            # 运行全部测试
uv run pytest tests/test_diffusers_receiver.py  # 运行单个测试文件
uv run ruff check .      # 代码检查（与 CI 一致，覆盖 src/ scripts/ tests/）
uv run ruff format .     # 代码格式化
uv run ruff format --check .  # 格式化检查（与 CI 一致，仅检查不修改）
uv run python scripts/evaluate.py --input-dir <输出目录> --original-dir resources/test_images  # 批量评估还原质量
uv run semantic-tx --help           # 查看 CLI 所有子命令
uv run semantic-tx demo --image <图片> --prompt "描述文本"  # CLI 方式运行端到端 demo
uv run semantic-tx check vlm         # 检查发送端 VLM 模型就绪
uv run semantic-tx check diffusers   # 检查接收端 Diffusers 模型就绪
uv run semantic-tx check relay --host 127.0.0.1 --port 9000  # 检查双机部署对端 TCP 可达
uv run semantic-tx download --dry-run  # 查看模型下载计划
uv run semantic-tx gui               # 启动 Gradio 可视化界面（默认 127.0.0.1:7860）
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
| 阶段二：ComfyUI API 原型 | 基于 ComfyUI API 打通端到端流程 | 已完成（接收端已完全脱离 ComfyUI，历史材料归档在 `docs/archive/comfyui-prototype/`） |
| 阶段三：方案迭代与优化 | 提升还原质量，优化压缩效率 | 进行中 |
| 阶段四：工程化与部署 | 构建独立可部署的系统 | 待启动 |

## 源码结构

```
src/semantic_transmission/
├── common/          # 公共模块：配置、类型定义、模型就绪检测（model_check）
├── cli/             # CLI 入口：click 子命令（sender/receiver/demo/check/download/gui）
├── gui/             # Gradio 可视化界面（配置面板、发送端、接收端、端到端演示）
├── pipeline/        # 端到端管道编排（含 relay 中继转发）
├── sender/          # 发送端：图像/视频 → 语义描述 + 条件信息（本地 Canny + Qwen-VL）
├── receiver/        # 接收端：语义描述 → 图像/视频还原（Diffusers 本地推理）
└── evaluation/      # 质量评估：PSNR/SSIM/LPIPS/CLIP Score
```

## 关键资源

- `docs/ROADMAP.md` — 项目路线图
- `docs/research/selection-report.md` — 模型/方案选型报告
- `docs/archive/comfyui-prototype/` — Phase 2 ComfyUI 原型历史材料（部署指南、工作流 JSON、原始脚本，已归档不再使用）
- `docs/workflow/` — structured-workflow 插件产物（agent coding 任务管理，详见"分支与协作约定"）
- `docs/test-reports/` — 端到端测试报告
- `docs/collaboration/` — 团队协作指南
- `docs/README.md` — 文档总索引
- `docs/development-guide.md` — 开发指南
- `docs/architecture.md` — 系统架构（模块关系、数据流、接口设计）
- `docs/user-guide.md` — 使用指南
- `docs/demo-handbook.md` — 演示手册（单机/双机操作步骤）
- `docs/gui-design.md` — GUI 设计文档（Gradio 界面布局与交互设计）
- `docs/cli-reference.md` — CLI 参考文档（semantic-tx 全部子命令参数说明）
- `docs/project-overview.md` — 项目总览（面向负责人）
- `resources/test_images/` — 测试用图片集

## CI 注意事项

- **任何变更（含文档、workflow 文件）前必须先创建工作分支**（`git checkout -b <branch>`），禁止在 main 上直接修改或提交
- 推送前务必在本地运行 `uv run ruff check .` 和 `uv run ruff format --check .` 确认通过
- CI 检查范围是整个项目（`.`），不仅限于 `src/`

## 文档规范

- 文档中的流程图、拓扑图等使用 Mermaid 格式（```mermaid），不使用 ASCII art

## GUI 开发注意事项

- Gradio `gr.Image` 默认 `type="numpy"`，回调收到的是 `numpy.ndarray` 而非 PIL Image 或文件路径；需要文件路径时须显式指定 `type="filepath"`

## 环境前置条件

- Python >= 3.10（CI 使用 3.12）
- PyTorch 使用 CUDA 13.0 索引源安装（`pyproject.toml` 中已配置 `pytorch-cu130`）
- 接收端 Diffusers 需要模型文件：`$MODEL_CACHE_DIR/Z-Image-Turbo/z-image-turbo-Q8_0.gguf`（GGUF transformer）+ `Z-Image-Turbo-Fun-Controlnet-Union.safetensors` + HuggingFace cache 中的 pipeline base 组件（可通过 `semantic-tx check diffusers` 检测）
- 发送端 VLM auto-prompt 可选：`$MODEL_CACHE_DIR/Qwen/Qwen2.5-VL-7B-Instruct`（可通过 `semantic-tx check vlm` 检测）

## 技术栈

- **工作流管理**：使用 structured-workflow 系统辅助 agent coding，详见下方"分支与协作约定"
- **Python**：主要开发语言，使用 uv 管理依赖
- **接收端推理**：Diffusers 0.37 + Z-Image-Turbo + ControlNet Union；transformer 使用 GGUF Q8_0 量化（`gguf>=0.18`），分组件加载适配 24 GB 显存
- **发送端边缘提取**：OpenCV Canny 算子（`LocalCannyExtractor`）
- **视觉理解模型**：Qwen2.5-VL 多模态大模型用于图像/视频描述生成
- **中继传输**：`SocketRelaySender` / `SocketRelayReceiver`（TCP 长度前缀协议），用于双机部署
- **CLI 框架**：click（子命令体系，入口点 `semantic-tx`）
- **GUI 框架**：Gradio 5.x（可视化界面，`semantic-tx gui` 启动）

## 分支与协作约定

- 所有变更必须走 feature branch → PR → Squash Merge，禁止直接 push main
- 分支粒度：使用 workflow 时，一个 workflow 对应一个分支/PR；不使用 workflow 时，按独立功能或目的划分
- 分支名前缀应匹配任务类型（`feature/`、`refactor/`、`fix/`、`chore/`、`docs/` 等），后接自描述工作内容（如 `refactor/unify-config-and-loader`），不使用 workflow 编号
- 协作者的 PR 需至少 1 人 approve + CI 通过；管理员的 PR 仅需 CI 通过即可自行合并
- 管理员合并自己的 PR 时需使用 `gh pr merge <number> --squash --delete-branch --admin`（GitHub 不允许自我 approve，需用 `--admin` 绕过 Rulesets）
- 分支命名规范见 `docs/collaboration/05-project-conventions.md`

### workflow 系统使用规范

`docs/workflow/` 由 [structured-workflow](https://github.com/chy5301/cc-plugins) 插件管理，提供大型工程任务的结构化管理工作流（分析→规划→执行→回顾→归档全生命周期），不是团队协作的任务分配系统：

- 任何安装了 structured-workflow 插件的开发者都可以在自己的 feature branch 上使用
- 在 feature branch 上运行：task-init → 开发 → task-archive 全部在分支上完成
- PR 前清理：archive 后确保 `docs/workflow/` 下无活跃文件（TASK_STATUS.md、TASK_PLAN.md 等）
- GitHub Issues 仅按需创建，用于分配给协作者的任务
