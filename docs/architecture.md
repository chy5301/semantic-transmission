# 系统架构

## 模块关系

```mermaid
graph TB
    subgraph common["common — 公共模块"]
        config["config.py<br/>ComfyUI 连接配置"]
        types["types.py<br/>数据类型定义"]
        client["comfyui_client.py<br/>ComfyUI HTTP/WS 客户端"]
    end

    subgraph sender["sender — 发送端"]
        base_s["base.py<br/>BaseSender / BaseConditionExtractor"]
        comfyui_s["comfyui_sender.py<br/>ComfyUI 工作流调用"]
        qwen_vl["qwen_vl_sender.py<br/>Qwen-VL 本地推理"]
    end

    subgraph receiver["receiver — 接收端"]
        base_r["base.py<br/>BaseReceiver"]
        comfyui_r["comfyui_receiver.py<br/>ComfyUI 工作流调用"]
        wf_conv["workflow_converter.py<br/>工作流 JSON→API 格式转换"]
    end

    subgraph pipeline["pipeline — 管道编排"]
        relay["relay.py<br/>LocalRelay / SocketRelay"]
    end

    subgraph evaluation["evaluation — 质量评估"]
        pixel["pixel_metrics.py<br/>PSNR / SSIM"]
        perceptual["perceptual_metrics.py<br/>LPIPS"]
        semantic["semantic_metrics.py<br/>CLIP Score"]
    end

    base_s --> types
    base_r --> types
    comfyui_s --> client
    comfyui_s --> config
    comfyui_r --> client
    comfyui_r --> config
    comfyui_r --> wf_conv
    qwen_vl --> base_s
    comfyui_s --> base_s
    comfyui_r --> base_r
    relay --> types
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
    Note over Sender: 1. Qwen-VL 生成语义描述<br/>2. OpenCV Canny 提取边缘图
    Sender->>Relay: TransmissionData<br/>(text + edge_image + metadata)
    Note over Relay: LocalRelay: 内存传递<br/>SocketRelay: TCP length-prefixed framing
    Relay->>Receiver: text + condition_image
    Note over Receiver: ComfyUI API 调用<br/>Z-Image-Turbo + ControlNet Union
    Receiver->>Out: ReceiverOutput (还原图像)
```

## 抽象接口设计

项目采用适配器模式，便于后续替换具体实现：

| 抽象基类 | 当前实现 | 说明 |
|----------|----------|------|
| `BaseSender` | `QwenVLSender` | 使用 Qwen-VL 多模态模型生成语义描述 |
| `BaseConditionExtractor` | `ComfyUISender` 内嵌 | 使用 OpenCV Canny 提取边缘图 |
| `BaseReceiver` | `ComfyUIReceiver` | 通过 ComfyUI API 调用 Z-Image-Turbo + ControlNet |
| `BaseRelay` | `LocalRelay` / `SocketRelaySender`+`SocketRelayReceiver` | 内存传递或 TCP 传输 |

## ComfyUI 客户端调用流程

```mermaid
sequenceDiagram
    participant App as 应用层
    participant Client as ComfyUIClient
    participant API as ComfyUI HTTP API
    participant WS as ComfyUI WebSocket

    App->>Client: submit_workflow(api_format_json)
    Client->>API: POST /prompt
    API-->>Client: prompt_id
    Client->>API: GET /history/{prompt_id} (轮询)
    API-->>Client: history_entry (完成时)
    Client->>Client: get_result_images(history_entry)
    Client->>API: GET /view?filename=...
    API-->>Client: 图像数据
    Client-->>App: 结果图像列表
```

## 传输协议

TCP 中继使用 length-prefixed framing 协议，每个字段由 4 字节大端 uint32 长度头 + 原始数据组成：

```
[edge_image_length:4B][edge_image:NB][text_length:4B][text:NB][metadata_length:4B][metadata:NB]
```

## 扩展点

- **发送端模型替换**：实现 `BaseSender` 接口即可接入新的视觉理解模型
- **条件类型扩展**：实现 `BaseConditionExtractor` 支持深度图、分割图等条件
- **接收端模型替换**：实现 `BaseReceiver` 可接入非 ComfyUI 的生成模型（如 diffusers 直接推理）
- **传输协议扩展**：实现 `BaseRelay` 可替换为 WebSocket、gRPC 等传输方式
