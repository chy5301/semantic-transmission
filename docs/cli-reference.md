# CLI 参考文档

`semantic-tx` 是语义传输系统的命令行工具，提供发送、接收、端到端演示、连通性检查和模型下载功能。

## 安装

```bash
uv sync
```

安装后即可使用 `uv run semantic-tx` 或（在虚拟环境激活后）直接使用 `semantic-tx`。

## 命令总览

| 命令 | 说明 |
|------|------|
| `semantic-tx sender` | 发送端：提取边缘图 + 语义描述 → 发送到接收端 |
| `semantic-tx receiver` | 接收端：监听端口接收数据 → 还原图像 |
| `semantic-tx demo` | 端到端演示：图像 → 边缘提取 → 语义还原 |
| `semantic-tx check connection` | 测试 ComfyUI API 连通性 |
| `semantic-tx check workflows` | 验证发送端/接收端工作流 |
| `semantic-tx download` | 下载 ComfyUI 所需模型文件 |

## 全局选项

```
--version  显示版本号
--help     显示帮助信息
```

---

## semantic-tx sender

双机演示的发送端。提取输入图像的 Canny 边缘图，生成语义描述，通过网络发送到接收端。

### 参数

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| `--image` | PATH | 是 | - | 输入图像路径 |
| `--prompt` | TEXT | 与 --auto-prompt 二选一 | - | 手动指定描述文本 |
| `--auto-prompt` | FLAG | 与 --prompt 二选一 | - | 使用 VLM 自动生成描述 |
| `--vlm-model` | TEXT | 否 | - | VLM 模型名称 |
| `--vlm-model-path` | TEXT | 否 | `$MODEL_CACHE_DIR/Qwen/Qwen2.5-VL-7B-Instruct` | VLM 模型本地路径 |
| `--comfyui-host` | TEXT | 否 | 127.0.0.1 | 本机 ComfyUI 地址 |
| `--comfyui-port` | INT | 否 | 8188 | 本机 ComfyUI 端口 |
| `--relay-host` | TEXT | 是 | - | 接收端机器 IP 地址 |
| `--relay-port` | INT | 否 | 9000 | 接收端监听端口 |
| `--seed` | INT | 否 | - | KSampler 随机种子 |

### 示例

```bash
# 手动 prompt 模式
semantic-tx sender --image photo.jpg --prompt "A red car" --relay-host 192.168.1.20

# VLM 自动描述模式
semantic-tx sender --image photo.jpg --auto-prompt --relay-host 192.168.1.20

# 指定端口和种子
semantic-tx sender --image photo.jpg --prompt "..." --relay-host 192.168.1.20 --relay-port 9000 --seed 42
```

---

## semantic-tx receiver

双机演示的接收端。监听端口接收发送端数据，调用 ComfyUI 还原图像。

### 参数

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| `--relay-host` | TEXT | 否 | 0.0.0.0 | 监听地址 |
| `--relay-port` | INT | 否 | 9000 | 监听端口 |
| `--comfyui-host` | TEXT | 否 | 127.0.0.1 | 本机 ComfyUI 地址 |
| `--comfyui-port` | INT | 否 | 8188 | 本机 ComfyUI 端口 |
| `--output-dir` | PATH | 否 | output/received | 输出目录 |
| `--continuous` | FLAG | 否 | - | 连续模式：持续监听 |

### 示例

```bash
# 默认配置，单次接收
semantic-tx receiver

# 连续接收模式
semantic-tx receiver --continuous

# 指定监听地址和端口
semantic-tx receiver --relay-host 0.0.0.0 --relay-port 9000 --comfyui-host 127.0.0.1
```

---

## semantic-tx demo

单机端到端演示。在同一台机器上完成：输入图像 → 边缘提取 → 语义还原 → 对比图生成。

### 参数

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| `--image` | PATH | 是 | - | 输入图像路径 |
| `--prompt` | TEXT | 与 --auto-prompt 二选一 | - | 手动指定描述文本 |
| `--auto-prompt` | FLAG | 与 --prompt 二选一 | - | 使用 VLM 自动生成描述 |
| `--sender-host` | TEXT | 否 | 127.0.0.1 | 发送端 ComfyUI 地址 |
| `--sender-port` | INT | 否 | 8188 | 发送端 ComfyUI 端口 |
| `--receiver-host` | TEXT | 否 | 127.0.0.1 | 接收端 ComfyUI 地址 |
| `--receiver-port` | INT | 否 | 8188 | 接收端 ComfyUI 端口 |
| `--output-dir` | PATH | 否 | output/demo | 输出目录 |
| `--seed` | INT | 否 | - | KSampler 随机种子 |
| `--vlm-model` | TEXT | 否 | - | VLM 模型名称 |
| `--vlm-model-path` | TEXT | 否 | `$MODEL_CACHE_DIR/Qwen/Qwen2.5-VL-7B-Instruct` | VLM 模型本地路径 |

### 示例

```bash
# 手动 prompt 模式
semantic-tx demo --image photo.jpg --prompt "A cat sitting on a sofa"

# VLM 自动描述模式
semantic-tx demo --image photo.jpg --auto-prompt

# 指定双端 ComfyUI 地址（双机场景）
semantic-tx demo --image photo.jpg --prompt "..." --sender-host 192.168.1.10 --receiver-host 192.168.1.20
```

### 输出文件

| 文件 | 说明 |
|------|------|
| `edge.png` | Canny 边缘图 |
| `restored.png` | 还原图像 |
| `comparison.png` | 对比图（原图 \| 边缘图 \| 还原图） |
| `prompt.txt` | 语义描述文本 |

---

## semantic-tx check

检查 ComfyUI 连接和工作流的子命令组。

### semantic-tx check connection

逐步测试 ComfyUI 的 REST API 和 WebSocket 端点（共 6 步）。

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| `--host` | TEXT | 否 | 从环境变量读取 | ComfyUI 主机地址 |
| `--port` | INT | 否 | 从环境变量读取 | ComfyUI 端口 |

```bash
semantic-tx check connection
semantic-tx check connection --host 192.168.1.10 --port 8188
```

### semantic-tx check workflows

验证发送端和接收端工作流是否能正常执行。

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| `--host` | TEXT | 否 | 从环境变量读取 | ComfyUI 主机地址 |
| `--port` | INT | 否 | 从环境变量读取 | ComfyUI 端口 |
| `--sender-only` | FLAG | 否 | - | 仅验证发送端 |
| `--receiver-only` | FLAG | 否 | - | 仅验证接收端 |
| `--edge-image` | PATH | 否 | - | 接收端验证用的边缘图路径 |

```bash
semantic-tx check workflows
semantic-tx check workflows --sender-only
semantic-tx check workflows --receiver-only --edge-image path/to/edge.png
```

---

## semantic-tx download

下载 ComfyUI 运行所需的模型文件（Z-Image-Turbo、ControlNet Union、Qwen2.5-VL）。

### 参数

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| `--comfyui-dir` | PATH | 否 | `$COMFYUI_DIR` | ComfyUI 安装目录 |
| `--proxy` | TEXT | 否 | `http://127.0.0.1:7890` | HuggingFace 下载代理地址（设为 `none` 禁用） |
| `--no-mirror` | FLAG | 否 | - | 禁用 HuggingFace 国内镜像（默认使用 hf-mirror.com） |
| `--cache-dir` | PATH | 否 | `$MODEL_CACHE_DIR` | 下载缓存目录 |
| `--dry-run` | FLAG | 否 | - | 仅显示将要执行的操作，不实际下载 |

### 前置工具

```bash
uv tool install modelscope
uv tool install "huggingface_hub[cli]"
```

### 示例

```bash
# 查看将要下载的文件（不实际下载）
semantic-tx download --dry-run

# 正式下载（使用默认镜像）
semantic-tx download

# 禁用镜像，使用代理
semantic-tx download --no-mirror --proxy http://127.0.0.1:7890

# 指定 ComfyUI 路径
semantic-tx download --comfyui-dir D:\path\to\ComfyUI
```

---

## 旧脚本迁移对照

| 旧脚本 | 新命令 |
|--------|--------|
| `scripts/run_sender.py` | `semantic-tx sender` |
| `scripts/run_receiver.py` | `semantic-tx receiver` |
| `scripts/demo_e2e.py` | `semantic-tx demo` |
| `scripts/test_comfyui_connection.py` | `semantic-tx check connection` |
| `scripts/verify_workflows.py` | `semantic-tx check workflows` |
| `scripts/download_models.py` | `semantic-tx download` |

旧脚本仍可运行，但会输出废弃警告，建议迁移到新 CLI 命令。
