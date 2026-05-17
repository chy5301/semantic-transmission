# 任务状态跟踪

> 创建时间: 2026-04-12
> Workflow: unify-config-and-loader
> 任务类型: refactor + bugfix + infrastructure
> 任务前缀: R

## 进度总览

| 阶段 | 总数 | 完成 | 进行中 | 待开始 |
|------|------|------|--------|--------|
| Phase 0: 基础设施 | 2 | 2 | 0 | 0 |
| Phase 1: receiver 侧垂直切 | 4 | 4 | 0 | 0 |
| Phase 2: sender/CLI 侧垂直切 | 3 | 3 | 0 | 0 |
| Phase 3: GUI 侧垂直切 | 2 | 0 | 0 | 2 |
| Phase 4: cleanup + 收尾 | 3 | 0 | 0 | 3 |
| **合计** | **14** | **9** | **0** | **5** |

## 任务状态

| 编号 | 标题 | 阶段 | 状态 | 依赖 |
|------|------|------|------|------|
| R-01 | 创建-ProjectConfig 与 config.toml 体系 | Phase 0 | ✅ | 无 |
| R-02 | 创建-ModelLoader 抽象基类 | Phase 0 | ✅ | 无 |
| R-03 | 实现-DiffusersModelLoader | Phase 1 | ✅ | R-01, R-02 |
| R-04 | 迁移-DiffusersReceiver + 动态尺寸 #24 | Phase 1 | ✅ | R-03 |
| R-05 | 简化-BaseReceiver.process_batch #31 | Phase 1 | ✅ | R-04 |
| R-06 | 对齐-采样器参数 #25 | Phase 1 | ✅ | R-04 |
| R-07 | 实现-QwenVLModelLoader + 迁移 QwenVLSender | Phase 2 | ✅ | R-02 |
| R-08 | 合并-CLI sender/batch_sender #19 | Phase 2 | ✅ | R-01, R-07 |
| R-09 | 重构-download.py + 迁移 demo/batch_demo CLI | Phase 2 | ✅ | R-01, R-08 |
| R-10 | 修复-GUI 面板生命周期 #23 | Phase 3 | ⬜ | R-04, R-07 |
| R-11 | 迁移-GUI 面板读 ProjectConfig 默认值 | Phase 3 | ⬜ | R-01, R-10 |
| R-12 | 创建-load_as_rgb + 替换 core 模块 #22 | Phase 4 | ⬜ | R-04, R-07 |
| R-13 | 替换-CLI + GUI 模块 RGB 散落 #22 续 | Phase 4 | ⬜ | R-12 |
| R-14 | 删除-LocalRelay #33 + 文档更新 + issue 关闭 | Phase 4 | ⬜ | R-08, R-13 |

状态图例: ⬜ 待开始 | 🔄 进行中 | ✅ 已完成 | ⏸️ 暂停 | ❌ 已取消 | 🔀 已拆分

## 已知问题

（执行过程中发现的问题记录在此）

## 决策日志

| 日期 | 决策 | 原因 |
|------|------|------|
| 2026-04-11 | 选定 L3 深切片（#20 + #21 捆绑） | 两者耦合度高，只做其中一个改动面不减 |
| 2026-04-11 | 按模块垂直切（非架构优先/P0优先） | 每模块改完即稳定，任一 phase 断点可合并 |
| 2026-04-11 | CLI 不保留旧 batch_sender 子命令 | 预研阶段无外部用户 |
| 2026-04-11 | --image 和 --input-dir 保留差异化输出 | 两种心智（快测 vs 数据集），行为可预测 |
| 2026-04-11 | config.toml 扩展集（模型+推理+路径） | 覆盖 ModelLoader 和 CLI 两层需求 |
| 2026-04-11 | ModelLoader 不直接依赖 ProjectConfig | 用 dataclass 子集解耦，config 变 loader 不动 |
| 2026-04-11 | tomllib + 手写 dataclass（不引 pydantic） | stdlib 零依赖成本 |
| 2026-04-11 | 不走 docs/superpowers/ 独立 spec | 与 structured-workflow 合并单一路径，避免两套文档 |
| 2026-04-12 | guidance_scale/steps 默认值待 R-06 实验确定 | 代码分析发现当前值 1.0/9 vs seed 建议 3.5/20 差异大 |
| 2026-04-12 | R-05/R-06 编号互换（原 R-06→R-05, 原 R-05→R-06） | process_batch 审计是确定性工作先做，采样器对齐是实验性任务后做 |
| 2026-04-12 | requires-python 提升到 >=3.12 | 预研项目+CI 3.12+本地 3.12，直接用 stdlib tomllib |
| 2026-04-12 | Phase 0 阶段回顾通过 | 审计无 🔴/🟡 发现，205 passed，退出标准全满足 |
| 2026-04-12 | R-05 process_batch 审计结论：保留不合并 | base.py 和 CLI batch_demo 职责不同，合并时机在 R-08 |
| 2026-04-13 | scheduler_shift=3.0 作为初始值，后续可调 | ComfyUI 基线 AuraFlow shift=3，res_multistep/simple 无需对齐 |
| 2026-04-13 | 尺寸对齐到 16 的倍数 | pipeline 要求 height/width 必须是 16 的倍数 |
| 2026-04-13 | config.toml 新增 hf_endpoint | 解决 HF 下载在国内需镜像站的持久化配置问题 |
| 2026-04-14 | Phase 1 阶段回顾通过 | 审计无 🔴/🟡 发现，214 passed，退出标准全满足，后续阶段无需调整 |
| 2026-05-17 | Phase 2 阶段回顾通过 | 审计无 🔴/🟡 发现，241 passed，退出标准 3 项 PASS + 1 项 PARTIAL（真机 GPU 端到端未跑），3 条 🔵 建议已合并到 R-11/R-13/R-14 |

## 交接记录

### R-01 交接（2026-04-12）

**完成内容**：建立 `ProjectConfig` frozen dataclass + `load_config()` 加载器 + `config.toml` 默认配置文件，实现 4 层配置优先级（代码默认 < config.toml < config.local.toml < 环境变量）。

**修改的文件**：
- `src/semantic_transmission/common/config.py` — 新增 `ProjectConfig`、`load_config()`、环境变量展开工具函数；修复 `from_env()` 兼容 `from __future__ import annotations`
- `config.toml` — 新建，仓库根，当前代码实际默认值
- `.gitignore` — 新增 `config.local.toml`
- `tests/test_project_config.py` — 新建，10 个测试用例覆盖默认值/toml 加载/local 覆盖/环境变量展开
- `pyproject.toml` — `requires-python` 从 `>=3.10` 提升到 `>=3.12`（用 stdlib tomllib）

**验证结果**：198 passed / ruff check + format 全绿

**关键决策**：
- `requires-python` 提升到 `>=3.12`：预研项目、CI 3.12、团队均 3.12+，直接用 stdlib tomllib
- `config.toml` 的 inference 默认值用当前代码实际值（`guidance_scale=1.0`, `steps=9`），待 R-06 实验后更新
- `DiffusersReceiverConfig.from_env()` 修复：加了 `from __future__ import annotations` 后 `f.type` 变字符串，改用 `_TYPE_MAP` 字符串查找

**下一任务**：R-02 创建 ModelLoader 抽象基类（无依赖，可直接开始）

**遗留问题**：无

---

### R-02 交接（2026-04-12）

**完成内容**：创建 `ModelLoader(ABC, Generic[TModel])` 抽象基类，定义统一的模型生命周期接口。

**修改的文件**：
- `src/semantic_transmission/common/model_loader.py` — 新建，`ModelLoader` ABC + `session()` context manager
- `tests/test_model_loader.py` — 新建，7 个测试用例覆盖 load/unload/is_loaded/session 正常+异常路径

**验证结果**：7 passed / ruff 全绿

**关键决策**：无

**下一任务**：R-03 实现 DiffusersModelLoader（依赖 R-01 ✅ + R-02 ✅，可开始）

**遗留问题**：无

---

### R-03 交接（2026-04-12）

**完成内容**：实现 `DiffusersModelLoader(ModelLoader)`，封装 GGUF transformer + ControlNet + base pipeline 分组件加载；新增 `DiffusersLoaderConfig` frozen dataclass 及 `ProjectConfig.to_diffusers_loader_config()` 派生方法。

**修改的文件**：
- `src/semantic_transmission/common/model_loader.py` — 新增 `DiffusersModelLoader` 类 + `TORCH_DTYPE_MAP` 常量
- `src/semantic_transmission/common/config.py` — 新增 `DiffusersLoaderConfig` dataclass + `ProjectConfig.to_diffusers_loader_config()`
- `tests/test_model_loader.py` — 新增 5 个 DiffusersModelLoader mock 测试

**验证结果**：22 passed / ruff 全绿

**关键决策**：
- `TORCH_DTYPE_MAP` 从 `diffusers_receiver.py` 提升到 `model_loader.py` 公共位置（R-04 迁移 receiver 时会从此处引用）

**下一任务**：R-04 迁移 DiffusersReceiver 使用 ModelLoader + 修复动态尺寸 #24

**遗留问题**：无

---

### R-04 交接（2026-04-12）

**完成内容**：DiffusersReceiver 改为持有 DiffusersModelLoader 委托加载，process() 从 control_image 读取 H/W 动态传入 pipeline（修复 #24）。

**修改的文件**：
- `src/semantic_transmission/receiver/diffusers_receiver.py` — 重写：委托 `_loader` 管理生命周期，`process()` 传 `height`/`width`
- `src/semantic_transmission/receiver/__init__.py` — `create_receiver()` 新增 `loader` 参数
- `tests/test_diffusers_receiver.py` — 适配 loader 结构，新增 `test_passes_height_width` 和 `test_portrait_image_dimensions`

**验证结果**：212 passed / ruff 全绿

**关键决策**：
- `DiffusersReceiver.__init__` 同时支持旧 `config` 参数和新 `loader` 参数，保持向后兼容
- 不传 `loader` 时从 `config` 字段自动构造 `DiffusersLoaderConfig` → `DiffusersModelLoader`
- PIL `Image.size` 返回 `(W, H)`，传给 pipeline 时 `height=size[1], width=size[0]`

**下一任务**：R-05 简化 BaseReceiver.process_batch 循环（依赖 R-04 ✅）

**遗留问题**：
- 竖版图本地 RTX 5090 逼眼验证待 Phase 1 阶段检查点时执行

---

### R-05 交接（2026-04-12）

**完成内容**：审计 `BaseReceiver.process_batch()` 与 CLI `batch_demo.py` 的循环关系，结论为两者职责不同，无需合并。

**审计发现**：
- `base.py:process_batch()` 是纯 receiver 批量处理（逐帧调 `self.process()`），被 GUI `receiver_panel` 使用
- `batch_demo.py` 是端到端 demo 管道（sender + receiver 串联 + 对比图 + 保存），逻辑完全不同
- 真正的 CLI 重复（4 个命令共享 options）属于 R-08 Phase 2 范围

**修改的文件**：无代码变更（reviewed, no change needed）

**验证结果**：N/A（无代码变更）

**关键决策**：
- `BaseReceiver.process_batch()` 保留现有实现，不与 CLI 批量逻辑合并

**下一任务**：R-06 对齐采样器参数（本次执行范围限制不包含 R-06）

**遗留问题**：无

---

### R-06 交接（2026-04-13）

**完成内容**：对齐 Diffusers 采样器参数与 ComfyUI 基线。新增 `scheduler_shift=3.0` 配置，pipeline 加载后调用 `set_shift()`。修复尺寸对齐到 16 倍数。新增 `hf_endpoint` 配置解决镜像站持久化。CLI 入口触发 `load_config()` 注入环境变量。端到端 demo 跑通。

**修改的文件**：
- `src/semantic_transmission/common/config.py` — `ProjectConfig`/`DiffusersReceiverConfig`/`DiffusersLoaderConfig` 新增 `scheduler_shift` 字段；新增 `hf_endpoint` 字段 + 环境变量注入；`to_diffusers_loader_config()` 传 shift；`_TOML_FIELD_MAP` 新增映射
- `src/semantic_transmission/common/model_loader.py` — `load()` 末尾调 `scheduler.set_shift()`
- `src/semantic_transmission/receiver/diffusers_receiver.py` — 构造 loader 时传 `scheduler_shift`；尺寸对齐到 16 倍数
- `src/semantic_transmission/cli/main.py` — CLI 根命令调 `load_config()` 触发环境变量注入
- `config.toml` — `[inference]` 新增 `scheduler_shift=3.0`；`[paths]` 新增 `hf_endpoint`
- `tests/test_model_loader.py` — 新增 scheduler shift 验证测试
- `tests/test_diffusers_receiver.py` — 更新尺寸测试适配 16 倍数对齐，新增 `test_non_aligned_dimensions`

**验证结果**：214 passed / ruff 全绿 / 端到端 demo 跑通（canyon_jeep.jpg，shift=3.0，9 步，55.2s）

**关键决策**：
- `scheduler_shift=3.0` 作为初始值，映射自 ComfyUI 的 `ModelSamplingAuraFlow(shift=3)`
- `res_multistep` sampler 在 diffusers 中无等价，使用默认 Euler step
- `simple` scheduler 已是 `FlowMatchEulerDiscreteScheduler` 默认行为
- 尺寸向下对齐到 16 倍数（`w - w % 16`）
- `hf_endpoint` 注入 `os.environ["HF_ENDPOINT"]`，解决 HF 镜像站持久化（超出 R-06 原始范围，但阻塞了 demo 测试）

**下一任务**：R-07 实现 QwenVLModelLoader + 迁移 QwenVLSender（Phase 2）

**遗留问题**：
- shift=3.0 的生成质量待用户后续逼眼对比确认，可能需要调参
- `HF_HUB_DISABLE_XET=1` 环境变量需持久化（hf-mirror 不支持 xet CDN）

---

### R-07 交接（2026-05-17）

**完成内容**：新增 `QwenVLModelLoader(ModelLoader[QwenVLBundle])` 封装 Qwen2.5-VL 模型加载与量化 cascade（torchao → bitsandbytes → float16），新增 `VLMLoaderConfig` frozen dataclass 与 `ProjectConfig.to_vlm_loader_config()` 派生方法；`QwenVLSender` 改为持有 loader 实例并通过 `loader.load()` 获取 model/processor，移除原 `_load_model()` 私有方法。

**修改的文件**：
- `src/semantic_transmission/common/config.py` — 新增 `VLMLoaderConfig` dataclass + `ProjectConfig.to_vlm_loader_config()` 派生方法
- `src/semantic_transmission/common/model_loader.py` — 新增 `QwenVLBundle` dataclass + `QwenVLModelLoader` 类（保留 cascade 顺序与回退逻辑）
- `src/semantic_transmission/sender/qwen_vl_sender.py` — 重构：`__init__` 双入口（loader= 或 kwargs），`describe()` 委托 `loader.load()`，新增 `is_loaded` 属性，删除 `_load_model()`
- `tests/test_model_loader.py` — 新增 11 个 QwenVLModelLoader/VLMLoaderConfig 测试（cascade 回退、idempotent、unload、session、ProjectConfig 派生）
- `tests/test_qwen_vl_sender.py` — 适配 loader 结构，新增 `test_accepts_loader_directly` 等用例

**验证结果**：
- 编译: ✅ `uv sync` 完成（venv 由 R-06 后被重建为空，本次 sync 拉满 3.6G 依赖）
- 测试: ✅ 226 passed（R-06 是 214 passed，+12 来自 R-07 新增 mock 测试）
- 功能: ✅ 符合验收标准（QwenVLModelLoader 实现 load/unload/is_loaded/session；QwenVLSender 不再有 `_load_model`；量化 cascade 保留在 loader 中）
- Lint: ✅ `ruff check .` 全绿；`ruff format` 对 `tests/test_model_loader.py` 应用一次自动 reformat 后 `format --check .` 全绿

**关键决策**：
- `QwenVLSender.__init__` 同时支持 `loader=` 和旧 kwargs（向后兼容，与 R-04 `DiffusersReceiver` 的双入口模式对齐）
- 引入 `QwenVLBundle` dataclass 封装 `(model, processor, actual_quantization)`，避免 loader 返回值类型不一致
- 保留 cascade 顺序：torchao → bitsandbytes → float16，与原 `_load_model()` 一致
- 量化 dtype 选择：torchao 用 `bfloat16`，其余 `float16`（与原逻辑一致）
- `model_path` 默认值用空串 `""` 而非 `None`（dataclass frozen + 兼容旧 None 语义通过 property 转换）

**Coordinator 接管说明**：implementer subagent 写完代码后卡在第 4 步验证 —— 当时 `.venv` 是空的（由 R-06 后某次操作重建），`uv sync` 需要拉 ~3.6G 依赖耗时过长，subagent 超时无回应。Coordinator 接管完成验证（pytest/ruff/format）+ 一次自动 ruff format + 交接记录 + commit。后续 spec-reviewer 与 code-quality-reviewer 链照常派遣。

**下一任务需关注**（R-08）：
- CLI options 默认值改读 `ProjectConfig`，参考本任务 `VLMLoaderConfig` 派生模式
- `sender.py` 和 `batch_sender.py` 合并时，VLM 初始化逻辑应改为 `QwenVLSender(loader=QwenVLModelLoader(config.to_vlm_loader_config()))` 形式
- 注意 `QwenVLSender` 的 `_model_name` / `_quantization` 等 property 现在访问 `self._loader._config.<field>`（双下划线进入 loader 私有 `_config`）—— 这是过渡兼容代码，R-08 重写 CLI 时可考虑改为直接读 loader.config 公共字段

**遗留问题**：
- `QwenVLSender` 的 4 个兼容性 property 访问 `self._loader._config.<field>` 违反封装，待 Phase 2 收尾或 R-14 cleanup 一并清理（若旧测试不再依赖这些字段，可直接删 property）
- venv 重建原因未查清：可能是 `.python-version` 新加（untracked，值为 `3.12`）触发 uv 重建。`.python-version` 是否要提交进版本控制待后续 phase-review 时决策

---

#### R-07 修正记录（code-quality 审计后 第 1 轮 — 2026-05-17）

**触发**: code-quality-reviewer 发现 5 条 Important（详见审计清单）

**修正内容**:
1. 针对审计 #1：将 `except (ImportError, Exception) as e:` 收紧为 `except ImportError as e:`（model_loader.py 两处 cascade），避免吞噬 AttributeError/TypeError 等逻辑错误
2. 针对审计 #2/#3：用本地 `used_torchao` 布尔变量替代脆弱的 `"TorchAoConfig" in str(quantization_config.__class__)` 字符串匹配，dtype 简化为单行三元 `torch.bfloat16 if used_torchao else torch.float16`
3. 针对审计 #4：在 `QwenVLModelLoader` 新增 `@property config` 公共 accessor；`QwenVLSender` 的 4 个兼容 property 改读 `self._loader.config.<field>`，消除跨越 loader 私有 `_config` 的访问（遗留问题里的封装违反点同时解决）
4. 针对审计 #5：重写 `_patch_torchao_unavailable`，改为 `monkeypatch.setitem(sys.modules, "torchao", None)` + `... "torchao.quantization", None)`，让 import 真正抛 `ImportError`（原来的 `MagicMock(spec=[])` 抛 AttributeError，在 catch 收紧后会无声失效）；`_patch_bnb_unavailable` 不存在，bnb 不可用场景已用内联 `MagicMock(side_effect=ImportError(...))` 正确处理

**修改的文件**:
- `src/semantic_transmission/common/model_loader.py` — except 收紧为 ImportError（两处）/ dtype 探测改用 `used_torchao` 本地布尔 / 新增 `QwenVLModelLoader.config` 公共 property
- `src/semantic_transmission/sender/qwen_vl_sender.py` — 4 个兼容 property 改读 `loader.config.<field>`
- `tests/test_model_loader.py` — `_patch_torchao_unavailable` 改为 `sys.modules[...] = None` 使 import 真正抛 ImportError

**修正后验证**:
- 编译: ✅（直接调 `.venv/Scripts/`，未触发 uv sync）
- 测试: ✅ 226 passed（与 R-07 baseline 一致；targeted `test_model_loader.py + test_qwen_vl_sender.py` 41 passed）
- Lint: ✅ `.venv/Scripts/ruff.exe check .` 全绿；`.venv/Scripts/ruff.exe format --check .` 55 files already formatted

---

### R-08 交接（2026-05-17）

**完成内容**：合并 `sender` 与 `batch_sender` CLI 子命令为单一 `sender`，通过互斥选项 `--image` / `--input-dir` 区分单图/批量两条路径。新增共享核心函数 `process_one(image_path, extractor, vlm_sender, prompt, seed) -> SenderResult`，单图路径走扁平输出 + fail-fast，批量路径走 `NN-name/` 子目录 + `batch_summary.json` + continue-on-error。CLI 共享参数（Canny 阈值、VLM 模型/路径）默认值改为运行时读 `load_config()`，CLI options 作为 override。删除 `cli/batch_sender.py`，从 `cli/main.py` 移除注册。

**修改的文件**：
- `src/semantic_transmission/cli/sender.py` — 重写：吸收 batch_sender 功能；新增 `SenderResult` dataclass + `process_one()` + `_build_vlm_sender()` 辅助函数；引入 `load_config()` 读 ProjectConfig 默认；单图/批量分别走 `_run_single()` / `_run_batch()` 输出适配器
- `src/semantic_transmission/cli/batch_sender.py` — **删除**
- `src/semantic_transmission/cli/main.py` — 移除 `from semantic_transmission.cli.batch_sender import batch_sender` 与 `cli.add_command(batch_sender)`
- `tests/test_cli_sender.py` — **新建**，15 个测试用例：`--help` 覆盖、`batch-sender` 不存在校验（CLI 报错 + 模块不可导入）、互斥校验（4 组）、单图扁平输出验证、批量子目录 + summary 验证、ProjectConfig 默认值 + CLI override 验证（2 个）、`process_one()` 纯逻辑测试（2 个）

**验证结果**：
- 编译: ✅（直接调 `.venv/Scripts/`，未触发 uv sync）
- 测试: ✅ 241 passed（R-07 baseline 226 + 15 新增 `test_cli_sender.py`）；`tests/test_cli.py` 18 个原有用例全部仍然通过（无回归）
- Lint: ✅ `ruff check .` 全绿；`ruff format --check .` 55 files already formatted（自动 format 应用过一次 sender.py + test_cli_sender.py）
- 功能: ✅ `.venv/Scripts/semantic-tx.exe sender --help` 显示新选项与模式说明；`.venv/Scripts/semantic-tx.exe batch-sender --help` 报 `No such command 'batch-sender'`

**关键决策**：
- `SenderResult` dataclass 封装单图处理产物（不含落盘文件），由外层 `_run_single` / `_run_batch` 适配器负责实际写文件，符合 spec "两条路径共享 process_one 核心，只在输出适配器和错误策略层分叉"
- CLI 共享参数默认值通过 `load_config()` 运行时读取（而非 click `default=` callable），原因：click 的 `default=callable` 会在模块 import 时即调用，触发 config 加载副作用；运行时读更安全且与 R-06 `cli/main.py` 根命令的 `load_config()` 复用同一份配置
- 批量模式必须传 `--output-dir`，单图模式可省略（默认 `output/sender`）—— 与旧 `batch_sender` 行为一致
- 批量模式 VLM 加载放在 `_run_batch` 入口而非 `process_one` 内部，避免每张图反复构造 loader
- spec 提到"prompt 校验逻辑 4 处相同"目前仅消除了 `sender` + `batch_sender` 两处（合并入 `sender()` 顶层），余下 `demo` / `batch_demo` 由 R-09 处理
- spec 提到 ProjectConfig 已有 `canny_low_threshold` / `canny_high_threshold`（R-01 已加），无需新增字段；VLM 字段亦已就位
- 没有 hardcoded fallback：所有共享默认值都从 `ProjectConfig` 拿，与 spec 一致

**下一任务需关注**（R-09）：
- 同样的模式应用到 `demo` + `batch_demo` 合并：可复用 `process_one()`（已支持手动 prompt + VLM 两条路径）
- `cli/main.py` 同步移除 `batch_demo` 注册（如果 R-09 也走合并思路）；本任务保留 `batch_demo` 单独命令直到 R-09 处理
- R-09 还需重构 `download.py`（按 R-09 spec 描述）
- 注意：`get_default_vlm_path()` 函数本任务未删除（仍在 `common/config.py`），R-09 处理 `download.py` 时再视情况清理

**遗留问题**：
- 文档（`docs/cli-reference.md`、`docs/demo-handbook.md`、`docs/ROADMAP.md`）仍提及 `batch-sender` 命令，本任务不涉及文档（spec 涉及文件中无文档）；属于 R-14 cleanup 范围
- `cli/batch_demo.py` 中重复的 prompt 校验、VLM 初始化逻辑保留不动，等 R-09 合并 demo 子命令时一并处理
- `_build_vlm_sender()` 内部使用 `dataclasses.replace()` 对 VLMLoaderConfig 做 CLI override —— 这是 frozen dataclass 的标准做法，但 import 放在函数体内只是局部 alias；如团队不接受可移到顶层 import

#### R-08 修正记录（code-quality 审计后 第 1 轮 — 2026-05-17）

**触发**: code-quality-reviewer 发现 2 条 Important（无 Critical）

**修正内容**:
1. 针对审计 #1：清理 `_run_batch` 中的自言自语注释（sender.py:582-584），改为简洁 why
2. 针对审计 #2：`_run_batch` 的 `relay.close()` 错误改为 warn 输出而非静默吞

**修改的文件**:
- `src/semantic_transmission/cli/sender.py` — 注释清理 + relay.close() 异常加 warn

**修正后验证**:
- 测试: ✅ (241 passed)
- Lint: ✅ (ruff check + format --check 全通过)

---

### R-09 交接（2026-05-17）

**完成内容**: 重构 `cli/download.py` 移除硬编码 `COMFYUI_MODELS` 与 `--comfyui-dir`，改为从 `ProjectConfig.models.diffusers` + `ProjectConfig.models.vlm` 派生下载清单；`cli/demo.py` 与 `cli/batch_demo.py` 的 click options 默认值改为 `None`，函数体内 `load_config()` fallback（与 R-08 sender.py 模式一致）；`cli/receiver.py` 的 finally 块新增 `recv.unload()` 释放 GPU 显存。

**修改的文件**:
- `src/semantic_transmission/cli/download.py` — 重写：删除 `COMFYUI_MODELS` / `DEFAULT_COMFYUI_DIR` / `--comfyui-dir` option；新增 `_SingleFileTarget` / `_RepoTarget` dataclass + `_SINGLE_FILE_SOURCES` 文件名→仓库 映射；`_derive_single_file_targets()` 从 `ProjectConfig.diffusers_transformer_path`/`diffusers_controlnet_name` 派生 GGUF 与 ControlNet；`_derive_repo_targets()` 从 `vlm_model_name`/`vlm_model_path` 派生 VLM 仓库目标
- `src/semantic_transmission/cli/demo.py` — `--threshold1/--threshold2/--vlm-model/--vlm-model-path` 默认值改 `None`；函数体加 `load_config()` fallback；help 文本指向 config.toml；删除 `get_default_vlm_path` 引用
- `src/semantic_transmission/cli/batch_demo.py` — 同 demo.py 处理
- `src/semantic_transmission/cli/receiver.py` — finally 块新增 `if hasattr(recv, "unload"): recv.unload()` + 异常 warn
- `tests/test_cli.py` — `TestDownloadCommand::test_help` 改为断言 `--comfyui-dir not in result.output`

**验证结果**:
- 测试: ✅ 241 passed（与 R-08 baseline 一致，无回归）
- Lint: ✅ `ruff check .` + `ruff format --check .` 全绿（自动 format 应用一次 `download.py`）
- 功能: ✅ `semantic-tx download --dry-run` 输出**不再**列出 ComfyUI 模型，仅 Diffusers 单文件 + HF VLM 仓库；`semantic-tx demo --help` / `batch-demo --help` 显示新的 "默认读 config.toml" 文案，未阻塞

**关键决策**:
- `download.py` 的"文件名→仓库"映射用模块级常量 `_SINGLE_FILE_SOURCES`：`ProjectConfig` 仅给出本地落盘路径（无仓库信息），不在 ProjectConfig 加新字段（避免越权，spec 明确要求"不要给 ProjectConfig 加新字段"）。映射用 basename 匹配，与文件名解耦于 cache 路径
- `z-image-turbo-Q8_0.gguf` 仓库改为 `city96/Z-Image-Turbo-gguf`（旧 `COMFYUI_MODELS` 的 `Comfy-Org/z_image_turbo` 是 ComfyUI 专用的 fp8 拆分版本，GGUF Q8_0 文件在 `city96` 的镜像仓库下，与 R-04 之后的实际 transformer 加载路径一致）
- ControlNet 来源保持 ModelScope `PAI/Z-Image-Turbo-Fun-Controlnet-Union`（与旧 `COMFYUI_MODELS` 一致）
- demo/batch_demo 的 `QwenVLSender(**vlm_kwargs)` 旧 kwargs 入口保留不动，因 R-07 兼容入口仍然可用；只把 kwargs 的来源从 `get_default_vlm_path` 改为 `ProjectConfig`
- `receiver.py` 的 unload 用 `hasattr` 防御性检查，因 `BaseReceiver` 抽象类未定义 `unload`（仅 `DiffusersReceiver` 实现），未来若新增其他后端无 unload 时不会阻塞退出
- VLM 目标目录派生：`vlm_model_path` 已给完整路径时直接用；为空时回退到 `cache_dir / repo_id`（兼容旧行为，不强制依赖 config.toml）

**下一任务需关注**（R-10 GUI 面板生命周期 #23）:
- R-09 的 receiver.py finally unload 模式可参考迁移到 GUI receiver_panel（若该面板存在类似生命周期问题）
- demo/batch_demo CLI 已不再用 `get_default_vlm_path()`；GUI 若仍引用该函数可在 R-11 一并清理
- `cli/main.py` 仍注册 `batch_demo` 单独命令，若 R-14 cleanup 希望合并到 `demo`（如 R-08 处理 sender 的模式），可考虑下一阶段
- `_SINGLE_FILE_SOURCES` 是模块级映射常量，若未来支持多 transformer 量化或多 ControlNet 变体，需扩展此 map（或考虑迁移到 config.toml 的扩展字段）

**遗留问题**:
- `common/config.py` 中的 `get_default_vlm_path()` / `get_default_z_image_path()` 仍存在但 demo/batch_demo CLI 已不再调用；GUI 模块是否还在用、是否可在 R-11/R-13 cleanup 中清理待 audit
- `download.py` 通过 basename 匹配仓库来源是脆弱设计：若 `config.toml` 改了 ControlNet 文件名或换 transformer 量化版本会触发"未知目标文件 [WARN]"。属可接受妥协（避免在 ProjectConfig 加 `repo_id` 字段越权）
- `_SINGLE_FILE_SOURCES` 中的 GGUF 仓库来源 (`city96/Z-Image-Turbo-gguf`) 是基于 README 记录推断，实际首次下载时需要验证仓库 ID 与文件路径正确（本地已有该文件，本任务 dry-run 跳过下载，无法实测）

---

#### Phase 2 (sender/CLI 侧垂直切) — 回顾记录

**回顾时间**: 2026-05-17

**执行摘要**:
- 计划 task 数：3（R-07 / R-08 / R-09）
- 完成数（✅）：3
- 阻塞 / 跳过数：0
- 关键决策：6 项（VLMLoaderConfig 派生模式 / QwenVLSender 双入口 / SenderResult 数据结构 / `_SINGLE_FILE_SOURCES` basename map / receiver.py finally unload / CLI 共享参数 ProjectConfig fallback）
- 计划变更：0（Phase 2 内部，R-07 → R-08 → R-09 按 PLAN 顺序执行）
- 遗留问题：3 项（`get_default_vlm_path()` 残留 / `_SINGLE_FILE_SOURCES` basename 脆弱 / city96 仓库 ID 未实测）

**变更审计**:
- 审计 task 数：3
- 变更文件数：16（src/ 内 9 文件 + tests/ 3 文件 + docs/workflow/ 2 文件 + cli/batch_sender.py 删除）
- 总 diff：+1731 / -741 行
- 🔴 阻断：0
- 🟡 需修正：0
- 🔵 建议：3（均已合并到 R-11 / R-13 / R-14 步骤）

**审计结论**:
- 完整性：R-07/R-08/R-09 每个任务的 spec 步骤均有对应变更，无漏项
- 准确性：变更文件与 PLAN "涉及文件" 一致；R-07 新增 `QwenVLBundle` dataclass（spec 未明列但实现需要）/ R-09 新增 `_SingleFileTarget`/`_RepoTarget` dataclass（spec 未明列，但合理拆分）属正常实现细节
- 边界：未发现偷跑或范围外修改。R-07 引入的 `_loader.config` 公共 property 在第 1 轮修正中已加，R-08 引入的 `_build_vlm_sender()` 局部函数符合 spec "process_one 共享核心"
- 跨任务一致性：R-08 / R-09 共用 `load_config()` fallback 模式，互不冲突；R-09 删除 `--comfyui-dir` 后 `tests/test_cli.py` 同步更新断言，无遗漏

**退出标准验证**:
- QwenVLSender 迁 loader: ✅ PASS — `_load_model()` 已删除，量化 cascade 移入 `QwenVLModelLoader.load()`，`describe()` 走 bundle
- #19 CLI 合并: ✅ PASS — `batch_sender.py` 已删除，`main.py` 注册移除，`sender.py` 通过互斥选项分两条路径并共享 `process_one()` 核心
- #27 download.py 接 config: ✅ PASS — `COMFYUI_MODELS` / `--comfyui-dir` / `DEFAULT_COMFYUI_DIR` 全部移除，改为 `_derive_*_targets()` 从 ProjectConfig 派生
- sender 单图/批量均正常: ⚠️ PARTIAL — 测试维度通过（241 passed 含 15 个 `test_cli_sender.py` 用例覆盖 dry-run + 互斥 + 模式校验 + ProjectConfig 默认值 + override）；真实 GPU 端到端验证未跑（首次下载 `city96/Z-Image-Turbo-gguf` 仓库 ID 待实测），属可接受妥协（R-14 PR 前最终冒烟时验证）

**构建 / 测试 integration 验证**:
- 编译: SKIPPED (venv ready, 3.6G 依赖完整无需 sync)
- 测试: ✅ PASS — 241 passed in 36.39s（与 R-09 交接记录一致；R-07 +12 / R-08 +15 累计净增 27 个 mock + CLI 测试）
- Lint: ✅ PASS — `ruff check .` All checks passed / `ruff format --check .` 55 files already formatted

**下游影响评估**:
- [必须] R-11 步骤补充：grep `get_default_vlm_path` / `get_default_z_image_path` 在 src/ 内引用，无 GUI 残留则连带删除（已合并到 R-11 spec）
- [建议] R-13 步骤补充：R-08 重写 `sender.py` 200→650 行，新增 RGB 调用点（`process_one()` 中 `Image.open(...).convert("RGB")` / `Image.fromarray()`）需纳入替换范围（已合并到 R-13 spec）
- [建议] R-14 步骤补充：PR 前最终冒烟实测 `semantic-tx download` 真实下载流程，验证 `city96/Z-Image-Turbo-gguf` 仓库 ID 正确性（已合并到 R-14 spec）
- [可选] `_SINGLE_FILE_SOURCES` basename 匹配脆弱性：当前作为可接受妥协保留在 `cli/download.py`；若未来支持多量化版本时可考虑在 ProjectConfig 加 `repo_id` 字段（不强制本 workflow 处理）

**Phase 3 / Phase 4 依赖准确性**:
- R-10 (依赖 R-04 + R-07)：receiver/sender loader 接口未变，准确
- R-11 (依赖 R-01 + R-10)：ProjectConfig 字段已被广泛使用，准确（含 `get_default_*` 清理补充）
- R-12 (依赖 R-04 + R-07)：image_io 未动，准确
- R-13 (依赖 R-12)：含 sender.py 行数膨胀补充，准确
- R-14 (依赖 R-08 + R-13)：CLI 合并已完成；含 PR 前冒烟补充，准确

**结论**: ✅ 通过

---

### R-10 交接（2026-05-17）

**完成内容**: 修复 #23 — `pipeline_panel.py` 与 `batch_panel.py` 的 receiver / LPIPS 模型生命周期泄漏。两个面板均改为 `gr.State` 持久化跨次复用（与 `receiver_panel.py` 已有的样板模式对齐），并新增显式"卸载模型"按钮。VLM 在两个面板中均通过 try/finally 确保异常路径也卸载（VLM 单次性使用不跨次复用，与原行为一致）。

**修改的文件**:
- `src/semantic_transmission/gui/pipeline_panel.py` — `_run_e2e()` 签名新增 `receiver` 入参与 yield 输出；首次运行创建 receiver，后续复用；加载失败清空 state，推理失败保留 state；新增 `unload_receiver()` 函数和"卸载 Receiver 模型"按钮；VLM 加 try/finally 保证 describe() 异常路径也调 unload
- `src/semantic_transmission/gui/batch_panel.py` — `run_batch_process()` 签名新增 `receiver` + `lpips_model` 入参与 yield 输出；receiver 首次创建后跨次复用，LPIPS 同理（仅 `run_eval=True` 路径加载）；VLM 用 try/finally 在循环结束/异常时卸载；新增 `unload_models()` 函数（同时释放 receiver via `unload()` + LPIPS via `del/gc.collect()/torch.cuda.empty_cache()`）和"卸载模型"按钮

**验证结果**:
- 测试: ✅ 241 passed（与 R-09 baseline 一致，无回归）；`test_gui_batch_panel.py` 9 个 + `test_gui_receiver_panel.py` 25 个均通过
- Lint: ✅ `ruff check .` All checks passed / `ruff format --check .` 55 files already formatted（自动 format 应用一次 `batch_panel.py`）
- 功能: ⚠️ PARTIAL — GUI 端到端连续 3 次跑无回归与显存释放验证需 GPU 环境，本任务限于 mock 单测 + 静态代码审查 + 模块 import 烟测；spec 自测方法（本地 GUI 连续跑 3 次观察）需用户在合并前于真机执行

**关键决策**:
- 方案选择 **B（state 持久化 + 显式 unload 按钮）** 而非 A（try/finally + 每次跑完 unload）：pipeline_panel 跑一次端到端 ~55s（R-06 验证），方案 A 每次重加载 receiver 会额外增加 30+ 秒到首次跑（连续 3 次则总开销 +90s 而无收益），方案 B 与 `receiver_panel.py` / `batch_sender_panel.py` 样板一致，保持用户体验
- pipeline_panel 失败路径分两段：receiver **加载失败**清空 state（避免半 init 状态污染下次）；receiver **推理失败**保留 state（失败可能是 prompt/seed/边缘图问题，不应重加载模型）
- batch_panel 的 LPIPS 卸载用 `del + gc.collect() + torch.cuda.empty_cache()`，因 `lpips.LPIPS` 没有官方 unload 接口（`load_lpips_model()` 返回 `nn.Module`，靠引用计数 + CUDA cache 清理触发 GPU 显存回收）
- VLM 仍按"每次跑加载，跑完卸载"模式（不跨次复用），因 VLM 仅 prompt_mode=auto 时使用，频次低；try/finally 保证 describe()/循环异常路径也卸载，消除显存遗漏
- yield tuple 加入 receiver/lpips 是 Gradio state 跨次持久化的唯一路径（gr.State.value 通过 outputs 写回），无法用纯函数替代
- 两个面板的 `unload_*` 函数遵循 `receiver_panel.unload_model()` 一致风格：`getattr(receiver, "unload", None)` 防御性检查 + 失败时仍返回 None 清空 state

**下一任务需关注**（R-11）:
- R-11 spec "迁移 GUI 面板读 ProjectConfig 默认值"，本任务两个面板的 receiver 加载都走 `create_receiver()` 工厂（已自动读 config）；GUI 显式传入的 `vlm_model_name` / `vlm_model_path` 由 `config_components` 提供，已在 R-08/R-09 中部分接入，R-11 需验证 GUI 默认值与 CLI 一致
- R-11 同时需清理 `get_default_vlm_path` 残留：本任务沿用 `from semantic_transmission.common.config import get_default_vlm_path` 旧引用（pipeline_panel 与 batch_panel 都有），如 R-11 决定彻底删该函数，需同步替换为 `load_config()` 取值
- 两个面板新增的 `gr.State(value=None)` 在 `create_app()` 重启时会自动归零，无需额外清理逻辑

**遗留问题**:
- GUI 真机连续 3 次跑验证未执行（需 GPU + Gradio 实跑），属可接受妥协；建议 R-14 PR 前最终冒烟时执行 spec 自测方法（pipeline / batch 面板各连续跑 3 次，观察推理速度无 16x 减速）
- batch_panel 的 `Image.open(image_path).convert("RGB")` 与 `Image.fromarray(edge_np)` 等 RGB 散落点本次未触动，属 R-13 范围
- pipeline_panel 的"卸载 Receiver 模型"按钮与 batch_panel 的"卸载模型"按钮文案略有差异（前者只卸载 receiver，后者同时含 LPIPS），UI 上是合理区分；如统一文案需求强烈可在后续 GUI polish 阶段对齐

---
