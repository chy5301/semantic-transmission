# ComfyUI 原型阶段归档

本目录保存 **Phase 2: ComfyUI API 原型** 阶段的历史产物。`receiver-decouple-comfyui`
workflow（2026-04-06 ~ 2026-04-09）完成后，项目接收端已完全脱离 ComfyUI 运行时，
采用 **Diffusers 本地推理**（Z-Image-Turbo + ControlNet Union，GGUF Q8_0 量化）替代。

此目录**仅作历史参考**。其中 Python 脚本依赖已删除的 `semantic_transmission.common.comfyui_client`
/ `semantic_transmission.sender.comfyui_sender` / `semantic_transmission.receiver.comfyui_receiver`，
**无法直接运行**。

## 目录结构

```
docs/archive/comfyui-prototype/
├── README.md                         # 本文件
├── comfyui-setup.md                  # 原 ComfyUI 部署指南（Phase 2）
├── workflows/                        # 原 ComfyUI 工作流 JSON
│   ├── sender_workflow_api.json      # 发送端 Canny 边缘提取工作流
│   └── receiver_workflow_api.json    # 接收端 Z-Image-Turbo + ControlNet 生成工作流
└── scripts/                          # 原 CLI 原型脚本
    ├── test_comfyui_connection.py    # ComfyUI 连通性检查脚本（已被 semantic-tx check relay/vlm/diffusers 取代）
    ├── verify_workflows.py           # 发送端/接收端工作流验证脚本
    ├── run_sender.py                 # 原始双机发送端脚本（已被 semantic-tx sender 取代）
    ├── run_receiver.py               # 原始双机接收端脚本（已被 semantic-tx receiver 取代）
    └── demo_e2e.py                   # 原始端到端 demo 脚本（已被 semantic-tx demo 取代）
```

## 当前替代方案

| 原 ComfyUI 组件 | 当前替代方案 |
|----------------|-------------|
| `common/comfyui_client.py` | 不再需要，Diffusers 直接调用 |
| `receiver/comfyui_receiver.py` | `receiver/diffusers_receiver.py` |
| `sender/comfyui_sender.py` | `sender/local_condition_extractor.py`（本地 OpenCV Canny） |
| `scripts/test_comfyui_connection.py` | `semantic-tx check vlm` / `check diffusers` / `check relay` |
| `scripts/run_sender.py` | `semantic-tx sender` |
| `scripts/run_receiver.py` | `semantic-tx receiver` |
| `scripts/demo_e2e.py` | `semantic-tx demo` |
| `resources/comfyui/*.json` workflow | Diffusers Pipeline 构造（`DiffusersReceiver.load()`） |

## 历史资料价值

- `comfyui-setup.md` 记录了 Phase 2 的 ComfyUI 服务部署细节，对理解项目早期技术决策仍有参考价值
- `workflows/*.json` 定义了原型阶段使用的节点图结构，可用于对比 Diffusers 实现下的
  采样器配置差异（AuraFlow shift=3、res_multistep 等尚未在 Diffusers 端完全对齐，见
  `docs/workflow/TASK_STATUS.md` 2026-04-07 M-09 阻断记录）
- `scripts/*.py` 可用于理解早期 CLI 的参数风格和调试工作流程
