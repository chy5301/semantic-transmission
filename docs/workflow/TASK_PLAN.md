# 任务计划

## 总体策略

**Strangler Fig（绞杀者模式）**：保留 ComfyUIReceiver 不动，新建 DiffusersReceiver 并行实现，通过配置切换后端。验证新实现的生成质量对齐后，GUI/CLI 默认使用新实现。

选择理由：

- 风险最低，任何时候可回退到 ComfyUI 方案
- 便于对比两种实现的生成质量
- 不阻塞其他开发工作

## 阶段里程碑


| 阶段        | 名称                 | 退出标准                                                                                     |
| --------- | ------------------ | ---------------------------------------------------------------------------------------- |
| Phase 0   | 准备                 | 依赖就绪、接口设计完成、seed bug 修复                                                                  |
| Phase 1   | 核心实施               | DiffusersReceiver 单帧生成可工作，质量可对比                                                          |
| Phase 2   | 完善                 | 批量连续帧、后端切换、GUI/CLI 集成完成                                                                  |
| Phase 2.5 | GUI 完善与 ComfyUI 清除 | ComfyUI 运行时代码完全移除，GUI 可测试（接收端队列化、批量端到端完整展示、Diffusers 模型检测就绪），文档完成归档 |
| Phase 3   | 验证                 | 全部测试通过，端到端流程可运行                                                                          |


## 任务列表

### Phase 0: 准备

#### [M-01] 修复-seed=0 误判 bug

- **阶段**: Phase 0 - 准备
- **依赖**: 无
- **目标**: 修复 GUI 接收端和端到端面板中 seed=0 被误判为未设置的 bug（issue #3）
- **背景信息**: `receiver_panel.py:50` 中 `seed_int = int(seed) if seed else None`，当 seed=0 时 `if seed` 求值为 False，导致 seed=0 不会覆盖工作流默认种子（582911328872996）。`pipeline_panel.py:269` 有同样问题。需要改为 `if seed is not None` 判断。
- **涉及文件**:
  - `src/semantic_transmission/gui/receiver_panel.py`
  - `src/semantic_transmission/gui/pipeline_panel.py`
- **具体步骤**:
  1. 修改 `receiver_panel.py:50` 的 seed 判断逻辑：`int(seed) if seed else None` → `int(seed) if seed is not None and seed != "" else None`
  2. 修改 `pipeline_panel.py:269` 的 seed 判断逻辑，同上
  3. 新增 seed=0 的测试用例
- **验收标准**:
  - seed=0 时实际传入 seed=0 而非 None
  - seed 为空/None 时仍回退到默认值
  - `uv run ruff check .` 通过
  - 现有测试通过
- **自测方法**: `uv run pytest tests/` 全部通过；`uv run ruff check .` 无报错
- **回滚方案**: `git checkout -- src/semantic_transmission/gui/receiver_panel.py src/semantic_transmission/gui/pipeline_panel.py`
- **预估工作量**: S

#### [M-1A] 决策-PR #14 合并后计划调整

- **阶段**: Phase 0 - 准备
- **依赖**: M-01
- **目标**: 逐一决策 PR #14 合并带来的 6 个影响点，确认是否需要调整后续任务计划
- **背景信息**: 2026-04-02 同事 Vickynsx 的 PR #14 已合并到 main，引入了批量处理基础设施（`pipeline/batch_processor.py`）、发送端脱离 ComfyUI（`LocalCannyExtractor`）、新的 GUI 面板和 CLI 命令。这些变更与本工作流的 M-06/M-07/M-08 有交集，需要在继续开发前决策是否调整计划。详细分析见 `docs/workflow/PR14_IMPACT_ANALYSIS.md`。
- **涉及文件**:
  - `docs/workflow/PR14_IMPACT_ANALYSIS.md`（只读参考）
  - `docs/workflow/TASK_PLAN.md`（根据决策结果更新）
  - `docs/workflow/TASK_STATUS.md`（记录决策日志）
- **具体步骤**:
  1. 阅读 `docs/workflow/PR14_IMPACT_ANALYSIS.md` 中的 6 个待决策点
  2. 逐一与用户确认每个决策点
  3. 根据决策结果更新 TASK_PLAN.md 中受影响的任务（M-06/M-07/M-08 等）
  4. 在 TASK_STATUS.md 决策日志中记录决策结果
- **验收标准**:
  - 6 个待决策点均已确认
  - TASK_PLAN.md 已根据决策更新（如有需要）
  - 决策日志已记录
- **自测方法**: 检查 TASK_STATUS.md 决策日志是否包含 PR #14 相关决策记录
- **回滚方案**: `git checkout -- docs/workflow/TASK_PLAN.md docs/workflow/TASK_STATUS.md`
- **预估工作量**: S

#### [M-02] 添加-diffusers 依赖与模型配置

- **阶段**: Phase 0 - 准备
- **依赖**: M-1A
- **目标**: 在 pyproject.toml 中添加 diffusers 依赖，新建接收端模型配置类
- **背景信息**: 项目计划脱离 ComfyUI，改用 diffusers 直接调用 Z-Image-Turbo + ControlNet Union 进行图像生成。需要添加 diffusers 库依赖（可能需要从源码安装以获取 ZImagePipeline 支持），并创建接收端的模型配置类（模型名称/路径、设备、推理步数等），与现有 ComfyUIConfig 并列。
- **涉及文件**:
  - `pyproject.toml`
  - `src/semantic_transmission/common/config.py`
- **具体步骤**:
  1. 在 `pyproject.toml` 的 dependencies 中添加 `diffusers` 依赖（确认版本要求，可能需要 git 源码安装）
  2. 在 `config.py` 中新增 `DiffusersReceiverConfig` dataclass，包含 model_name、controlnet_name、model_path、device、num_inference_steps、torch_dtype 等字段
  3. 为 `DiffusersReceiverConfig` 添加 `from_env` 类方法，支持环境变量覆盖
  4. 运行 `uv sync` 验证依赖安装
- **验收标准**:
  - `uv sync` 成功安装 diffusers
  - `DiffusersReceiverConfig` 可正常实例化
  - `uv run ruff check .` 通过
- **自测方法**: `uv sync && uv run python -c "from semantic_transmission.common.config import DiffusersReceiverConfig; print(DiffusersReceiverConfig())"`
- **回滚方案**: `git checkout -- pyproject.toml src/semantic_transmission/common/config.py`
- **预估工作量**: M

#### [M-03] 设计-接收端后端切换接口

- **阶段**: Phase 0 - 准备
- **依赖**: M-02
- **目标**: 设计接收端后端切换机制，使 GUI/CLI 可在 ComfyUI 和 Diffusers 后端间切换
- **背景信息**: 当前 GUI/CLI 中硬编码了 ComfyUIReceiver 实例化（4 处调用点）。需要一个工厂函数或统一入口，根据配置返回对应后端的 receiver 实例。同时需要统一 ComfyUIReceiver 和未来 DiffusersReceiver 的接口（当前 ComfyUIReceiver 未继承 BaseReceiver，使用的是自己的 `process` 方法签名）。
- **涉及文件**:
  - `src/semantic_transmission/receiver/__init__.py`
  - `src/semantic_transmission/receiver/base.py`
- **具体步骤**:
  1. 审视 `BaseReceiver` 抽象基类，调整接口使其同时适用于 ComfyUI 和 Diffusers 后端（统一 `process` 方法签名）
  2. 在 `receiver/__init__.py` 中实现工厂函数 `create_receiver(backend, **kwargs)`，根据 backend 参数（"comfyui" / "diffusers"）返回对应实例
  3. 确保工厂函数的参数设计支持两种后端的不同初始化需求
- **验收标准**:
  - `BaseReceiver` 接口统一了 `process` 方法签名
  - 工厂函数 `create_receiver` 可正确返回 ComfyUIReceiver 实例
  - `uv run ruff check .` 通过
  - 现有测试通过
- **自测方法**: `uv run pytest tests/test_comfyui_receiver.py` 通过
- **回滚方案**: `git checkout -- src/semantic_transmission/receiver/`
- **预估工作量**: M

### Phase 1: 核心实施

#### [M-04] 实现-DiffusersReceiver 单帧生成

- **阶段**: Phase 1 - 核心实施
- **依赖**: M-02, M-03
- **目标**: 实现基于 diffusers 的接收端，支持单帧图像生成（边缘图 + prompt → 还原图像）
- **背景信息**: 使用 diffusers 库的 `ZImageControlNetPipeline` 和 `ZImageControlNetModel` 加载 Z-Image-Turbo + ControlNet Union 模型。模型权重分别在 HuggingFace 的 `Tongyi-MAI/Z-Image-Turbo` 和 `alibaba-pai/Z-Image-Turbo-Fun-Controlnet-Union`。新实现需继承 BaseReceiver，提供与 ComfyUIReceiver 相同的 `process(edge_image, prompt_text, seed)` 接口。需要处理模型加载/卸载、GPU 显存管理。
- **涉及文件**:
  - `src/semantic_transmission/receiver/diffusers_receiver.py`（新建）
  - `tests/test_diffusers_receiver.py`（新建）
- **具体步骤**:
  1. 新建 `diffusers_receiver.py`，实现 `DiffusersReceiver` 类
  2. 构造函数中加载 ZImageControlNetPipeline + ZImageControlNetModel
  3. 实现 `process` 方法：接收边缘图 bytes/path + prompt + seed，返回 PIL.Image
  4. 实现 `load` / `unload` 方法管理模型加载卸载
  5. 编写单元测试（mock pipeline 调用）
- **验收标准**:
  - DiffusersReceiver 可正确加载模型
  - `process` 方法输入边缘图 + prompt 返回有效的 PIL.Image
  - seed 参数正确控制随机种子（包括 seed=0）
  - `unload` 后释放 GPU 显存
  - 单元测试通过
  - `uv run ruff check .` 通过
- **自测方法**: `uv run pytest tests/test_diffusers_receiver.py`；手动测试 `uv run python -c "from semantic_transmission.receiver.diffusers_receiver import DiffusersReceiver"` 能正常导入
- **回滚方案**: 删除新建的两个文件
- **预估工作量**: L

#### [M-05] 更新-工厂函数支持 Diffusers 后端

- **阶段**: Phase 1 - 核心实施
- **依赖**: M-03, M-04
- **目标**: 更新 receiver 工厂函数，使其能够创建 DiffusersReceiver 实例
- **背景信息**: M-03 中创建了工厂函数 `create_receiver`，但当时只支持 ComfyUI 后端。现在 DiffusersReceiver 已实现，需要将其注册到工厂函数中，使 `create_receiver("diffusers", config=...)` 能返回 DiffusersReceiver 实例。
- **涉及文件**:
  - `src/semantic_transmission/receiver/__init__.py`
- **具体步骤**:
  1. 在工厂函数中添加 "diffusers" 分支，创建 DiffusersReceiver
  2. 添加对应的测试用例
- **验收标准**:
  - `create_receiver("diffusers", ...)` 返回 DiffusersReceiver 实例
  - `create_receiver("comfyui", ...)` 仍正常工作
  - 无效 backend 参数抛出明确错误
- **自测方法**: `uv run pytest tests/`
- **回滚方案**: `git checkout -- src/semantic_transmission/receiver/__init__.py`
- **预估工作量**: S

### Phase 2: 完善

#### [M-06] 实现-批量连续帧图像生成

- **阶段**: Phase 2 - 完善
- **依赖**: M-04
- **目标**: 在 DiffusersReceiver 上支持批量连续帧图像生成（输入一组 prompt + 边缘图序列，逐帧生成图像）
- **背景信息**: 根据 issue #10 讨论结论，当前阶段只做批量图像处理（逐帧生成），不实现视频合成。接收端收到几帧描述就生成几帧图像，帧数量对接收端透明。模型在批量处理期间保持常驻 GPU，避免反复加载。同时在中继数据结构中预留可选的 metadata 扩展字段。**M-1A 决策**：复用 `pipeline/batch_processor.py` 中的 `BatchResult`/`SampleResult` 做结果统计，不复用 `BatchImageDiscoverer` 和 `make_sample_output_dir`（接收端输入来源不同，场景不匹配）。
- **涉及文件**:
  - `src/semantic_transmission/receiver/diffusers_receiver.py`
  - `src/semantic_transmission/receiver/base.py`
  - `tests/test_diffusers_receiver.py`
- **具体步骤**:
  1. 在 BaseReceiver 中新增 `process_batch` 方法（接收帧列表，逐帧调用 `process`，返回图像列表）
  2. 在 DiffusersReceiver 中实现/覆写 `process_batch`，确保模型常驻不反复加载
  3. 结果统计复用 `BatchResult`/`SampleResult`（从 `pipeline.batch_processor` 导入）
  4. 确认 metadata 字段已预留扩展位（现有 `dict[str, Any]` 已满足）
  5. 编写批量生成的测试用例
- **验收标准**:
  - `process_batch` 接收 N 帧输入，返回 N 张图像
  - 批量处理期间模型只加载一次
  - metadata 字段可携带任意扩展数据
  - 测试通过
- **自测方法**: `uv run pytest tests/test_diffusers_receiver.py`
- **回滚方案**: `git checkout -- src/semantic_transmission/receiver/`
- **预估工作量**: M

#### [M-07] 集成-GUI 接收端面板适配

- **阶段**: Phase 2 - 完善
- **依赖**: M-05
- **目标**: GUI 接收端面板和端到端面板支持 Diffusers 后端切换；修复 `batch_panel.py` 发送端遗漏
- **背景信息**: 当前 `gui/receiver_panel.py` 和 `gui/pipeline_panel.py` 中硬编码了 ComfyUIReceiver。需要改为使用工厂函数，并在 GUI 配置面板中添加后端选择（ComfyUI / Diffusers）。当选择 Diffusers 后端时，ComfyUI 相关的 host/port 配置应隐藏或禁用。**M-1A 决策**：`gui/batch_panel.py` 也需适配接收端后端切换，同时修复其发送端仍用 `ComfyUISender` 的遗漏（PR #14 中 `batch_sender_panel.py` 已改为 `LocalCannyExtractor`，`batch_panel.py` 遗漏未改）。Radio 组件沿用 `(label, value)` 元组模式。
- **涉及文件**:
  - `src/semantic_transmission/gui/receiver_panel.py`
  - `src/semantic_transmission/gui/pipeline_panel.py`
  - `src/semantic_transmission/gui/config_panel.py`
  - `src/semantic_transmission/gui/batch_panel.py`（M-1A 新增）
- **具体步骤**:
  1. 在 `config_panel.py` 中添加接收端后端选择组件（Radio: `(label, value)` 元组模式）
  2. 修改 `receiver_panel.py` 使用工厂函数创建 receiver，根据后端类型传入对应配置
  3. 修改 `pipeline_panel.py` 同上
  4. 修改 `batch_panel.py`：接收端改用工厂函数；发送端 `ComfyUISender` → `LocalCannyExtractor`（修复 PR #14 遗漏）
  5. 添加后端切换时的 UI 联动（Diffusers 模式下隐藏 ComfyUI 配置）
- **验收标准**:
  - GUI 可选择 ComfyUI 或 Diffusers 后端
  - 选择 Diffusers 后端时能正常运行接收端
  - 选择 ComfyUI 后端时行为与之前一致
  - `uv run ruff check .` 通过
- **自测方法**: `uv run semantic-tx gui` 启动后手动验证两种后端切换
- **回滚方案**: `git checkout -- src/semantic_transmission/gui/`
- **预估工作量**: M

#### [M-08] 集成-CLI 接收端命令适配

- **阶段**: Phase 2 - 完善
- **依赖**: M-05
- **目标**: CLI receiver 和 demo 子命令支持 Diffusers 后端切换
- **背景信息**: 当前 `cli/receiver.py` 和 `cli/demo.py` 中硬编码了 ComfyUIReceiver。需要添加 `--backend` 参数（默认 "diffusers"），使用工厂函数创建 receiver。双机演示场景下，接收端也支持直接推理。**M-1A 决策**：`cli/batch_demo.py` 也包含硬编码的 `ComfyUIReceiver`，需一并适配。CLI 代码重复问题（`batch_demo.py` 与 `batch_sender.py`）不在本任务精简，workflow 完成后单独提 issue。
- **涉及文件**:
  - `src/semantic_transmission/cli/receiver.py`
  - `src/semantic_transmission/cli/demo.py`
  - `src/semantic_transmission/cli/batch_demo.py`（M-1A 新增）
- **具体步骤**:
  1. 在 `cli/receiver.py` 添加 `--backend` 选项（choice: comfyui/diffusers，默认 diffusers）
  2. 根据 backend 使用工厂函数创建 receiver
  3. 在 `cli/demo.py` 同样添加 `--backend` 选项
  4. 在 `cli/batch_demo.py` 同样添加 `--backend` 选项，适配接收端后端切换
  5. Diffusers 模式下跳过 ComfyUI 连接检查
- **验收标准**:
  - `semantic-tx receiver --backend diffusers` 可正常启动
  - `semantic-tx demo --backend comfyui` 行为与之前一致
  - `semantic-tx receiver --help` 显示 backend 选项
  - `uv run ruff check .` 通过
- **自测方法**: `uv run semantic-tx receiver --help`；`uv run pytest tests/test_cli.py`
- **回滚方案**: `git checkout -- src/semantic_transmission/cli/receiver.py src/semantic_transmission/cli/demo.py`
- **预估工作量**: M

### Phase 2.5: GUI 完善与 ComfyUI 清除

> **背景**：M-09 收尾阶段（2026-04-08 brainstorming）发现 GUI 多处调整点 + ComfyUI 运行时遗留尾巴。本阶段在 M-09 最终验证前插入，用于完成 GUI 完善、接收端解耦收尾、ComfyUI 全面清除。详见决策日志 2026-04-08 条目。

#### [M-10] 清除-ComfyUI 底层运行时代码 + 抽取模型检测模块

- **阶段**: Phase 2.5 - GUI 完善与 ComfyUI 清除
- **依赖**: M-09a
- **目标**: 删除 ComfyUI 运行时代码路径，简化 receiver 工厂和 common/config；同时新建 `common/model_check.py` 作为 CLI 和 GUI 共享的模型就绪检测单一数据源
- **背景信息**: receiver-decouple-comfyui workflow 的核心目标是接收端脱离 ComfyUI。M-03 时采用 Strangler Fig 模式保留 ComfyUIReceiver 作为 fallback，但 M-09a 已验证 Diffusers 路径稳定，fallback 不再必要。全面清除 ComfyUI 运行时代码（保留 docs 和 resources 作为历史材料，由 M-16 处理）。本任务聚焦底层：common/comfyui_client.py、receiver/comfyui_receiver.py、对应测试、receiver 工厂、common/config 和 common 包的 re-export。同时为避免 M-11 和 M-12 重复实现模型检测逻辑（CLI 从 GUI 模块 import 会造成依赖方向错误），本任务顺便新建 `common/model_check.py` 作为 VLM / Diffusers 模型检测的单一数据源，CLI 和 GUI 都从这里 import。CLI 和 GUI 层的清理分别由 M-11/M-12 接续。**`SemanticTransmissionConfig`** 类型签名持有两个 `ComfyUIConfig`（sender/receiver），是 ComfyUI 场景专用的顶层配置，本任务一并删除（影响 `test_config.py` 的 `TestSemanticTransmissionConfig` 测试类）。
- **涉及文件**（13 — 超出 `maxFilesPerTask=8` 约束 5 个，原因见任务末尾"约束例外说明"）:
  - `src/semantic_transmission/common/comfyui_client.py`（删除）
  - `src/semantic_transmission/receiver/comfyui_receiver.py`（删除）
  - `src/semantic_transmission/sender/comfyui_sender.py`（**删除** — 2026-04-09 Plan Audit 修正追加：连锁依赖 `common.comfyui_client.ComfyUIClient`，且被 `sender/__init__.py` re-export，不删会导致 `import semantic_transmission.sender` ImportError）
  - `tests/test_comfyui_client.py`（删除）
  - `tests/test_comfyui_receiver.py`（删除）
  - `tests/test_comfyui_sender.py`（**删除** — 同 `sender/comfyui_sender.py` 连锁关系）
  - `src/semantic_transmission/common/__init__.py`（清理 re-export：移除 `ComfyUIClient` / `ComfyUIConfig` / `ComfyUIConnectionError` / `ComfyUIError` / `ComfyUITimeoutError` / `SemanticTransmissionConfig` 六项；re-export `check_vlm_model` / `check_diffusers_receiver_model`）
  - `src/semantic_transmission/common/config.py`（移除 `ComfyUIConfig` 类 + 移除 `SemanticTransmissionConfig` 类）
  - `src/semantic_transmission/common/model_check.py`（**新建**：`check_vlm_model` / `check_diffusers_receiver_model` 纯函数）
  - `src/semantic_transmission/receiver/__init__.py`（简化 `create_receiver`）
  - `src/semantic_transmission/sender/__init__.py`（**连锁清理** — 移除 `ComfyUISender` re-export 和 `__all__` 条目）
  - `tests/test_config.py`（**重写**：删除 `TestComfyUIConfig` / `TestSemanticTransmissionConfig` 测试类；新增 `get_default_vlm_path` / `get_default_z_image_path` / `DiffusersReceiverConfig` 测试类）
  - `tests/test_receiver_factory.py`（移除 backend 切换用例）
- **具体步骤**:
  1. grep 确认 `common/comfyui_client.py` 和 `common.config.ComfyUIConfig` / `SemanticTransmissionConfig` 在 CLI/GUI 之外无其他引用（CLI/GUI 引用由 M-11/M-12 接续清理）
  2. 删除 `common/comfyui_client.py` 和 `receiver/comfyui_receiver.py`
  3. 删除对应的 `tests/test_comfyui_client.py` 和 `tests/test_comfyui_receiver.py`
  4. **清理 `common/__init__.py`** 的 re-export：
     - 移除 `from ... comfyui_client import ...` 一整段（`ComfyUIClient`、`ComfyUIConnectionError`、`ComfyUIError`、`ComfyUITimeoutError`）
     - 移除 `from ... config import` 里的 `ComfyUIConfig` 和 `SemanticTransmissionConfig` 两项
     - 更新 `__all__` 列表
     - 可选：re-export `check_vlm_model` / `check_diffusers_receiver_model`（从下一步新建的 model_check.py）
  5. **修改 `common/config.py`**：
     - 移除 `ComfyUIConfig` 类
     - 移除 `SemanticTransmissionConfig` 类（它持有两个 `ComfyUIConfig`，是 ComfyUI 专用顶层配置）
     - 保留 `DiffusersReceiverConfig` / `get_default_vlm_path` 等与 ComfyUI 无关的内容
  6. **新建** `common/model_check.py`：
     - `check_vlm_model(model_path: str) -> tuple[bool, str]`：检查路径存在 + `config.json` 存在，返回 `(ok, 人类可读消息)`
     - `check_diffusers_receiver_model(config: DiffusersReceiverConfig) -> tuple[bool, str]`：检查 GGUF transformer 文件、ControlNet bf16 文件、HF cache pipeline base 三处路径
     - 纯函数，不依赖 Gradio 或 click（让 CLI 和 GUI 都能 import，避免依赖方向错误）
  7. 简化 `receiver/__init__.py` 的 `create_receiver`：不再接受 `backend` 参数，直接返回 `DiffusersReceiver` 实例
  8. **修改 `tests/test_config.py`**：
     - 删除 `TestComfyUIConfig` 整个测试类（所有关于 `ComfyUIConfig.from_env` / host / port / timeout / base_url 等的测试）
     - 删除 `TestSemanticTransmissionConfig` 整个测试类
     - 保留其他与 ComfyUI 无关的测试
  9. 更新 `tests/test_receiver_factory.py`，移除 backend 切换测试用例（如 `test_create_receiver_comfyui_backend` 等）
  10. 运行 `uv run pytest tests/test_receiver_factory.py tests/test_config.py tests/test_diffusers_receiver.py` 验证 common/receiver 层测试通过（CLI/GUI 相关测试此时仍会报 import 错误，由 M-11/M-12 接续修复）
- **验收标准**:
  - `common/comfyui_client.py` 和 `receiver/comfyui_receiver.py` 不存在
  - `from semantic_transmission.receiver import ComfyUIReceiver` 报 ImportError
  - `from semantic_transmission.common import SemanticTransmissionConfig` 报 ImportError
  - `from semantic_transmission.common import ComfyUIConfig` 报 ImportError
  - `create_receiver()` 签名已简化（无 backend 参数）
  - `common/model_check.py` 存在且可 `from semantic_transmission.common.model_check import check_vlm_model, check_diffusers_receiver_model`
  - `uv run ruff check src/semantic_transmission/common/ src/semantic_transmission/receiver/ tests/test_config.py tests/test_receiver_factory.py` 通过（整个项目的 ruff 会因 CLI/GUI 残留 import 失败，这是预期的，由 M-11/M-12 解决）
  - `uv run pytest tests/test_receiver_factory.py tests/test_config.py tests/test_diffusers_receiver.py` 通过
- **自测方法**: `uv run pytest tests/test_receiver_factory.py tests/test_config.py tests/test_diffusers_receiver.py`
- **回滚方案**: `git revert` 本任务提交
- **预估工作量**: M
- **约束例外说明**: 本任务涉及文件数 13 > `maxFilesPerTask=8`。超出的 5 个文件均为 `common/comfyui_client.py` + `ComfyUIConfig` 移除的**必要连锁改动**：
  1. `common/__init__.py` — 不处理会导致 Python 启动时 `ImportError`
  2. `tests/test_config.py` — 不处理会导致 pytest collection 失败
  3. `sender/comfyui_sender.py`（2026-04-09 Plan Audit 修正追加）— 直接 import 已删的 `ComfyUIClient`，不删会导致 `sender/__init__.py` 链式 ImportError，整个测试套全挂
  4. `sender/__init__.py`（2026-04-09 追加）— re-export `ComfyUISender`，不改会导致 `import semantic_transmission.sender` ImportError
  5. `tests/test_comfyui_sender.py`（2026-04-09 追加）— 直接依赖 `ComfyUISender`，保留会 pytest collection 失败
  拆分为 M-10a/M-10b 会引入额外的依赖链复杂度但无实质收益。2026-04-09 Plan Audit 修正后的决定：作为单次例外允许超约束，不修改 workflow.json 的 `maxFilesPerTask`。注：`scripts/run_sender.py` / `scripts/run_receiver.py` / `scripts/demo_e2e.py` 也依赖已删的 `common.comfyui_client`，但为避免 M-10 范围进一步膨胀，由 **M-16 归档** 统一处理（M-16 涉及文件清单同步更新）

#### [M-11] 清理-CLI 层 ComfyUI 分支 + check 子命令改写

- **阶段**: Phase 2.5 - GUI 完善与 ComfyUI 清除
- **依赖**: M-10
- **目标**: 移除 CLI 的 `--backend` 选项，将 `check` 子命令重写为模型 / 中继对端三个独立子命令
- **背景信息**: M-08 为 `cli/demo.py`、`cli/batch_demo.py`、`cli/receiver.py` 添加了 `--backend` 选项以支持后端切换。M-10 移除底层 ComfyUIReceiver 后该选项失去意义。同时 `cli/check.py` 的 `check connection` 和 `check workflows` 两个子命令都是 ComfyUI 专用，需要重写为：`check vlm`（发送端用）/ `check diffusers`（接收端用）/ `check relay --host X --port Y`（双机对端 TCP 可达性测试）三个独立子命令。
- **涉及文件**:
  - `src/semantic_transmission/cli/demo.py`（移除 `--backend`）
  - `src/semantic_transmission/cli/batch_demo.py`（移除 `--backend`）
  - `src/semantic_transmission/cli/receiver.py`（移除 `--backend`，保留 relay 参数）
  - `src/semantic_transmission/cli/check.py`（重写为三个子命令）
  - `tests/test_cli.py`（删除 backend 用例，新增 check 子命令用例）
- **具体步骤**:
  1. `cli/demo.py`、`cli/batch_demo.py`、`cli/receiver.py` 移除 `--backend` click option 及相关分支逻辑，直接实例化 DiffusersReceiver
  2. `cli/check.py` 完全重写：
     - 移除 `check connection` 和 `check workflows`
     - 新增 `check vlm`：从 `common.model_check` 导入 `check_vlm_model` 并调用（M-10 已建立单一数据源）
     - 新增 `check diffusers`：从 `common.model_check` 导入 `check_diffusers_receiver_model` 并调用
     - 新增 `check relay --host X --port Y`：通过 `SocketRelaySender.connect()` + 立即 close 测试 TCP 可达性（SocketRelaySender 从 `pipeline.relay` 导入）
  3. 更新 `tests/test_cli.py`：删除 backend 相关用例，为三个新 check 子命令添加基础测试（mock `common.model_check` 和 `SocketRelaySender`）
- **验收标准**:
  - `uv run semantic-tx demo --help` / `batch-demo --help` / `receiver --help` 不再显示 `--backend`
  - `uv run semantic-tx check --help` 显示三个子命令（vlm / diffusers / relay）
  - 三个新 check 子命令能正常执行（即使模型不存在也给出合理错误提示）
  - `uv run pytest tests/test_cli.py` 通过
  - `uv run ruff check .` 和 `uv run ruff format --check .` 通过
- **自测方法**: `uv run semantic-tx check vlm`、`uv run semantic-tx check diffusers`、`uv run semantic-tx check relay --host 127.0.0.1 --port 9000`
- **回滚方案**: `git revert` 本任务提交
- **预估工作量**: M

#### [M-12] 清理-GUI 层 ComfyUI 分支 + config_panel 重构

- **阶段**: Phase 2.5 - GUI 完善与 ComfyUI 清除
- **依赖**: M-10
- **目标**: GUI 层清除所有 ComfyUI 分支，重构 config_panel 为"模型就绪检测 + 全局设置"，修复中继字段隐性 bug
- **背景信息**: 本次 brainstorming 发现 GUI config_panel 的"ComfyUI 连接"区块（两列 host/port + 测试连接按钮）已经半过时：发送端列完全是 dead code（发送端已脱离 ComfyUI），接收端列仅 ComfyUI 模式下有意义。同时 `relay_host`/`relay_port` 字段 label 是"监听地址"但实际被 `batch_sender_panel` 当作对端地址使用，属于**隐性 bug**（详见 TASK_STATUS.md 决策日志 2026-04-08 D11：新-2 issue 在本任务顺手修复，不单独提 issue）。M-10 删除底层后各 panel 的 `if backend == "comfyui"` 分支也会 import 错误。本任务统一清理：移除 config_panel 的 ComfyUI 连接区（加 Diffusers 模型检测取代，检测函数从 M-10 新建的 `common.model_check` 导入），移除 pipeline/receiver/batch panel 的 ComfyUI 分支，中继配置从 config_panel 挪到 batch_sender_panel 内部（**同时修复上述 relay 字段语义错位 bug**）并添加对端连接测试按钮。
- **涉及文件**:
  - `src/semantic_transmission/gui/config_panel.py`（大改：移除 receiver_backend Radio、ComfyUI 连接区、中继配置；新增 Diffusers 模型检测区）
  - `src/semantic_transmission/gui/pipeline_panel.py`（移除 `[1/5] 连接检查` 分支 + backend 参数）
  - `src/semantic_transmission/gui/receiver_panel.py`（最小删除：移除 `[1/2] 检查 ComfyUI 连接` 分支 + backend 参数，M-13 会重写该文件）
  - `src/semantic_transmission/gui/batch_panel.py`（移除 ComfyUI 分支 + backend 参数）
  - `src/semantic_transmission/gui/batch_sender_panel.py`（承接中继配置：内部添加 relay_host/relay_port 字段 + 测试对端连接按钮 + `_test_relay_connection` 函数）
  - `src/semantic_transmission/gui/app.py`（更新 config_components 传递）
- **具体步骤**:
  1. `config_panel.py` 重写：
     - 移除 `receiver_backend` Radio 和"ComfyUI 连接"整个区块（`sender_host` / `sender_port` / `sender_test_btn` / `sender_status` / `receiver_host` / `receiver_port` / `receiver_test_btn` / `receiver_status` / `_test_comfyui_connection` 全部删除）
     - **删除原 `relay_host` / `relay_port` 字段**（隐性 bug：label 是"监听地址"但被 batch_sender_panel 当对端地址用，字段挪到 M-12 步骤 5 的 batch_sender_panel 里并修正语义）
     - 新增"Diffusers 模型"区块：显示检查按钮和状态 Markdown，点击时调用 `from semantic_transmission.common.model_check import check_diffusers_receiver_model`（M-10 已建立）
     - 保留 VLM 模型检查区，但内部实现改为调用 `from semantic_transmission.common.model_check import check_vlm_model`（替代原 `_check_vlm_model`，避免重复代码）
  2. `pipeline_panel.py` 移除 `[1/5] 连接检查` 的 `if receiver_backend == "comfyui"` 分支和 backend 参数传递
  3. `receiver_panel.py` 最小删除（M-13 会彻底重写）：删除 `if receiver_backend == "comfyui"` 分支
  4. `batch_panel.py` 移除 ComfyUI 分支和 backend 参数
  5. `batch_sender_panel.py` 内部添加中继配置（**同时修复隐性 bug**）：
     - 新增 `relay_host` / `relay_port` 输入字段，label 明确为"接收端 IP 地址"/"接收端端口"（**纠正原 config_panel 里 label "监听地址" 的错误语义**）
     - 默认值从 `0.0.0.0` 改为空字符串（发送端视角下 `0.0.0.0` 完全无意义）
     - 添加"测试对端连接"按钮和状态显示
     - 实现 `_test_relay_connection(host, port)` 函数：`SocketRelaySender(host, port).connect()` 成功立即 close，返回 OK + 延迟；失败返回具体错误（ConnectionRefusedError / TimeoutError 等）
     - 更新 `run_batch_sender` 内部从 `config_components["relay_host"]` 读取的地方改为从本 Tab 新字段读取
  6. `app.py` 更新 `config_components` 字段集合：移除 `relay_host` / `relay_port`（不再是全局配置）+ 移除 ComfyUI 连接相关字段
  7. `uv run semantic-tx gui` 人工抽查所有 Tab 能正常打开
  8. `uv run pytest && uv run ruff check . && uv run ruff format --check .`
- **验收标准**:
  - config_panel 只有"VLM 模型"区和"Diffusers 模型"区（和其他全局设置如有）
  - 所有 panel 代码里无 `if backend == "comfyui"` 残留
  - `📦 批量发送` Tab 能独立配置中继 + 测试对端连接
  - GUI 启动无 import 错误，所有 Tab 可打开
  - `uv run pytest` 通过
  - `uv run ruff check .` 和 `uv run ruff format --check .` 通过
- **自测方法**: `uv run semantic-tx gui` 手动验证 + `uv run pytest tests/`
- **回滚方案**: `git revert` 本任务提交
- **预估工作量**: M

#### [M-13] 重构-接收端 Tab 统一队列模式

- **阶段**: Phase 2.5 - GUI 完善与 ComfyUI 清除
- **依赖**: M-12
- **目标**: 将接收端 Tab 从"单张单次触发"重写为"队列模式"，顺便修复每次点击都重载模型的隐性 bug
- **背景信息**: 当前 `receiver_panel.py` 每次点击"运行接收端"都 `create_receiver(...)` 创建新实例并 `load()` 加载 ~18 GB 模型，且没有显式 `unload()`。多次点击会导致反复加载或显存累积。底层 `DiffusersReceiver.process_batch()` 已实现"模型加载一次、循环处理多帧"的能力（M-06 留下），只差 GUI 层队列 UI。本次 brainstorming 确认：接收端 Tab 统一为队列模式，单张场景作为"队列中只有 1 项"的特例。同时发送端 Tab 的"→ 发送到接收端"按钮改为"→ 加入接收端队列"，通过 gr.State 实现跨 Tab 队列 append。
- **涉及文件**:
  - `src/semantic_transmission/gui/receiver_panel.py`（大改：改为队列模式）
  - `src/semantic_transmission/gui/sender_panel.py`（修改 `send_to_receiver_btn` 的 handler：append 而非 replace）
  - `src/semantic_transmission/gui/app.py`（更新 Tab 间传递绑定逻辑）
  - `tests/test_receiver_panel.py` 或 `tests/test_gui.py`（新增或更新队列行为测试）
- **具体步骤**:
  1. `receiver_panel.py` 重写：
     - 引入 `gr.State` 维护队列 `List[dict]`（edge_path / prompt / seed）
     - UI 组件：当前输入区（edge + prompt + seed）→ "加入队列" 按钮 → 队列展示区（Dataframe 或 List，显示序号和 prompt 摘要）→ "运行队列" 按钮 → "清空队列" 按钮 → "卸载模型" 按钮
     - `_run_receiver_queue`：`create_receiver()` 一次 → 遍历队列调 `receiver.process_batch()` 或 `receiver.process()` 循环 → 结束后显式 `unload()` → 保存每张还原图到输出目录
     - 运行过程中 yield 逐条更新 UI
  2. `sender_panel.py` 修改 `send_to_receiver_btn`：
     - handler 从 `lambda edge, prompt: (edge, prompt)` 改为"append 到接收端 gr.State 队列"
     - 按钮文本改为"→ 加入接收端队列"
  3. `app.py` 更新 Tab 间传递绑定：
     - `send_to_receiver_btn.click()` 的 outputs 目标从 receiver 的单字段改为 receiver 的 gr.State
  4. 写测试：空队列不运行、单项运行、多项运行、清空队列、运行后显存释放
  5. `uv run semantic-tx gui` 人工验证：发送端 VLM auto 生成 → 加入接收端队列 → 多张后点运行 → 观察显存曲线
  6. `uv run pytest && uv run ruff check . && uv run ruff format --check .`
- **验收标准**:
  - 接收端 Tab 支持"加入队列"和"运行队列"两步操作
  - 一次"运行队列"内只加载模型一次，结束后显存释放（显式 unload）
  - 单张场景通过"加入 1 项后运行"工作流程完成，不需要额外 UI
  - 发送端 Tab 的"→ 加入接收端队列"按钮能正确 append 而不是 replace
  - 相关测试通过
  - `uv run ruff check .` 和 `uv run ruff format --check .` 通过
- **自测方法**: `uv run semantic-tx gui` 手动测试队列流程（3 张图）+ `uv run pytest`
- **回滚方案**: `git revert` 本任务提交
- **预估工作量**: M

#### [M-14] 打磨-UI 圆点 + 描述 + Prompt Mode 默认值

- **阶段**: Phase 2.5 - GUI 完善与 ComfyUI 清除
- **依赖**: 无（可与 M-10~M-13 并行）
- **目标**: 统一 Radio 圆点视觉、统一 Prompt Mode 默认值（VLM 在前 + 默认 auto）、为所有 Tab 补上简短描述
- **背景信息**: 本次 brainstorming 发现：① PR #9 的 `.mode-radio { display: none }` CSS 隐藏了 sender_panel 和 pipeline_panel 的 Radio 圆点，但 batch_sender_panel 和 batch_panel 没加这个 class，视觉不统一；② 四处 prompt_mode Radio 全部是"手动在前 + 默认 manual"，与 demo 实际默认流程（VLM auto）不符；③ 批量发送 Tab 描述"(双机演示) ... 发送端不依赖 ComfyUI"属于过时强调，其他 Tab 没有描述，整体不一致。
- **涉及文件**:
  - `src/semantic_transmission/gui/theme.py`（删除 `.mode-radio` CSS 规则）
  - `src/semantic_transmission/gui/sender_panel.py`（移除 elem_classes + 改 Prompt Mode 顺序默认 + 加描述）
  - `src/semantic_transmission/gui/pipeline_panel.py`（移除 elem_classes + 改 Prompt Mode 顺序默认 + 加描述）
  - `src/semantic_transmission/gui/batch_sender_panel.py`（改描述 + 改 Prompt Mode 顺序默认）
  - `src/semantic_transmission/gui/batch_panel.py`（改 Prompt Mode 顺序默认 + 加描述）
  - `src/semantic_transmission/gui/receiver_panel.py` / `config_panel.py`（如 M-12/M-13 没加简短描述，这里补）
- **具体步骤**:
  1. `theme.py` 删除 `.mode-radio input[type="radio"] { display: none !important; }` 这段 CSS
  2. 统一四处 Prompt Mode Radio：
     - `sender_panel.py`:139-140：`choices=[("VLM 自动生成","auto"),("手动输入","manual")], value="auto"` + 移除 `elem_classes=["mode-radio"]`
     - `pipeline_panel.py`:387-391：同上
     - `batch_sender_panel.py`:315-322：`choices=[("VLM 自动生成描述（每张独立）","auto"),("手动指定统一描述","manual")], value="auto"`
     - `batch_panel.py`:278-285：同 batch_sender_panel
  3. 调整各面板的 `on_prompt_mode_change` 显示逻辑：默认 auto 时手动 prompt 输入框隐藏
  4. 批量发送描述简化：`"### 批量发送\n批量提取目录下所有图片的边缘图与语义描述，发送到对端接收端。"`
  5. 为所有 6 个 Tab 补充一行简短 markdown 描述（与批量发送的风格统一）
  6. `uv run semantic-tx gui` 人工抽查视觉效果
  7. `uv run pytest && uv run ruff check . && uv run ruff format --check .`
- **验收标准**:
  - 所有 4 个涉及发送的面板 Prompt Mode 默认为 "VLM 自动生成"，Radio 圆点显示且统一
  - 所有 6 个 Tab 都有一行简短描述
  - `uv run pytest` 通过
  - `uv run ruff check .` 和 `uv run ruff format --check .` 通过
- **自测方法**: `uv run semantic-tx gui` 人工抽查 6 个 Tab
- **回滚方案**: `git revert` 本任务提交
- **预估工作量**: S

#### [M-15] 增强-批量端到端 Accordion 展示 + 每组质量评估

- **阶段**: Phase 2.5 - GUI 完善与 ComfyUI 清除
- **依赖**: M-12
- **目标**: 批量端到端 Tab 改造展示层，支持每组独立折叠展示和可选的批量质量评估
- **背景信息**: 当前 `batch_panel.py:320-325` 只显示"最后一张对比图"，多张结果丢失。`pipeline_panel.py:432-443` 有质量评估 Accordion（PSNR/SSIM/LPIPS），但 `batch_panel.py` 没有。本任务改造批量端到端 Tab：每组一个 Accordion 折叠块展示原图/边缘/还原/prompt；可选勾选"运行质量评估"，每组独立计算 + 最后给总体平均汇总。
- **涉及文件**:
  - `src/semantic_transmission/gui/batch_panel.py`（大改：结果展示区 + 评估勾选）
  - `src/semantic_transmission/pipeline/batch_processor.py`（如需扩展 BatchResult/SampleResult 存储 metrics）
  - `src/semantic_transmission/evaluation/__init__.py` 或新增工具函数（如需封装批量评估 helper）
  - `tests/test_batch_panel.py` 或 `tests/test_evaluation.py`（新增/更新）
- **具体步骤**:
  1. 设计 Accordion 动态生成策略：运行前按 `BatchImageDiscoverer` 发现的图片数量预生成 N 个隐藏 Accordion，运行中逐一 update 展开可见
  2. `batch_panel._run_batch_process` 返回值结构扩展：每组结果包含 `original_path`/`edge_path`/`restored_path`/`prompt`/`metrics`
  3. 新增"运行质量评估（会额外耗时）"复选框，勾选时每组处理完后立即调用 `evaluation` 模块计算 PSNR/SSIM/LPIPS
  4. 结束后汇总平均值展示在"总体评估" Dataframe
  5. 如果 `BatchResult` / `SampleResult` 数据结构需要扩展支持 metrics，更新 `batch_processor.py`
  6. 更新相关测试
  7. `uv run semantic-tx gui` 人工测试批量端到端流程（3 张图）
  8. `uv run pytest && uv run ruff check . && uv run ruff format --check .`
- **验收标准**:
  - 批量端到端 Tab 能逐组展示所有样本（Accordion 每组一个）
  - 每组 Accordion 展开后显示原图 / 边缘图 / 还原图 / VLM prompt 文本
  - 勾选"运行质量评估"后每组有 PSNR/SSIM/LPIPS，最后有总体平均表
  - 不勾选时不跑评估，保持原有速度
  - `uv run pytest` 通过
  - `uv run ruff check .` 和 `uv run ruff format --check .` 通过
- **自测方法**: `uv run semantic-tx gui` 手动测试 + `uv run pytest`
- **回滚方案**: `git revert` 本任务提交
- **预估工作量**: M

#### [M-16] 归档-文档更新 + ComfyUI 历史归档 + 批量提 issue

- **阶段**: Phase 2.5 - GUI 完善与 ComfyUI 清除
- **依赖**: M-10, M-11, M-12, M-13, M-14, M-15
- **目标**: 更新项目文档以反映 ComfyUI 完全清除，把 ComfyUI 原型阶段的历史材料归档到 archive 子目录，并批量提交 17 个 GitHub issue（13 个原 HANDOFF 清单有效项 + 4 个本次 brainstorming 新发现）
- **背景信息**: M-10~M-15 完成后代码层面已无 ComfyUI 痕迹，但文档和资源里仍有大量 ComfyUI 引用。`docs/comfyui-setup.md` 和 `resources/comfyui/` 目录是 PR #6 ComfyUI 原型阶段的产物，当前已过时但有历史参考价值。此外 `scripts/test_comfyui_connection.py` 和 `scripts/verify_workflows.py` 两个脚本直接 import `common.comfyui_client` 和 `ComfyUIConfig`，M-10 之后会立即失效，也必须归档。本次 brainstorming 决定（2-b 方案）：归档到 `docs/archive/comfyui-prototype/` 子目录并加 README 说明。同时更新 demo-handbook、architecture、ROADMAP、cli-reference 等文档移除 ComfyUI 后端相关内容。**此外**：HANDOFF.md 第 4 节原有 14 个待提 issue + 本次 brainstorming 新发现 4 个 issue，原计划是 M-09 完成后在 PR 步骤中批量提交，但 HANDOFF.md 已因本次插入 Phase 2.5 而过时，issue 提交动作归属到本任务（archive 性质匹配）。注意原 HANDOFF 清单的 #12（ComfyUIReceiver 不继承 BaseReceiver）在 M-10 后已失效，不再提交，实际有效为 13 个，加 4 个新 = 17 个。
- **涉及文件**（13 — 超出 `maxFilesPerTask=8` 约束 5 个，原因见任务末尾"约束例外说明"）:
  - `docs/comfyui-setup.md` → 移动到 `docs/archive/comfyui-prototype/comfyui-setup.md`
  - `resources/comfyui/` → 移动到 `docs/archive/comfyui-prototype/workflows/`
  - `scripts/test_comfyui_connection.py` → 移动到 `docs/archive/comfyui-prototype/scripts/test_comfyui_connection.py`
  - `scripts/verify_workflows.py` → 移动到 `docs/archive/comfyui-prototype/scripts/verify_workflows.py`
  - `scripts/run_sender.py` → 移动到 `docs/archive/comfyui-prototype/scripts/run_sender.py`（**2026-04-09 追加** — M-10 执行时发现该脚本依赖已删的 `common.comfyui_client` / `ComfyUIConfig` / `sender/comfyui_sender`，必须归档）
  - `scripts/run_receiver.py` → 移动到 `docs/archive/comfyui-prototype/scripts/run_receiver.py`（**2026-04-09 追加** — 同上，依赖已删的 `receiver/comfyui_receiver`）
  - `scripts/demo_e2e.py` → 移动到 `docs/archive/comfyui-prototype/scripts/demo_e2e.py`（**2026-04-09 追加** — 同上，完整双端 ComfyUI demo 脚本，已被 `semantic-tx demo` 子命令替代）
  - `docs/archive/comfyui-prototype/README.md`（新建）
  - `docs/demo-handbook.md`（移除 ComfyUI 后端路径描述）
  - `docs/architecture.md`（更新架构图 + 模块描述）
  - `docs/ROADMAP.md`（更新 Phase 2 状态追加 ComfyUI 完全退出说明）
  - `docs/cli-reference.md`（删除 `check connection` / `check workflows` 章节 + 新增 `check vlm` / `check diffusers` / `check relay` 三个章节 + 更新 demo/batch-demo/receiver 参数说明 + 更新脚本迁移表）
  - `CLAUDE.md`（更新项目阶段表、源码结构、环境前置条件、常用命令、技术栈、resources 路径引用共 7-8 处 ComfyUI 相关内容）
- **具体步骤**:
  1. `mkdir -p docs/archive/comfyui-prototype/scripts`
  2. `git mv docs/comfyui-setup.md docs/archive/comfyui-prototype/comfyui-setup.md`
  3. `git mv resources/comfyui docs/archive/comfyui-prototype/workflows`
  4. `git mv scripts/test_comfyui_connection.py docs/archive/comfyui-prototype/scripts/test_comfyui_connection.py`
  5. `git mv scripts/verify_workflows.py docs/archive/comfyui-prototype/scripts/verify_workflows.py`
  5a. `git mv scripts/run_sender.py docs/archive/comfyui-prototype/scripts/run_sender.py`（2026-04-09 追加）
  5b. `git mv scripts/run_receiver.py docs/archive/comfyui-prototype/scripts/run_receiver.py`（2026-04-09 追加）
  5c. `git mv scripts/demo_e2e.py docs/archive/comfyui-prototype/scripts/demo_e2e.py`（2026-04-09 追加）
  6. 新建 `docs/archive/comfyui-prototype/README.md`：说明"Phase 2 ComfyUI 原型阶段的产物，当前代码已完全脱离 ComfyUI，此目录仅作历史参考。内含：原 ComfyUI 部署指南（comfyui-setup.md）、原 ComfyUI 工作流 JSON（workflows/）、原连通性测试和工作流验证脚本（scripts/，依赖已删除的 common.comfyui_client，无法运行）、原始端到端 demo 脚本 run_sender.py / run_receiver.py / demo_e2e.py（已被 `semantic-tx demo`、`semantic-tx sender`、`semantic-tx receiver` 子命令取代）"
  7. **更新 `CLAUDE.md`**（grep "ComfyUI" CLAUDE.md 命中约 10 处，逐项处理）：
     - 常用命令部分：删除 `uv run python scripts/demo_e2e.py  # 运行端到端 demo（需 ComfyUI 服务运行中）` 一行的"需 ComfyUI 服务运行中"
     - 常用命令部分：删除 `uv run semantic-tx check connection  # 检查 ComfyUI 连通性` 一行，改为 3 行：`check vlm` / `check diffusers` / `check relay --host X --port Y`
     - 项目阶段表 "阶段二：ComfyUI API 原型" 状态从"进行中"改为"已完成"，追加"接收端已完全脱离 ComfyUI，运行时代码清除，历史归档在 docs/archive/"
     - 源码结构部分 common 模块描述从"ComfyUI 客户端、配置、类型定义"改为"配置、类型定义、模型检测（model_check）"
     - 关键资源部分：`resources/comfyui/` → `docs/archive/comfyui-prototype/workflows/`（路径更新）
     - 关键资源部分：`docs/comfyui-setup.md` → `docs/archive/comfyui-prototype/comfyui-setup.md`（路径更新或标注已归档）
     - 环境前置条件部分删除 "ComfyUI 服务需在本地运行（默认地址 127.0.0.1:8188），配置见 ..." 一行
     - 技术栈部分删除 "ComfyUI API 模式：通过 HTTP API 调用 ComfyUI 工作流" 条目
     - "阶段四：工程化与脱离 ComfyUI" 这一项可保留为未来规划（不变）
  8. **更新 `docs/cli-reference.md`** — 这是本任务最大的文档改动：
     - **删除** `check connection` 章节（原 line 146-158 区域）
     - **删除** `check workflows` 章节（原 line 160-177 区域）
     - **新增** `check vlm` 章节：命令说明、参数（无参数或可选 `--model-path`）、输出格式示例、使用场景（发送端机器自检）
     - **新增** `check diffusers` 章节：命令说明、参数、输出格式示例（显示 transformer/ControlNet/HF cache 三处状态）、使用场景（接收端机器自检）
     - **新增** `check relay --host X --port Y` 章节：参数必填说明、成功/失败返回示例、使用场景（双机部署对端连通性测试）
     - **更新** 命令表格（原 line 20-21 两条 check 子命令改为三条）
     - **更新** `demo` / `batch-demo` / `receiver` 三个命令的参数说明，移除 `--backend` 相关内容
     - **更新** 脚本迁移表（原 line 256-257 引用的 `scripts/test_comfyui_connection.py` 和 `scripts/verify_workflows.py` 已归档，这段应删除或改为"历史脚本，已归档到 docs/archive/comfyui-prototype/scripts/"说明）
  9. **更新 `docs/demo-handbook.md`**：删除所有 ComfyUI 后端相关章节，只保留 Diffusers 路径的演示手册
  10. **更新 `docs/architecture.md`**：更新架构图（Mermaid），移除 ComfyUI 分支；更新模块描述，common 部分去掉 ComfyUI 客户端；删除"ComfyUI API 原型"相关段落，或改写为历史描述
  11. **更新 `docs/ROADMAP.md`**：Phase 2 状态从"进行中"改为"已完成"，补充"receiver-decouple-comfyui workflow 完成后接收端完全脱离 ComfyUI"说明
  12. 验证：`grep -rn "ComfyUI" docs/ src/ CLAUDE.md scripts/ --include="*.py" --include="*.md"` 应只在 `docs/archive/` 和 `docs/workflow/TASK_STATUS.md`（决策日志历史）、`docs/workflow/TASK_PLAN.md`（任务描述历史）、`docs/workflow/HANDOFF.md`（archive 后的历史文档）中命中；`scripts/` 目录不再有任何 ComfyUI 相关 Python 文件
  13. **批量提交 17 个 GitHub issue**（使用 `gh issue create`）：
     - **HANDOFF.md 原 14 个清单中有效的 13 个**（详见 HANDOFF.md archive 版第 4 节，排除 #12 "ComfyUIReceiver 不继承 BaseReceiver"，该项在 M-10 后已自然消失）：#1/#2/#3/#4/#5/#7/#8/#9/#10/#11/#13/#14/#15
     - **本次 brainstorming 新发现的 4 个**（详见 TASK_STATUS.md 决策日志 2026-04-08 D11 + 下次 workflow 方向修正条目）：
       - **新-1**：**统一 socket 通信架构 & 批量 VRAM 临界 & 双端演示能力综合问题**（高优先级）—— 这个 issue 描述**问题本身**（单机 VLM+Diffusers 同时驻留会 OOM / GUI 无法作为完整双机演示工具 / 批量模型生命周期耦合），**明确不预设解决方案**。候选解法（Phase-Separated Batch / 统一 socket 架构 / 独立接收端监听 Tab / ModelStore 抽象）可参考 HANDOFF.md archive 版第 5 节 + 本次 brainstorming 记录，但下次 workflow 启动时**必须重新 brainstorm**，不直接复用本次或 HANDOFF 原种子结论
       - **新-3**：`SocketRelaySender` 不支持指定源端口（低，防火墙场景可能需要）
       - **新-4**：`SocketRelayReceiver` 不做来源白名单过滤（低）
       - **新-5**：GUI 缺少独立"接收端监听" Tab（中，与新-1 相关但可独立讨论）
     - 每个 issue 需要 label（refactor / bug / architecture / vram / network / config / cleanup / priority-low/medium/high）
     - 提交后把 issue 编号记录到 TASK_STATUS.md 的 M-16 交接记录
- **验收标准**:
  - `docs/archive/comfyui-prototype/` 目录存在且包含 README + comfyui-setup.md + workflows/ + scripts/
  - `grep -rn "ComfyUI" src/ scripts/ --include="*.py"` 无命中（运行时代码和脚本层全干净）
  - `grep -rn "ComfyUI" docs/ CLAUDE.md --include="*.md"` 只在 `docs/archive/` 和 `docs/workflow/` 下命中（后者是历史决策记录）
  - `docs/demo-handbook.md` / `docs/architecture.md` / `docs/ROADMAP.md` / `CLAUDE.md` 都已更新
  - `docs/cli-reference.md` 包含 `check vlm` / `check diffusers` / `check relay` 三个子命令的完整参数文档；旧的 `check connection` / `check workflows` 章节已删除；脚本迁移表已更新
  - 17 个 GitHub issue 已提交，编号记录在 M-16 交接记录中
- **自测方法**:
  - `grep -rn "ComfyUI" docs/ src/ scripts/ CLAUDE.md --include="*.py" --include="*.md"` 只在 archive 目录和 docs/workflow/ 历史文件命中
  - `ls scripts/` 不包含 test_comfyui_connection.py 和 verify_workflows.py
  - `gh issue list --state open --limit 30` 显示 17 个新 issue
- **回滚方案**: `git revert` 本任务提交；如 issue 已提交错误，`gh issue close <number>` 批量关闭
- **预估工作量**: M（原估 S，加入 scripts 归档 + issue 批量提交后升级）
- **约束例外说明**: 本任务涉及文件数 13 > `maxFilesPerTask=8`。超出的 5 个文件均与 M-10 删除 `common/comfyui_client.py` 和 `ComfyUIConfig` 的**必要连锁归档**相关：
  - `scripts/test_comfyui_connection.py` + `scripts/verify_workflows.py`（原有 2 个）
  - `scripts/run_sender.py` + `scripts/run_receiver.py` + `scripts/demo_e2e.py`（2026-04-09 M-10 执行时发现追加 3 个）
  这 5 个脚本都在 M-10 之后立即因 ImportError 失效，必须在 Phase 2.5 内处理。放在 M-16 归档是最贴合任务性质的选择。2026-04-09 Plan Audit 修正后的决定：作为单次例外允许超约束，不修改 workflow.json 的 `maxFilesPerTask`

### Phase 3: 验证

#### [M-09a] 修复-模型加载 GGUF 量化与分组件加载

- **阶段**: Phase 3 - 验证
- **依赖**: M-04
- **目标**: 使用 GGUF 量化的 transformer + 分组件加载，使显存占用 < 20 GB，推理速度 < 2 分钟/张
- **背景信息**: M-09 验证过程中发现，`from_pretrained("Tongyi-MAI/Z-Image-Turbo")` 从 HF 仓库加载 float32 权重（transformer 23 GB），即使指定 `torch_dtype=bfloat16` 也会先读 float32 再转换。所有组件同时驻留 GPU 占满 23.5 GB 显存，推理时激活值无空间，被迫 swap 到系统内存，单张图推理 34 分钟（ComfyUI 约 1 分钟）。此外已修复两个 bug：ControlNet 仓库无 config.json 需用 `from_single_file` 加载；Canny 边缘图单通道需转 RGB。解决方案：使用社区 GGUF 量化版本（unsloth/Z-Image-Turbo-GGUF）的 Q8_0 格式（7 GB，质量 ~99%），通过 `ZImageTransformer2DModel.from_single_file` 加载 GGUF transformer，其余组件从 HF 缓存加载 bf16，ControlNet 用本地 bf16 文件。
- **涉及文件**:
  - `pyproject.toml`
  - `src/semantic_transmission/common/config.py`
  - `src/semantic_transmission/receiver/diffusers_receiver.py`
  - `tests/test_diffusers_receiver.py`
  - `tests/test_receiver_factory.py`
- **具体步骤**:
  1. 在 `pyproject.toml` 添加 `gguf>=0.6.0` 依赖
  2. 下载 GGUF Q8_0 模型文件到 `$MODEL_CACHE_DIR/Z-Image-Turbo/`
  3. `DiffusersReceiverConfig` 新增 `transformer_path` 字段，默认指向 GGUF 文件（通过 `get_default_z_image_path` 解析）
  4. `DiffusersReceiver.load()` 改为分组件加载：transformer 用 `ZImageTransformer2DModel.from_single_file` + `GGUFQuantizationConfig` 加载 GGUF；ControlNet 用 `from_single_file` 加载本地 bf16；pipeline 用 `from_pretrained` 传入已加载的 transformer 和 controlnet，其余组件从 HF 缓存以 bf16 加载
  5. 提交已修复的 bug（ControlNet from_single_file、边缘图 RGB 转换）
  6. 更新测试
- **验收标准**:
  - GPU 显存占用 < 20 GB
  - 单张图推理时间 < 2 分钟
  - `uv run pytest` 全部通过
  - `uv run ruff check .` 通过
- **自测方法**: `uv run pytest`；`uv run semantic-tx demo --image resources/test_images/canyon_jeep.jpg --prompt "test" --seed 42`（观察显存和耗时）
- **回滚方案**: `git checkout -- src/semantic_transmission/common/config.py src/semantic_transmission/receiver/diffusers_receiver.py pyproject.toml`
- **预估工作量**: M

#### [M-09] 验证-端到端测试与 Phase 2.5 产物验收

- **阶段**: Phase 3 - 验证
- **依赖**: M-09a, M-10, M-11, M-12, M-13, M-14, M-15, M-16
- **目标**: 完成端到端最终验证，覆盖 Phase 2.5 所有新产物的功能工作性 + 全量回归测试，作为本 workflow 的最后一道关。
- **背景信息**: 本任务是 receiver-decouple-comfyui workflow 的收尾验证。由于 Phase 2.5 已完全清除 ComfyUI 运行时代码（M-10~M-12），原定义里"Diffusers vs ComfyUI 质量对比"已**物理上无法执行** — ComfyUIReceiver 和 test_comfyui_receiver.py 都已被删除。本任务重新聚焦：① 全量回归（pytest + ruff）② CLI 实测（manual prompt + Diffusers，复用 M-09a 已有产物）③ GUI 手测覆盖 Phase 2.5 所有新产物（Diffusers 模型检测 / 接收端队列化 / 批量端到端 Accordion / VLM 优先默认 / 对端连接测试）④ 提交 M-09a 实测产物（`output/demo/*` 4 个 untracked 文件）⑤ 归纳最终测试结果作为 phase-review 的证据。跨后端 PSNR/SSIM/LPIPS 对比已经不适用（没有对照组），相关需求降级为 issue #8（采样器对齐）。
- **涉及文件**（非代码修改，仅验证动作 + commit 4 个现有产物）:
  - `tests/test_diffusers_receiver.py`（回归测试，不改动）
  - `tests/test_cli.py`（回归测试，不改动）
  - `tests/test_gui.py` 或 `tests/test_receiver_panel.py`（回归测试，不改动）
  - `output/demo/comparison.png`（M-09a 产物，本任务 commit 入库）
  - `output/demo/edge.png`（M-09a 产物，本任务 commit 入库）
  - `output/demo/restored.png`（M-09a 产物，本任务 commit 入库）
  - `output/demo/prompt.txt`（M-09a 产物，本任务 commit 入库）
- **前置**: 环境变量必须已导出（`HF_HOME=D:/Downloads/Models/huggingface`、`MODEL_CACHE_DIR=D:/Downloads/Models`）
- **具体步骤**:
  1. **全量回归测试**：`uv run pytest`，确认所有测试通过（Phase 2.5 可能新增了测试，总数应 >= 211 + Phase 2.5 新增数）
  2. **代码检查**：`uv run ruff check .` 和 `uv run ruff format --check .` 通过
  3. **CLI 实测**（验证 M-11 的产物）：
     - `uv run semantic-tx check vlm` 应报告 VLM 模型就绪
     - `uv run semantic-tx check diffusers` 应报告 Diffusers 三件套就绪
     - `uv run semantic-tx check relay --host 127.0.0.1 --port 9000` 应按预期报"连接拒绝"（本地无接收端在监听是正常的）
     - `uv run semantic-tx demo --image resources/test_images/canyon_jeep.jpg --prompt "A jeep driving through a desert canyon" --seed 42` 应成功生成（~64s），`output/demo/` 下产物齐备（可复用 M-09a 产物无需重跑）
  4. **GUI 手测**（验证 M-12 ~ M-15 的产物，按以下 checklist 逐项验证）：
     - [ ] `uv run semantic-tx gui` 启动无 import 错误
     - [ ] **⚙ 配置** Tab：
       - [ ] 无"接收端后端"Radio（M-12 移除）
       - [ ] 无"ComfyUI 连接"区块（M-12 移除）
       - [ ] 无"中继传输"区块（M-12 挪到批量发送 Tab）
       - [ ] "VLM 模型"区能点击检查，状态正确
       - [ ] "Diffusers 模型"区能点击检查，状态正确（M-12 新增）
     - [ ] **▲ 单张发送** Tab：
       - [ ] Prompt Mode Radio 默认 "VLM 自动生成"，Radio 圆点可见（M-14）
       - [ ] 有简短描述（M-14）
       - [ ] VLM auto 流程能完成：Canny + VLM describe + VLM unload
       - [ ] 点击"→ 加入接收端队列"按钮（M-13 改造）能把 edge + prompt append 到接收端队列
     - [ ] **📦 批量发送** Tab：
       - [ ] 描述已简化（M-14）
       - [ ] Prompt Mode Radio 默认 "VLM 自动生成"（M-14）
       - [ ] "接收端 IP 地址"/"接收端端口"字段（M-12，原 config_panel 中继配置挪过来）
       - [ ] "测试对端连接"按钮能工作（测 127.0.0.1:9000 应报连接拒绝）
     - [ ] **▼ 接收端** Tab（M-13 队列化）：
       - [ ] UI 显示"队列 + 加入 + 运行 + 清空 + 卸载"按钮组
       - [ ] 队列空时点"运行队列"给出合理提示
       - [ ] 加入 1 项后运行队列 → 模型加载一次 → 完成 → 显式 unload（可通过 nvidia-smi 旁观验证显存回落）
       - [ ] 加入 2-3 项后一键运行能循环完成
     - [ ] **◆ 端到端演示** Tab：
       - [ ] Prompt Mode 默认 VLM auto（M-14）
       - [ ] 单机一站式流程正常工作
     - [ ] **◇ 批量端到端** Tab（M-15 Accordion）：
       - [ ] Prompt Mode 默认 VLM auto（M-14）
       - [ ] 运行后每组显示为一个 Accordion 折叠块
       - [ ] 展开 Accordion 可见原图/边缘/还原/prompt
       - [ ] 勾选"运行质量评估"后每组显示 PSNR/SSIM/LPIPS
       - [ ] 总体平均指标表显示正常
  5. **提交 M-09a 实测产物**：把 `output/demo/{comparison,edge,restored}.png` + `prompt.txt` 4 个 untracked 文件纳入 M-09 的 commit（配合 `.gitignore` 的 `!output/demo/` 例外规则）
  6. **记录测试结果**：把上述 checklist 的逐项结果写入 TASK_STATUS.md 的 M-09 交接记录
- **验收标准**:
  - `uv run pytest` 全部通过
  - `uv run ruff check .` 和 `uv run ruff format --check .` 通过
  - CLI 三个 check 子命令都能运行并返回合理结果
  - CLI `demo` 命令产物齐备（复用 M-09a 产物即可）
  - GUI 手测 checklist 全部打勾（6 个 Tab 均验证）
  - `output/demo/*` 4 个产物已在本任务 commit 入库
- **自测方法**: `uv run pytest && uv run ruff check . && uv run ruff format --check .`；随后 `uv run semantic-tx gui` 逐项走 checklist
- **回滚方案**: 本任务不修改源码，仅验证 + commit 4 个产物。如 commit 需要回滚：`git restore --staged output/demo/ && git checkout -- output/demo/`
- **预估工作量**: L

