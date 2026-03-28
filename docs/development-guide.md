# 开发指南

面向开发者的完整开发指南，涵盖环境搭建、项目结构、测试方法和贡献流程。

## 环境要求

| 项目 | 要求 |
|------|------|
| Python | >= 3.10（CI 使用 3.12） |
| 包管理 | [uv](https://docs.astral.sh/uv/) |
| GPU | NVIDIA GPU + CUDA 13.0+（ComfyUI 和 VLM 推理需要） |
| Git LFS | 用于管理 output/ 下的 PNG 测试结果 |
| ComfyUI | 本机运行，默认 `127.0.0.1:8188` |

## 依赖安装

```bash
# 安装全部依赖（含 dev 依赖）
uv sync

# 仅安装生产依赖
uv sync --no-dev
```

PyTorch 使用 CUDA 13.0 索引源，`pyproject.toml` 中已配置 `pytorch-cu130`，`uv sync` 会自动从正确的索引安装。

## 项目结构

```
src/semantic_transmission/
├── common/              # 公共模块
│   ├── config.py        #   ComfyUI 连接配置（支持环境变量覆盖）
│   ├── types.py         #   数据类型定义（SenderOutput, TransmissionData, ReceiverOutput）
│   └── comfyui_client.py#   ComfyUI HTTP API 客户端
├── sender/              # 发送端
│   ├── base.py          #   抽象基类（BaseSender, BaseConditionExtractor）
│   ├── qwen_vl_sender.py#   Qwen-VL 本地推理实现
│   └── comfyui_sender.py#   ComfyUI 工作流调用实现
├── receiver/            # 接收端
│   ├── base.py          #   抽象基类（BaseReceiver）
│   ├── comfyui_receiver.py#  ComfyUI 工作流调用实现
│   └── workflow_converter.py# 工作流 JSON→API 格式转换器
├── pipeline/            # 管道编排
│   └── relay.py         #   中继传输（LocalRelay / SocketRelay）
└── evaluation/          # 质量评估
    ├── pixel_metrics.py #   PSNR / SSIM
    ├── perceptual_metrics.py# LPIPS
    └── semantic_metrics.py#  CLIP Score

scripts/                 # 工具脚本
├── demo_e2e.py          #   端到端演示（单机）
├── run_sender.py        #   独立发送端（双机模式）
├── run_receiver.py      #   独立接收端（双机模式）
├── evaluate.py          #   批量质量评估
├── download_models.py   #   模型下载
├── test_comfyui_connection.py # 连通性测试
└── verify_workflows.py  #   工作流验证

tests/                   # 单元测试（167 个）
resources/
├── comfyui/             # ComfyUI 工作流文件
└── test_images/         # 测试用图片集
```

详细架构说明见 [architecture.md](architecture.md)。

## 开发工作流

### 分支策略

采用 GitHub Flow，禁止直接 push main：

1. 从 main 创建功能分支（`feature/xxx`、`fix/xxx`、`docs/xxx`）
2. 在分支上开发并提交
3. 推送分支，创建 Pull Request
4. CI 通过 + Code Review 后 Squash Merge 合入 main

分支命名规范和 Commit Convention 详见 [collaboration/05-project-conventions.md](collaboration/05-project-conventions.md)。

### 提交前检查

每次提交前需确认以下检查全部通过：

```bash
# 代码检查（与 CI 一致）
uv run ruff check .

# 格式化检查（与 CI 一致，仅检查不修改）
uv run ruff format --check .

# 运行全部测试
uv run pytest
```

如需自动格式化：

```bash
uv run ruff format .
```

## 测试

测试位于 `tests/` 目录，使用 pytest 框架：

```bash
# 运行全部测试
uv run pytest

# 运行单个测试文件
uv run pytest tests/test_comfyui_client.py

# 运行匹配名称的测试
uv run pytest -k "test_submit"

# 显示详细输出
uv run pytest -v
```

测试通过 mock 运行，不依赖 ComfyUI 实例。需要真实 ComfyUI 环境的集成测试通过 scripts/ 中的脚本完成。

## CI

GitHub Actions 工作流（`.github/workflows/ci.yml`）在每次 push 和 PR 时运行：

1. `uv run ruff check .` — 代码检查
2. `uv run ruff format --check .` — 格式化检查
3. `uv run pytest` — 单元测试

检查范围是整个项目（`.`），不仅限于 `src/`。

## 编码规范

- 代码检查和格式化工具：[ruff](https://docs.astral.sh/ruff/)
- Commit 遵循 Angular Convention，Subject 和 Body 使用中文
- 文档中的流程图使用 Mermaid 格式
