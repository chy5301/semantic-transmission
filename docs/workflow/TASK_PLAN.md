# 任务计划

> Workflow: `unify-config-and-loader` | 类型: refactor + bugfix + infrastructure
> 策略: 接口优先 + Strangler Fig 混合（按模块垂直切）
> 任务总数: 14 | 阶段: 5 (Phase 0-4)

## 总体策略

1. **Phase 0** 建立新抽象（`ProjectConfig` + `ModelLoader` ABC + `config.toml`），不动旧代码
2. **Phase 1-3** 按模块垂直切迁移：receiver → sender/CLI → GUI，每步新旧可共存
3. **Phase 4** 横切 cleanup（RGB helper、dead code、文档、issue 关闭）
4. 每个 phase 独立成 commit 组，退出条件失败可回滚到上一 phase

## 阶段里程碑

| Phase | 名称 | 退出标准 |
|---|---|---|
| 0 | 基础设施（纯新增不接线） | `ProjectConfig` + `ModelLoader` ABC + `config.toml` 新增完毕，pytest/ruff 全绿，旧代码零变化 |
| 1 | receiver 侧垂直切 | `DiffusersReceiver` 迁 loader + #24 动态尺寸 + #25 采样器对齐 + #31 去重，本地 demo 单图逼眼对比 |
| 2 | sender/CLI 侧垂直切 | `QwenVLSender` 迁 loader + #19 CLI 合并 + #27 download.py，sender 单图/批量均正常 |
| 3 | GUI 侧垂直切 | #23 生命周期修复，四面板各连续 3 次不出现减速 |
| 4 | cleanup + 收尾 | #22 RGB helper + #33 删除 + 文档更新 + issue 关闭 + workflow archive |

---

## Phase 0: 基础设施（纯新增不接线）

### [R-01] 创建-ProjectConfig 与 config.toml 体系

- **阶段**: Phase 0 - 基础设施
- **依赖**: 无
- **目标**: 建立项目级配置的 single source of truth：`ProjectConfig` dataclass + `config.toml` 文件 + 多层 override 加载器
- **背景信息**: 当前项目有四套独立的配置入口：`DiffusersReceiverConfig` dataclass（7 字段 + `DIFFUSERS_*` 环境变量）、CLI click options（每命令 9-13 个 options 各自定义默认值）、`QwenVLSender` 构造函数参数（无 dataclass）、GUI textbox（`config_panel.py` 向下游面板传 VLM 名/路径）。这导致同一参数（如 Canny 阈值 100/200）在 4 个 CLI 文件中各写一遍，且 `DiffusersReceiverConfig.from_env()` 只有 receiver 用得上。本任务建立统一的 `ProjectConfig`，用 `tomllib` 从 `config.toml` 加载，支持 `config.local.toml` 覆盖层。**本任务只建不接线**——旧代码继续走旧路径，新代码仅供后续 phase 消费。
- **涉及文件**:
  - `src/semantic_transmission/common/config.py`（扩展，新增 `ProjectConfig` + loader）
  - `config.toml`（新建，仓库根，checked in）
  - `.gitignore`（加 `config.local.toml`）
  - `tests/test_project_config.py`（新建）
- **具体步骤**:
  1. 在 `common/config.py` 中新增 `ProjectConfig` frozen dataclass，包含 `[models]`、`[models.diffusers]`、`[models.vlm]`、`[inference]`、`[paths]` 五个子区块对应的字段
  2. 新增 `load_config(path: Path | None = None) -> ProjectConfig` 函数：用 `tomllib` 加载 `config.toml`，叠加 `config.local.toml`，叠加环境变量（仅 `MODEL_CACHE_DIR`），返回冻结实例
  3. 支持 `${MODEL_CACHE_DIR}` 环境变量在 toml 字段值中展开
  4. 新建仓库根 `config.toml`，填入 seed §3.2 的扩展集 schema 默认值
  5. `.gitignore` 加 `config.local.toml`
  6. 写 `tests/test_project_config.py`：测试 toml 加载、local 覆盖、环境变量展开、缺失文件时回退到代码默认
- **验收标准**:
  - [ ] `ProjectConfig` 包含 models/inference/paths 三大区块全部字段
  - [ ] `load_config()` 正确实现 5 层优先级（代码默认 < config.toml < config.local.toml < 环境变量 < 运行时参数）
  - [ ] `config.toml` checked in 且包含安全默认值
  - [ ] `config.local.toml` 在 `.gitignore` 中
  - [ ] `uv run pytest tests/test_project_config.py` 通过
  - [ ] `uv run ruff check . && uv run ruff format --check .` 通过
  - [ ] 旧代码行为零变化（`DiffusersReceiverConfig` 不动）
- **自测方法**: `uv run pytest tests/test_project_config.py -v` + `uv run ruff check .`
- **回滚方案**: 删除新增文件，还原 config.py 和 .gitignore
- **预估工作量**: L

### [R-02] 创建-ModelLoader 抽象基类

- **阶段**: Phase 0 - 基础设施
- **依赖**: 无
- **目标**: 定义 `ModelLoader[TModel]` ABC，统一模型加载/卸载/生命周期接口
- **背景信息**: 当前 `DiffusersReceiver` 和 `QwenVLSender` 各自实现了 `load()`/`unload()`/`is_loaded`，行为模式相同（幂等 load、pipeline/model = None + empty_cache + gc.collect unload）但没有公共接口。GUI/CLI/pipeline 的调用方需要知道具体类型才能管理生命周期。本任务新建 `ModelLoader` ABC + `session()` context manager，为 Phase 1-3 的具体 loader 实现铺路。
- **涉及文件**:
  - `src/semantic_transmission/common/model_loader.py`（新建）
  - `tests/test_model_loader.py`（新建）
- **具体步骤**:
  1. 新建 `common/model_loader.py`，定义 `ModelLoader(ABC, Generic[TModel])`，含 `load() -> TModel`、`unload() -> None`、`is_loaded -> bool` 抽象方法/属性，及 `session()` context manager 默认实现
  2. 写 `tests/test_model_loader.py`：用 mock 实现验证 `session()` 的 try/finally 行为（正常退出 + 异常退出都调 unload）、`load()` 返回 model 实例、`is_loaded` 状态切换
- **验收标准**:
  - [ ] `ModelLoader` 包含 `load()`、`unload()`、`is_loaded`、`session()` 四个公共接口
  - [ ] `session()` 在正常/异常退出时均调用 `unload()`
  - [ ] `uv run pytest tests/test_model_loader.py` 通过
  - [ ] `uv run ruff check . && uv run ruff format --check .` 通过
  - [ ] 旧代码行为零变化
- **自测方法**: `uv run pytest tests/test_model_loader.py -v`
- **回滚方案**: 删除新增的两个文件
- **预估工作量**: S

---

## Phase 1: receiver 侧垂直切

### [R-03] 实现-DiffusersModelLoader

- **阶段**: Phase 1 - receiver 侧垂直切
- **依赖**: R-01, R-02
- **目标**: 创建 `DiffusersModelLoader(ModelLoader[ZImageControlNetPipeline])` 具体实现，封装 GGUF transformer + ControlNet + base pipeline 分组件加载
- **背景信息**: `DiffusersReceiver` 当前在 `load()` 方法（`diffusers_receiver.py:35-67`）中直接加载三个组件：1) `ZImageTransformer2DModel.from_single_file(gguf_path, quantization_config=GGUFQuantizationConfig(...))` 加载 Q8_0 量化 transformer，2) `ZImageControlNetModel.from_single_file(safetensors_path)` 加载 ControlNet，3) `ZImageControlNetPipeline.from_pretrained(model_name, transformer=..., controlnet=...)` 组装 pipeline 并 `.to(device)`。`unload()` 方法正确实现了 `_pipeline=None + empty_cache + gc.collect`。本任务将此加载逻辑抽取到独立的 `DiffusersModelLoader` 类，并引入 `DiffusersLoaderConfig` frozen dataclass 作为构造参数（从 `ProjectConfig` 派生，但不直接依赖 `ProjectConfig`）。
- **涉及文件**:
  - `src/semantic_transmission/common/model_loader.py`（扩展，新增 `DiffusersModelLoader` + `DiffusersLoaderConfig`）
  - `src/semantic_transmission/common/config.py`（新增 `DiffusersLoaderConfig` dataclass）
  - `tests/test_model_loader.py`（扩展，新增 DiffusersModelLoader mock 测试）
- **具体步骤**:
  1. 在 `config.py` 新增 `DiffusersLoaderConfig` frozen dataclass：模型路径字段（model_name、controlnet_name、transformer_path）、device、torch_dtype、compute_dtype。新增 `ProjectConfig.to_diffusers_loader_config()` 方法
  2. 在 `model_loader.py` 新增 `DiffusersModelLoader(ModelLoader[ZImageControlNetPipeline])`：构造接收 `DiffusersLoaderConfig`，`load()` 从当前 `DiffusersReceiver.load()` 复制逻辑（lazy import diffusers + 三步加载），`unload()` 复制现有 unload 逻辑
  3. 补充 mock 单测
- **验收标准**:
  - [ ] `DiffusersModelLoader.load()` 返回 `ZImageControlNetPipeline` 实例
  - [ ] `DiffusersModelLoader.unload()` 调用 `empty_cache + gc.collect`
  - [ ] `DiffusersLoaderConfig` 可从 `ProjectConfig.to_diffusers_loader_config()` 派生
  - [ ] 新增单测覆盖 load/unload/is_loaded/session
  - [ ] CI fixture 使用 `device="cpu"` 不触发 CUDA
  - [ ] 旧 `DiffusersReceiver` 行为未变（本任务不改 receiver）
- **自测方法**: `uv run pytest tests/test_model_loader.py -v`
- **回滚方案**: 还原 model_loader.py 和 config.py 的扩展
- **预估工作量**: M

### [R-04] 迁移-DiffusersReceiver 使用 ModelLoader 并修复动态尺寸

- **阶段**: Phase 1 - receiver 侧垂直切
- **依赖**: R-03
- **目标**: `DiffusersReceiver` 改为持有 `DiffusersModelLoader`，并从 `control_image` 动态读 H/W 传入 pipeline（修复 #24 尺寸不等比）
- **背景信息**: `DiffusersReceiver.process()` (lines 78-111) 调用 pipeline 时未传 `height`/`width` 参数，pipeline 使用默认尺寸。竖版原图被 resize 成更矮更宽（#24 P0）。同时，receiver 的 `load()/unload()` 逻辑已在 R-03 中抽取到 `DiffusersModelLoader`，需要将 receiver 改为委托给 loader。`create_receiver()` 工厂函数（`receiver/__init__.py`）需同步更新，接收 `ProjectConfig` 或 `DiffusersLoaderConfig`。
- **涉及文件**:
  - `src/semantic_transmission/receiver/diffusers_receiver.py`（重构：委托 loader + 动态尺寸）
  - `src/semantic_transmission/receiver/__init__.py`（更新 `create_receiver` 签名）
  - `tests/test_diffusers_receiver.py`（补动态尺寸测试）
- **具体步骤**:
  1. `DiffusersReceiver.__init__` 改为接收 `DiffusersModelLoader` 实例（或内部构造），删除内联加载代码，委托给 `self._loader`
  2. `process()` 方法中：加载 `control_image` 后读取 `image.size` 得到 (W, H)，传 `height=H, width=W` 给 pipeline 调用
  3. `load()/unload()/is_loaded` 全部委托给 `self._loader`
  4. 更新 `create_receiver()` 工厂，支持传入 `ProjectConfig` 或 `DiffusersLoaderConfig` 参数
  5. 补充单测：mock pipeline 验证 `height`/`width` 参数被正确传入；验证 loader lifecycle 委托
- **验收标准**:
  - [ ] `DiffusersReceiver` 不再直接 import diffusers 加载类（由 loader 负责）
  - [ ] `process()` 传 `height`/`width` 给 pipeline
  - [ ] 竖版图还原后尺寸与原图等比（本地 RTX 5090 逼眼验证）
  - [ ] `uv run pytest` 全绿（含新增 + 旧测试）
  - [ ] CI fixture 仍强制 `device="cpu"`
- **自测方法**: `uv run pytest tests/test_diffusers_receiver.py -v` + 本地 `semantic-tx demo --image <竖版图>` 逼眼对比
- **回滚方案**: `git checkout -- src/semantic_transmission/receiver/`
- **预估工作量**: L

### [R-05] 简化-BaseReceiver.process_batch 循环

- **阶段**: Phase 1 - receiver 侧垂直切
- **依赖**: R-04
- **目标**: 消除 `BaseReceiver.process_batch()` 与 CLI `batch_demo.py` 的循环重复，统一走 `pipeline/batch_processor` 的数据结构
- **背景信息**: `BaseReceiver.process_batch()` (base.py:55-80) 实现了通用的逐帧处理循环（调 `self.process()` + 收集 `SampleResult` → `BatchResult`）。CLI `batch_demo.py` (lines 195-260) 也有几乎相同的循环。GUI `receiver_panel.py` 通过 `DiffusersReceiver.process_batch()` 调用 base 实现。#31 要求消除这种重复。**注意**：`DiffusersReceiver.process_batch()` 在 R-04 中改为委托 loader.load() 后调 `super().process_batch()`，此逻辑需保留；简化的是 base.py 与 CLI 之间的重复。
- **涉及文件**:
  - `src/semantic_transmission/receiver/base.py`（可能简化或保留）
  - `src/semantic_transmission/pipeline/batch_processor.py`（评估是否需要适配）
- **具体步骤**:
  1. 审计 `base.py:process_batch()` 与 `batch_processor.py` 的 `BatchResult/SampleResult` 使用方式
  2. 确认 `receiver_panel.py` 的 queue 处理是否唯一依赖 `process_batch()`
  3. 如果 base.py 的循环与 batch_processor 的数据结构兼容，保留 base.py 的实现但简化为使用 batch_processor 的 `SampleResult` 构造
  4. 如果存在不必要的重复逻辑，删除并统一入口
- **验收标准**:
  - [ ] `BaseReceiver.process_batch()` 与 CLI 批量逻辑不再重复同一循环模式
  - [ ] `receiver_panel.py` 的 queue 处理仍正常工作
  - [ ] `uv run pytest` 全绿
- **自测方法**: `uv run pytest tests/test_diffusers_receiver.py -v`
- **回滚方案**: `git checkout -- src/semantic_transmission/receiver/base.py`
- **预估工作量**: M

### [R-06] 对齐-Diffusers 采样器参数与 ComfyUI 基线

- **阶段**: Phase 1 - receiver 侧垂直切
- **依赖**: R-04
- **目标**: 将 ComfyUI 基线的采样器参数（AuraFlow shift=3.0、res_multistep sampler、simple scheduler）映射到 diffusers 等价 API，更新配置默认值
- **背景信息**: ComfyUI 原型使用 `ModelSamplingAuraFlow(shift=3)` + `res_multistep` sampler + `simple` scheduler，Diffusers 端当前用默认值（`guidance_scale=1.0`、`num_inference_steps=9`、默认 scheduler）。这导致生成质量与 ComfyUI 基线差距明显（#25）。需要在 diffusers API 中找到等价参数（可能是 `FlowMatchEulerDiscreteScheduler` + `shift` 参数，或其他 scheduler）。`config.toml` 的 `[inference]` 区块已预留了 `sampler`、`scheduler`、`sampling_shift` 字段（R-01），本任务确定实际值并写入。
- **涉及文件**:
  - `src/semantic_transmission/receiver/diffusers_receiver.py`（修改 pipeline 调用参数）
  - `src/semantic_transmission/common/config.py`（确认 inference 字段默认值）
  - `config.toml`（更新 [inference] 默认值）
  - `tests/test_diffusers_receiver.py`（补采样器参数测试）
- **具体步骤**:
  1. 研究 diffusers 0.37 中 `ZImageControlNetPipeline` 支持的 scheduler API，找到 `AuraFlow shift` 和 `res_multistep` 的等价
  2. 在 `diffusers_receiver.py` 的 pipeline 调用处传入对齐参数
  3. 更新 `config.toml` 的 `[inference]` 默认值（guidance_scale、num_inference_steps、scheduler 相关参数）
  4. 本地 RTX 5090 逼眼对比：修复前 vs 修复后，在 `resources/test_images` 上选 2-3 张图
  5. 如果 diffusers 没有直接等价 API，记录差异并选择最接近的替代方案
- **验收标准**:
  - [ ] Pipeline 调用时传入与 ComfyUI 基线对齐的 scheduler/sampler 参数
  - [ ] `config.toml` 的 `[inference]` 默认值已更新为实验确定的值
  - [ ] 本地逼眼对比显示质量接近或优于 ComfyUI 基线
  - [ ] `uv run pytest` 全绿
- **自测方法**: `semantic-tx demo --image <测试图>` 生成对比图，目测评估
- **回滚方案**: `git checkout -- src/semantic_transmission/receiver/diffusers_receiver.py config.toml`
- **预估工作量**: L

---

## Phase 2: sender/CLI 侧垂直切

### [R-07] 实现-QwenVLModelLoader 并迁移 QwenVLSender

- **阶段**: Phase 2 - sender/CLI 侧垂直切
- **依赖**: R-02
- **目标**: 创建 `QwenVLModelLoader` 并将 `QwenVLSender` 改为委托 loader 管理模型生命周期
- **背景信息**: `QwenVLSender` 当前在 `_load_model()` 私有方法中实现了模型加载（含 torchao/bitsandbytes/float16 量化 cascade），`unload()` 方法清理模型引用 + empty_cache + gc.collect。但它没有公共的 `load()` 方法（只有 `_load_model()` 私有），也没有 `is_loaded` 属性。`describe()` 在首次调用时 lazy load。本任务新建 `QwenVLModelLoader(ModelLoader)` 封装这些逻辑，并引入 `VLMLoaderConfig` dataclass（从 `ProjectConfig` 派生）。`QwenVLSender` 改为持有 loader 实例。
- **涉及文件**:
  - `src/semantic_transmission/common/model_loader.py`（扩展，新增 `QwenVLModelLoader` + `VLMLoaderConfig`）
  - `src/semantic_transmission/common/config.py`（新增 `VLMLoaderConfig` + `ProjectConfig.to_vlm_loader_config()`）
  - `src/semantic_transmission/sender/qwen_vl_sender.py`（重构：委托 loader）
  - `tests/test_model_loader.py`（扩展）
- **具体步骤**:
  1. 在 `config.py` 新增 `VLMLoaderConfig` frozen dataclass：model_name、model_path、quantization、max_new_tokens
  2. 在 `model_loader.py` 新增 `QwenVLModelLoader(ModelLoader)`：`load()` 从 `QwenVLSender._load_model()` 提取逻辑
  3. `QwenVLSender.__init__` 改为接收 `QwenVLModelLoader` 或 `VLMLoaderConfig`，`describe()` 调用 `loader.load()` 获取 model+processor
  4. 补充 mock 单测
- **验收标准**:
  - [ ] `QwenVLModelLoader` 实现 `load()/unload()/is_loaded/session()`
  - [ ] `QwenVLSender` 不再有 `_load_model()` 私有方法
  - [ ] 量化 cascade 逻辑保留在 loader 中
  - [ ] `uv run pytest` 全绿
- **自测方法**: `uv run pytest tests/test_model_loader.py -v`
- **回滚方案**: `git checkout -- src/semantic_transmission/sender/qwen_vl_sender.py src/semantic_transmission/common/`
- **预估工作量**: L

### [R-08] 合并-CLI sender 与 batch_sender 子命令

- **阶段**: Phase 2 - sender/CLI 侧垂直切
- **依赖**: R-01, R-07
- **目标**: 将 `sender` 和 `batch_sender` 合并为单一 `sender` 命令（通过 `--image`/`--input-dir` 互斥选项区分），CLI 入口改为读 `config.toml` 默认值 + CLI override
- **背景信息**: 当前 `cli/sender.py` 和 `cli/batch_sender.py` 有 9 个相同的 click options（Canny 阈值、VLM 选项、prompt 选项、seed 等），prompt 校验逻辑 4 处相同，VLM 初始化逻辑 4 处相同。#19 要求合并。合并后 `--image` 走单图路径（扁平输出、fail-fast），`--input-dir` 走批量路径（`001_xxx/` 子目录 + `batch_summary.json`、continue-on-error）。**即使 input-dir 只有一张图也保留批量输出结构**。两条路径共享 `SenderCore.process_one()` 核心逻辑，只在输出适配器和错误策略层分叉。CLI 默认值改为从 `ProjectConfig` 读取，click options 作为 override。
- **涉及文件**:
  - `src/semantic_transmission/cli/sender.py`（重写：吸收 batch_sender 功能）
  - `src/semantic_transmission/cli/batch_sender.py`（**删除**）
  - `src/semantic_transmission/cli/main.py`（移除 `batch_sender` 注册）
  - `tests/test_cli_sender.py`（新建或扩展）
- **具体步骤**:
  1. 重写 `sender.py`：`--image` 和 `--input-dir` 互斥 click options，共享参数从 `ProjectConfig` 读默认值
  2. 提取 `process_one(image_path, extractor, vlm_sender, prompt) -> SenderResult` 核心函数
  3. 单图路径：调用 `process_one()` → 扁平写文件 → 可选 relay 发送 → fail-fast
  4. 批量路径：扫描目录 → 逐图 `process_one()` → 写子目录 + `batch_summary.json` → 可选 relay 发送 → continue-on-error
  5. 删除 `batch_sender.py`，更新 `main.py` 注册
  6. 补充 CLI 测试
- **验收标准**:
  - [ ] `semantic-tx sender --image <file>` 单图跑通，扁平输出
  - [ ] `semantic-tx sender --input-dir <dir>` 批量跑通，`001_xxx/ + batch_summary.json`
  - [ ] `semantic-tx batch-sender` 命令不存在
  - [ ] CLI options 默认值来自 `config.toml`
  - [ ] `uv run pytest` 全绿
  - [ ] `uv run ruff check .` 通过
- **自测方法**: `semantic-tx sender --help` 确认新选项 + `semantic-tx sender --image <file> --auto-prompt` 跑通
- **回滚方案**: `git checkout -- src/semantic_transmission/cli/` + 恢复 batch_sender.py
- **预估工作量**: L

### [R-09] 重构-download.py 与迁移 demo/batch_demo CLI

- **阶段**: Phase 2 - sender/CLI 侧垂直切
- **依赖**: R-01, R-08
- **目标**: `download.py` 从 `ProjectConfig.models` 派生下载清单；`demo.py`/`batch_demo.py` 改读 config；`receiver.py` 加 finally unload
- **背景信息**: `cli/download.py` 硬编码了 `COMFYUI_MODELS` (lines 23-52) 和 `HF_REPO_MODELS` (lines 54-56) 两个模型清单，其中 `COMFYUI_MODELS` 包含已废弃的 ComfyUI 路径。应改为从 `ProjectConfig.models` 区块读取。同时 `demo.py` 和 `batch_demo.py` 的 click options 也应改为读 config 默认值（与 R-08 的 sender.py 模式一致）。`cli/receiver.py` 的 finally block 缺少 `receiver.unload()`，需补上。
- **涉及文件**:
  - `src/semantic_transmission/cli/download.py`（重构：读 config）
  - `src/semantic_transmission/cli/demo.py`（改读 config 默认值）
  - `src/semantic_transmission/cli/batch_demo.py`（改读 config 默认值）
  - `src/semantic_transmission/cli/receiver.py`（加 finally unload）
- **具体步骤**:
  1. `download.py`：用 `ProjectConfig.models.diffusers` 和 `ProjectConfig.models.vlm` 替换硬编码清单，移除 `COMFYUI_MODELS`（ComfyUI 已脱离）
  2. `demo.py` / `batch_demo.py`：click options 默认值改为 `None`，在 callback 中用 `load_config()` 填充未指定的参数
  3. `receiver.py`：finally block 加 `if hasattr(recv, 'unload'): recv.unload()`
  4. 验证 `semantic-tx download --dry-run` 输出与新 config 一致
- **验收标准**:
  - [ ] `semantic-tx download --dry-run` 不再列出 ComfyUI 模型
  - [ ] `demo.py` / `batch_demo.py` 默认值来自 config
  - [ ] `cli/receiver.py` finally block 调用 unload
  - [ ] `uv run pytest` 全绿
- **自测方法**: `semantic-tx download --dry-run` + `semantic-tx demo --help` 确认默认值
- **回滚方案**: `git checkout -- src/semantic_transmission/cli/`
- **预估工作量**: M

---

## Phase 3: GUI 侧垂直切

### [R-10] 修复-GUI 面板模型生命周期泄漏

- **阶段**: Phase 3 - GUI 侧垂直切
- **依赖**: R-04, R-07
- **目标**: `pipeline_panel.py` 和 `batch_panel.py` 加 `try/finally + unload`，消除连续跑 3 次后的 16× 减速（#23 P0）
- **背景信息**: 代码分析发现 `pipeline_panel.py` 每次 `_run_e2e()` 新建 `create_receiver()` 但**从不 unload**，导致 GPU 内存泄漏。`batch_panel.py` 的 receiver 同样不 unload，且 LPIPS 模型（如开启评估）也不释放。`receiver_panel.py` 已有正确的 state 持久化 + 手动 unload 按钮（作为参考样板）。`batch_sender_panel.py` 也正确实现了 VLM load-once + unload。本任务统一修复。
- **涉及文件**:
  - `src/semantic_transmission/gui/pipeline_panel.py`（加 receiver unload + try/finally）
  - `src/semantic_transmission/gui/batch_panel.py`（加 receiver + LPIPS unload + try/finally）
- **具体步骤**:
  1. `pipeline_panel.py._run_e2e()`：在 receiver 创建后用 try/finally 包裹，finally 中调 `receiver.unload()`。或改为 receiver state 持久化 + 手动 unload 按钮（参考 receiver_panel.py）
  2. `batch_panel.py`：同理，receiver 和 LPIPS 模型在处理完成后 finally unload
  3. 确认 `batch_sender_panel.py` 和 `sender_panel.py` 不需要修改（已正确）
- **验收标准**:
  - [ ] `pipeline_panel` 连续跑 3 次不出现 16× 减速
  - [ ] `batch_panel` 连续跑 3 次批量端到端不再灾难性慢
  - [ ] LPIPS 模型（如加载）在批量完成后被释放
  - [ ] `uv run pytest` 全绿
- **自测方法**: 本地 GUI `semantic-tx gui` → pipeline / batch 面板各连续跑 3 次，观察推理速度
- **回滚方案**: `git checkout -- src/semantic_transmission/gui/pipeline_panel.py src/semantic_transmission/gui/batch_panel.py`
- **预估工作量**: M

### [R-11] 迁移-GUI 面板读 ProjectConfig 默认值

- **阶段**: Phase 3 - GUI 侧垂直切
- **依赖**: R-01, R-10
- **目标**: GUI 面板启动时从 `ProjectConfig` 读默认值填入控件，取代分散的硬编码默认值
- **背景信息**: 当前 GUI 面板的默认值来源分散：`config_panel.py` 硬编码 VLM 名 `"Qwen/Qwen2.5-VL-7B-Instruct"` 和路径 `get_default_vlm_path()`；`sender_panel.py` / `batch_sender_panel.py` 硬编码 Canny 阈值 100/200。R-01 已建立 `ProjectConfig` 作为统一配置源，本任务让 GUI 从 config 读一次默认值。**不做"GUI 改动写回 config"的双向绑定**。
- **涉及文件**:
  - `src/semantic_transmission/gui/config_panel.py`（读 `ProjectConfig`）
  - `src/semantic_transmission/gui/sender_panel.py`（读 config 默认值）
  - `src/semantic_transmission/gui/batch_sender_panel.py`（读 config 默认值）
  - `src/semantic_transmission/gui/app.py`（可能需要在组装时传入 config）
- **具体步骤**:
  1. `app.py` 启动时调用 `load_config()` 获取 `ProjectConfig` 实例
  2. 传给 `config_panel` 用于填充 VLM 控件默认值
  3. 传给 `sender_panel` / `batch_sender_panel` 用于填充 Canny 阈值等默认值
  4. receiver_panel / pipeline_panel / batch_panel 如有硬编码默认值也统一替换
- **验收标准**:
  - [ ] 删除 `config.local.toml` 后 GUI 所有面板仍能正常启动
  - [ ] 修改 `config.toml` 中的默认值后 GUI 控件反映新值
  - [ ] GUI 中用户修改控件不会写回 config 文件
  - [ ] `uv run pytest` 全绿
- **自测方法**: `semantic-tx gui` 启动，观察控件默认值是否与 `config.toml` 一致
- **回滚方案**: `git checkout -- src/semantic_transmission/gui/`
- **预估工作量**: M

---

## Phase 4: cleanup + 收尾

### [R-12] 创建-load_as_rgb 公共 helper 并替换 core 模块

- **阶段**: Phase 4 - cleanup + 收尾
- **依赖**: R-04, R-07
- **目标**: 新建 `common/image_io.py::load_as_rgb()` helper，替换 receiver/sender/evaluation/scripts 中散落的图像加载 + RGB 转换（#22 第一批）
- **背景信息**: 代码扫描发现 `Image.open(...).convert("RGB")` 模式在 16+ 文件中出现 68 次（GUI 51%、CLI 32%、其余 17%）。`evaluation/utils.py::to_numpy()` 已有健壮的格式转换但几乎未被外部使用。本任务建立统一的图像加载入口 `load_as_rgb(source) -> Image.Image`，优先替换 core 模块，GUI/CLI 留给 R-13。
- **涉及文件**:
  - `src/semantic_transmission/common/image_io.py`（**新建**）
  - `src/semantic_transmission/receiver/diffusers_receiver.py`（替换 `_load_condition_image` 中的 convert 调用）
  - `src/semantic_transmission/sender/qwen_vl_sender.py`（替换 Image.fromarray 调用）
  - `src/semantic_transmission/evaluation/utils.py`（与新 helper 对齐或复用）
  - `src/semantic_transmission/evaluation/semantic_metrics.py`（替换 fromarray 调用）
  - `scripts/evaluate.py`（替换 Image.open.convert 调用）
- **具体步骤**:
  1. 新建 `common/image_io.py`：`load_as_rgb(source: str | Path | bytes | np.ndarray | Image.Image) -> Image.Image`，统一处理各种输入格式
  2. 可选：`image_to_numpy(image: Image.Image) -> np.ndarray` 标准化为 RGB uint8 (H,W,3)
  3. 替换上述 6 个文件中的散落调用
  4. 确保 `evaluation/utils.py::to_numpy()` 可复用或被 `image_to_numpy()` 替代
- **验收标准**:
  - [ ] `load_as_rgb()` 支持 str/Path/bytes/ndarray/PIL Image 输入
  - [ ] core 模块（receiver/sender/evaluation/scripts）无直接 `Image.open().convert("RGB")` 调用
  - [ ] `uv run pytest` 全绿
- **自测方法**: `uv run pytest` + `uv run ruff check .`
- **回滚方案**: 删除 image_io.py，还原各文件改动
- **预估工作量**: M

### [R-13] 替换-CLI 与 GUI 模块 RGB 散落调用

- **阶段**: Phase 4 - cleanup + 收尾
- **依赖**: R-12
- **目标**: 用 `load_as_rgb()` 替换 CLI 和 GUI 模块中剩余的图像加载散落点（#22 第二批）
- **背景信息**: R-12 处理了 core 模块，但 CLI 模块（demo.py、sender.py、batch_demo.py）和 GUI 模块（sender_panel.py、batch_panel.py、batch_sender_panel.py、pipeline_panel.py、receiver_panel.py）仍有 ~40 处散落的 `Image.open().convert("RGB")` / `np.array()` / `Image.fromarray()` 调用。注意 `batch_sender.py` 已在 R-08 中删除，不需要处理。
- **涉及文件**:
  - `src/semantic_transmission/cli/demo.py`
  - `src/semantic_transmission/cli/sender.py`（R-08 重写后的版本）
  - `src/semantic_transmission/cli/batch_demo.py`
  - `src/semantic_transmission/gui/sender_panel.py`
  - `src/semantic_transmission/gui/batch_panel.py`
  - `src/semantic_transmission/gui/pipeline_panel.py`
  - `src/semantic_transmission/gui/batch_sender_panel.py`
- **具体步骤**:
  1. 逐文件搜索 `Image.open(` / `.convert("RGB")` / `Image.fromarray(` / `np.array(`
  2. 用 `load_as_rgb()` 或 `image_to_numpy()` 替换
  3. 确保所有 Canny 提取仍收到正确的 numpy array 输入
- **验收标准**:
  - [ ] CLI / GUI 模块无直接 `Image.open().convert("RGB")` 调用（允许 receiver_panel 的 `Image.fromarray` 用于 Gradio 显示）
  - [ ] `uv run pytest` 全绿
  - [ ] `semantic-tx gui` 所有面板功能正常
- **自测方法**: `uv run pytest` + `uv run ruff check .` + `semantic-tx gui` 快速功能验证
- **回滚方案**: `git checkout -- src/semantic_transmission/cli/ src/semantic_transmission/gui/`
- **预估工作量**: M

### [R-14] 删除-LocalRelay 并关闭 issues 与文档更新

- **阶段**: Phase 4 - cleanup + 收尾
- **依赖**: R-08, R-13
- **目标**: 删除 LocalRelay dead code (#33)，更新受 CLI 合并影响的文档，关闭所有纳入 issue，workflow archive
- **背景信息**: `LocalRelay` 类无业务调用方（#33），纯 dead code。CLI 合并后 `docs/cli-reference.md` 和 `docs/user-guide.md` 中的 `batch-sender` 引用需更新。PR commit message 需含 `Closes #19 #20 #21 #22 #23 #24 #25 #27 #31` + `Refs #33 #13 #17`。
- **涉及文件**:
  - `src/semantic_transmission/pipeline/relay.py`（或 LocalRelay 所在文件，删除 class）
  - `docs/cli-reference.md`（更新 CLI 合并）
  - `docs/user-guide.md`（更新 CLI 合并）
- **具体步骤**:
  1. 找到 LocalRelay 类定义，确认无调用方后删除
  2. 更新 `docs/cli-reference.md`：移除 `batch-sender` 子命令、更新 `sender` 命令参数说明
  3. 更新 `docs/user-guide.md`：更新使用示例
  4. 检查 #13（日志冗余）是否已在 Phase 3 顺带修掉，如未修则简单清理
  5. 在 #17 下追加评论：指向本 workflow 的 ModelLoader 量化策略统一
  6. 准备 PR commit message
  7. `docs/workflow/` archive（使用 `/workflow-archive`）
  8. 更新 memory：`project_pending_issues.md` / `project_next_workflow_seed.md`
- **验收标准**:
  - [ ] LocalRelay class 已删除，grep 无残留引用
  - [ ] `docs/cli-reference.md` 不含 `batch-sender`
  - [ ] PR commit message 正确引用所有 issue
  - [ ] `docs/workflow/` 无活跃文件（archive 完成）
  - [ ] `uv run pytest` 全绿
  - [ ] `uv run ruff check . && uv run ruff format --check .` 通过
- **自测方法**: `uv run pytest` + `uv run ruff check .` + grep LocalRelay 确认无残留
- **回滚方案**: `git checkout -- src/semantic_transmission/pipeline/ docs/`
- **预估工作量**: M
