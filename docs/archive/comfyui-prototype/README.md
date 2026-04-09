# ComfyUI 原型阶段归档

本目录保存 **Phase 2: ComfyUI API 原型** 阶段的历史产物。`receiver-decouple-comfyui`
workflow（2026-04-06 ~ 2026-04-09）完成后，项目接收端已完全脱离 ComfyUI 运行时，
采用 **Diffusers 本地推理**（Z-Image-Turbo + ControlNet Union，GGUF Q8_0 量化）替代。

此目录**仅作历史参考**，保留 Phase 2 阶段具有设计参考价值的文档和工作流定义。
原 ComfyUI 原型脚本（`run_sender.py` / `run_receiver.py` / `demo_e2e.py` /
`test_comfyui_connection.py` / `verify_workflows.py`）已从归档目录移除 ——
它们依赖已删除的运行时模块、无法直接运行，如需查看请参考 git 历史。

## 目录结构

```
docs/archive/comfyui-prototype/
├── README.md                         # 本文件
├── comfyui-setup.md                  # 原 ComfyUI 部署指南（Phase 2）
└── workflows/                        # 原 ComfyUI 工作流 JSON
    ├── sender_workflow_api.json      # 发送端 Canny 边缘提取工作流
    └── receiver_workflow_api.json    # 接收端 Z-Image-Turbo + ControlNet 生成工作流
```

## 当前替代方案

| 原 ComfyUI 组件 | 当前替代方案 |
|----------------|-------------|
| `common/comfyui_client.py` | 不再需要，Diffusers 直接调用 |
| `receiver/comfyui_receiver.py` | `receiver/diffusers_receiver.py` |
| `sender/comfyui_sender.py` | `sender/local_condition_extractor.py`（本地 OpenCV Canny） |
| 原 `scripts/test_comfyui_connection.py` | `semantic-tx check vlm` / `check diffusers` / `check relay` |
| 原 `scripts/run_sender.py` | `semantic-tx sender` |
| 原 `scripts/run_receiver.py` | `semantic-tx receiver` |
| 原 `scripts/demo_e2e.py` | `semantic-tx demo` |
| `resources/comfyui/*.json` workflow | Diffusers Pipeline 构造（`DiffusersReceiver.load()`） |

## 历史资料价值

- `comfyui-setup.md` 记录了 Phase 2 的 ComfyUI 服务部署细节，对理解项目早期技术决策仍有参考价值
- `workflows/*.json` 定义了原型阶段使用的节点图结构，可用于对比 Diffusers 实现下的
  采样器配置差异（AuraFlow shift=3、res_multistep 等尚未在 Diffusers 端完全对齐，见
  `docs/workflow/TASK_STATUS.md` 2026-04-07 M-09 阻断记录）
