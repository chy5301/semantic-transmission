# 语义传输（Semantic Transmission）

基于 AI 生成模型的视频语义级压缩传输预研项目。核心思路是用语义描述替代像素级编码，在极低码率（<0.01 bpp）下实现视频传输。

## 系统架构

```mermaid
graph LR
    subgraph sender["发送端"]
        A[源视频] --> B[视觉理解模型<br/>语义描述生成]
        A --> C[条件提取<br/>Canny/深度图/分割]
    end
    subgraph transport["传输层（极低码率）"]
        B --> D[文本描述]
        C --> E[结构化条件]
    end
    subgraph receiver["接收端"]
        D --> F[生成模型<br/>图像/视频重建]
        E --> F
        F --> G[还原视频]
    end
```

- **发送端**：通过多模态大模型（如 Qwen-VL）将视频帧压缩为文本描述，并提取结构化条件信息（边缘图、深度图等）
- **传输层**：仅传输文本和轻量条件信息，实现极低码率
- **接收端**：通过扩散生成模型（如 Z-Image-Turbo、Wan2.x）从语义信息还原视觉内容

## 项目阶段

| 阶段 | 目标 | 状态 |
|------|------|------|
| 阶段一：调研与选型 | 论文综述、开源项目评估、技术路线确定 | ✅ 已完成 |
| 阶段二：ComfyUI API 原型 | 基于 ComfyUI API 打通端到端流程 | 🔄 进行中（10/16） |
| 阶段三：方案迭代优化 | 模型升级、条件优化、视频级扩展 | 待启动 |
| 阶段四：工程化 | 脱离 ComfyUI，构建独立可部署系统 | 待启动 |

详见 [项目路线图](docs/ROADMAP.md)。

## 项目结构

```
├── src/semantic_transmission/
│   ├── common/                     # 公共模块：ComfyUI 客户端、配置、类型定义
│   ├── pipeline/                   # 端到端管道编排
│   ├── sender/                     # 发送端：图像/视频 → 语义描述 + 条件信息
│   └── receiver/                   # 接收端：语义描述 → 图像/视频还原
├── tests/                          # 单元测试
├── docs/
│   ├── ROADMAP.md                  # 项目路线图
│   ├── comfyui-setup.md            # ComfyUI 本机部署指南
│   ├── research/                   # 调研产出
│   │   ├── papers/                 # 论文综述
│   │   ├── projects/               # 开源项目评估
│   │   ├── models/                 # 模型对比（待完成）
│   │   └── comfyui-workflow-analysis.md  # ComfyUI 工作流分析
│   ├── collaboration/              # 协作规范（Git/GitHub/PR/Issue）
│   └── workflow/                   # 结构化工作流管理
├── resources/
│   └── comfyui/                    # ComfyUI 工作流文件及截图
├── .github/                        # GitHub 模板与 CI 工作流
└── CLAUDE.md                       # AI 辅助开发配置
```

## 技术栈

- **开发语言**：Python（uv 管理依赖）
- **工作流引擎**：ComfyUI（API 模式远程调用）
- **视觉理解**：Qwen-VL 等多模态大模型
- **图像生成**：Z-Image-Turbo + ControlNet Union（当前基线）
- **视频生成**：Wan2.x（规划中）

## 调研成果

阶段一调研已完成，主要结论：

- 在 <0.01 bpp 超低码率下，生成式语义传输全面优于 H.264/H.265（多篇论文交叉验证）
- 确定以 ComfyUI API 为基础设施，自行组装发送端（VLM）和接收端（生成模型）的技术路线
- 详细调研报告见 [docs/research/](docs/research/)
