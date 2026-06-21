# 使用指南

面向用户的完整安装与使用指南。

## 系统要求

| 项目 | 要求 |
|------|------|
| 操作系统 | Windows 10/11 或 Linux |
| Python | >= 3.10 |
| GPU | NVIDIA GPU（VRAM >= 12GB，推荐 >= 24GB） |
| CUDA | >= 13.0 |
| 磁盘空间 | >= 30GB（模型文件约 25GB + 项目约 1GB） |

## 安装步骤

### 1. 安装前置工具

- [Python](https://www.python.org/downloads/) >= 3.10
- [uv](https://docs.astral.sh/uv/)：Python 包管理器
- [Git](https://git-scm.com/) + [Git LFS](https://git-lfs.com/)

```bash
# 安装 Git LFS（首次使用需执行）
git lfs install
```

### 2. 克隆项目

```bash
git clone https://github.com/chy5301/semantic-transmission.git
cd semantic-transmission
```

### 3. 安装依赖

```bash
uv sync
```

此命令会自动安装所有 Python 依赖，包括 PyTorch（CUDA 13.0 版本）。

### 4. 下载模型

接收端 Diffusers 本地推理需要以下模型文件：

| 模型 | 大小 | 用途 |
|------|------|------|
| `z-image-turbo-Q8_0.gguf` | ~6.9 GB | 扩散 transformer（GGUF Q8_0 量化） |
| `Z-Image-Turbo-Fun-Controlnet-Union.safetensors` | ~3 GB | ControlNet Union（结构条件控制） |
| HuggingFace pipeline base 组件 | 若干 GB | text encoder / VAE 等（存于 HF cache） |
| `Qwen/Qwen2.5-VL-7B-Instruct`（可选） | ~16 GB | 发送端 VLM 自动描述（auto-prompt 模式需要） |

使用 CLI 下载（按 `config.toml` 配置，默认国内 HuggingFace 镜像）：

```bash
uv run semantic-tx download            # 下载全部模型
uv run semantic-tx download --dry-run  # 预览下载计划（不实际下载）
```

### 5. 验证环境

```bash
uv run semantic-tx check diffusers   # 接收端 Diffusers 模型就绪
uv run semantic-tx check vlm         # 发送端 VLM 模型就绪
```

全部通过即可开始使用。双机部署时还可用 `semantic-tx check relay --host <对端IP> --port <端口>` 检测对端 TCP 可达。

## 基本使用

### 端到端演示（单机）

```bash
# 手动 prompt 模式（快速，不需要 VLM 模型）
uv run semantic-tx demo --image photo.jpg --prompt "A cat sitting on a sofa"

# 自动 prompt 模式（需要 VLM 模型）
uv run semantic-tx demo --image photo.jpg --auto-prompt
```

输出结果保存在 `output/demo/` 目录，包含原图、边缘图、还原图和对比图。

### 质量评估

对演示输出进行质量评估：

```bash
uv run python scripts/evaluate.py --input-dir output/demo --original-dir resources/test_images
```

详细演示操作说明见 [demo-handbook.md](demo-handbook.md)，命令行完整参数见 [cli-reference.md](cli-reference.md)。

### GUI 可视化界面

除了命令行方式，还可以通过 Gradio GUI 进行操作：

```bash
uv run semantic-tx gui
```

浏览器打开 http://127.0.0.1:7860，界面包含 6 个标签页：

- **配置**：模型就绪检测（VLM / Diffusers）、模型路径、中继传输配置
- **单张发送**：上传图像 → 提取边缘图 + 生成语义描述
- **批量发送**：批量处理多张图像
- **接收端**：输入边缘图和描述 → 还原图像
- **端到端演示**：一键完成全流程，展示传输统计和质量评估
- **批量端到端**：批量端到端处理 + 可选质量评估

常用选项：

```bash
semantic-tx gui --port 8080      # 指定端口
semantic-tx gui --host 0.0.0.0   # 允许局域网访问
semantic-tx gui --share          # 生成公网分享链接
```
