# 任务计划

## 总体策略

**Strangler Fig（绞杀者模式）**：保留 ComfyUIReceiver 不动，新建 DiffusersReceiver 并行实现，通过配置切换后端。验证新实现的生成质量对齐后，GUI/CLI 默认使用新实现。

选择理由：

- 风险最低，任何时候可回退到 ComfyUI 方案
- 便于对比两种实现的生成质量
- 不阻塞其他开发工作

## 阶段里程碑


| 阶段      | 名称   | 退出标准                            |
| ------- | ---- | ------------------------------- |
| Phase 0 | 准备   | 依赖就绪、接口设计完成、seed bug 修复         |
| Phase 1 | 核心实施 | DiffusersReceiver 单帧生成可工作，质量可对比 |
| Phase 2 | 完善   | 批量连续帧、后端切换、GUI/CLI 集成完成         |
| Phase 3 | 验证   | 全部测试通过，端到端流程可运行                 |


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
- **背景信息**: 根据 issue #10 讨论结论，当前阶段只做批量图像处理（逐帧生成），不实现视频合成。接收端收到几帧描述就生成几帧图像，帧数量对接收端透明。模型在批量处理期间保持常驻 GPU，避免反复加载。同时在中继数据结构中预留可选的 metadata 扩展字段。
- **涉及文件**:
  - `src/semantic_transmission/receiver/diffusers_receiver.py`
  - `src/semantic_transmission/receiver/base.py`
  - `tests/test_diffusers_receiver.py`
- **具体步骤**:
  1. 在 BaseReceiver 中新增 `process_batch` 方法（接收帧列表，逐帧调用 `process`，返回图像列表）
  2. 在 DiffusersReceiver 中实现/覆写 `process_batch`，确保模型常驻不反复加载
  3. 确认 metadata 字段已预留扩展位（现有 `dict[str, Any]` 已满足）
  4. 编写批量生成的测试用例
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
- **目标**: GUI 接收端面板和端到端面板支持 Diffusers 后端切换
- **背景信息**: 当前 `gui/receiver_panel.py` 和 `gui/pipeline_panel.py` 中硬编码了 ComfyUIReceiver。需要改为使用工厂函数，并在 GUI 配置面板中添加后端选择（ComfyUI / Diffusers）。当选择 Diffusers 后端时，ComfyUI 相关的 host/port 配置应隐藏或禁用。
- **涉及文件**:
  - `src/semantic_transmission/gui/receiver_panel.py`
  - `src/semantic_transmission/gui/pipeline_panel.py`
  - `src/semantic_transmission/gui/config_panel.py`
- **具体步骤**:
  1. 在 `config_panel.py` 中添加接收端后端选择组件（Radio: ComfyUI / Diffusers）
  2. 修改 `receiver_panel.py` 使用工厂函数创建 receiver，根据后端类型传入对应配置
  3. 修改 `pipeline_panel.py` 同上
  4. 添加后端切换时的 UI 联动（Diffusers 模式下隐藏 ComfyUI 配置）
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
- **背景信息**: 当前 `cli/receiver.py` 和 `cli/demo.py` 中硬编码了 ComfyUIReceiver。需要添加 `--backend` 参数（默认 "diffusers"），使用工厂函数创建 receiver。双机演示场景下，接收端也支持直接推理。
- **涉及文件**:
  - `src/semantic_transmission/cli/receiver.py`
  - `src/semantic_transmission/cli/demo.py`
- **具体步骤**:
  1. 在 `cli/receiver.py` 添加 `--backend` 选项（choice: comfyui/diffusers，默认 diffusers）
  2. 根据 backend 使用工厂函数创建 receiver
  3. 在 `cli/demo.py` 同样添加 `--backend` 选项
  4. Diffusers 模式下跳过 ComfyUI 连接检查
- **验收标准**:
  - `semantic-tx receiver --backend diffusers` 可正常启动
  - `semantic-tx demo --backend comfyui` 行为与之前一致
  - `semantic-tx receiver --help` 显示 backend 选项
  - `uv run ruff check .` 通过
- **自测方法**: `uv run semantic-tx receiver --help`；`uv run pytest tests/test_cli.py`
- **回滚方案**: `git checkout -- src/semantic_transmission/cli/receiver.py src/semantic_transmission/cli/demo.py`
- **预估工作量**: M

### Phase 3: 验证

#### [M-09] 验证-端到端测试与质量对比

- **阶段**: Phase 3 - 验证
- **依赖**: M-06, M-07, M-08
- **目标**: 完成端到端测试，验证 Diffusers 后端的生成质量和功能完整性
- **背景信息**: 所有模块集成完毕后，需要验证：1) 单帧生成功能正确；2) 批量连续帧生成功能正确；3) GUI 和 CLI 两种入口都能正常工作；4) Diffusers 后端与 ComfyUI 后端的生成质量对比（使用现有 evaluation 模块的 PSNR/SSIM/LPIPS 指标）；5) 所有现有测试通过无回归。
- **涉及文件**:
  - `tests/test_diffusers_receiver.py`
  - `tests/test_comfyui_receiver.py`
  - `tests/test_cli.py`
- **具体步骤**:
  1. 运行全量测试 `uv run pytest`，确认无回归
  2. 运行 `uv run ruff check .` 和 `uv run ruff format --check .` 确认 CI 通过
  3. 手动测试 GUI 端到端流程（Diffusers 后端）
  4. 手动测试 CLI demo（Diffusers 后端）
  5. 使用 evaluation 模块对比 ComfyUI 和 Diffusers 后端的生成质量
  6. 记录测试结果
- **验收标准**:
  - `uv run pytest` 全部通过
  - `uv run ruff check .` 和 `uv run ruff format --check .` 通过
  - GUI 端到端演示可完整运行
  - CLI demo 可完整运行
  - 质量对比报告已生成
- **自测方法**: `uv run pytest && uv run ruff check . && uv run ruff format --check .`
- **回滚方案**: 不涉及代码修改，仅验证
- **预估工作量**: L

