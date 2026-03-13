# 任务计划

## 总体策略

**适配器模式（Adapter Pattern）**

为发送端（VLM）和接收端（ComfyUI）分别定义抽象接口，具体实现作为可替换的适配器。Pipeline 层只依赖抽象接口，后续替换模型或脱离 ComfyUI 时只需新增适配器实现。

选择理由：
1. ROADMAP 阶段三明确要替换模型（Qwen → InternVL、Z-Image-Turbo → FLUX），适配器天然支持
2. ROADMAP 阶段四要完全脱离 ComfyUI，接收端适配器可无缝切换到直接推理
3. 发送端 VLM 有两种部署方式（Transformers/vLLM），适配器统一抽象

## 阶段里程碑

| 阶段 | 名称 | 退出标准 |
|------|------|----------|
| Phase 0 | 契约确认与项目骨架 | Python 项目结构就绪，ComfyUI API 连通性验证通过，抽象接口定义完成 |
| Phase 1 | 适配层实现 | 发送端适配器（VLM + Canny）和接收端适配器（ComfyUI API）各自独立可用 |
| Phase 2 | 端到端联调 | 图像输入 → 发送端 → 接收端 → 还原图像的完整 pipeline 可运行 |
| Phase 3 | 评估与稳定化 | 质量评估指标（CLIP Score、LPIPS）可计算，异常处理覆盖关键路径 |

## 任务列表

### Phase 0: 契约确认与项目骨架

#### [P2-01] 搭建-Python 项目骨架

- **阶段**: Phase 0 - 契约确认与项目骨架
- **依赖**: 无
- **目标**: 创建 Python 项目结构、依赖配置和基本目录布局，使后续任务有统一的开发环境
- **背景信息**: 本项目是语义传输预研，目前仅有文档和 ComfyUI 工作流 JSON（`resources/comfyui/`），无任何 Python 代码。需要使用 uv 作为包管理器创建项目，技术栈为 Python 3.10+。项目采用适配器模式，需要 `src/` 下的模块化目录结构。
- **涉及文件**:
  - `pyproject.toml`（新建）
  - `src/semantic_transmission/__init__.py`（新建）
  - `src/semantic_transmission/sender/__init__.py`（新建）
  - `src/semantic_transmission/receiver/__init__.py`（新建）
  - `src/semantic_transmission/pipeline/__init__.py`（新建）
  - `src/semantic_transmission/common/__init__.py`（新建）
  - `tests/__init__.py`（新建）
- **具体步骤**:
  1. 创建 `pyproject.toml`，配置项目名称、Python 版本、基础依赖（requests、websocket-client、Pillow、opencv-python、numpy）
  2. 创建 `src/semantic_transmission/` 包及子包目录（sender、receiver、pipeline、common）
  3. 创建 `tests/` 目录
  4. 运行 `uv sync` 验证依赖安装
- **验收标准**:
  - [ ] `uv sync` 成功完成，无报错
  - [ ] `uv run python -c "import semantic_transmission"` 正常执行
  - [ ] 目录结构包含 sender、receiver、pipeline、common 四个子包
- **自测方法**: `uv sync && uv run python -c "import semantic_transmission; print('OK')"`
- **回滚方案**: 删除 pyproject.toml、src/、tests/ 目录
- **预估工作量**: S

---

#### [P2-02] 定义-抽象接口

- **阶段**: Phase 0 - 契约确认与项目骨架
- **依赖**: P2-01
- **目标**: 定义发送端（Sender）和接收端（Receiver）的抽象基类，确立适配器模式的接口契约
- **背景信息**: 项目采用适配器模式进行系统集成。发送端负责将图像转换为文本描述+条件图，接收端负责从文本+条件图还原图像。抽象接口需要覆盖：(1) Sender：输入图像，输出结构化描述文本；(2) ConditionExtractor：输入图像，输出条件图（Canny 边缘等）；(3) Receiver：输入文本+条件图，输出还原图像。接口设计需考虑后续扩展（更换 VLM、更换生成模型、脱离 ComfyUI）。
- **涉及文件**:
  - `src/semantic_transmission/sender/base.py`（新建）
  - `src/semantic_transmission/receiver/base.py`（新建）
  - `src/semantic_transmission/common/types.py`（新建）
- **具体步骤**:
  1. 在 `common/types.py` 中定义公共数据类型：`SenderOutput`（text + metadata）、`TransmissionData`（text + condition_image + metadata）、`ReceiverOutput`（image + metadata）
  2. 在 `sender/base.py` 中定义 `BaseSender`（ABC）：`describe(image) → SenderOutput` 和 `BaseConditionExtractor`（ABC）：`extract(image) → ndarray`
  3. 在 `receiver/base.py` 中定义 `BaseReceiver`（ABC）：`reconstruct(text, condition_image) → ReceiverOutput`
  4. 为每个抽象方法添加类型注解和 docstring
- **验收标准**:
  - [ ] 三个抽象基类均已定义，包含类型注解
  - [ ] 公共数据类型使用 dataclass 定义
  - [ ] `uv run python -c "from semantic_transmission.sender.base import BaseSender"` 正常
  - [ ] `uv run python -c "from semantic_transmission.receiver.base import BaseReceiver"` 正常
- **自测方法**: 导入所有基类并验证为 ABC（不可直接实例化）
- **回滚方案**: 删除 base.py 和 types.py 文件
- **预估工作量**: S

---

#### [P2-03] 验证-ComfyUI API 连通性

- **阶段**: Phase 0 - 契约确认与项目骨架
- **依赖**: P2-01
- **目标**: 编写 ComfyUI API 连通性测试脚本，验证能够远程调用 ComfyUI 服务并提交工作流
- **背景信息**: ComfyUI 提供 REST API + WebSocket 接口，需以 `--listen` 模式启动。核心端点：POST `/prompt`（提交工作流）、GET `/history/{id}`（查询结果）、GET `/view`（下载图像）、POST `/upload/image`（上传图像）、WebSocket `ws://{host}/ws`（实时监听）。本任务不实现完整客户端，仅验证网络连通性和基本 API 调用。ComfyUI 部署地址需从配置读取。
- **涉及文件**:
  - `src/semantic_transmission/common/config.py`（新建）
  - `scripts/test_comfyui_connection.py`（新建）
- **具体步骤**:
  1. 创建 `common/config.py`，定义配置类（ComfyUI host/port、超时时间等），支持环境变量和默认值
  2. 编写 `scripts/test_comfyui_connection.py` 脚本：
     - GET `/queue` 检查服务是否在线
     - POST `/upload/image` 上传一张测试图像
     - POST `/prompt` 提交现有工作流 JSON（`resources/comfyui/image_z_image_turbo_fun_union_controlnet.json`）
     - WebSocket 连接测试
     - GET `/history/{id}` 和 GET `/view` 获取结果
  3. 输出每个步骤的成功/失败状态
- **验收标准**:
  - [ ] 配置类支持通过环境变量 `COMFYUI_HOST` 和 `COMFYUI_PORT` 设置地址
  - [ ] 脚本能在 ComfyUI 不可用时给出明确的错误信息（而非崩溃）
  - [ ] 脚本能在 ComfyUI 可用时完成完整的提交-监听-获取流程
- **自测方法**: `uv run python scripts/test_comfyui_connection.py`（ComfyUI 不可用时应输出连接失败信息）
- **回滚方案**: 删除 config.py 和 test 脚本
- **预估工作量**: M

---

#### [P2-04] 分析-工作流 JSON 到 API 格式转换

- **阶段**: Phase 0 - 契约确认与项目骨架
- **依赖**: P2-03
- **目标**: 实现 ComfyUI 工作流 JSON（UI 导出格式）到 API 提交格式的转换工具
- **背景信息**: ComfyUI 有两种 JSON 格式：(1) UI 导出格式（`resources/comfyui/` 中的文件，包含 nodes、links、groups 等 UI 元数据）；(2) API 提交格式（扁平的 node_id → {class_type, inputs} 映射）。POST `/prompt` 端点接受的是 API 格式。需要实现转换逻辑：解析 UI 格式的节点和连接关系，生成 API 格式，并支持动态注入参数（prompt 文本、条件图像路径）。
- **涉及文件**:
  - `src/semantic_transmission/receiver/workflow_converter.py`（新建）
  - `tests/test_workflow_converter.py`（新建）
- **具体步骤**:
  1. 分析 `resources/comfyui/image_z_image_turbo_fun_union_controlnet.json` 的 UI 格式结构
  2. 实现 `WorkflowConverter` 类：
     - `load(json_path)` 加载 UI 格式工作流
     - `to_api_format()` 转换为 API 格式
     - `set_prompt(text)` 注入文本描述
     - `set_condition_image(image_name)` 注入条件图像引用
  3. 编写单元测试，验证转换结果的结构正确性
- **验收标准**:
  - [ ] 能正确解析现有工作流 JSON（18 个节点、20+ 条连接）
  - [ ] 转换后的 API 格式包含所有节点及其输入参数
  - [ ] 支持动态注入 prompt 文本和条件图像路径
  - [ ] 单元测试通过
- **自测方法**: `uv run pytest tests/test_workflow_converter.py -v`
- **回滚方案**: 删除 workflow_converter.py 和对应测试
- **预估工作量**: M

---

### Phase 1: 适配层实现

#### [P2-05] 实现-Canny 条件提取器

- **阶段**: Phase 1 - 适配层实现
- **依赖**: P2-02
- **目标**: 实现基于 OpenCV 的 Canny 边缘条件提取器，作为 BaseConditionExtractor 的第一个具体实现
- **背景信息**: 语义传输发送端需要从原始图像提取结构化条件信息。Canny 边缘图是最基础的条件类型，ComfyUI 工作流中使用的参数为 low_threshold=0.15、high_threshold=0.35。提取结果为二值边缘图（uint8 numpy array），后续需上传到 ComfyUI 作为 ControlNet 条件输入。提取过程纯 CPU 计算，依赖 opencv-python。
- **涉及文件**:
  - `src/semantic_transmission/sender/canny_extractor.py`（新建）
  - `tests/test_canny_extractor.py`（新建）
- **具体步骤**:
  1. 实现 `CannyExtractor(BaseConditionExtractor)`：
     - 构造参数：low_threshold（默认 0.15）、high_threshold（默认 0.35）
     - `extract(image: ndarray) → ndarray`：灰度转换 → Canny 边缘检测 → 返回边缘图
  2. 处理输入图像的格式兼容（RGB/BGR、PIL Image/ndarray）
  3. 编写单元测试（使用合成测试图像）
- **验收标准**:
  - [ ] 继承 BaseConditionExtractor 并实现 extract 方法
  - [ ] 输出为 uint8 二值图像（0/255）
  - [ ] 支持 numpy array 和 PIL Image 输入
  - [ ] 单元测试通过
- **自测方法**: `uv run pytest tests/test_canny_extractor.py -v`
- **回滚方案**: 删除 canny_extractor.py 和测试
- **预估工作量**: S

---

#### [P2-06] 实现-VLM 发送端适配器

- **阶段**: Phase 1 - 适配层实现
- **依赖**: P2-02
- **目标**: 实现基于 Qwen2.5-VL 的发送端适配器，能够输入图像并输出结构化场景描述文本
- **背景信息**: 发送端的核心功能是将图像转换为文本描述。主选模型为 Qwen2.5-VL-7B，部署方式优先使用 Transformers 本地加载（单卡 RTX 4090，FP16 约 18GB，INT4 约 8GB）。需要设计结构化 prompt 模板引导模型输出格式化描述，参考 ComfyUI 工作流中的 prompt 结构：[Scene Style]/[Perspective]/[Key Elements] 等。输出文本将作为接收端生成图像的 prompt。
- **涉及文件**:
  - `src/semantic_transmission/sender/qwen_vl_sender.py`（新建）
  - `src/semantic_transmission/sender/prompt_templates.py`（新建）
  - `tests/test_qwen_vl_sender.py`（新建）
- **具体步骤**:
  1. 在 `prompt_templates.py` 中定义结构化 prompt 模板（引导模型输出 [Scene Style]/[Perspective]/[Key Elements] 格式）
  2. 实现 `QwenVLSender(BaseSender)`：
     - 构造参数：model_path、device、quantization（none/int4/int8）
     - `load_model()` 加载 Qwen2.5-VL 模型和 processor
     - `describe(image) → SenderOutput`：构建多模态消息 → 模型推理 → 解析输出
  3. 编写测试（使用 mock 模拟模型推理，不需要真实模型文件）
- **验收标准**:
  - [ ] 继承 BaseSender 并实现 describe 方法
  - [ ] prompt 模板能引导生成结构化描述
  - [ ] 支持 FP16 和 INT4 量化加载
  - [ ] mock 测试通过
- **自测方法**: `uv run pytest tests/test_qwen_vl_sender.py -v`
- **回滚方案**: 删除 qwen_vl_sender.py、prompt_templates.py 和测试
- **预估工作量**: L

---

#### [P2-07] 实现-ComfyUI 接收端适配器

- **阶段**: Phase 1 - 适配层实现
- **依赖**: P2-02, P2-04
- **目标**: 实现基于 ComfyUI API 的接收端适配器，能够提交文本+条件图并获取生成的还原图像
- **背景信息**: 接收端通过 ComfyUI REST API 提交工作流并获取生成结果。完整流程：(1) 上传条件图像到 ComfyUI（POST `/upload/image`）；(2) 使用 WorkflowConverter 构建 API 格式的工作流 JSON，注入 prompt 文本和条件图引用；(3) 提交工作流（POST `/prompt`）获取 prompt_id；(4) 通过 WebSocket 监听执行进度；(5) 查询结果（GET `/history/{prompt_id}`）；(6) 下载生成图像（GET `/view`）。工作流使用 Z-Image-Turbo + ControlNet Union，9 步采样，CFG=1。
- **涉及文件**:
  - `src/semantic_transmission/receiver/comfyui_receiver.py`（新建）
  - `src/semantic_transmission/receiver/comfyui_client.py`（新建）
  - `tests/test_comfyui_receiver.py`（新建）
- **具体步骤**:
  1. 实现 `ComfyUIClient` 类，封装底层 HTTP/WebSocket 调用：
     - `upload_image(image, name)` — 上传图像
     - `submit_workflow(workflow_json)` — 提交工作流，返回 prompt_id
     - `wait_for_completion(prompt_id)` — WebSocket 监听直到完成
     - `get_result_image(prompt_id)` — 获取生成图像
  2. 实现 `ComfyUIReceiver(BaseReceiver)`：
     - 构造参数：comfyui_host、comfyui_port、workflow_path
     - `reconstruct(text, condition_image) → ReceiverOutput`：编排完整的提交-等待-获取流程
  3. 编写测试（mock HTTP 响应）
- **验收标准**:
  - [ ] 继承 BaseReceiver 并实现 reconstruct 方法
  - [ ] ComfyUIClient 封装全部 6 个关键 API 调用
  - [ ] WebSocket 监听支持超时处理
  - [ ] mock 测试通过
- **自测方法**: `uv run pytest tests/test_comfyui_receiver.py -v`
- **回滚方案**: 删除 comfyui_receiver.py、comfyui_client.py 和测试
- **预估工作量**: L

---

### Phase 2: 端到端联调

#### [P2-08] 搭建-端到端 Pipeline

- **阶段**: Phase 2 - 端到端联调
- **依赖**: P2-05, P2-06, P2-07
- **目标**: 实现 Pipeline 编排层，将发送端和接收端串联为完整的端到端语义传输流程
- **背景信息**: Pipeline 是系统的编排层，负责协调发送端（VLM 描述 + Canny 提取）和接收端（ComfyUI 生成）。流程：输入图像 → 并行执行 VLM 描述和 Canny 提取 → 打包传输数据（文本 + 边缘图）→ 记录传输数据量（码率统计）→ 提交接收端还原 → 输出还原图像。Pipeline 依赖抽象接口，不直接引用具体实现。
- **涉及文件**:
  - `src/semantic_transmission/pipeline/semantic_pipeline.py`（新建）
  - `src/semantic_transmission/pipeline/transmission.py`（新建）
  - `tests/test_pipeline.py`（新建）
- **具体步骤**:
  1. 在 `transmission.py` 中实现传输数据的序列化/反序列化和码率统计
  2. 实现 `SemanticPipeline` 类：
     - 构造参数：sender、condition_extractor、receiver
     - `process(image_path) → PipelineResult`：编排完整流程
     - `process_batch(image_dir) → list[PipelineResult]`：批量处理
  3. 记录每次处理的传输数据量（文本字节数 + 条件图压缩大小）
  4. 编写集成测试（mock sender 和 receiver）
- **验收标准**:
  - [ ] Pipeline 只依赖抽象接口（BaseSender、BaseConditionExtractor、BaseReceiver）
  - [ ] 单帧处理流程完整：输入图像 → 输出还原图像 + 传输统计
  - [ ] 传输数据量统计正确（文本字节 + 条件图 PNG 大小）
  - [ ] 批量处理支持目录扫描
  - [ ] 测试通过
- **自测方法**: `uv run pytest tests/test_pipeline.py -v`
- **回滚方案**: 删除 pipeline 模块文件和测试
- **预估工作量**: M

---

#### [P2-09] 编写-端到端 Demo 脚本

- **阶段**: Phase 2 - 端到端联调
- **依赖**: P2-08
- **目标**: 编写可直接运行的 demo 脚本，演示完整的语义传输流程并输出对比结果
- **背景信息**: Demo 脚本是 Phase 2 的核心交付物，用于向团队演示端到端流程。脚本应：(1) 加载配置（ComfyUI 地址、模型路径等）；(2) 初始化 Pipeline（实例化具体的 Sender、Extractor、Receiver）；(3) 处理指定图像；(4) 保存结果（原图、边缘图、还原图并排对比）；(5) 输出传输统计（数据量、压缩比、bpp）。需要提供示例配置和使用说明。
- **涉及文件**:
  - `scripts/demo.py`（新建）
  - `configs/default.yaml`（新建）
  - `scripts/README.md`（新建）
- **具体步骤**:
  1. 创建 `configs/default.yaml` 配置文件（ComfyUI 地址、模型路径、Canny 参数等）
  2. 实现 `scripts/demo.py`：
     - 解析命令行参数（输入图像、配置文件、输出目录）
     - 初始化各组件并组装 Pipeline
     - 执行处理并保存结果
     - 生成对比图（原图 | Canny | 还原图）
     - 打印传输统计信息
  3. 编写 `scripts/README.md` 使用说明
- **验收标准**:
  - [ ] `uv run python scripts/demo.py --image <path> --config configs/default.yaml` 可运行
  - [ ] 输出目录包含：对比图、独立的还原图、传输统计 JSON
  - [ ] README 包含使用步骤和配置说明
- **自测方法**: `uv run python scripts/demo.py --help` 正常显示帮助信息
- **回滚方案**: 删除 scripts/demo.py、configs/ 和 scripts/README.md
- **预估工作量**: M

---

### Phase 3: 评估与稳定化

#### [P2-10] 实现-质量评估模块

- **阶段**: Phase 3 - 评估与稳定化
- **依赖**: P2-08
- **目标**: 实现图像还原质量的自动化评估模块，支持 CLIP Score、LPIPS、PSNR、SSIM 指标计算
- **背景信息**: 语义传输的核心评估维度是还原质量 vs 传输码率的权衡。主要指标：(1) CLIP Score——衡量生成图像与文本描述的语义一致性，语义传输最关键的指标；(2) LPIPS——感知相似度，衡量生成图像与原图的视觉感知差异；(3) PSNR/SSIM——传统像素级指标，作为参考（生成式方案在此指标上非强项）。评估模块需要额外依赖：torch、clip、lpips。
- **涉及文件**:
  - `src/semantic_transmission/evaluation/__init__.py`（新建）
  - `src/semantic_transmission/evaluation/metrics.py`（新建）
  - `tests/test_metrics.py`（新建）
- **具体步骤**:
  1. 在 pyproject.toml 中添加评估依赖组（torch、transformers、lpips），作为可选依赖 `[evaluation]`
  2. 实现 `ImageMetrics` 类：
     - `clip_score(image, text) → float`
     - `lpips(image1, image2) → float`
     - `psnr(image1, image2) → float`
     - `ssim(image1, image2) → float`
  3. 实现 `evaluate_result(original, reconstructed, text) → dict` 汇总函数
  4. 编写测试（使用小尺寸合成图像）
- **验收标准**:
  - [ ] 四个指标函数均可独立调用
  - [ ] 输入支持 PIL Image 和 numpy array
  - [ ] 评估依赖作为可选组，不影响核心功能安装
  - [ ] 测试通过
- **自测方法**: `uv run --extra evaluation pytest tests/test_metrics.py -v`
- **回滚方案**: 删除 evaluation 模块和测试
- **预估工作量**: M

---

#### [P2-11] 添加-异常处理与日志

- **阶段**: Phase 3 - 评估与稳定化
- **依赖**: P2-08
- **目标**: 为关键路径添加异常处理、重试机制和结构化日志，提升系统稳定性
- **背景信息**: 当前 Pipeline 的关键故障点：(1) ComfyUI 服务不可用或执行超时；(2) VLM 推理超时或 OOM；(3) WebSocket 连接中断；(4) 工作流 JSON 格式错误。需要添加：自定义异常类型、关键操作的超时控制、ComfyUI 提交的重试（最多 3 次）、结构化日志（使用 Python logging）。
- **涉及文件**:
  - `src/semantic_transmission/common/exceptions.py`（新建）
  - `src/semantic_transmission/common/logging.py`（新建）
  - `src/semantic_transmission/receiver/comfyui_client.py`（修改）
  - `src/semantic_transmission/pipeline/semantic_pipeline.py`（修改）
- **具体步骤**:
  1. 定义自定义异常：`ComfyUIConnectionError`、`ComfyUITimeoutError`、`VLMInferenceError`、`WorkflowConversionError`
  2. 配置结构化日志（控制台 + 文件输出，带时间戳和模块名）
  3. 为 ComfyUIClient 添加连接重试（3 次，指数退避）和超时处理
  4. 为 Pipeline 添加各阶段的异常捕获和日志记录
- **验收标准**:
  - [ ] ComfyUI 不可用时抛出 `ComfyUIConnectionError`（而非原始异常）
  - [ ] WebSocket 超时时抛出 `ComfyUITimeoutError`
  - [ ] 日志输出包含时间戳、模块名和日志级别
  - [ ] 重试机制在连接失败时自动重试 3 次
- **自测方法**: `uv run pytest tests/ -v`（全部测试通过）
- **回滚方案**: 还原修改的文件，删除 exceptions.py 和 logging.py
- **预估工作量**: M

---

#### [P2-12] 执行-初步质量评估

- **阶段**: Phase 3 - 评估与稳定化
- **依赖**: P2-09, P2-10
- **目标**: 使用 demo pipeline 处理一组测试图像，记录质量指标和传输码率，形成基线评估报告
- **背景信息**: Phase 2 的最终交付物之一是初步质量评估数据。需要：(1) 选取 5-10 张不同场景的测试图像（室内、室外、人像、风景等）；(2) 运行 pipeline 生成还原图像；(3) 计算 CLIP Score、LPIPS、PSNR、SSIM；(4) 记录每张图的传输数据量和 bpp；(5) 汇总为评估报告，作为后续优化的基线。
- **涉及文件**:
  - `scripts/evaluate.py`（新建）
  - `docs/evaluation/baseline-report.md`（新建）
- **具体步骤**:
  1. 编写 `scripts/evaluate.py` 批量评估脚本：
     - 扫描测试图像目录
     - 对每张图运行 pipeline + 质量评估
     - 输出 CSV 格式的指标数据
     - 生成汇总统计（均值、标准差）
  2. 准备测试图像集（可使用公开数据集的样本）
  3. 执行评估，记录结果到 `docs/evaluation/baseline-report.md`
- **验收标准**:
  - [ ] 评估脚本可批量处理图像目录
  - [ ] 输出包含每张图的完整指标（CLIP Score、LPIPS、PSNR、SSIM、bpp）
  - [ ] 基线报告包含汇总表格和初步分析
- **自测方法**: `uv run python scripts/evaluate.py --help`
- **回滚方案**: 删除评估脚本和报告
- **预估工作量**: L
