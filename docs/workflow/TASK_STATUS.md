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
| Phase 2: sender/CLI 侧垂直切 | 3 | 0 | 0 | 3 |
| Phase 3: GUI 侧垂直切 | 2 | 0 | 0 | 2 |
| Phase 4: cleanup + 收尾 | 3 | 0 | 0 | 3 |
| **合计** | **14** | **6** | **0** | **8** |

## 任务状态

| 编号 | 标题 | 阶段 | 状态 | 依赖 |
|------|------|------|------|------|
| R-01 | 创建-ProjectConfig 与 config.toml 体系 | Phase 0 | ✅ | 无 |
| R-02 | 创建-ModelLoader 抽象基类 | Phase 0 | ✅ | 无 |
| R-03 | 实现-DiffusersModelLoader | Phase 1 | ✅ | R-01, R-02 |
| R-04 | 迁移-DiffusersReceiver + 动态尺寸 #24 | Phase 1 | ✅ | R-03 |
| R-05 | 简化-BaseReceiver.process_batch #31 | Phase 1 | ✅ | R-04 |
| R-06 | 对齐-采样器参数 #25 | Phase 1 | ✅ | R-04 |
| R-07 | 实现-QwenVLModelLoader + 迁移 QwenVLSender | Phase 2 | ⬜ | R-02 |
| R-08 | 合并-CLI sender/batch_sender #19 | Phase 2 | ⬜ | R-01, R-07 |
| R-09 | 重构-download.py + 迁移 demo/batch_demo CLI | Phase 2 | ⬜ | R-01, R-08 |
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
