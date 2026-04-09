# PR #14 合并影响分析

> 2026-04-02，PR #14（Sender）review 及合并过程中的发现，供继续工作流前决策参考。

## PR #14 概要

- 作者：Vickynsx
- 内容：批量图片处理（CLI + GUI）、发送端 Canny 边缘提取脱离 ComfyUI（LocalCannyExtractor）、bitsandbytes 量化依赖
- 新增文件：`cli/batch_demo.py`、`cli/batch_sender.py`、`gui/batch_panel.py`、`gui/batch_sender_panel.py`、`pipeline/batch_processor.py`、`sender/local_condition_extractor.py`

## 对工作流的潜在影响

### 可复用的基础设施

**`pipeline/batch_processor.py`** 提供了通用批量处理数据结构：
- `BatchResult` / `SampleResult` — 批量处理结果统计
- `BatchImageDiscoverer` — 目录图片扫描
- `make_sample_output_dir` — 输出目录创建

这些和发送/接收无关，是通用工具。M-06（批量连续帧生成）可能可以复用。

### 不如我们计划的地方

1. **无工厂模式** — PR 直接在各调用点把 `ComfyUISender` 换成 `LocalCannyExtractor`，没有抽象层。结果 `gui/batch_panel.py` 遗漏未改，仍用 `ComfyUISender`。证明了 M-03 工厂函数方案的必要性。

2. **CLI 代码重复** — `cli/batch_demo.py`（333 行）和 `cli/batch_sender.py`（350 行）之间大量重复逻辑（参数定义、目录扫描、VLM 加载、结果统计）。

3. **`batch_panel.py` 仍依赖 ComfyUI** — 声称发送端脱离 ComfyUI，但"批量端到端"面板仍硬编码 `ComfyUISender`。

### 新增的适配范围

M-07（GUI 适配）和 M-08（CLI 适配）原计划只涉及 `receiver_panel.py`、`pipeline_panel.py`、`cli/demo.py`。PR #14 新增的以下文件也需要适配后端切换：
- `gui/batch_panel.py`
- `gui/batch_sender_panel.py`
- `cli/batch_demo.py`
- `cli/batch_sender.py`

### 可参考的模式

- `LocalCannyExtractor` 继承 `BaseConditionExtractor` 本地实现，和我们 M-04 DiffusersReceiver 继承 BaseReceiver 的思路一致
- GUI Radio 已统一为 `(label, value)` 元组方式，后端切换 UI 可复用此模式

## 待决策清单

1. M-06 是否复用 `batch_processor.py` 的数据结构？
2. M-07/M-08 是否扩充涉及文件列表？
3. `batch_panel.py` 仍用 `ComfyUISender` 的问题在哪里修复？
4. CLI 代码重复是否在 M-08 中精简？
5. M-07 后端切换 UI 是否沿用 Radio 元组模式？
6. `LocalCannyExtractor` 的模式对 M-04 设计有无调整需要？

## 遗留 Issue

- #16 — `comfyui_client.py` timeout 倍数变更需确认原因
- #17 — 量化依赖按平台条件安装（torchao / bitsandbytes）
