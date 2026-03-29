# 使用指南

面向用户的完整安装与使用指南。

## 系统要求

| 项目 | 要求 |
|------|------|
| 操作系统 | Windows 10/11 或 Linux |
| Python | >= 3.10 |
| GPU | NVIDIA GPU（VRAM >= 12GB，推荐 >= 24GB） |
| CUDA | >= 13.0 |
| 磁盘空间 | >= 50GB（模型文件约 24GB + ComfyUI 约 10GB + 项目约 1GB） |

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

### 4. 部署 ComfyUI

推荐使用 [秋叶 ComfyUI 整合包](https://space.bilibili.com/12566101)（ComfyUI-aki v3），开箱即用。

详细部署说明见 [comfyui-setup.md](comfyui-setup.md)。

### 5. 下载模型

项目需要以下模型文件（总计约 24GB）：

| 模型 | 大小 | 用途 |
|------|------|------|
| `qwen_3_4b.safetensors` | ~8 GB | 文本编码器 |
| `z_image_turbo_bf16.safetensors` | ~12.3 GB | 扩散模型（Z-Image-Turbo） |
| `ae.safetensors` | ~335 MB | VAE 解码器 |
| `Z-Image-Turbo-Fun-Controlnet-Union.safetensors` | ~3.1 GB | ControlNet Union |

使用下载脚本：

```bash
# 下载全部模型（默认使用国内 HuggingFace 镜像）
uv run python scripts/download_models.py

# 预览下载内容（不实际下载）
uv run python scripts/download_models.py --dry-run

# 禁用镜像，使用代理
uv run python scripts/download_models.py --no-mirror --proxy http://127.0.0.1:7890
```

VLM 模型（Qwen2.5-VL-7B-Instruct，自动 prompt 模式需要）也由该脚本一并下载。

### 6. 验证环境

启动 ComfyUI 后，运行验证脚本确认环境正确：

```bash
# 连通性测试（6 项检查）
uv run python scripts/test_comfyui_connection.py

# 端到端工作流验证
uv run python scripts/verify_workflows.py
```

全部通过即可开始使用。

## 基本使用

### 端到端演示（单机）

```bash
# 手动 prompt 模式（快速，不需要 VLM 模型）
uv run python scripts/demo_e2e.py --image photo.jpg --prompt "A cat sitting on a sofa"

# 自动 prompt 模式（需要 VLM 模型）
uv run python scripts/demo_e2e.py --image photo.jpg --auto-prompt
```

输出结果保存在 `output/demo/` 目录，包含原图、边缘图和还原图。

### 质量评估

对演示输出进行质量评估：

```bash
uv run python scripts/evaluate.py --input-dir output/demo --original-dir resources/test_images
```

详细演示操作说明见 [demo-handbook.md](demo-handbook.md)。

### GUI 可视化界面

除了命令行方式，还可以通过 Gradio GUI 进行操作：

```bash
uv run semantic-tx gui
```

浏览器打开 http://127.0.0.1:7860，界面包含 4 个标签页：

- **配置**：ComfyUI 连接管理、VLM 模型路径、中继传输配置
- **发送端**：上传图像 → 提取边缘图 + 生成语义描述
- **接收端**：输入边缘图和描述 → 还原图像
- **端到端演示**：一键完成全流程，展示传输统计和质量评估

常用选项：

```bash
semantic-tx gui --port 8080      # 指定端口
semantic-tx gui --host 0.0.0.0   # 允许局域网访问
semantic-tx gui --share           # 生成公网分享链接
```
