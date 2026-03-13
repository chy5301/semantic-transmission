# 语义传输预研 — 调研总览

## 调研目标

为语义传输 demo 原型的技术选型提供依据，覆盖以下问题：

1. **学术前沿**：语义传输/语义通信领域有哪些代表性方案？各自的压缩率、还原质量和系统架构如何？
2. **可复用资源**：有哪些开源项目、框架、ComfyUI 工作流可以直接利用或参考？
3. **模型选型**：发送端（视觉理解）和接收端（图像/视频生成）分别选用什么模型？条件控制采用什么方式？

## 调研范围

| 维度 | 范围 | 产出 |
|------|------|------|
| 论文综述 | 语义通信/视频语义通信，2024-2026 年核心论文 ≥5 篇 | `papers/semantic-communication-survey.md` |
| 开源项目 | GitHub 语义通信项目 + ComfyUI 生态相关工作流 | `projects/opensource-evaluation.md` |
| 视觉理解模型 | Qwen-VL、InternVL、LLaVA 等多模态大模型 | `models/visual-understanding-models.md` |
| 生成模型 | SD3/FLUX/Z-Image-Turbo（图像）、Wan2.x/CogVideoX（视频） | `models/generation-models.md` |
| 条件控制 | Canny/深度图/语义分割等 ControlNet 条件方式 | `models/controlnet-conditions.md` |

## 文档索引

| 文档 | 说明 | 状态 |
|------|------|------|
| [skill-evaluation.md](skill-evaluation.md) | 调研辅助 Skill 搜索与评估 | 已完成 |
| [papers/](papers/) | 论文综述 | 待完成 |
| [projects/](projects/) | 开源项目评估 | 待完成 |
| [models/](models/) | 模型能力对比 | 待完成 |

## 技术基线

现有 ComfyUI 工作流（详见 [comfyui-workflow-analysis.md](comfyui-workflow-analysis.md)，待完成）使用的技术栈：

- **文本编码**: qwen_3_4b
- **图像生成**: Z-Image-Turbo (9 步采样)
- **条件控制**: ControlNet Union (Canny 边缘，阈值 0.15/0.35)
- **VAE**: ae

调研需要评估是否有更优的模型或条件控制方式替代上述组件。
