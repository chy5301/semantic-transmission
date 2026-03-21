# ComfyUI 本机部署指南

## 环境信息

- **ComfyUI 版本**: v0.9.2（秋叶整合包 v3）
- **安装路径**: `D:\CONGHAOYANG\工具\ComfyUI\ComfyUI-aki\ComfyUI-aki-v3\ComfyUI`
- **Python 环境**: 整合包自带 `ComfyUI-aki-v3\python\python.exe`
- **GPU 需求**: CUDA 兼容 GPU，显存 ≥6GB（仅 ComfyUI），≥24GB（ComfyUI + VLM）

## 模型文件

本项目工作流需要 4 个模型文件，均放在 ComfyUI 的 `models/` 子目录下：

| 文件 | 目录 | 大小 | 用途 | 来源 |
|------|------|------|------|------|
| `qwen_3_4b.safetensors` | `text_encoders/` | ~8 GB | 文本编码器（将 prompt 编码为条件向量） | HuggingFace `Comfy-Org/z_image_turbo` |
| `z_image_turbo_bf16.safetensors` | `diffusion_models/` | ~12.3 GB | 扩散模型（9 步快速图像生成） | HuggingFace `Comfy-Org/z_image_turbo` |
| `ae.safetensors` | `vae/` | ~335 MB | VAE 解码器（latent → RGB 像素） | HuggingFace `Comfy-Org/z_image_turbo` |
| `Z-Image-Turbo-Fun-Controlnet-Union.safetensors` | `model_patches/` | ~3.1 GB | ControlNet 条件控制（让生成遵循边缘图结构） | 魔搭 `PAI/Z-Image-Turbo-Fun-Controlnet-Union` |

### 自动下载

项目提供了下载脚本，自动从 HuggingFace 和魔搭社区下载模型到 ComfyUI 对应目录：

```bash
# 查看将要下载的文件
uv run python scripts/download_models.py --dry-run

# 正式下载（默认使用代理 http://127.0.0.1:7890 访问 HuggingFace）
uv run python scripts/download_models.py

# 使用 HuggingFace 国内镜像替代代理
uv run python scripts/download_models.py --hf-mirror
```

下载工具需提前安装：

```bash
uv tool install modelscope
uv tool install "huggingface_hub[cli]"
```

### 手动下载

如果自动下载失败，可手动下载并放到对应目录：

- HuggingFace 仓库：`https://huggingface.co/Comfy-Org/z_image_turbo/tree/main/split_files`
- 魔搭 ControlNet：`https://www.modelscope.cn/models/PAI/Z-Image-Turbo-Fun-Controlnet-Union`

## 自定义节点

本项目工作流使用的所有节点类型均为 ComfyUI v0.3.51+ 内置节点，无需安装自定义节点包：

- `QwenImageDiffsynthControlnet` — ControlNet 条件注入
- `ModelPatchLoader` — 加载模型补丁
- `ModelSamplingAuraFlow` — 采样参数配置
- `ImageScaleToMaxDimension` — 图像缩放

## 启动 ComfyUI

以 `--listen` 模式启动，开放 API 端口供项目调用：

```bash
cd "D:\CONGHAOYANG\工具\ComfyUI\ComfyUI-aki\ComfyUI-aki-v3"
python\python.exe ComfyUI\main.py --listen
```

启动后 API 默认监听 `http://0.0.0.0:8188`。

## 验证步骤

### 1. 连通性测试

```bash
uv run python scripts/test_comfyui_connection.py --host 127.0.0.1 --port 8188
```

6 项测试全部 PASS 表示连通正常。

### 2. 工作流验证

```bash
# 完整验证（发送端 + 接收端）
uv run python scripts/verify_workflows.py --host 127.0.0.1 --port 8188

# 仅验证发送端
uv run python scripts/verify_workflows.py --sender-only

# 仅验证接收端（需提供边缘图）
uv run python scripts/verify_workflows.py --receiver-only --edge-image output/verify/sender_edge_output.png
```

验证输出保存在 `output/verify/` 目录下。

## 项目配置

项目通过环境变量配置 ComfyUI 连接地址：

```bash
# 单机模式（发送端和接收端共用一个 ComfyUI 实例）
export COMFYUI_HOST=127.0.0.1
export COMFYUI_PORT=8188

# 双机模式（发送端和接收端各自连接不同的 ComfyUI 实例）
export COMFYUI_SENDER_HOST=192.168.1.100
export COMFYUI_SENDER_PORT=8188
export COMFYUI_RECEIVER_HOST=192.168.1.101
export COMFYUI_RECEIVER_PORT=8188
```
