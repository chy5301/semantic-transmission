# 依赖关系图

## 任务依赖拓扑

```mermaid
graph TD
    subgraph phase0["Phase 0: 契约确认与项目骨架"]
        P2-01[P2-01: 搭建-Python 项目骨架]
        P2-02[P2-02: 定义-抽象接口]
        P2-03[P2-03: 验证-ComfyUI API 连通性]
        P2-04[P2-04: 分析-工作流 JSON 转换]
    end

    subgraph phase1["Phase 1: 工作流拆分与语义压缩"]
        P2-05[P2-05: 拆分-工作流 JSON]
        P2-06[P2-06: 扩展-配置支持双实例]
        P2-07[P2-07: 实现-ComfyUI API 客户端]
        P2-08[P2-08: 实现-发送端调用]
        P2-09[P2-09: 实现-接收端调用]
        P2-16[P2-16: 部署-本机 ComfyUI]
        P2-10[P2-10: 搭建-端到端 Demo]
        P2-13[P2-13: 集成-VLM 自动 prompt]
    end

    subgraph phase2["Phase 2: 中继传输与双机演示"]
        P2-11[P2-11: 实现-中继传输协议]
        P2-12[P2-12: 编写-双机演示脚本]
    end

    subgraph phase3["Phase 3: 质量评估与文档重构"]
        P2-14[P2-14: 实现-质量评估模块]
        P2-17[P2-17: 重构-README 为文档门户]
        P2-18[P2-18: 编写-开发指南]
        P2-19[P2-19: 编写-使用指南与演示手册]
        P2-20[P2-20: 编写-项目总览与进度摘要]
    end

    subgraph phase4["Phase 4: CLI 正规化"]
        P2-21[P2-21: 注册-CLI 入口与框架]
        P2-22[P2-22: 实现-CLI 核心子命令]
        P2-23[P2-23: 实现-CLI 工具子命令]
        P2-24[P2-24: 编写-CLI 参考文档与测试]
    end

    subgraph phase5["Phase 5: GUI 开发"]
        P2-25[P2-25: 搭建-Gradio GUI 基础框架]
        P2-26[P2-26: 实现-GUI 发送/接收视图]
        P2-27[P2-27: 实现-GUI 端到端+日志]
    end

    %% Phase 0 内部
    P2-01 --> P2-02
    P2-01 --> P2-03
    P2-03 --> P2-04

    %% Phase 0 → Phase 1
    P2-04 --> P2-05
    P2-03 --> P2-06
    P2-06 --> P2-07
    P2-05 --> P2-08
    P2-07 --> P2-08
    P2-05 --> P2-09
    P2-07 --> P2-09
    P2-05 --> P2-16
    P2-08 --> P2-10
    P2-09 --> P2-10
    P2-16 --> P2-10
    P2-10 --> P2-13

    %% Phase 1 → Phase 2
    P2-10 --> P2-11
    P2-11 --> P2-12

    %% Phase 1 → Phase 3
    P2-10 --> P2-14

    %% Phase 3 内部：P2-17~P2-20 无依赖

    %% Phase 4 内部
    P2-21 --> P2-22
    P2-21 --> P2-23
    P2-22 --> P2-24
    P2-23 --> P2-24

    %% Phase 4 → Phase 5
    P2-21 --> P2-25
    P2-25 --> P2-26
    P2-26 --> P2-27

    %% 样式
    style P2-01 fill:#e1f5fe
    style P2-02 fill:#e1f5fe
    style P2-03 fill:#e1f5fe
    style P2-04 fill:#e1f5fe
    style P2-05 fill:#fff3e0
    style P2-06 fill:#fff3e0
    style P2-07 fill:#fff3e0
    style P2-08 fill:#fff3e0
    style P2-09 fill:#fff3e0
    style P2-16 fill:#fff3e0
    style P2-10 fill:#fff3e0
    style P2-13 fill:#fff3e0
    style P2-11 fill:#e8f5e9
    style P2-12 fill:#e8f5e9
    style P2-14 fill:#fce4ec
    style P2-17 fill:#fce4ec
    style P2-18 fill:#fce4ec
    style P2-19 fill:#fce4ec
    style P2-20 fill:#fce4ec
    style P2-21 fill:#f3e5f5
    style P2-22 fill:#f3e5f5
    style P2-23 fill:#f3e5f5
    style P2-24 fill:#f3e5f5
    style P2-25 fill:#fff8e1
    style P2-26 fill:#fff8e1
    style P2-27 fill:#fff8e1
```

## 并行执行机会

| 可并行组 | 任务 | 前置条件 |
|----------|------|----------|
| 组 A | P2-14 ∥ P2-17 ∥ P2-18 ∥ P2-19 ∥ P2-20 ∥ P2-21 | 无（Phase 3+4 入口全部独立） |
| 组 B | P2-22 ∥ P2-23 ∥ P2-25 | P2-21 完成后 |
| 组 C | P2-24 ∥ P2-26 | P2-22+P2-23 完成后 / P2-25 完成后 |

## 关键路径

**最长路径（新增）**：P2-21 → P2-25 → P2-26 → P2-27（CLI 框架 → GUI 全链路）

此路径决定了 Phase 4+5 的最短完成时间。P2-21（CLI 框架）是 Phase 4 和 Phase 5 的共同前置，应优先实施。
