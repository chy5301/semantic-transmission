# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

本项目是一个"语义传输"（Semantic Transmission / Semantic Communication）预研项目。核心思路是用 AI 模型实现视频的语义级压缩传输：

- **发送端**：通过视频理解模型（视频生文/图生文）将视频帧压缩为文本描述 + 结构化条件（关键帧、边缘图等）
- **接收端**：通过生成模型（文生图/文生视频）从文本和条件信息还原出视觉内容

目标是实现极低码率下的视频传输 demo。

## 项目阶段

1. **调研阶段**：收集语义传输相关论文和项目（GVSC、GVC、GSC 等），形成调研报告
2. **ComfyUI API 集成**：基于同事已有的 ComfyUI 工作流，将发送端和接收端封装为 API 打通流程
3. **逐步替换优化**：用更优实现替换 ComfyUI 工作流节点，最终可能完全脱离 ComfyUI

## 当前资源

- `resources/comfyui/` — 同事构建的 ComfyUI 工作流文件（JSON）及界面截图
  - 当前工作流使用 Z-Image-Turbo + ControlNet Union 实现图像到图像的 Canny 边缘控制生成
  - 模型：qwen_3_4b (text encoder)、z_image_turbo_bf16 (diffusion)、ae (VAE)、Z-Image-Turbo-Fun-Controlnet-Union (controlnet)
- `docs/` — 文档目录（待填充调研报告等）

## 技术栈（规划中）

- **ComfyUI API 模式**：通过 HTTP API 调用 ComfyUI 工作流（本机未安装 ComfyUI，需远程调用或部署）
- **Python**：主要开发语言，使用 uv 管理依赖
- **生成模型**：Stable Diffusion 系列、Wan2.x 等扩散模型
- **视觉理解模型**：Qwen-VL 等多模态大模型用于图像/视频描述生成
