# 工作流完成摘要

## 基本信息
- **任务名称**: comfyui-api-prototype
- **任务类型**: integration + infrastructure
- **任务前缀**: P2
- **开始时间**: 2026-03-13
- **归档时间**: 2026-03-30

## 总体统计
- 阶段数: 7（Phase 0 ~ Phase 6）
- 任务总数: 28
- 已完成: 26
- 已取消: 2（P2-15、P2-29）
- 未完成: 0

## 各阶段摘要

### Phase 0: 契约确认与项目骨架（4/4 完成）
- P2-01 搭建 Python 项目骨架（pyproject.toml + src layout）
- P2-02 定义抽象接口（BaseSender / BaseReceiver / 数据类型）
- P2-03 验证 ComfyUI API 连通性（6 端点测试）
- P2-04 分析工作流 JSON 到 API 格式转换（子图展开、widget 隐藏值处理）
- **关键成果**: 项目结构就绪，ComfyUI API 连通性验证通过，工作流转换器完成

### Phase 1: 工作流拆分与语义压缩（8/8 完成）
- P2-05 拆分工作流 JSON 为发送端/接收端
- P2-06 扩展配置支持双 ComfyUI 实例
- P2-07 实现 ComfyUI API 客户端（轮询 /history 模式）
- P2-08/P2-09 实现发送端和接收端调用
- P2-16 部署本机 ComfyUI 实例（HuggingFace 镜像 + 魔搭混合下载策略）
- P2-10 搭建端到端 Demo 脚本
- P2-13 集成 VLM 自动生成 prompt（Qwen2.5-VL-7B，transformers 原生推理）
- **关键成果**: 单机跑通「VLM 自动语义压缩 → 条件还原」完整流程

### Phase 2: 中继传输与双机演示（2/2 完成）
- P2-11 实现中继传输协议（TCP）
- P2-12 编写双机演示脚本
- **关键成果**: 两台机器可分别运行发送端/接收端，通过网络传输完成还原

### Phase 3: 质量评估与文档重构（6/6 完成，含 P2-15 已取消）
- P2-14 实现质量评估模块（PSNR / SSIM / LPIPS / CLIP Score）
- P2-17 重构 README 为文档门户
- P2-18 编写开发指南
- P2-19 编写使用指南与演示手册
- P2-20 编写项目总览与进度摘要
- P2-28 编写评估脚本与报告生成
- P2-15 脱离 ComfyUI 发送端（❌ 已取消，属于 ROADMAP 阶段四范畴）
- **关键成果**: 质量评估指标可计算，文档体系完善覆盖开发者/用户/负责人三类受众

### Phase 4: CLI 正规化（4/4 完成）
- P2-21 注册 CLI 入口与基础框架（click + semantic-tx 入口点）
- P2-22 实现 CLI 核心子命令（send / receive / demo）
- P2-23 实现 CLI 工具子命令（check / download）
- P2-24 编写 CLI 参考文档与测试
- **关键成果**: `semantic-tx` 命令注册为 console_scripts 入口点，5 个子命令可用

### Phase 5: GUI 开发（3/3 完成）
- P2-25 搭建 Gradio GUI 基础框架（`semantic-tx gui` 启动）
- P2-26 实现 GUI 发送端与接收端视图
- P2-27 实现 GUI 端到端模式与日志
- **关键成果**: Gradio 界面覆盖配置面板、发送端、接收端、端到端演示四个 Tab

### Phase 6: 修复与体验优化（0/1，P2-29 已取消）
- P2-29 修复 GUI 已知体验问题（❌ 已取消，问题迁移至 GitHub Issues #2~#5）

## 关键决策汇总

| 决策 | 理由 |
|------|------|
| 适配器模式 | ROADMAP 阶段三/四需渐进替换模型和脱离 ComfyUI |
| 任务计划重构：从"Python 重写"改为"ComfyUI 工作流拆分" | 原计划偏离用户意图，Phase 1 应聚焦工作流拆分而非重写 |
| VLM 集成从 Phase 3 提前到 Phase 1 | 自动语义压缩是核心能力，应优先验证 |
| 取消 P2-15（脱离 ComfyUI 发送端） | 属于 ROADMAP 阶段四范畴，当前工作流聚焦原型 |
| VLM 推理：transformers 原生而非 ComfyUI 节点 | ComfyUI 缺少 system prompt 控制，transformers 为脱离 ComfyUI 铺路 |
| PyTorch 使用 cu130 索引 | RTX 5090 需 CUDA 13.0+，兼容 CPU-only 环境 |
| 质量评估用独立库而非 torchmetrics | 预研项目需可见可控的实现，代码量小 |
| 模型下载：HuggingFace 镜像 + 魔搭混合 | 魔搭模型文件格式不兼容 ComfyUI，主模型走 hf-mirror |
| Gradio 6.x theme/css 参数迁移 | Gradio 6.0 将 theme/css 从构造函数移至 launch() |

## 遗留问题清单

以下问题已迁移至 GitHub Issues，在后续分支中修复：

1. **GUI 端到端质量评估报错** — `Image.open` 收到 `numpy.ndarray`（[#2](https://github.com/chy5301/semantic-transmission/issues/2)）
2. **GUI 接收端 seed=0 被误判为未设置** — `if seed` 对 0 为 False（[#3](https://github.com/chy5301/semantic-transmission/issues/3)）
3. **GUI 界面优化** — Radio 圆点冗余 + 接收端输出区布局（[#4](https://github.com/chy5301/semantic-transmission/issues/4)）
4. **GUI 运行记录持久化** — 待讨论实现程度（[#5](https://github.com/chy5301/semantic-transmission/issues/5)）

## 经验教训

1. **尽早对齐用户意图，避免过度设计**: Phase 1 最初计划用 Python 重写发送端，偏离了用户"最快打通 demo"的目标。重构后聚焦工作流拆分，进度明显加快。
2. **核心能力优先验证**: VLM 自动语义压缩是项目区分于传统压缩的关键，从 Phase 3 提前到 Phase 1 后，尽早验证了端到端可行性。
3. **模型下载需验证文件格式兼容性**: 魔搭仓库的 DiffSynth 分片格式与 ComfyUI 不兼容，仅检查 config.json 不足以判断下载完整性，需逐个验证权重分片文件。
4. **冻结而非删除暂时不需要的代码**: P2-02 抽象接口先冻结后解冻复用，避免了 revert 的复杂性。
5. **工作流范围应严格对应 ROADMAP 阶段**: P2-15 越界到 ROADMAP 阶段四，及时取消避免了范围蔓延。
