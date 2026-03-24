# 任务计划

## 总体策略

**语义传输端到端原型：ComfyUI 工作流拆分 + VLM 自动语义压缩 + 中继传输**

将同事已实现的 ComfyUI 工作流拆分为发送端和接收端，两端通过 ComfyUI API 调用。发送端集成 VLM（Qwen2.5-VL）自动生成图像语义描述，实现"自动语义压缩→条件还原"的核心能力闭环。

核心思路：
1. 发送端：输入图像 → VLM 自动生成语义描述（文本 prompt） + ComfyUI Canny 边缘提取（条件特征）
2. 接收端 ComfyUI 工作流：输入边缘图 + prompt 文本 → Z-Image-Turbo + ControlNet → 输出还原图像
3. 中继层：从发送端获取边缘图 + prompt → 传给接收端

部署模式：
- 单机双端：发送端和接收端连同一个 ComfyUI 实例，快速调试
- 双机双端：发送端和接收端各部署一台机器，实际演示

硬件需求：
- GPU 显存 ≥24GB（ComfyUI ~6GB + VLM INT4 ~8GB 可同机运行）

后续演进（Phase 3+）：
- 用 Python OpenCV 替代 ComfyUI 发送端（启用 P2-02 的 BaseConditionExtractor 抽象接口）
- 完全脱离 ComfyUI（ROADMAP 阶段四）

## 阶段里程碑

| 阶段 | 名称 | 退出标准 |
|------|------|----------|
| Phase 0 | 契约确认与项目骨架 | Python 项目结构就绪，ComfyUI API 连通性验证通过，工作流转换器完成 |
| Phase 1 | 工作流拆分与语义压缩 | 单机上能跑通"VLM 自动语义压缩→条件还原"完整流程，demo 脚本支持手动/自动 prompt 双模式 |
| Phase 2 | 中继传输与双机演示 | 两台机器分别运行发送端和接收端，通过网络传输完成还原 |
| Phase 3 | 质量优化 | 质量评估指标可计算 |

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
  - [x] `uv sync` 成功完成，无报错
  - [x] `uv run python -c "import semantic_transmission"` 正常执行
  - [x] 目录结构包含 sender、receiver、pipeline、common 四个子包
- **自测方法**: `uv sync && uv run python -c "import semantic_transmission; print('OK')"`
- **回滚方案**: 删除 pyproject.toml、src/、tests/ 目录
- **预估工作量**: S

---

#### [P2-02] 定义-抽象接口

- **阶段**: Phase 0 - 契约确认与项目骨架
- **依赖**: P2-01
- **目标**: 定义发送端（Sender）和接收端（Receiver）的抽象基类，确立适配器模式的接口契约
- **背景信息**: 项目采用适配器模式进行系统集成。抽象接口定义了 BaseSender、BaseConditionExtractor、BaseReceiver 三个 ABC。P2-13（VLM 集成）将启用 BaseSender 接口实现 QwenVLSender 适配器。
- **涉及文件**:
  - `src/semantic_transmission/sender/base.py`（新建）
  - `src/semantic_transmission/receiver/base.py`（新建）
  - `src/semantic_transmission/common/types.py`（新建）
- **验收标准**:
  - [x] 三个抽象基类均已定义，包含类型注解
  - [x] 公共数据类型使用 dataclass 定义
- **预估工作量**: S

---

#### [P2-03] 验证-ComfyUI API 连通性

- **阶段**: Phase 0 - 契约确认与项目骨架
- **依赖**: P2-01
- **目标**: 编写 ComfyUI API 连通性测试脚本，验证能够远程调用 ComfyUI 服务并提交工作流
- **背景信息**: ComfyUI 提供 REST API + WebSocket 接口，需以 `--listen` 模式启动。核心端点：POST `/prompt`（提交工作流）、GET `/history/{id}`（查询结果）、GET `/view`（下载图像）、POST `/upload/image`（上传图像）、WebSocket `ws://{host}/ws`（实时监听）。
- **涉及文件**:
  - `src/semantic_transmission/common/config.py`（新建）
  - `scripts/test_comfyui_connection.py`（新建）
- **验收标准**:
  - [x] 配置类支持通过环境变量 `COMFYUI_HOST` 和 `COMFYUI_PORT` 设置地址
  - [x] 脚本能在 ComfyUI 不可用时给出明确的错误信息（而非崩溃）
  - [x] 脚本能在 ComfyUI 可用时完成完整的提交-监听-获取流程
- **自测方法**: `uv run python scripts/test_comfyui_connection.py`
- **回滚方案**: 删除 config.py 和 test 脚本
- **预估工作量**: M

---

#### [P2-04] 分析-工作流 JSON 到 API 格式转换

- **阶段**: Phase 0 - 契约确认与项目骨架
- **依赖**: P2-03
- **目标**: 实现 ComfyUI 工作流 JSON（UI 导出格式）到 API 提交格式的转换工具
- **背景信息**: ComfyUI 有两种 JSON 格式：(1) UI 导出格式（包含 nodes、links、groups 等 UI 元数据）；(2) API 提交格式（扁平的 node_id → {class_type, inputs} 映射）。转换工具可用于辅助生成拆分后的工作流 JSON。
- **涉及文件**:
  - `src/semantic_transmission/receiver/workflow_converter.py`（新建）
  - `tests/test_workflow_converter.py`（新建）
- **验收标准**:
  - [x] 能正确解析现有工作流 JSON
  - [x] 转换后的 API 格式包含所有节点及其输入参数
  - [x] 支持动态注入 prompt 文本和条件图像路径
  - [x] 单元测试通过（20 个）
- **自测方法**: `uv run pytest tests/test_workflow_converter.py -v`
- **回滚方案**: 删除 workflow_converter.py 和对应测试
- **预估工作量**: M

---

### Phase 1: 工作流拆分与语义压缩

#### [P2-05] 拆分-工作流 JSON

- **阶段**: Phase 1 - 工作流拆分与语义压缩
- **依赖**: P2-04
- **目标**: 将完整工作流拆分为发送端和接收端两个独立的 API 格式 JSON
- **背景信息**: 同事的 ComfyUI 工作流（`resources/comfyui/image_z_image_turbo_fun_union_controlnet.json`）将发送端（图像→Canny边缘提取）和接收端（边缘图+prompt→Z-Image-Turbo生成）集成在一个工作流中。需要拆分为两个独立的 API 格式 JSON，分别用于发送端和接收端的 ComfyUI API 调用。
  - 发送端工作流：LoadImage + ImageScaleToMaxDimension + Canny + SaveImage（4 个节点）
  - 接收端工作流：LoadImage（加载边缘图）+ 子图展开后的全部生成节点 + SaveImage（~14 个节点）
- **涉及文件**:
  - `resources/comfyui/sender_workflow_api.json`（新建）
  - `resources/comfyui/receiver_workflow_api.json`（新建）
- **具体步骤**:
  1. 分析完整工作流的节点拓扑，确定发送端/接收端的拆分边界（Canny 输出为边界）
  2. 构造发送端 API JSON：LoadImage → ImageScaleToMaxDimension → Canny → SaveImage
  3. 构造接收端 API JSON：LoadImage（边缘图）→ 展开后的子图节点（CLIPLoader、UNETLoader、VAELoader、ModelPatchLoader、CLIPTextEncode、ConditioningZeroOut、QwenImageDiffsynthControlnet、ModelSamplingAuraFlow、GetImageSize、EmptySD3LatentImage、KSampler、VAEDecode）→ SaveImage
  4. 可借助 P2-04 的 WorkflowConverter 辅助生成，或手工编写 API 格式 JSON
  5. 验证两个 JSON 分别提交 ComfyUI `/prompt` 端点能正常执行
- **验收标准**:
  - [ ] 发送端 JSON 提交后能输出 Canny 边缘图
  - [ ] 接收端 JSON 提交后能从边缘图 + prompt 生成还原图像
  - [ ] 两个 JSON 均为有效的 ComfyUI API 格式
- **自测方法**: 用 `scripts/test_comfyui_connection.py` 的逻辑分别提交两个工作流
- **回滚方案**: 删除两个新建的 JSON 文件
- **预估工作量**: M

---

#### [P2-06] 扩展-配置支持双 ComfyUI 实例

- **阶段**: Phase 1 - 工作流拆分与语义压缩
- **依赖**: P2-03
- **目标**: 扩展 config.py 支持发送端和接收端指向不同的 ComfyUI 实例
- **背景信息**: 当前 `ComfyUIConfig` 只支持单个 ComfyUI 实例。在双机双端演示场景下，发送端和接收端可能运行在不同的机器上，需要分别配置地址。单机调试时两端可以指向同一实例。
- **涉及文件**:
  - `src/semantic_transmission/common/config.py`（修改）
  - `tests/test_config.py`（新建）
- **具体步骤**:
  1. 保留 `ComfyUIConfig` 单实例配置不变
  2. 新增 `SemanticTransmissionConfig`，包含 `sender: ComfyUIConfig` 和 `receiver: ComfyUIConfig`
  3. 支持环境变量：`COMFYUI_SENDER_HOST`/`COMFYUI_SENDER_PORT` 和 `COMFYUI_RECEIVER_HOST`/`COMFYUI_RECEIVER_PORT`，未设置时回退到 `COMFYUI_HOST`/`COMFYUI_PORT`
  4. 编写单元测试
- **验收标准**:
  - [ ] 单机模式：未设置 SENDER/RECEIVER 环境变量时，两端使用相同地址
  - [ ] 双机模式：设置不同的 SENDER/RECEIVER 地址后，两端配置独立
  - [ ] 测试通过
- **自测方法**: `uv run pytest tests/test_config.py -v`
- **回滚方案**: 还原 config.py，删除测试
- **预估工作量**: S

---

#### [P2-07] 实现-ComfyUI API 客户端

- **阶段**: Phase 1 - 工作流拆分与语义压缩
- **依赖**: P2-06
- **目标**: 封装通用 ComfyUI REST API + WebSocket 客户端，供发送端和接收端复用
- **背景信息**: `scripts/test_comfyui_connection.py` 中已有各 API 端点的调用示例，本任务将其封装为可复用的客户端类。核心 API：POST `/upload/image`（上传图像）、POST `/prompt`（提交工作流）、WebSocket 监听或轮询 `/history`（等待完成）、GET `/history/{id}` + GET `/view`（获取结果图像）。
- **涉及文件**:
  - `src/semantic_transmission/common/comfyui_client.py`（新建）
  - `tests/test_comfyui_client.py`（新建）
- **具体步骤**:
  1. 实现 `ComfyUIClient(config: ComfyUIConfig)`：
     - `upload_image(image_bytes, filename) → str` — POST `/upload/image`，返回服务端文件名
     - `submit_workflow(api_json, client_id=None) → str` — POST `/prompt`，返回 prompt_id
     - `wait_for_completion(prompt_id, timeout=None) → dict` — WebSocket 监听或轮询 `/history` 直到完成
     - `get_result_images(prompt_id) → list[bytes]` — GET `/history/{id}` 解析输出节点 + GET `/view` 下载图像
  2. 参考 `scripts/test_comfyui_connection.py` 中的实现模式（上传、提交、等待、下载流程）
  3. 编写 mock 测试
- **验收标准**:
  - [ ] 四个核心方法功能正确
  - [ ] 超时处理：`wait_for_completion` 支持 timeout 参数
  - [ ] 错误处理：ComfyUI 不可用时抛出明确异常
  - [ ] mock 测试通过
- **自测方法**: `uv run pytest tests/test_comfyui_client.py -v`
- **回滚方案**: 删除 comfyui_client.py 和测试
- **预估工作量**: M

---

#### [P2-08] 实现-发送端调用

- **阶段**: Phase 1 - 工作流拆分与语义压缩
- **依赖**: P2-05, P2-07
- **目标**: 封装发送端逻辑，通过 ComfyUI API 执行发送端工作流，输入原始图像，输出 Canny 边缘图
- **背景信息**: 发送端工作流（`sender_workflow_api.json`）接收原始图像，经过缩放和 Canny 边缘提取后输出边缘图。参数注入只需替换 LoadImage 节点的 `image` 字段为上传后的文件名。
- **涉及文件**:
  - `src/semantic_transmission/sender/comfyui_sender.py`（新建）
  - `tests/test_comfyui_sender.py`（新建）
- **具体步骤**:
  1. 实现 `ComfyUISender`：
     - 构造参数：`client: ComfyUIClient`、`workflow_path: str`（默认指向 `sender_workflow_api.json`）
     - `process(image_path: str) → PIL.Image`：加载图像 → 上传到 ComfyUI → 注入 LoadImage.image → 提交工作流 → 等待完成 → 获取输出边缘图
  2. 编写 mock 测试
- **验收标准**:
  - [ ] 能通过 ComfyUI API 获取 Canny 边缘图
  - [ ] 参数注入正确（LoadImage 节点的 image 字段）
  - [ ] mock 测试通过
- **自测方法**: `uv run pytest tests/test_comfyui_sender.py -v`
- **回滚方案**: 删除 comfyui_sender.py 和测试
- **预估工作量**: S

---

#### [P2-09] 实现-接收端调用

- **阶段**: Phase 1 - 工作流拆分与语义压缩
- **依赖**: P2-05, P2-07
- **目标**: 封装接收端逻辑，通过 ComfyUI API 执行接收端工作流，输入边缘图+prompt，输出还原图像
- **背景信息**: 接收端工作流（`receiver_workflow_api.json`）接收边缘图和文本 prompt，通过 Z-Image-Turbo + ControlNet Union 生成还原图像。参数注入需替换：LoadImage 节点的 `image`（边缘图文件名）、CLIPTextEncode 节点的 `text`（prompt 文本）、KSampler 节点的 `seed`（可选）。
- **涉及文件**:
  - `src/semantic_transmission/receiver/comfyui_receiver.py`（新建）
  - `tests/test_comfyui_receiver.py`（新建）
- **具体步骤**:
  1. 实现 `ComfyUIReceiver`：
     - 构造参数：`client: ComfyUIClient`、`workflow_path: str`（默认指向 `receiver_workflow_api.json`）
     - `process(edge_image: bytes | str, prompt_text: str, seed: int | None = None) → PIL.Image`：上传边缘图 → 注入 LoadImage.image + CLIPTextEncode.text + KSampler.seed → 提交工作流 → 等待完成 → 获取还原图像
  2. 编写 mock 测试
- **验收标准**:
  - [ ] 能通过 ComfyUI API 获取还原图像
  - [ ] 参数注入正确（LoadImage、CLIPTextEncode、KSampler 三个节点）
  - [ ] mock 测试通过
- **自测方法**: `uv run pytest tests/test_comfyui_receiver.py -v`
- **回滚方案**: 删除 comfyui_receiver.py 和测试
- **预估工作量**: S

---

#### [P2-16] 部署-本机 ComfyUI 实例

- **阶段**: Phase 1 - 工作流拆分与语义压缩
- **依赖**: P2-05
- **目标**: 在本机部署 ComfyUI 并加载项目所需的模型和自定义节点，使发送端/接收端工作流可通过 API 执行
- **背景信息**: 项目的发送端和接收端工作流（`resources/comfyui/sender_workflow_api.json` 和 `receiver_workflow_api.json`）需要 ComfyUI 实例运行。工作流使用了 4 个模型文件和若干自定义节点（如 `ModelPatchLoader`、`QwenImageDiffsynthControlnet`），需要从同事处获取或从源下载。ComfyUI 需以 `--listen` 模式启动以开放 API 端口。本机 GPU 显存需 ≥6GB（仅 ComfyUI 推理），后续 P2-13 VLM 集成时总需求 ≥24GB。
- **涉及文件**:
  - `docs/comfyui-setup.md`（新建：部署指南，记录模型来源、自定义节点安装步骤）
- **具体步骤**:
  1. 安装 ComfyUI（克隆仓库或使用便携版），确认 Python 环境和 PyTorch GPU 支持
  2. 下载/拷贝模型文件到 ComfyUI 对应目录：
     - `models/text_encoders/qwen_3_4b.safetensors`（CLIP text encoder，lumina2 格式）
     - `models/diffusion_models/z_image_turbo_bf16.safetensors`（Z-Image-Turbo 扩散模型）
     - `models/vae/ae.safetensors`（VAE）
     - `models/model_patches/Z-Image-Turbo-Fun-Controlnet-Union.safetensors`（ControlNet Union patch）
  3. 安装自定义节点（包含 `ModelPatchLoader`、`QwenImageDiffsynthControlnet`、`ImageScaleToMaxDimension` 等节点类型），来源需向同事确认
  4. 以 `--listen` 模式启动 ComfyUI：`python main.py --listen`
  5. 用已有脚本验证连通性：`uv run python scripts/test_comfyui_connection.py`
  6. 分别提交发送端和接收端工作流 JSON 验证执行成功
  7. 将部署步骤记录到 `docs/comfyui-setup.md`
- **验收标准**:
  - [ ] ComfyUI 以 `--listen` 模式启动，API 端口可访问
  - [ ] `scripts/test_comfyui_connection.py` 连通性测试通过
  - [ ] 发送端工作流提交后能输出 Canny 边缘图
  - [ ] 接收端工作流提交后能从边缘图 + prompt 生成还原图像
  - [ ] 部署步骤记录在 `docs/comfyui-setup.md` 中
- **自测方法**: `uv run python scripts/test_comfyui_connection.py --host 127.0.0.1 --port 8188`
- **回滚方案**: 卸载 ComfyUI，删除 `docs/comfyui-setup.md`
- **预估工作量**: L

---

#### [P2-10] 搭建-端到端 Demo 脚本

- **阶段**: Phase 1 - 工作流拆分与语义压缩
- **依赖**: P2-08, P2-09, P2-16
- **目标**: 编写可运行的 demo 脚本，演示 发送端→接收端 完整流程，支持手动 prompt 和 VLM 自动 prompt 双模式
- **背景信息**: Demo 脚本是 Phase 1 的核心交付物。单机模式下发送端和接收端连同一个 ComfyUI 实例。prompt 文本支持两种来源：(1) `--prompt` 手动指定（无 VLM 依赖，快速调试）；(2) `--auto-prompt` 调用 VLM 自动生成（需 P2-13 完成后可用）。
- **涉及文件**:
  - `scripts/demo_e2e.py`（新建）
- **具体步骤**:
  1. CLI 接口：`--image <输入图像> [--prompt <描述文本>] [--auto-prompt] [--sender-host ...] [--receiver-host ...] [--output-dir ...]`
  2. 流程：
     - 初始化 ComfyUIClient（发送端）和 ComfyUIClient（接收端）
     - ComfyUISender 提取 Canny 边缘图
     - 获取 prompt：手动指定（`--prompt`）或 VLM 生成（`--auto-prompt`，P2-13 完成后可用）
     - 保存边缘图到本地（模拟传输中间数据）
     - ComfyUIReceiver 从边缘图 + prompt 还原图像
     - 保存对比图（原图 | 边缘图 | 还原图）
  3. 打印传输统计：边缘图大小（bytes）+ prompt 文本大小（bytes）= 总传输数据量
- **验收标准**:
  - [x] `uv run python scripts/demo_e2e.py --help` 正常显示帮助
  - [ ] 在 ComfyUI 可用时，`--prompt` 模式能完成完整流程并输出对比图
  - [x] 支持 `--sender-host` 和 `--receiver-host` 分别指定地址
  - [x] `--auto-prompt` 参数定义就绪（实际 VLM 调用在 P2-13 中实现）
- **自测方法**: `uv run python scripts/demo_e2e.py --help`
- **回滚方案**: 删除 demo_e2e.py
- **预估工作量**: M

---

#### [P2-13] 集成-VLM 自动生成 prompt

- **阶段**: Phase 1 - 工作流拆分与语义压缩
- **依赖**: P2-10
- **目标**: 用 Qwen2.5-VL 自动生成图像语义描述，实现"自动语义压缩"核心能力，替代手动 prompt 输入
- **背景信息**: 语义传输的核心是"AI 自动理解图像内容并压缩为语义信息"。本任务实现 `QwenVLSender` 适配器（继承 P2-02 定义的 `BaseSender`），调用 Qwen2.5-VL-7B 模型对输入图像生成结构化文本描述。同事的 ComfyUI 工作流中已有分段式 prompt 模板（`[Scene Style]`、`[Perspective]`、`[Key Elements]` 等），VLM 需按此格式输出。硬件需求：GPU 显存 ≥24GB（VLM INT4 ~8GB + ComfyUI ~6GB 可同机运行）。
- **涉及文件**:
  - `src/semantic_transmission/sender/vlm_sender.py`（新建）
  - `tests/test_vlm_sender.py`（新建）
  - `pyproject.toml`（修改：添加 VLM 可选依赖组）
- **具体步骤**:
  1. 在 `pyproject.toml` 中添加 `[dependency-groups]` vlm 组：`transformers`、`torch`、`accelerate`
  2. 实现 `QwenVLSender(BaseSender)`：
     - 构造参数：模型名称（默认 `Qwen/Qwen2.5-VL-7B-Instruct`）、量化方式（默认 INT4）
     - `describe(image) → SenderOutput`：加载图像 → VLM 推理 → 返回结构化文本描述
     - system prompt 约束输出格式为分段式描述模板
  3. 集成到 `demo_e2e.py` 的 `--auto-prompt` 模式
  4. 编写 mock 测试（不需要真实 GPU）
- **验收标准**:
  - [x] `QwenVLSender` 实现 `BaseSender.describe()` 接口
  - [x] system prompt 约束 VLM 输出为分段式结构化描述
  - [x] `demo_e2e.py --auto-prompt` 能调用 VLM 自动生成 prompt 并完成端到端流程（6/6 张测试图通过）
  - [x] mock 测试通过（13 个）
  - [x] VLM 依赖在主依赖中，`uv sync` 直接安装（用户偏好，变更自原计划的可选组方案）
- **自测方法**: `uv run pytest tests/test_qwen_vl_sender.py -v`
- **回滚方案**: 删除 qwen_vl_sender.py 和测试，移除 pyproject.toml 中的 VLM 依赖
- **预估工作量**: L

---

### Phase 2: 中继传输与双机演示

#### [P2-11] 实现-中继传输协议

- **阶段**: Phase 2 - 中继传输与双机演示
- **依赖**: P2-10
- **目标**: 实现发送端到接收端的数据中继，支持本地传输和网络传输两种模式
- **背景信息**: Phase 1 的 demo 脚本在单进程内直接串联发送端和接收端。本任务将传输层独立出来，支持：(1) LocalRelay——内存传递，单机调试用；(2) SocketRelay——基于 TCP socket 的简单二进制传输，双机演示用。传输数据包含：边缘图（PNG 压缩）+ prompt 文本 + 元数据（时间戳、图像尺寸等）。
- **涉及文件**:
  - `src/semantic_transmission/pipeline/relay.py`（新建）
  - `tests/test_relay.py`（新建）
- **具体步骤**:
  1. 定义传输数据结构：`TransmissionPacket`（edge_image_bytes + prompt_text + metadata）
  2. 实现 `LocalRelay`：直接内存传递
  3. 实现 `SocketRelay`：TCP socket 二进制传输（length-prefixed framing）
  4. 编写单元测试
- **验收标准**:
  - [ ] LocalRelay 能正确传递数据
  - [ ] SocketRelay 能在 localhost 上完成传输
  - [ ] 测试通过
- **自测方法**: `uv run pytest tests/test_relay.py -v`
- **回滚方案**: 删除 relay.py 和测试
- **预估工作量**: M

---

#### [P2-12] 编写-双机演示脚本

- **阶段**: Phase 2 - 中继传输与双机演示
- **依赖**: P2-11
- **目标**: 编写分别运行在发送端机器和接收端机器上的独立脚本
- **背景信息**: 双机演示需要发送端和接收端作为独立进程运行，通过网络传输数据。发送端脚本负责：读取图像 → ComfyUI 提取边缘图 → 通过 SocketRelay 发送。接收端脚本负责：监听端口 → 接收数据 → ComfyUI 还原图像 → 保存结果。
- **涉及文件**:
  - `scripts/run_sender.py`（新建）
  - `scripts/run_receiver.py`（新建）
- **具体步骤**:
  1. `run_sender.py`：CLI 接收图像路径和 prompt → ComfyUI 提取边缘图 → SocketRelay 发送
  2. `run_receiver.py`：监听指定端口 → 接收 TransmissionPacket → ComfyUI 还原 → 保存结果
  3. 支持连续模式（持续监听）和单次模式
- **验收标准**:
  - [ ] 两个脚本分别运行在不同终端/机器上能完成完整流程
  - [ ] 支持 `--host` / `--port` 参数配置网络地址
- **自测方法**: 两个终端分别运行 sender 和 receiver
- **回滚方案**: 删除两个脚本
- **预估工作量**: M

---

### Phase 3: 质量优化

> **同事技术建议（2026-03-18）**：
> - **接收端模型选型约束**：接收端不是普通文生图，需要具备图片编辑功能或 ControlNet 参考能力，才能实现"基于上一帧 + 下一帧特征"的条件生成。当前推荐：Z-Image-Turbo（已在用）、FLUX.2-klein-9B（备选）
> - **条件特征扩展**：当前使用 Canny 边缘图作为条件输入，深度图（Depth Map）也是可选方案。边缘图保留轮廓、数据量小；深度图保留空间层次、对场景还原更有利。切换条件类型只需替换发送端提取节点和接收端 ControlNet preprocessor 类型

#### [P2-14] 实现-质量评估模块

- **阶段**: Phase 3 - 质量优化
- **依赖**: P2-10
- **目标**: 实现 CLIP Score、LPIPS、PSNR、SSIM 等质量评估指标
- **预估工作量**: M

---

#### ~~[P2-15] 脱离-ComfyUI 发送端~~ ❌ 已取消

- **取消原因**: 属于 ROADMAP 阶段四（工程化与脱离 ComfyUI）的范畴，不应在阶段二工作流中实施，留待阶段四独立规划
