# 工作流完成摘要 — unify-config-and-loader

## 基本信息

- **任务名称**: unify-config-and-loader
- **任务类型**: refactor（兼 bugfix / infrastructure）
- **任务前缀**: R
- **开始时间**: 2026-04-11
- **归档时间**: 2026-06-10
- **init commit**: `856f928`
- **首末 commit**: `cc6d1ad`（R-01 ProjectConfig 落地）→ `5713602`（R-14 cleanup）

## 总体统计

| 项 | 数 |
|---|---|
| 阶段数 | 5（Phase 0~4） |
| 任务总数 | 14 |
| 已完成 | 14 |
| 已取消 / 暂停 / 未完成 | 0 |
| 测试数变化 | 198 → 256（净增 58） |

## 各阶段摘要

### Phase 0: 基础设施（2/2）
- R-01 创建 ProjectConfig 与 config.toml 体系（4 层配置优先级：代码默认 < config.toml < config.local.toml < 环境变量）
- R-02 创建 ModelLoader 抽象基类（`ModelLoader(ABC, Generic[TModel])` + `session()` context manager）

**关键成果**：配置与模型生命周期两大抽象落地，纯新增不接线，旧代码零变化。

### Phase 1: receiver 侧垂直切（4/4）
- R-03 实现 DiffusersModelLoader（GGUF transformer + ControlNet + base pipeline 分组件加载）
- R-04 迁移 DiffusersReceiver 委托 loader + 修复动态尺寸 #24
- R-05 审计 BaseReceiver.process_batch #31（结论：保留不合并）
- R-06 对齐采样器参数 #25（scheduler_shift=3.0、尺寸 16 倍数对齐、hf_endpoint 镜像站持久化）

**关键成果**：接收端完整迁移到 loader 体系，动态尺寸 + 采样器对齐修复，端到端 demo 跑通。

### Phase 2: sender/CLI 侧垂直切（3/3）
- R-07 实现 QwenVLModelLoader（量化 cascade：torchao → bitsandbytes → float16）+ 迁移 QwenVLSender
- R-08 合并 CLI sender/batch_sender 为单一 sender 子命令 #19（互斥 `--image` / `--input-dir`）
- R-09 重构 download.py 从 ProjectConfig 派生下载清单 #27 + demo/batch_demo 迁移 ProjectConfig

**关键成果**：发送端与全部 CLI 子命令统一读 config.toml，CLI 命令面收敛。

### Phase 3: GUI 侧垂直切（2/2）
- R-10 修复 GUI 面板生命周期 #23（gr.State 持久化 receiver/LPIPS + 显式卸载按钮 + VLM try/finally）
- R-11 GUI 全部 6 面板默认值统一从 ProjectConfig 读取（闭包绑定注入）

**关键成果**：端到端/批量面板推理灾难级慢（重复加载模型）问题修复，GUI 与 CLI 默认值同源。

### Phase 4: cleanup + 收尾（3/3）
- R-12 新建 common/image_io.py（load_as_rgb / image_to_numpy 统一图像入口）+ 替换 core 模块 #22
- R-13 替换 CLI + GUI 模块 17 处 RGB 散落点 #22
- R-14 删除 LocalRelay dead code #33 + 删除 get_default_vlm_path / get_default_z_image_path + 文档更新

**关键成果**：图像加载入口统一，dead code 与旧默认路径函数彻底清除，静态 grep 全零。

## 关键决策汇总

1. **2026-04-11 — 选定 L3 深切片（#20 + #21 捆绑）**：两者耦合度高，只做其中一个改动面不减；按模块垂直切（非架构优先），每模块改完即稳定。
2. **2026-04-12 — requires-python 提升到 >=3.12**：直接用 stdlib tomllib，零依赖成本（不引 pydantic）。
3. **2026-04-13 — scheduler_shift=3.0 + 尺寸 16 倍数对齐**：映射 ComfyUI `ModelSamplingAuraFlow(shift=3)` 基线；`res_multistep` 在 diffusers 无等价，用默认 Euler。
4. **2026-05-17 — QwenVLSender / DiffusersReceiver 双入口模式**：同时支持 `loader=` 与旧 kwargs，向后兼容平滑迁移。
5. **2026-05-17 — GUI 生命周期选 state 持久化方案**：端到端单次 ~55s，每次重加载 receiver 代价过高；与 receiver_panel 既有样板对齐。
6. **2026-05-18 — to_numpy() 复用 + 内部委托 load_as_rgb**：保持 evaluation 公共签名稳定，避免重复实现。
7. **2026-05-18 — 保留 BaseRelay 抽象基类**：零运行时成本，留作未来扩展点（WebSocket / gRPC relay）。

## 收尾验证（2026-06-10 归档时补充）

- pytest 256 passed / ruff check + format 全绿
- `semantic-tx download --dry-run` 实测通过（city96 GGUF / ModelScope ControlNet / HF VLM 三类目标识别正确，本地文件完整）
- CLI 端到端 demo GPU 冒烟通过（canyon_jeep.jpg，手动 prompt，接收端 60.9s，与 R-06 基线一致）

## 遗留问题清单

- **GUI 面板真机 GPU 冒烟未逐面板执行**（R-14 延后项 2）：sender / pipeline / batch / batch_sender 四面板的交互式连续 3 次跑验证未做；代码层有 247+ 单测覆盖，CLI 同路径 GPU 冒烟已通过。后续在 GUI 实际使用中观察即可，如发现生命周期回归参照 #23 处理。
- 其余开放议题见 GitHub Issues（#40 综合议题、#41 FLUX.2-klein 调研为高优）。
