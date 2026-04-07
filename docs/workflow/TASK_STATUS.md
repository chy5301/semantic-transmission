# 任务状态跟踪

> 创建时间: 2026-03-31
> 任务类型: migration
> 任务前缀: M

## 进度总览

| 阶段 | 总数 | 完成 | 进行中 | 待开始 |
|------|------|------|--------|--------|
| Phase 0: 准备 | 4 | 4 | 0 | 0 |
| Phase 1: 核心实施 | 2 | 2 | 0 | 0 |
| Phase 2: 完善 | 3 | 3 | 0 | 0 |
| Phase 3: 验证 | 2 | 1 | 0 | 1 |
| **合计** | **11** | **10** | **0** | **1** |

## 任务状态

| 编号 | 标题 | 阶段 | 状态 | 依赖 |
|------|------|------|------|------|
| M-01 | 修复-seed=0 误判 bug | Phase 0 | ✅ 已完成 | 无 |
| M-1A | 决策-PR #14 合并后计划调整 | Phase 0 | ✅ 已完成 | M-01 |
| M-02 | 添加-diffusers 依赖与模型配置 | Phase 0 | ✅ 已完成 | M-1A |
| M-03 | 设计-接收端后端切换接口 | Phase 0 | ✅ 已完成 | M-02 |
| M-04 | 实现-DiffusersReceiver 单帧生成 | Phase 1 | ✅ 已完成 | M-02, M-03 |
| M-05 | 更新-工厂函数支持 Diffusers 后端 | Phase 1 | ✅ 已完成 | M-03, M-04 |
| M-06 | 实现-批量连续帧图像生成 | Phase 2 | ✅ 已完成 | M-04 |
| M-07 | 集成-GUI 接收端面板适配 | Phase 2 | ✅ 已完成 | M-05 |
| M-08 | 集成-CLI 接收端命令适配 | Phase 2 | ✅ 已完成 | M-05 |
| M-09a | 修复-模型加载 GGUF 量化与分组件加载 | Phase 3 | ✅ 已完成 | M-04 |
| M-09 | 验证-端到端测试与质量对比 | Phase 3 | ⬜ 待开始 | M-06, M-07, M-08, M-09a |

状态图例: ⬜ 待开始 | 🔄 进行中 | ✅ 已完成 | ⏸️ 暂停 | ❌ 已取消 | 🔀 已拆分

## 已知问题

- 遗留 issue: #16（timeout 倍数需确认）、#17（量化依赖按平台条件安装）
- [待提 issue] CLI 代码重复：`batch_demo.py` 与 `batch_sender.py` 之间大量重复逻辑，应通过工厂函数精简（M-1A D4 决策延后）
- [待提 issue] DiffusersReceiver 模型加载缺乏抽象：当前加载逻辑（from_pretrained / from_single_file / 量化加载）直接写死在 `load()` 方法中，更换模型格式或加载方式需同时修改 config.py、diffusers_receiver.py、tests 三处。应重构为策略模式（ModelLoader 抽象），使 Receiver 与具体加载方式解耦
- [环境变量] Diffusers 接收端运行需要以下环境变量：
  - `MODEL_CACHE_DIR=D:\Downloads\Models` — 模型根目录（GGUF/ControlNet bf16 文件在 `$MODEL_CACHE_DIR/Z-Image-Turbo/` 下）
  - `HF_HOME=D:\Downloads\Models\huggingface` — HuggingFace 缓存目录（text_encoder/tokenizer/scheduler 从此缓存加载）
  - `HF_ENDPOINT=https://hf-mirror.com`（可选）— HuggingFace 镜像站，国内网络加速
  - `HF_HUB_DISABLE_SYMLINKS_WARNING=1`（可选）— 禁用 Windows symlinks 警告

## PR #14 合并后待决策事项

> 以下为 2026-04-02 PR #14 review 和合并过程中发现的事项，需在继续 M-02 之前逐一决策是否调整计划。

1. **`batch_processor.py` 复用** — PR #14 新增了 `BatchResult`、`SampleResult`、`BatchImageDiscoverer` 等通用批量处理数据结构。M-06 是否复用这些，还是自己实现？
2. **M-07/M-08 涉及文件扩充** — PR #14 新增了 `gui/batch_panel.py`、`gui/batch_sender_panel.py`、`cli/batch_demo.py`、`cli/batch_sender.py`。这些文件是否需要加入 M-07/M-08 的适配范围？
3. **`batch_panel.py` 仍用 `ComfyUISender`** — PR #14 声称发送端脱离 ComfyUI，但"批量端到端"面板仍硬编码 `ComfyUISender`。是否在我们的工作流中一并修复，还是单独提 issue？
4. **CLI 代码重复** — `cli/batch_demo.py` 和 `cli/batch_sender.py` 之间大量重复逻辑。是否在 M-08 中通过工厂函数精简，还是保持现状？
5. **Radio 元组模式** — 已在 PR #14 中统一为 `(label, value)` 元组（#15 已关闭）。M-07 后端切换 UI 是否沿用此模式？
6. **发送端脱离模式参考** — `LocalCannyExtractor` 继承 `BaseConditionExtractor` 本地实现的方式，对 M-04 DiffusersReceiver 的设计有无参考价值或需要调整？

## 决策日志

- 2026-03-31: 迁移策略选择 Strangler Fig，保留 ComfyUI 后端作为备选
- 2026-03-31: 继续使用 Z-Image-Turbo + ControlNet Union，通过 diffusers ZImageControlNetPipeline 加载
- 2026-03-31: 双机接收端也改为直接推理，同时支持后端切换
- 2026-04-06: [M-1A] PR #14 影响决策（6 项）：
  - D1: M-06 部分复用 batch_processor.py（BatchResult/SampleResult），不复用 BatchImageDiscoverer
  - D2: M-07 扩充 batch_panel.py，M-08 扩充 batch_demo.py
  - D3: batch_panel.py 发送端 ComfyUISender 遗漏在 M-07 中顺手修复
  - D4: CLI 代码重复不在 M-08 精简，workflow 完成后单独提 issue
  - D5: Radio 沿用 (label, value) 元组模式
  - D6: LocalCannyExtractor 模式验证了 M-04 设计方向，无需调整
- 2026-04-06: [M-02] diffusers 0.37.1 稳定版已包��� ZImageControlNetPipeline，无需源码安装
- 2026-04-06: [M-03] BaseReceiver 统一方法名为 `process`（弃用 `reconstruct`），返回 PIL.Image 而非 ReceiverOutput；ComfyUIReceiver 暂不改继承关系，通过 `# type: ignore` 标注工厂函数返回
- 2026-04-06: [Phase 0 回顾] 阶段通过。审计 4 任务无阻断/需修正问题。退出标准全部满足。M-05 步骤建议微调（工厂函数分支骨架已在 M-03 建好）
- 2026-04-06: [Phase 1 回顾] 阶段通过。审计 2 任务（M-04/M-05）无阻断/需修正问题。🔵 建议：M-02/M-03 遗留改动混入 M-04 commit。退出标准全部满足（202 tests passed，ruff 通过）。下游 Phase 2 任务无需调整
- 2026-04-06: [Phase 2 回顾] 阶段通过。审计 3 任务（M-06/M-07/M-08）无阻断/需修正问题。🔵 建议：pipeline_panel.py 发送端改 LocalCannyExtractor 超出 M-07 显式范围（因 import 清理必须一并修改）。退出标准全部满足（210 tests passed，ruff 通过，GUI/CLI 均适配后端切换）。下游 Phase 3 任务（M-09）无需调整
- 2026-04-07: [M-09 验证阻断] M-09 执行发现 DiffusersReceiver 不可用：HF 仓库 float32 权重占满 24 GB 显存，推理 34 分钟/张（ComfyUI 约 1 分钟）。根因：①`from_pretrained` 加载 float32 权重后转 bf16 峰值显存翻倍 ②所有组件同时驻留 GPU 无法分时复用。另修复两个 bug：ControlNet 仓库无 config.json 需 from_single_file、Canny 灰度图需转 RGB。决策：新增 M-09a 使用 GGUF Q8_0 量化 transformer（12 GB→7 GB）+ 分组件加载，M-09 阻塞等待 M-09a 完成
- 2026-04-07: [M-09a] GGUF 分组件加载方案落地。技术验证：diffusers 0.37.1 `from_pretrained(..., transformer=tf, controlnet=cn)` 在源码层面通过 `passed_class_obj` 跳过 `load_sub_model` 并把对应子目录加入 `ignore_patterns`，确认不会重复下载/加载已传入的组件。实施：transformer 用 `ZImageTransformer2DModel.from_single_file` + `GGUFQuantizationConfig(compute_dtype=bf16)` 加载本地 Q8_0 文件；ControlNet 用 `from_single_file` 加载本地 bf16；Pipeline 从 HF 缓存加载剩余组件。实测：单张 9 步推理 63.7s（之前 34 分钟，提速 ~32 倍），每步约 3s 平稳无 swap，达成 < 2 分钟目标。GGUF 包安装 `gguf==0.18.0`

## 交接记录

---

#### [M-01] 修复-seed=0 误判 bug — 交接记录

**完成时间**: 2026-03-31

**完成内容**:
- 修复 GUI 接收端和端到端面板中 seed=0 被误判为未设置的 bug
- GUI `gr.Number` 默认值从 0 改为 None（显示为空），语义为"未设置"
- seed=None 时接收端随机生成种子，而非使用工作流中的固定历史种子

**修改的文件**:
- `src/semantic_transmission/gui/receiver_panel.py` — seed 判断逻辑修复 + gr.Number 默认值改为 None
- `src/semantic_transmission/gui/pipeline_panel.py` — 同上
- `src/semantic_transmission/receiver/comfyui_receiver.py` — seed=None 时随机生成种子
- `tests/test_comfyui_receiver.py` — 更新测试：删除旧的 default seed 断言，新增 seed=None 随机和 seed=0 有效性测试

**验证结果**:
- Lint: ✅ `uv run ruff check .` 通过
- 测试: ✅ 181 passed
- 功能: ✅ 符合验收标准

**关键决策**:
- seed=None 时改为随机生成而非使用工作流固定种子（582911328872996），因为该值只是 ComfyUI 导出时的历史遗留，无特殊含义
- GUI 默认值从 0 改为 None，避免用户不设种子时 seed=0 被误判

**计划变更**: 无

**下一任务**: M-02 添加-diffusers 依赖与模型配置

**下一任务需关注**:
- diffusers 的 ZImagePipeline 可能需要从源码安装（稳定版未包含），需验证安装方式
- DiffusersReceiverConfig 中的 seed 处理应与本次修复保持一致（None=随机）

**遗留问题**: 无

---

#### [M-1A] 决策-PR #14 合并后计划调整 — 交接记录

**完成时间**: 2026-04-06

**完成内容**:
- 逐一决策 PR #14 合并带来的 6 个影响点
- 根据决策结果更新 TASK_PLAN.md 中 M-06、M-07、M-08 的任务定义

**修改的文件**:
- `docs/workflow/TASK_PLAN.md` — 更新 M-06（部分复用批量数据结构）、M-07（扩充 batch_panel.py + 修发送端遗漏 + Radio 元组模式）、M-08（扩充 batch_demo.py）
- `docs/workflow/TASK_STATUS.md` — 更新进度、决策日志、交接记录

**验证结果**:
- 6 个决策点均已确认 ✅
- TASK_PLAN.md 已更新 ✅
- 决策日志已记录 ✅

**关键决策**:
- D1: M-06 部分复用 BatchResult/SampleResult，不复用 BatchImageDiscoverer（接收端输入场景不匹配）
- D2: M-07 扩充 batch_panel.py，M-08 扩充 batch_demo.py（只纳入含接收端逻辑的文件）
- D3: batch_panel.py 发送端 ComfyUISender 遗漏在 M-07 中顺手修复（确认是 PR #14 遗漏）
- D4: CLI 重复不在 M-08 精简，workflow 完成后单独提 issue
- D5: Radio 沿用 (label, value) 元组模式，保持项目内 GUI 风格一致
- D6: LocalCannyExtractor 验证了 M-04 设计方向，无需调整

**计划变更**:
- M-06: 具体步骤新增"复用 BatchResult/SampleResult"
- M-07: 涉及文件新增 batch_panel.py，具体步骤新增修复发送端遗漏
- M-08: 涉及文件新增 batch_demo.py，具体步骤新增 batch_demo.py 后端切换

**下一任务**: M-02 添加-diffusers 依赖与模型配置

**下一任务需关注**:
- diffusers 的 ZImagePipeline 可能需要从源码安装（稳定版未包含），需验证安装方式
- DiffusersReceiverConfig 中的 seed 处理应与 M-01 修复保持一致（None=随机）

**遗留问题**:
- CLI 代码重复（batch_demo.py 与 batch_sender.py），workflow 完成后单独提 issue

---

#### [M-02] 添加-diffusers 依赖与模型配置 — 交接记录

**完成时间**: 2026-04-06

**完成内容**:
- 在 pyproject.toml 添加 `diffusers>=0.33.0` 依赖（实际安装 0.37.1）
- 在 config.py 新建 `DiffusersReceiverConfig` dataclass，包含模型路径、设备、推理参数等配置
- 验证 `ZImageControlNetPipeline` 在 diffusers 稳定版中可用，无需源码安装

**修改的文件**:
- `pyproject.toml` — dependencies 新增 diffusers
- `src/semantic_transmission/common/config.py` — 新增 DiffusersReceiverConfig dataclass + from_env()

**验证结果**:
- uv sync: ✅ diffusers 0.37.1 安装成功
- ZImageControlNetPipeline 导入: ✅ 稳定版可用
- DiffusersReceiverConfig 实例化: ✅
- ruff check: ✅ All checks passed
- pytest: ✅ 181 passed

**关键决策**:
- diffusers 版本约束设为 `>=0.33.0`（ZImageControlNetPipeline 最低可用版本待确认，但 0.37.1 已验证可用）
- DiffusersReceiverConfig 不包含 seed 字段（seed 是运行时参数，与 ComfyUIConfig 保持一致）
- torch_dtype 使用字符串 "bfloat16" 存储，由 DiffusersReceiver 在运行时转换为 torch.bfloat16
- num_inference_steps 默认 9（对齐 ComfyUI 工作流 KSampler 配置）
- guidance_scale 默认 1.0（对齐 ComfyUI 工作流 cfg=1）

**计划变更**: 无

**下一任务**: M-03 设计-接收端后端切换接口

**下一任务需关注**:
- BaseReceiver 的 `reconstruct()` 方法签名需与 ComfyUIReceiver 的 `process()` 统一
- ComfyUIReceiver 当前未继承 BaseReceiver，需确认接口对齐策略
- 工厂函数 `create_receiver(backend, **kwargs)` 需支持两种后端的不同初始化参数

**遗留问题**:
- diffusers `>=0.33.0` 下限可能偏低，实际最低支持 ZImageControlNetPipeline 的版本未验证（当前 0.37.1 可用）

---

#### [M-03] 设计-接收端后端切换接口 — 交接记录

**完成时间**: 2026-04-06

**完成内容**:
- 重新设计 BaseReceiver 抽象基类：`reconstruct()` → `process()`，参数签名对齐 ComfyUIReceiver
- 在 `receiver/__init__.py` 实现 `create_receiver(backend, **kwargs)` 工厂函数
- 工厂函数支持 "comfyui" 后端（创建 ComfyUIClient + ComfyUIReceiver），"diffusers" 占位 NotImplementedError

**修改的文件**:
- `src/semantic_transmission/receiver/base.py` — BaseReceiver.process() 新签名：`(edge_image: Image.Image | bytes | str | Path, prompt_text: str, seed: int | None) -> Image.Image`
- `src/semantic_transmission/receiver/__init__.py` — create_receiver 工厂函数 + BaseReceiver 导出

**验证结果**:
- ruff check: ✅ All checks passed
- receiver 测试: ✅ 12 passed
- 全量测试: ✅ 181 passed
- 工厂函数导入: ✅

**关键决策**:
- 方法名统一为 `process`（弃用从未使用过的 `reconstruct`），因为 ComfyUIReceiver 和 GUI/CLI 中已广泛使用 `process`
- 返回类型从 `ReceiverOutput`（numpy 数组包装）改为 `PIL.Image`（实际使用类型）
- `ReceiverOutput` 类型保留不删（在 types.py 中，可能有其他用途）
- ComfyUIReceiver 暂不修改继承关系（不继承 BaseReceiver），工厂函数返回值用 `# type: ignore` 标注
- 工厂函数 comfyui 后端从 kwargs 提取 host/port/timeout/workflow_path，自动创建 ComfyUIClient

**计划变更**: 无

**下一任务**: M-04 实现-DiffusersReceiver 单帧生成

**下一任务需关注**:
- DiffusersReceiver 需继承 BaseReceiver 并实现 `process()` 方法
- process 签名：`(edge_image: Image.Image | bytes | str | Path, prompt_text: str, seed: int | None) -> Image.Image`
- seed=None 时随机生成（与 M-01/ComfyUIReceiver 保持一致）
- 模型配置使用 M-02 的 DiffusersReceiverConfig
- diffusers 使用 ZImageControlNetPipeline + ZImageControlNetModel
- torch_dtype 字符串需在运行时转换为 torch.bfloat16

**遗留问题**:
- ComfyUIReceiver 未继承 BaseReceiver（duck typing 可用但类型检查不完美），可在后续任务中视情况调整

---

#### [M-04] 实现-DiffusersReceiver 单帧生成 — 交接记录

**完成时间**: 2026-04-06

**完成内容**:
- 新建 `DiffusersReceiver` 类，继承 `BaseReceiver`，实现 `process()` 方法
- 使用 `ZImageControlNetPipeline` + `ZImageControlNetModel` 进行图像生成
- 支持 lazy load（首次 process 时自动加载模型）和 unload（释放 GPU 显存）
- edge_image 支持 PIL.Image、bytes、str、Path 四种输入格式
- seed=None 时随机生成，seed=0 有效
- 16 项单元测试全部通过（mock pipeline）

**修改的文件**:
- `src/semantic_transmission/receiver/diffusers_receiver.py`（新建）— DiffusersReceiver 实现，含 load/unload/process 方法
- `tests/test_diffusers_receiver.py`（新建）— 16 项单元测试（初始化、加载卸载、process 各输入格式、seed 行为）

**验证结果**:
- ruff check: ✅ All checks passed
- 新增测试: ✅ 16 passed
- 全量测试: ✅ 197 passed（原 181 + 新增 16）
- 导入验证: ✅ `from semantic_transmission.receiver.diffusers_receiver import DiffusersReceiver`

**关键决策**:
- 采用 lazy load 模式：构造时不加载模型，首次 process 调用时自动触发 load()，避免不必要的 GPU 占用
- edge_image 比 BaseReceiver 签名多支持 PIL.Image 类型（ComfyUIReceiver 不支持），因为 diffusers pipeline 直接接受 PIL Image
- torch.Generator 在 config.device 上创建，确保与 pipeline 设备一致
- _TORCH_DTYPE_MAP 将字符串映射到 torch dtype，未知类型回退到 bfloat16

**计划变更**: 无

**下一任务**: M-05 更新-工厂函数支持 Diffusers 后端

**下一任务需关注**:
- M-03 交接记录提到"M-05 步骤建议微调（工厂函数分支骨架已在 M-03 建好）"
- 只需将 `create_receiver` 中 "diffusers" 分支的 NotImplementedError 替换为实际创建 DiffusersReceiver
- 从 kwargs 提取 config 参数传入 DiffusersReceiver

**遗留问题**: 无

---

#### [M-05] 更新-工厂函数支持 Diffusers 后端 — 交接记录

**完成时间**: 2026-04-06

**完成内容**:
- 在 `create_receiver` 工厂函数中实现 "diffusers" 分支，替换 NotImplementedError
- 支持通过 `config` kwarg 传入自定义 DiffusersReceiverConfig，未传入时使用默认配置
- 新增 5 项工厂函数单元测试

**修改的文件**:
- `src/semantic_transmission/receiver/__init__.py` — "diffusers" 分支创建 DiffusersReceiver 实例
- `tests/test_receiver_factory.py`（新建）— 5 项测试：diffusers 后端（默认/自���义 config）、comfyui 后端、无效 backend

**验证结果**:
- ruff check: ✅ All checks passed
- 新增测试: ✅ 5 passed
- 全量测试: ✅ 202 passed
- 功能: ✅ 三项验收标准全部满足

**关键决策**:
- config 参数通过 kwargs.get("config") 获取，未传入时自动创建���认 DiffusersReceiverConfig（与 comfyui 分支的参数���取风格一致）

**计划变更**: 无

**下一任务**: Phase 1 全部完成，进入阶段检查点

**遗留问题**: 无

---

#### [M-06] 实现-批量连续帧图像生成 — 交接记录

**完成时间**: 2026-04-06

**完成内容**:
- 在 BaseReceiver 中新增 `process_batch(frames)` 方法，逐帧调用 `process` 并收集结果
- 新增 `FrameInput` dataclass（边缘图 + prompt + seed + metadata）和 `BatchOutput` dataclass（图像列表 + 统计）
- DiffusersReceiver 覆写 `process_batch`，先 load() 确保模型常驻 GPU 再调 super
- 复用 `pipeline.batch_processor` 中的 `BatchResult`/`SampleResult` 做结果统计
- 新增 8 项批量处理测试

**修改的文件**:
- `src/semantic_transmission/receiver/base.py` — 新增 FrameInput、BatchOutput dataclass + process_batch 默认实现
- `src/semantic_transmission/receiver/diffusers_receiver.py` — 覆写 process_batch（先 load 再调 super）
- `src/semantic_transmission/receiver/__init__.py` — 导出 FrameInput、BatchOutput
- `tests/test_diffusers_receiver.py` — 新增 TestProcessBatch 8 项测试

**验证结果**:
- ruff check: ✅ All checks passed
- ruff format: ✅ 62 files already formatted
- 新增测试: ✅ 8 passed
- 全量测试: ✅ 210 passed（原 202 + 新增 8）

**关键决策**:
- process_batch 返回 BatchOutput（images + stats），而非仅返回图像列表，因为下游 GUI/CLI 需要统计信息
- BaseReceiver 提供默认 process_batch 实现（逐帧调 process），子类可覆写优化
- FrameInput.metadata 使用 dict[str, Any] | None，满足扩展需求且保持简洁
- 失败帧在 images 中对应 None，不中断批量处理（tracked in BatchResult）

**计划变更**: 无

**下一任务**: M-07 集成-GUI 接收端面板适配

**下一任务需关注**:
- config_panel.py 需添加接收端后端选择 Radio 组件
- receiver_panel.py、pipeline_panel.py、batch_panel.py 改用 create_receiver 工厂函数
- batch_panel.py 还需修复发送端 ComfyUISender → LocalCannyExtractor（PR #14 遗漏）
- Radio 沿用 (label, value) 元组模式

**遗留问题**: 无

---

#### [M-07] 集成-GUI 接收端面板适配 — 交接记录

**完成时间**: 2026-04-06

**完成内容**:
- config_panel.py 新增接收端后端选择 Radio（Diffusers/ComfyUI），默认 Diffusers
- receiver_panel.py 改用 create_receiver 工厂函数，Diffusers 时跳过连接检查
- pipeline_panel.py 接收端改用工厂函数，发送端改用 LocalCannyExtractor（不再依赖 ComfyUI）
- batch_panel.py 接收端改用工厂函数，发送端 ComfyUISender → LocalCannyExtractor（修复 PR #14 遗漏）

**修改的文件**:
- `src/semantic_transmission/gui/config_panel.py` — 新增 receiver_backend Radio 组件，返回字典新增 "receiver_backend"
- `src/semantic_transmission/gui/receiver_panel.py` — 移除 ComfyUI 硬编码，改用 create_receiver + 后端分支连接检查
- `src/semantic_transmission/gui/pipeline_panel.py` — 接收端改工厂函数，发送端改 LocalCannyExtractor，移除 sender ComfyUI 连接检查
- `src/semantic_transmission/gui/batch_panel.py` — 接收端改工厂函数，发送端 ComfyUISender → LocalCannyExtractor

**验证结果**:
- ruff check: ✅ All checks passed
- ruff format: ✅ 62 files already formatted
- 全量测试: ✅ 210 passed

**关键决策**:
- pipeline_panel.py 发送端也改为 LocalCannyExtractor（虽然不在任务显式范围内，但 import 变更导致必须一并修改，且与 sender_panel 保持一致）
- pipeline_panel.py 移除了 sender_host/sender_port 参数（发送端不再需要 ComfyUI 连接）
- 后端 Radio 默认值为 "diffusers"，因为这是本工作流的目标方向
- batch_panel.py 中 receiver 在批量处理开始前创建一次，整个批量共用（模型常驻 GPU）

**计划变更**: 无

**下一任务**: M-08 集成-CLI 接收端命令适配

**下一任务需关注**:
- cli/receiver.py 添加 --backend 选项
- cli/demo.py 添加 --backend 选项
- cli/batch_demo.py 添加 --backend 选项
- Diffusers 模式下跳过 ComfyUI 连接检查

**遗留问题**: 无

---

#### [M-08] 集成-CLI 接收端命令适配 — 交接记录

**完成时间**: 2026-04-06

**完成内容**:
- cli/receiver.py 添加 `--backend` 选项（comfyui/diffusers，默认 diffusers），改用 create_receiver 工厂函数
- cli/demo.py 添加 `--backend` 选项，改用 create_receiver，Diffusers 时跳过连接检查
- cli/batch_demo.py 添加 `--backend` 选项，改用 create_receiver，Diffusers 时跳过连接检查

**修改的文件**:
- `src/semantic_transmission/cli/receiver.py` — 添加 --backend 选项，移除 ComfyUIReceiver 硬编码，改用 create_receiver + 后端分支连接检查
- `src/semantic_transmission/cli/demo.py` — 添加 --backend 选项，接收端改用 create_receiver，Diffusers 时跳过连接检查
- `src/semantic_transmission/cli/batch_demo.py` — 添加 --backend 选项，接收端改用 create_receiver，Diffusers 时跳过连接检查

**验证结果**:
- ruff check: ✅ All checks passed
- ruff format: ✅ 62 files already formatted
- 全量测试: ✅ 210 passed
- --help 输出: ✅ receiver/demo/batch-demo 均显示 --backend 选项

**关键决策**:
- --backend 默认值统一为 "diffusers"（与 GUI 一致，是本工作流的目标方向）
- receiver.py 的 _process_packet 函数类型标注从 ComfyUIReceiver 改为 BaseReceiver
- ComfyUI 相关导入改为条件导入（仅 comfyui 后端时加载）

**计划变更**: 无

**下一任务**: Phase 2 全部完成，进入阶段检查点

**遗留问题**: 无

---

#### [M-09a] 修复-模型加载 GGUF 量化与分组件加载 — 交接记录

**完成时间**: 2026-04-07

**完成内容**:
- 在 `pyproject.toml` 添加 `gguf>=0.10.0` 依赖（实际安装 `gguf==0.18.0`）
- `DiffusersReceiverConfig` 新增 `transformer_path: str = ""` 字段，`__post_init__` 默认指向 `$MODEL_CACHE_DIR/Z-Image-Turbo/z-image-turbo-Q8_0.gguf`
- `DiffusersReceiver.load()` 重写为分组件加载：
  1. transformer：`ZImageTransformer2DModel.from_single_file(gguf_path, quantization_config=GGUFQuantizationConfig(compute_dtype=bf16), torch_dtype=bf16)`
  2. ControlNet：`ZImageControlNetModel.from_single_file` 加载本地 bf16
  3. Pipeline：`ZImageControlNetPipeline.from_pretrained(model_name, transformer=..., controlnet=..., torch_dtype=bf16)` 跳过这两个子目录加载，剩余 text_encoder/tokenizer/scheduler/vae 从 HF 缓存以 bf16 加载
- 4 个 load 相关测试（`test_load_creates_pipeline`、`test_load_skips_if_already_loaded`、`test_auto_loads_if_not_loaded`、`test_model_loaded_once`）补充 `ZImageTransformer2DModel` 和 `GGUFQuantizationConfig` mock
- `test_receiver_factory.py` 新增 `test_default_transformer_path` 验证默认 GGUF 路径

**修改的文件**:
- `pyproject.toml` — 新增 gguf 依赖
- `src/semantic_transmission/common/config.py` — DiffusersReceiverConfig 新增 transformer_path
- `src/semantic_transmission/receiver/diffusers_receiver.py` — load() 改为分组件加载
- `tests/test_diffusers_receiver.py` — 4 个 load 测试补充 transformer mock
- `tests/test_receiver_factory.py` — 新增 transformer_path 默认值测试

**验证结果**:
- ruff check: ✅ All checks passed
- ruff format --check: ✅ 62 files already formatted
- 全量测试: ✅ 211 passed（原 210 + 新增 1）
- 实际推理验证（`semantic-tx demo --image canyon_jeep.jpg --prompt "..." --seed 42 --backend diffusers`）：
  - 接收端耗时: **63.7s**（vs 此前 34 分钟，提速 ~32 倍）
  - 9 步推理每步约 **3.0s**（平稳无 swap）
  - 总耗时: **1m 8s**（远低于 < 2 分钟目标）
  - GPU 推理结束后回落至 517 MiB，模型卸载正常
- VRAM 间接证据：每步耗时稳定（如 swap 会导致每步 4 分钟级），证明 Q8_0 + 分组件加载策略达成 VRAM < 20 GB 目标

**关键决策**:
- gguf 版本下限选 `>=0.10.0`（diffusers GGUFQuantizationConfig 稳定 API），实际 uv 解析为 0.18.0
- transformer_path 字段插入 `controlnet_name` 之后保持分组，所有字段均有默认值，不破坏 dataclass 位置参数兼容性
- 不在 `__post_init__` 中做 `os.path.exists` 检查，构造时无副作用，文件不存在时由 `load()` 阶段抛 FileNotFoundError
- 测试中保留 `mock_quant_cls` / `mock_cnet_cls` 等未直接断言的参数，因 `@patch` 装饰器要求参数位置与底→顶顺序一致

**计划变更**: 无（按原 TASK_PLAN 中 M-09a 定义执行，未新增/删除子任务）

**下一任务**: M-09 验证-端到端测试与质量对比（依赖 M-09a 已就绪，可解除阻塞）

**下一任务需关注**:
- M-09 需运行全量回归测试 + GUI/CLI 手动验证 + Diffusers vs ComfyUI 后端的 PSNR/SSIM/LPIPS 对比
- 实际推理已验证可工作，可重点关注图像质量（M-09a 修复了性能但未对齐 ComfyUI 的 AuraFlow shift=3、res_multistep sampler 等采样器配置，可能存在质量差异）
- 环境变量 `MODEL_CACHE_DIR` 和 `HF_HOME` 必须导出后再运行 demo，否则 GGUF 文件路径无法解析

**遗留问题**:
- ComfyUI 特有采样器配置（AuraFlow shift=3、res_multistep）未在 diffusers 端对齐，可能影响生成质量，留给 M-09 评估或后续优化
- DiffusersReceiver 模型加载缺乏抽象的问题（已记录为待提 issue），本任务进一步证实：transformer/controlnet/pipeline 三段加载逻辑写死在 `load()` 中
