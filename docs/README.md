# 文档索引

本目录包含语义传输项目的全部文档。按类别分类如下。

## 项目规划

| 文档 | 说明 |
|------|------|
| [project-overview.md](project-overview.md) | 项目总览：目标、进展、关键成果、后续计划（面向负责人） |
| [ROADMAP.md](ROADMAP.md) | 项目路线图：各阶段目标、当前状态、技术路线 |
| [research/2026-06-21-video-stream-tech-scout.md](research/2026-06-21-video-stream-tech-scout.md) | 视频流技术方案：帧生成/连续帧/插帧超分选型与开发计划（当前主线） |
| [superpowers/specs/2026-06-21-video-stream-6day-plan-design.md](superpowers/specs/2026-06-21-video-stream-6day-plan-design.md) | 视频流 6 天冲刺规划与三层 ROADMAP |
| [research/2026-06-reevaluation.md](research/2026-06-reevaluation.md) | 2026-06 综合评估：模型选型、技术路线、issue triage |

## 开发

| 文档 | 说明 |
|------|------|
| [development-guide.md](development-guide.md) | 开发指南：环境搭建、项目结构、测试方法、CI、编码规范 |
| [architecture.md](architecture.md) | 系统架构：模块关系图、数据流、接口设计、扩展点 |

## 使用

| 文档 | 说明 |
|------|------|
| [user-guide.md](user-guide.md) | 使用指南：系统要求、完整安装步骤、基本使用 |
| [cli-reference.md](cli-reference.md) | CLI 参考：`semantic-tx` 命令行工具完整参数说明 |
| [demo-handbook.md](demo-handbook.md) | 演示手册：单机/双机演示操作步骤、参数说明、常见错误排查 |
| [gui-design.md](gui-design.md) | GUI 设计文档：Gradio 界面布局与交互设计 |

## 调研成果

| 文档 | 说明 |
|------|------|
| [research/README.md](research/README.md) | 调研成果总索引 |
| [research/2026-07-08-teleoperation-video-route-survey.md](research/2026-07-08-teleoperation-video-route-survey.md) | 遥操作视频传输方案选型：路线决策报告（含需求锚定 + 候选方案表 + 三条推荐路线） |
| [research/selection-report.md](research/selection-report.md) | 模型与方案选型报告（阶段一结论） |
| [research/evaluation-metrics.md](research/evaluation-metrics.md) | 质量评估指标体系说明 |
| [research/comfyui-workflow-analysis.md](research/comfyui-workflow-analysis.md) | ComfyUI 工作流结构分析（阶段二历史材料） |
| [research/papers/](research/papers/) | 论文综述（语义通信领域综述） |
| [research/projects/](research/projects/) | 开源项目评估 |
| [research/models/](research/models/) | 模型对比（生成模型、视觉理解模型、ControlNet 条件） |

## 测试报告

| 文档 | 说明 |
|------|------|
| [test-reports/01-e2e-manual-prompt-test.md](test-reports/01-e2e-manual-prompt-test.md) | 端到端测试：手动 Prompt 模式 |
| [test-reports/02-e2e-detailed-prompt-test.md](test-reports/02-e2e-detailed-prompt-test.md) | 端到端测试：详细 Prompt 模式 |

## 协作规范

| 文档 | 说明 |
|------|------|
| [collaboration/README.md](collaboration/README.md) | 协作规范总索引 |
| [collaboration/01-git-basics.md](collaboration/01-git-basics.md) | Git 基础操作 |
| [collaboration/02-github-flow.md](collaboration/02-github-flow.md) | GitHub Flow 分支策略 |
| [collaboration/03-pull-request-guide.md](collaboration/03-pull-request-guide.md) | Pull Request 规范 |
| [collaboration/04-issue-management.md](collaboration/04-issue-management.md) | Issue 管理 |
| [collaboration/05-project-conventions.md](collaboration/05-project-conventions.md) | 项目约定（分支命名、Commit 规范等） |
| [collaboration/admin/](collaboration/admin/) | 仓库管理员指南（设置、CI、模板等） |

## 工作流管理

| 文档 | 说明 |
|------|------|
| [workflow/](workflow/) | structured-workflow 插件产物（任务规划、状态跟踪、依赖关系） |

> 接收端已脱离 ComfyUI（改用 Diffusers 本地推理），原 ComfyUI 部署指南与原型材料归档在 [archive/comfyui-prototype/](archive/comfyui-prototype/)。
