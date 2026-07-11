# 开发指南

面向开发者的完整开发指南，涵盖环境搭建、项目结构、测试方法和贡献流程。

## 环境要求

| 项目 | 要求 |
|------|------|
| Python | >= 3.10（CI 使用 3.12） |
| 包管理 | [uv](https://docs.astral.sh/uv/) |
| GPU | NVIDIA GPU + CUDA 13.0+（Diffusers 接收端与 VLM 推理需要） |
| Git LFS | 用于管理 output/ 下的 PNG 测试结果 |

接收端 Diffusers 需要模型文件（`Z-Image-Turbo` GGUF transformer + ControlNet Union + HuggingFace cache 中的 pipeline 组件），可通过 `semantic-tx check diffusers` 检测；发送端 VLM 可选，通过 `semantic-tx check vlm` 检测。

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
│   ├── config.py        #   ProjectConfig + config.toml 加载（4 层优先级）
│   ├── model_loader.py  #   ModelLoader 抽象（DiffusersModelLoader / QwenVLModelLoader）
│   ├── model_check.py   #   模型就绪检测（check vlm / diffusers）
│   ├── image_io.py      #   统一图像加载（load_as_rgb / image_to_numpy）
│   └── types.py         #   数据类型定义
├── sender/              # 发送端
│   ├── base.py          #   抽象基类（BaseSender, BaseConditionExtractor）
│   ├── qwen_vl_sender.py#   Qwen-VL 本地推理（语义描述生成）
│   └── local_condition_extractor.py # 本地 Canny 边缘提取
├── receiver/            # 接收端
│   ├── base.py          #   抽象基类 + create_receiver 工厂
│   └── diffusers_receiver.py # Diffusers 本地推理（Z-Image-Turbo + ControlNet Union）
├── pipeline/            # 管道编排
│   ├── batch_processor.py #  批量逐样本编排
│   └── relay.py         #   中继传输（SocketRelaySender / SocketRelayReceiver）
├── evaluation/          # 质量评估
│   ├── pixel_metrics.py #   PSNR / SSIM
│   ├── perceptual_metrics.py # LPIPS
│   ├── semantic_metrics.py#  CLIP Score
│   └── utils.py         #   指标计算工具
├── cli/                 # CLI 入口（click 子命令，入口点 semantic-tx）
│   ├── main.py          #   根命令组装
│   ├── sender.py        #   发送（单图 / 批量）
│   ├── receiver.py      #   接收（双机监听）
│   ├── demo.py          #   端到端演示
│   ├── batch_demo.py    #   批量端到端演示
│   ├── check.py         #   就绪检测（vlm / diffusers / relay）
│   ├── download.py      #   模型下载
│   └── gui.py           #   启动 Gradio 界面
└── gui/                 # Gradio 可视化界面
    ├── app.py           #   主应用组装（Blocks + Tabs）
    ├── theme.py         #   主题定义
    ├── config_panel.py  #   配置面板（模型就绪检测）
    ├── sender_panel.py  #   单图发送
    ├── receiver_panel.py / pipeline_panel.py    # 接收 / 端到端
    ├── video_panel.py   #   视频流演示（单机 video→video）
    └── video_relay_panel.py #   双机视频传输（发送端 + 接收端监听）

scripts/                 # 工具脚本
├── download_models.py   #   模型下载（亦可用 semantic-tx download）
└── evaluate.py          #   批量质量评估（亦可用 semantic-tx 配套）

tests/                   # 单元测试（pytest，mock 运行不依赖 GPU）
resources/
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
uv run pytest tests/test_diffusers_receiver.py

# 运行匹配名称的测试
uv run pytest -k "test_load"

# 显示详细输出
uv run pytest -v
```

单元测试通过 mock 运行，不依赖真实 GPU 或模型文件（CI runner 无 CUDA）。涉及真实推理的端到端验证通过 `semantic-tx demo` / `semantic-tx check` 在有 GPU 的环境手动执行。

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
