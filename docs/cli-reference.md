# CLI 参考文档

`semantic-tx` 是语义传输系统的命令行工具，提供发送、接收、端到端演示、
模型就绪检查和模型下载功能。

## 安装

```bash
uv sync
```

安装后即可使用 `uv run semantic-tx` 或（在虚拟环境激活后）直接使用 `semantic-tx`。

## 命令总览

| 命令 | 说明 |
|------|------|
| `semantic-tx sender` | 发送端：提取边缘图 + 语义描述 → 发送到接收端 |
| `semantic-tx receiver` | 接收端：监听端口接收数据 → Diffusers 本地还原 |
| `semantic-tx demo` | 端到端演示：图像 → 边缘提取 → 语义还原 |
| `semantic-tx batch-demo` | 批量端到端演示：目录中所有图片 → 逐一处理 |
| `semantic-tx check vlm` | 检查发送端 VLM 模型是否就绪 |
| `semantic-tx check diffusers` | 检查接收端 Diffusers 模型是否就绪 |
| `semantic-tx check relay` | 测试双机部署对端 TCP 可达性 |
| `semantic-tx download` | 下载模型文件（Z-Image-Turbo、ControlNet Union、Qwen2.5-VL） |
| `semantic-tx gui` | 启动 Gradio 可视化界面 |

## 全局选项

```
--version  显示版本号
--help     显示帮助信息
```

---

## semantic-tx sender

双机部署的发送端。提取输入图像的 Canny 边缘图，生成语义描述，通过 TCP 中继发送到接收端。

### 参数

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| `--image` | PATH | 是 | - | 输入图像路径 |
| `--prompt` | TEXT | 与 --auto-prompt 二选一 | - | 手动指定描述文本 |
| `--auto-prompt` | FLAG | 与 --prompt 二选一 | - | 使用 VLM 自动生成描述 |
| `--vlm-model` | TEXT | 否 | - | VLM 模型名称 |
| `--vlm-model-path` | TEXT | 否 | `$MODEL_CACHE_DIR/Qwen/Qwen2.5-VL-7B-Instruct` | VLM 模型本地路径 |
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

双机部署的接收端。监听端口接收发送端数据，使用 Diffusers 本地还原图像。

### 参数

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| `--relay-host` | TEXT | 否 | 0.0.0.0 | 监听地址 |
| `--relay-port` | INT | 否 | 9000 | 监听端口 |
| `--output-dir` | PATH | 否 | output/received | 输出目录 |
| `--continuous` | FLAG | 否 | - | 连续模式：持续监听 |

### 示例

```bash
# 默认配置，单次接收
semantic-tx receiver

# 连续接收模式
semantic-tx receiver --continuous

# 指定监听地址和端口
semantic-tx receiver --relay-host 0.0.0.0 --relay-port 9000
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
| `--threshold1` | INT | 否 | 100 | Canny 低阈值 |
| `--threshold2` | INT | 否 | 200 | Canny 高阈值 |
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

# 指定随机种子便于复现
semantic-tx demo --image photo.jpg --auto-prompt --seed 42
```

### 输出文件

| 文件 | 说明 |
|------|------|
| `edge.png` | Canny 边缘图 |
| `restored.png` | 还原图像 |
| `comparison.png` | 对比图（原图 \| 边缘图 \| 还原图） |
| `prompt.txt` | 语义描述文本 |

---

## semantic-tx batch-demo

批量端到端演示。对目录中所有支持的图片执行完整流程，每张图片生成独立子目录。

### 参数

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| `--input-dir` | PATH | 是 | - | 输入图像目录 |
| `--output-dir` | PATH | 否 | output/batch-demo | 输出根目录 |
| `--prompt` | TEXT | 与 --auto-prompt 二选一 | - | 手动指定描述文本（所有图片共用） |
| `--auto-prompt` | FLAG | 与 --prompt 二选一 | - | 为每张图片使用 VLM 自动生成描述 |
| `--recursive` | FLAG | 否 | - | 递归扫描子目录 |
| `--skip-errors` | FLAG | 否 | - | 跳过失败图片继续处理 |
| `--threshold1` | INT | 否 | 100 | Canny 低阈值 |
| `--threshold2` | INT | 否 | 200 | Canny 高阈值 |
| `--seed` | INT | 否 | - | KSampler 随机种子 |

### 示例

```bash
# 批量 VLM 自动描述
semantic-tx batch-demo --input-dir resources/test_images --auto-prompt

# 批量手动描述（所有图共用）
semantic-tx batch-demo --input-dir resources/test_images --prompt "A scenic view" --skip-errors
```

---

## semantic-tx check

模型就绪检测与双机连通性测试子命令组。所有 check 子命令以非零退出码表示失败，
便于 shell 脚本链式判断。

### semantic-tx check vlm

检查发送端 VLM（Qwen2.5-VL）模型是否就绪。

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| `--model-path` | TEXT | 否 | `$MODEL_CACHE_DIR/Qwen/Qwen2.5-VL-7B-Instruct` | VLM 模型本地路径 |

输出示例：

```
VLM 模型就绪：D:\Downloads\Models\Qwen\Qwen2.5-VL-7B-Instruct
```

```bash
semantic-tx check vlm
semantic-tx check vlm --model-path /path/to/alternative/Qwen2.5-VL
```

### semantic-tx check diffusers

检查接收端 Diffusers 模型是否就绪。检测 transformer GGUF、ControlNet 权重、
HF cache 下 pipeline base 组件三处资源。

该命令无参数，使用 `DiffusersReceiverConfig` 默认路径（受 `MODEL_CACHE_DIR` 和 `HF_HOME` 环境变量影响）。

输出示例：

```
Diffusers 接收端模型就绪
✓ transformer GGUF：D:\Downloads\Models\Z-Image-Turbo\z-image-turbo-Q8_0.gguf
✓ ControlNet 权重：D:\Downloads\Models\Z-Image-Turbo\Z-Image-Turbo-Fun-Controlnet-Union.safetensors
✓ HF cache pipeline base：C:\Users\chy\.cache\huggingface\hub\models--Tongyi-MAI--Z-Image-Turbo
```

```bash
semantic-tx check diffusers
```

### semantic-tx check relay

测试双机部署下对端接收端 TCP 端口是否可达。

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| `--host` | TEXT | 是 | - | 对端主机地址 |
| `--port` | INT | 是 | - | 对端端口 |
| `--timeout` | FLOAT | 否 | 5.0 | 连接超时秒数 |

输出示例：

```
测试对端连接：192.168.1.20:9000（超时 5.0s）
✓ 连接成功：192.168.1.20:9000 可达
```

```bash
semantic-tx check relay --host 192.168.1.20 --port 9000
semantic-tx check relay --host 127.0.0.1 --port 9000 --timeout 1.0
```

---

## semantic-tx download

下载运行所需的模型文件（Z-Image-Turbo、ControlNet Union、Qwen2.5-VL）。

### 参数

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
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
```

---

## semantic-tx gui

启动 Gradio 可视化界面。提供配置 / 单张发送 / 批量发送 / 接收端 / 端到端演示 / 批量端到端 共 6 个 Tab。

### 参数

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| `--host` | TEXT | 否 | 127.0.0.1 | 监听地址 |
| `--port` | INT | 否 | 7860 | 监听端口 |
| `--share` | FLAG | 否 | - | 生成 Gradio 公网分享链接 |

### 示例

```bash
# 默认启动
semantic-tx gui

# 指定端口
semantic-tx gui --port 8080

# 局域网访问
semantic-tx gui --host 0.0.0.0

# 生成公网链接（用于远程演示）
semantic-tx gui --share
```

---

## 历史脚本

以下脚本在 `receiver-decouple-comfyui` workflow（2026-04 完成）后已归档到
`docs/archive/comfyui-prototype/scripts/`，对应功能由 `semantic-tx` 子命令取代，
归档脚本**无法直接运行**：

| 归档脚本 | 当前替代命令 |
|---------|-------------|
| `scripts/run_sender.py` | `semantic-tx sender` |
| `scripts/run_receiver.py` | `semantic-tx receiver` |
| `scripts/demo_e2e.py` | `semantic-tx demo` |
| `scripts/test_comfyui_connection.py` | `semantic-tx check vlm` / `check diffusers` / `check relay` |
| `scripts/verify_workflows.py` | `semantic-tx check diffusers` |
