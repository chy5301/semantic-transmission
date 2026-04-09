# 系统架构

## 模块关系

```mermaid
graph TB
    subgraph common["common — 公共模块"]
        config["config.py<br/>DiffusersReceiverConfig / 路径工具"]
        model_check["model_check.py<br/>VLM / Diffusers 模型就绪检测"]
    end

    subgraph sender["sender — 发送端"]
        base_s["base.py<br/>BaseSender / BaseConditionExtractor"]
        local_canny["local_condition_extractor.py<br/>OpenCV Canny 边缘提取"]
        qwen_vl["qwen_vl_sender.py<br/>Qwen2.5-VL 本地推理"]
    end

    subgraph receiver["receiver — 接收端"]
        base_r["base.py<br/>BaseReceiver / FrameInput / BatchOutput"]
        diffusers_r["diffusers_receiver.py<br/>Z-Image-Turbo GGUF + ControlNet Union"]
        factory["__init__.py<br/>create_receiver 工厂函数"]
    end

    subgraph pipeline["pipeline — 管道编排"]
        relay["relay.py<br/>SocketRelaySender / SocketRelayReceiver"]
        batch["batch_processor.py<br/>批量发现 / BatchResult / SampleResult"]
    end

    subgraph evaluation["evaluation — 质量评估"]
        pixel["pixel_metrics.py<br/>PSNR / SSIM"]
        perceptual["perceptual_metrics.py<br/>LPIPS"]
        semantic["semantic_metrics.py<br/>CLIP Score"]
    end

    subgraph gui["gui — 可视化界面"]
        app["app.py<br/>Gradio Blocks 主应用"]
        theme["theme.py<br/>主题与样式"]
        config_panel["config_panel.py<br/>模型就绪检测面板"]
    end

    config_panel --> model_check
    model_check --> config

    base_s --> local_canny
    base_s --> qwen_vl
    diffusers_r --> base_r
    diffusers_r --> config
    factory --> diffusers_r
    relay --> batch
```

## 核心数据流

```mermaid
sequenceDiagram
    participant Src as 源图像
    participant Sender as 发送端
    participant Relay as 中继传输
    participant Receiver as 接收端
    participant Out as 还原图像

    Src->>Sender: 输入图像 (numpy array)
    Note over Sender: 1. OpenCV Canny 提取边缘图<br/>2. Qwen2.5-VL 生成语义描述（可选）
    Sender->>Relay: TransmissionPacket<br/>(edge_image + prompt_text + metadata)
    Note over Relay: SocketRelay: TCP length-prefixed framing<br/>单机场景可直接构造 packet 传入 receiver
    Relay->>Receiver: edge_image + prompt_text
    Note over Receiver: Diffusers 本地推理<br/>GGUF Q8_0 transformer + ControlNet Union<br/>Z-Image-Turbo pipeline
    Receiver->>Out: PIL.Image (还原图像)
```

## 抽象接口设计

项目采用适配器模式，便于后续替换具体实现：

| 抽象基类 | 当前实现 | 说明 |
|----------|----------|------|
| `BaseSender` | `QwenVLSender` | 使用 Qwen2.5-VL 多模态模型生成语义描述 |
| `BaseConditionExtractor` | `LocalCannyExtractor` | 使用 OpenCV Canny 提取边缘图 |
| `BaseReceiver` | `DiffusersReceiver` | 使用 Diffusers 0.37 + Z-Image-Turbo GGUF + ControlNet Union 本地推理 |
| 中继传输 | `SocketRelaySender` / `SocketRelayReceiver` | TCP length-prefixed 协议，双机部署时使用 |

## Diffusers 接收端加载流程

```mermaid
sequenceDiagram
    participant App as 应用层
    participant Factory as create_receiver
    participant Rec as DiffusersReceiver
    participant TF as ZImageTransformer2DModel
    participant CN as ZImageControlNetModel
    participant Pipe as ZImageControlNetPipeline

    App->>Factory: create_receiver()
    Factory-->>App: DiffusersReceiver 实例
    App->>Rec: process(edge_image, prompt, seed)
    Rec->>Rec: load()（首次调用）
    Rec->>TF: from_single_file(gguf_path, quantization_config=GGUFQuantizationConfig)
    TF-->>Rec: Q8_0 量化的 transformer
    Rec->>CN: from_single_file(controlnet_path, torch_dtype=bf16)
    CN-->>Rec: ControlNet Union 模型
    Rec->>Pipe: from_pretrained(model_name, transformer=tf, controlnet=cn)
    Note over Pipe: 跳过 transformer/controlnet 子目录加载<br/>从 HF cache 加载 text_encoder/tokenizer/scheduler/vae
    Pipe-->>Rec: 完整 Pipeline
    Rec->>Pipe: __call__(prompt, control_image, num_inference_steps=9)
    Pipe-->>Rec: 还原图像
    Rec-->>App: PIL.Image
```

## 传输协议

TCP 中继使用 length-prefixed framing 协议，每个字段由 4 字节大端 uint32 长度头 + 原始数据组成：

```
[edge_image_length:4B][edge_image:NB][text_length:4B][text:NB][metadata_length:4B][metadata:NB]
```

## 扩展点

- **发送端模型替换**：实现 `BaseSender` 接口即可接入新的视觉理解模型
- **条件类型扩展**：实现 `BaseConditionExtractor` 支持深度图、分割图等条件
- **接收端模型替换**：实现 `BaseReceiver` 可接入其他生成模型（Wan2.x 等）
- **量化策略扩展**：`DiffusersReceiver.load()` 目前写死 GGUF Q8_0 分组件加载，未来可抽象为 `ModelLoader` 策略模式
- **传输协议扩展**：`pipeline.relay` 可扩展 WebSocket / gRPC 等传输方式
