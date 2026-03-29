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
| Phase 3 | 质量评估与文档重构 | 质量评估指标可计算；README 门户完成；开发指南、使用指南、项目总览三类文档各就位 |
| Phase 4 | CLI 正规化 | semantic-tx 命令可用；send/receive/demo/check/download 子命令功能等价于原脚本 |
| Phase 5 | GUI 开发 | semantic-tx gui 启动 Gradio 界面；覆盖配置/发送/接收/端到端四个面板 |
| Phase 6 | 修复与体验优化 | 已知问题全部修复；GUI/CLI 交互体验无明显缺陷；用户测试中发现的问题均已处理 |

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

### Phase 3: 质量评估与文档重构

> **同事技术建议（2026-03-18）**：
> - **接收端模型选型约束**：接收端不是普通文生图，需要具备图片编辑功能或 ControlNet 参考能力，才能实现"基于上一帧 + 下一帧特征"的条件生成。当前推荐：Z-Image-Turbo（已在用）、FLUX.2-klein-9B（备选）
> - **条件特征扩展**：当前使用 Canny 边缘图作为条件输入，深度图（Depth Map）也是可选方案。边缘图保留轮廓、数据量小；深度图保留空间层次、对场景还原更有利。切换条件类型只需替换发送端提取节点和接收端 ControlNet preprocessor 类型

#### [P2-14] 实现-质量评估模块

- **阶段**: Phase 3 - 质量评估与文档重构
- **依赖**: P2-10
- **目标**: 实现 CLIP Score、LPIPS、PSNR、SSIM 等质量评估指标
- **预估工作量**: M

---

#### ~~[P2-15] 脱离-ComfyUI 发送端~~ ❌ 已取消

- **取消原因**: 属于 ROADMAP 阶段四（工程化与脱离 ComfyUI）的范畴，不应在阶段二工作流中实施，留待阶段四独立规划

---

#### [P2-28] 编写-评估脚本与报告生成

- **阶段**: Phase 3 - 质量评估与文档重构
- **依赖**: P2-14
- **目标**: 编写评估脚本，调用 evaluation 模块批量计算质量指标并生成评估报告
- **背景信息**: P2-14 已实现 PSNR、SSIM、LPIPS、CLIP Score 四个质量评估函数（位于 `src/semantic_transmission/evaluation/`），但缺少实际运行指标的脚本。`output/demo/` 目录下有端到端测试的输出结果（原图、边缘图、还原图、prompt 文本），需要一个脚本批量处理这些结果，计算四类指标，输出结构化的评估报告。LPIPS 和 CLIP Score 涉及模型加载，脚本应支持模型复用以提升批量评估性能。
- **涉及文件**:
  - `scripts/evaluate.py`（新建：评估脚本，批量处理 + 报告生成）
  - `tests/test_evaluate_script.py`（新建：脚本参数解析和输出格式测试）
- **具体步骤**:
  1. 创建 `scripts/evaluate.py`，接受输入目录（含原图、还原图、prompt）和输出路径
  2. 实现批量模式：遍历目录下所有测试样本，逐一计算 PSNR、SSIM、LPIPS、CLIP Score
  3. 对 LPIPS 和 CLIP Score 的模型做复用（加载一次，多次调用），避免重复初始化
  4. 输出结构化评估报告（终端表格 + JSON/CSV 文件），包含每张图的四项指标和汇总统计（均值、标准差）
  5. 支持 `--device` 参数（cuda/cpu）加速 LPIPS 和 CLIP Score
  6. 编写测试验证参数解析和输出格式
- **验收标准**:
  - [ ] `uv run python scripts/evaluate.py --help` 正常显示帮助
  - [ ] 给定测试目录，能正确计算四类指标
  - [ ] 输出包含每张图的详细指标和汇总统计
  - [ ] LPIPS/CLIP 模型仅加载一次
  - [ ] ruff check / format 通过
  - [ ] 全量测试无回归
- **自测方法**: `uv run python scripts/evaluate.py --input output/demo/round-03/ --output output/evaluation/`，检查输出报告内容
- **回滚方案**: 删除 `scripts/evaluate.py` 和 `tests/test_evaluate_script.py`
- **预估工作量**: M

---

#### [P2-17] 重构-README 为文档门户

- **阶段**: Phase 3 - 质量评估与文档重构
- **依赖**: 无
- **目标**: 将根 README.md 重构为面向所有受众的导航中枢，精简正文、补充文档索引
- **背景信息**: 当前 README.md 143 行，以开发者视角为主，缺少按受众分类的文档导航。docs/ 下 41 个文件分散在 6 个子目录，无统一索引。需要将 README 定位为"项目门户"，保留核心信息（架构图、快速开始），增加按受众分层的文档导航表。
- **涉及文件**:
  - `README.md`（修改）
  - `docs/README.md`（新建 — 文档总索引）
- **具体步骤**:
  1. 精简 README.md：保留项目简介、架构图、快速开始（安装+部署+验证），移除冗余细节
  2. 增加"文档导航"章节，按三类受众（开发者、用户、项目负责人）列出入口链接
  3. 新建 `docs/README.md` 作为文档总索引，列出所有文档及简要说明
  4. 确保所有链接有效
- **验收标准**:
  - [ ] README.md 包含文档导航章节，指向三类受众入口
  - [ ] `docs/README.md` 列出全部文档的分类索引
  - [ ] 所有内部链接可达
- **自测方法**: 手动检查每个链接的目标文件存在
- **回滚方案**: git restore README.md，删除 docs/README.md
- **预估工作量**: S

---

#### [P2-18] 编写-开发指南

- **阶段**: Phase 3 - 质量评估与文档重构
- **依赖**: 无
- **目标**: 编写面向开发者的完整开发指南，涵盖架构说明、环境搭建、测试规范、贡献流程
- **背景信息**: 开发相关信息分散在 CLAUDE.md（命令速查）、README.md（快速开始）、`docs/collaboration/`（Git 协作规范）多处。架构详解（源码模块关系、数据流、扩展点）完全缺失。需要一份整合文档，含架构图（Mermaid）。
- **涉及文件**:
  - `docs/development-guide.md`（新建）
  - `docs/architecture.md`（新建）
- **具体步骤**:
  1. 编写 `docs/development-guide.md`：环境要求、依赖安装、项目结构说明、开发工作流（分支/测试/CI）、代码规范（ruff）
  2. 编写 `docs/architecture.md`：模块关系图（Mermaid）、核心数据流（sender→relay→receiver）、ComfyUI 客户端调用流程、抽象接口设计、扩展点说明
- **验收标准**:
  - [ ] 开发指南覆盖：环境搭建、项目结构、测试方法、CI 说明、编码规范
  - [ ] 架构文档包含至少 2 个 Mermaid 图（模块关系、数据流）
  - [ ] 新开发者可仅凭文档完成环境搭建和首次测试
- **自测方法**: 按文档步骤操作验证流程可行
- **回滚方案**: 删除两个新建文件
- **预估工作量**: M

---

#### [P2-19] 编写-使用指南与演示手册

- **阶段**: Phase 3 - 质量评估与文档重构
- **依赖**: 无
- **目标**: 编写面向用户的操作手册，覆盖单机演示和双机演示的完整步骤
- **背景信息**: 脚本用法仅在脚本 docstring 中简要说明，缺少完整操作手册。用户需要从零开始的演示步骤，包括前置环境准备、ComfyUI 启动、各脚本的参数说明和示例。双机演示尤其需要网络配置说明。
- **涉及文件**:
  - `docs/user-guide.md`（新建）
  - `docs/demo-handbook.md`（新建）
- **具体步骤**:
  1. 编写 `docs/user-guide.md`：系统要求、ComfyUI 安装（引用 comfyui-setup.md）、模型下载、项目安装、基本使用流程
  2. 编写 `docs/demo-handbook.md`：单机端到端演示（完整操作步骤+参数说明）、双机演示（各端启动步骤、网络配置、防火墙注意事项）、常见错误与排查
  3. 每个命令附参数表格和示例
- **验收标准**:
  - [ ] 用户指南覆盖完整安装流程
  - [ ] 演示手册包含单机和双机两种模式的逐步操作说明
  - [ ] 每个命令都有参数表格和示例
- **自测方法**: 按手册步骤操作一遍验证流程
- **回滚方案**: 删除两个新建文件
- **预估工作量**: M

---

#### [P2-20] 编写-项目总览与进度摘要

- **阶段**: Phase 3 - 质量评估与文档重构
- **依赖**: 无
- **目标**: 编写面向项目负责人的项目总览，概括目标、技术路线、进展、关键成果
- **背景信息**: 负责人需要快速了解项目状态，不需要代码细节。ROADMAP.md 偏技术路线，缺少可快速浏览的进度摘要和关键成果展示。
- **涉及文件**:
  - `docs/project-overview.md`（新建）
  - `docs/ROADMAP.md`（修改 — 更新完成状态，补充新阶段）
- **具体步骤**:
  1. 编写 `docs/project-overview.md`：项目目标与愿景、技术路线（精简架构图）、阶段进展汇总表、关键成果、后续计划与风险
  2. 更新 ROADMAP.md：补充阶段二完成标记，添加新增阶段内容
- **验收标准**:
  - [ ] 项目总览可在 2 分钟内读完
  - [ ] ROADMAP 与实际进展同步
  - [ ] 包含进度汇总表
- **自测方法**: 检查文档内容与 TASK_STATUS.md 一致
- **回滚方案**: 删除 project-overview.md，git restore ROADMAP.md
- **预估工作量**: S

---

### Phase 4: CLI 正规化

#### [P2-21] 注册-CLI 入口与基础框架

- **阶段**: Phase 4 - CLI 正规化
- **依赖**: 无
- **目标**: 在 pyproject.toml 注册 `semantic-tx` CLI 入口点，搭建 click 子命令框架
- **背景信息**: 当前 6 个脚本通过 `uv run python scripts/xxx.py` 调用，没有统一入口。需要注册 `[project.scripts]` 入口点，使用 click 构建子命令体系（click 比 argparse 子命令支持更好、帮助文档自动生成更完善）。
- **涉及文件**:
  - `pyproject.toml`（修改 — 添加 click 依赖 + scripts 入口）
  - `src/semantic_transmission/cli/__init__.py`（新建）
  - `src/semantic_transmission/cli/main.py`（新建）
- **具体步骤**:
  1. 在 pyproject.toml dependencies 中添加 `click>=8.0`
  2. 在 `[project.scripts]` 中注册 `semantic-tx = "semantic_transmission.cli.main:cli"`
  3. 创建 `src/semantic_transmission/cli/` 包
  4. 在 `cli/main.py` 中实现 click Group 主入口（`--version`、帮助信息、子命令占位）
  5. 运行 `uv sync` 确认入口点注册成功
- **验收标准**:
  - [ ] `uv run semantic-tx --help` 输出子命令列表
  - [ ] `uv run semantic-tx --version` 输出版本号
  - [ ] click 依赖已添加到 pyproject.toml
- **自测方法**: `uv sync && uv run semantic-tx --help`
- **回滚方案**: 还原 pyproject.toml，删除 cli/ 目录
- **预估工作量**: S

---

#### [P2-22] 实现-CLI 核心子命令（send/receive/demo）

- **阶段**: Phase 4 - CLI 正规化
- **依赖**: P2-21
- **目标**: 将 demo_e2e.py、run_sender.py、run_receiver.py 的功能迁移为 CLI 子命令
- **背景信息**: 三个脚本各自使用 argparse 解析参数。需将参数迁移为 click 选项，核心业务逻辑保持不变，仅替换 CLI 入口层。原脚本保留但添加废弃提示。
- **涉及文件**:
  - `src/semantic_transmission/cli/main.py`（修改）
  - `src/semantic_transmission/cli/send.py`（新建）
  - `src/semantic_transmission/cli/receive.py`（新建）
  - `src/semantic_transmission/cli/demo.py`（新建）
  - `scripts/demo_e2e.py`（修改 — 添加废弃提示）
  - `scripts/run_sender.py`（修改 — 添加废弃提示）
  - `scripts/run_receiver.py`（修改 — 添加废弃提示）
- **具体步骤**:
  1. 创建 `cli/send.py`：将 run_sender.py 的 argparse 参数转为 click 选项，复用业务逻辑
  2. 创建 `cli/receive.py`：迁移 run_receiver.py
  3. 创建 `cli/demo.py`：迁移 demo_e2e.py
  4. 在 main.py 中注册三个子命令
  5. 原脚本 `__main__` 中添加打印提示：建议使用 `semantic-tx send/receive/demo`
- **验收标准**:
  - [ ] `semantic-tx send/receive/demo --help` 各显示与原脚本等价的参数
  - [ ] 三个子命令功能与原脚本一致
- **自测方法**: 分别运行三个子命令的 `--help`，确认参数完整
- **回滚方案**: 删除新建文件，还原 main.py 和三个脚本
- **预估工作量**: M

---

#### [P2-23] 实现-CLI 工具子命令（check/download）

- **阶段**: Phase 4 - CLI 正规化
- **依赖**: P2-21
- **目标**: 将 test_comfyui_connection.py、verify_workflows.py、download_models.py 迁移为 CLI 子命令
- **背景信息**: check 子命令合并连通性测试和工作流验证（`semantic-tx check connection` / `semantic-tx check workflows`），download 子命令迁移模型下载功能。
- **涉及文件**:
  - `src/semantic_transmission/cli/main.py`（修改）
  - `src/semantic_transmission/cli/check.py`（新建）
  - `src/semantic_transmission/cli/download.py`（新建）
  - `scripts/test_comfyui_connection.py`（修改 — 添加废弃提示）
  - `scripts/verify_workflows.py`（修改 — 添加废弃提示）
  - `scripts/download_models.py`（修改 — 添加废弃提示）
- **具体步骤**:
  1. 创建 `cli/check.py`：click Group 含 `connection` 和 `workflows` 两个子命令
  2. 创建 `cli/download.py`：迁移 download_models.py 参数（--hf-mirror, --proxy, --dry-run 等）
  3. 在 main.py 中注册 check 和 download 子命令
  4. 原脚本添加废弃提示
- **验收标准**:
  - [ ] `semantic-tx check connection/workflows` 等价于原脚本
  - [ ] `semantic-tx download --help` 显示完整参数
- **自测方法**: 运行各子命令的 `--help` 确认参数完整
- **回滚方案**: 删除新建文件，还原 main.py 和三个脚本
- **预估工作量**: M

---

#### [P2-24] 编写-CLI 参考文档与测试

- **阶段**: Phase 4 - CLI 正规化
- **依赖**: P2-22, P2-23
- **目标**: 编写 CLI 完整参考文档，补充集成测试
- **背景信息**: CLI 实现后需要完整的参考文档和基本测试确保入口点注册正确、子命令可发现。
- **涉及文件**:
  - `docs/cli-reference.md`（新建）
  - `tests/test_cli.py`（新建）
- **具体步骤**:
  1. 编写 `docs/cli-reference.md`：命令总览表、每个子命令的参数表格+示例
  2. 编写 `tests/test_cli.py`：使用 click.testing.CliRunner 测试各子命令 `--help` 和参数解析
  3. 更新 README.md 文档导航中的 CLI 参考链接
- **验收标准**:
  - [ ] CLI 参考文档覆盖所有子命令
  - [ ] 每个子命令至少 1 个 CliRunner 测试
  - [ ] `uv run pytest tests/test_cli.py` 通过
- **自测方法**: `uv run pytest tests/test_cli.py -v`
- **回滚方案**: 删除两个新建文件
- **预估工作量**: M

---

### Phase 5: GUI 开发

#### [P2-25] 搭建-Gradio GUI 基础框架与配置面板

- **阶段**: Phase 5 - GUI 开发
- **依赖**: P2-21
- **目标**: 搭建 Gradio GUI 基础框架，实现配置面板和 `semantic-tx gui` 启动入口
- **背景信息**: 项目完全没有 GUI。Gradio 是 Python 原生 AI Demo 框架，适合本项目的展示需求。通过 `semantic-tx gui` 启动。首先实现配置面板（ComfyUI 地址、VLM 模型路径的可视化配置和连通性测试）。
- **涉及文件**:
  - `pyproject.toml`（修改 — 添加 gradio 依赖）
  - `src/semantic_transmission/gui/__init__.py`（新建）
  - `src/semantic_transmission/gui/app.py`（新建）
  - `src/semantic_transmission/gui/config_panel.py`（新建）
  - `src/semantic_transmission/cli/main.py`（修改 — 实现 gui 子命令）
- **具体步骤**:
  1. 在 pyproject.toml 添加 `gradio>=4.0` 依赖
  2. 创建 `gui/app.py`：Gradio Blocks 主界面，Tabs 组织多面板
  3. 实现 `gui/config_panel.py`：ComfyUI 地址输入、VLM 路径配置、"测试连接"按钮、状态显示
  4. 在 cli/main.py 的 gui 子命令中调用 `app.launch()`，支持 `--port`/`--share`
- **验收标准**:
  - [ ] `uv run semantic-tx gui` 启动 Gradio 界面
  - [ ] 配置面板可输入 ComfyUI 地址并测试连接
  - [ ] 界面包含 Tabs 结构（配置/发送端/接收端/端到端 — 后三个暂为占位）
- **自测方法**: 启动 GUI，在配置面板中输入地址并测试连接
- **回滚方案**: 还原 pyproject.toml 和 cli/main.py，删除 gui/ 目录
- **预估工作量**: M

---

#### [P2-26] 实现-GUI 发送端与接收端视图

- **阶段**: Phase 5 - GUI 开发
- **依赖**: P2-25
- **目标**: 实现 GUI 的发送端和接收端标签页
- **背景信息**: 发送端视图：上传图片 → 提取 Canny 边缘图 + VLM 语义描述。接收端视图：输入 prompt + 边缘图 → 还原图像并对比。两个面板调用现有的 ComfyUISender 和 ComfyUIReceiver 业务逻辑。
- **涉及文件**:
  - `src/semantic_transmission/gui/sender_panel.py`（新建）
  - `src/semantic_transmission/gui/receiver_panel.py`（新建）
  - `src/semantic_transmission/gui/app.py`（修改 — 集成新面板）
- **具体步骤**:
  1. 实现 `gui/sender_panel.py`：图片上传、prompt 模式选择（手动/自动）、"提取"按钮、结果展示（边缘图+prompt 文本）
  2. 实现 `gui/receiver_panel.py`：边缘图上传、prompt 输入、"还原"按钮、还原结果+对比
  3. 在 app.py 中注册到对应 Tab
- **验收标准**:
  - [ ] 发送端面板：上传图片后可提取边缘图和语义描述
  - [ ] 接收端面板：输入边缘图和 prompt 后可还原图像
  - [ ] 处理过程中有进度提示
- **自测方法**: 启动 GUI，在两个面板分别完成操作
- **回滚方案**: 删除两个新建文件，还原 app.py
- **预估工作量**: M

---

#### [P2-27] 实现-GUI 端到端模式与日志面板

- **阶段**: Phase 5 - GUI 开发
- **依赖**: P2-26
- **目标**: 实现一键端到端演示和实时日志面板
- **背景信息**: 端到端模式：上传图片 → 一键完成"边缘提取→语义描述→还原→对比"全流程。日志面板：显示 API 调用过程、耗时统计、错误信息。
- **涉及文件**:
  - `src/semantic_transmission/gui/pipeline_panel.py`（新建）
  - `src/semantic_transmission/gui/app.py`（修改 — 集成 Pipeline Tab）
- **具体步骤**:
  1. 实现 `gui/pipeline_panel.py`：图片上传 + prompt 模式 → "一键演示" → 展示中间结果 → 最终对比
  2. 添加实时日志区域（Textbox streaming）
  3. 添加耗时统计（发送端/接收端/总耗时）
  4. 在 app.py 中注册 Pipeline Tab
- **验收标准**:
  - [ ] 一键演示可完成端到端流程
  - [ ] 界面展示中间结果和最终对比
  - [ ] 日志区域显示处理过程信息
- **自测方法**: 启动 GUI，上传图片完成端到端演示
- **回滚方案**: 删除 pipeline_panel.py，还原 app.py
- **预估工作量**: M

---

### Phase 6: 修复与体验优化

#### [P2-29] 修复-GUI 已知体验问题

- **阶段**: Phase 6 - 修复与体验优化
- **依赖**: P2-26
- **目标**: 批量修复双端 GUI 测试中发现的已知体验问题
- **背景信息**: Phase 5 完成后进行双端 GUI 测试，发现以下问题（完整列表见 TASK_STATUS.md「已知问题」章节）：
  1. **seed=0 误判为未设置**：`receiver_panel.py` 和 `pipeline_panel.py` 中 `if seed` 对 `0` 求值为 `False`，导致用户输入 `0` 时回退到工作流硬编码种子。应改为 `is not None` 判断。
  2. **Radio 圆点指示器冗余**：描述模式 Radio 组件选中项已有蓝色背景，圆点（●）视觉多余。需通过 CSS 隐藏，仅靠颜色区分。
  3. **接收端输出区重复显示边缘图**：输出区左侧"边缘图（输入）"echo 与上方输入区完全相同，视觉冗余。但简单移除会导致布局失衡，需重新设计输出区布局。
  后续测试中发现的新问题将追加到已知问题列表，执行时一并处理。
- **涉及文件**:
  - `src/semantic_transmission/gui/receiver_panel.py`（修改 — 修复 seed 判断逻辑）
  - `src/semantic_transmission/gui/pipeline_panel.py`（修改 — 同步修复 seed 判断逻辑）
  - `src/semantic_transmission/gui/theme.py`（修改 — CSS 隐藏 Radio 圆点）
- **具体步骤**:
  1. 修复 seed 判断：将 `int(seed) if seed else None` 改为正确的 None 判断，receiver_panel 和 pipeline_panel 同步修改
  2. 调整 seed 输入框默认行为：默认留空或随机，使行为符合直觉
  3. 确认 Gradio 版本对应的 Radio 组件 CSS 选择器，添加隐藏圆点的样式
  4. 逐项处理已知问题列表中的其他条目（如有新增）
  5. 启动 GUI 完整验证所有修复项
- **验收标准**:
  - [ ] seed=0 被正确传递给 ComfyUI
  - [ ] seed 输入框默认行为明确且符合直觉
  - [ ] Radio 选中项无圆点，仅通过背景色区分
  - [ ] TASK_STATUS.md「已知问题」章节中所有条目均已处理
  - [ ] `uv run ruff check .` 和 `uv run ruff format --check .` 通过
- **自测方法**: 启动 GUI 逐项验证每个修复项；seed 测试 0/42/留空三种情况
- **回滚方案**: `git checkout -- src/semantic_transmission/gui/receiver_panel.py src/semantic_transmission/gui/pipeline_panel.py src/semantic_transmission/gui/theme.py`
- **预估工作量**: M
