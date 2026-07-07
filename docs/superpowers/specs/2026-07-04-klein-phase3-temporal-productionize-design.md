# 设计：klein 阶段 3 productionize（一）——时序策略毕业到 VideoPipeline（单机）

> 上游：[阶段 2 结论报告](../../test-reports/2026-07-01-klein-video-phase2.md)（§7 锁定 productionize 方向）
> 阶段 2 设计：[klein 参考帧时间一致性补偿](2026-07-01-klein-phase2-reference-frame-design.md)
> 后续 spec（本 spec 外）：relay 整帧低频传输 + 接收端串行化（C，紧接第二个 spec）

## 0. 背景与问题

阶段 2 证明 klein 用 `image=[canny, 参考帧]` 通道做时间一致性补偿有效（生成帧间相邻帧 MAE 从 drop-in 的 22.16 降到 ~5.2，降约 76%），**klein 作关键帧主线成立**。但该时序策略（prev 链 + 关键帧透传 + 参考帧构造）**只活在 PoC harness `scripts/poc/klein_ab/run_phase2.py::run_policy()` 的有状态循环里**，没有进入生产管道。

**当前 `semantic-tx video --backend klein` 跑的是被证否的 drop-in baseline**：它走 `VideoPipeline.run()` → `receiver.process_batch()` → 逐帧独立 `process(edge, prompt, seed)`，完全不带 `reference_images`、无跨帧状态，即闪烁 MAE 22 的坏 baseline。

本 spec 的目标 = **把有状态串行时序循环从 PoC 毕业到生产**，让 `semantic-tx video --backend klein` 默认带上已验证的时序策略，单机端到端可跑、可演示。

## 1. 范围

### 做（本 spec）

- **A 策略纯逻辑毕业**：`TemporalPolicyConfig` / `is_keyframe` / `build_reference_images` 从 `scripts/poc/klein_ab/phase2.py` 搬到 `src/`。
- **B 串行执行路径**：`VideoPipeline` 增加持 prev/keyframe 状态的串行生成路径，与现有无状态 `process_batch` 路径并存。
- **C-cli 接线**：`semantic-tx video` 增加时序 flag，`--backend klein` 默认启用 prev-only@N12。

### 不做（后续 spec / 独立轨）

- **relay 整帧低频传输 + 接收端串行化重构**（`video_relay.py`）——紧接的第二个 spec。它改线协议、改接收端执行模型（从"全缓冲乱序独立还原"改为"按序串行带 prev 状态"）、改压缩率账本，是不同模块的独立风险，单独交付。
- **速度优化**（fp8 / 降步数 / TensorRT）——7 月独立轨，与本质量/一致性工作正交。
- **`--backend diffusers`（Z-Image）的多参考时序**——Z-Image 非多参考模型，时序仅 klein 支持。
- **长视频流式化降内存**（issue #49）——7 月独立议题。

## 2. 默认配置决策

`semantic-tx video --backend klein` 不显式传时序 flag 时，默认 **prev-only@N12**（`reference_mode=prev`, `keyframe_interval=12`）。

依据（阶段 2 报告 §2/§4/§7）：prev-only@N12 时序几乎打平质量最优的 prev+key@N12（生成帧间 MAE 5.25 vs 5.13），但快 ~24%、省 0.6GB 显存。速度是 7 月实时化的头号矛盾，默认偏向省算力。两者均可用 flag 切换；`N` 是"保真↔码率"旋钮、`prev+key/prev-only` 是"保真↔算力"旋钮。

## 3. 架构

### 3.1 策略纯逻辑（A）

新建 `src/semantic_transmission/pipeline/temporal_policy.py`，内容从 `scripts/poc/klein_ab/phase2.py` 迁移：

- `TemporalPolicyConfig`（`keyframe_interval: int = 12`, `reference_mode: str = "prev"`, `keyframe_passthrough: bool = True`）
- `is_keyframe(index, config) -> bool`
- `build_reference_images(mode, prev_output, last_keyframe) -> list`

`split_summary` **不迁移**：它是评估期关注点（依赖 baseline 对照做质量两栏拆分），留在 PoC / 归评估模块，不进生产管道。

`scripts/poc/klein_ab/phase2.py` 改为从 `src` 重新导出（`from semantic_transmission.pipeline.temporal_policy import ...`），保持 harness `run_phase2.py` 及其单测可跑、不重复实现。

### 3.2 串行执行路径（B）

`VideoPipeline.run()` 增加可选参数 `temporal_policy: TemporalPolicyConfig | None = None`：

- `temporal_policy is None`（默认）→ 现有无状态 `process_batch` 路径，**逐字节向后兼容**，diffusers 与不带时序的调用不受影响。
- `temporal_policy is not None` → 新的私有串行方法 `_run_temporal(...)`。

**前半段结构相同**：解码 → 逐帧 Canny → 收集 prompt → 保存产物 → `on_prompts_ready` 卸 VLM。唯一差别是**prompt 收集**：时序路径对透传关键帧下标跳过 `prompt_fn`（§5），无状态 `run()` 对全帧收集。除此之外分叉集中在生成阶段。

### 3.3 能力门控

串行时序路径要求 `receiver.process` 接受 `reference_images` 关键字。基类 `BaseReceiver.process()` 签名**不拓宽**（保持无状态单帧契约）；`KleinReceiver.process()` 已支持该参数。

在 `_run_temporal` 入口做能力检查（`hasattr` / 检测签名接受 `reference_images`），不满足时抛明确错误，避免时序参数被静默忽略。

## 4. 数据流：`_run_temporal` 串行循环

```text
# 前半段（与 run() 共享）：
frames, meta = read_frames(input_path)
逐帧 edge = extractor.extract(frame)
逐帧 prompt：仅对“非透传关键帧”调用 prompt_fn（见 §5 VLM 跳过优化）
保存产物（prompts.json + edges/）
on_prompts_ready()  # 卸 VLM 释放显存

# 生成阶段（串行、持状态）：
prev_out = None
last_kf = None
outputs = []
keyframe_indices = []
for i, (frame, edge, prompt) in enumerate(...):
    if is_keyframe(i, policy) and policy.keyframe_passthrough:
        kf = fit_working_size(frame, receiver.config.max_side)  # 透传原图，缩到工作分辨率
        outputs.append(kf)
        keyframe_indices.append(i)
        prev_out = kf        # 链首复位到真关键帧
        last_kf = kf
        continue
    if is_keyframe(i, policy):   # 关键帧但 passthrough=False：仍更新锚，正常生成
        last_kf = fit_working_size(frame, receiver.config.max_side)
    refs = build_reference_images(policy.reference_mode, prev_out, last_kf)
    try:
        img = receiver.process(edge, prompt, seed=seed, reference_images=refs)
    except Exception:
        img = None            # 记为失败帧
    outputs.append(img)
    prev_out = img if img is not None else prev_out   # 失败帧不污染 prev 链

filled = _fill_failed_frames(outputs)
processed = frame_postprocess(filled)
write_frames(output_path, processed, fps=...)
return stats（含 keyframe 信息）
```

**关键不变量**：

- **尺寸一致性**：透传关键帧必须缩到与生成帧相同的工作分辨率（生成帧尺寸由 `fit_working_size(edge, max_side)` 决定）。否则 `write_frames` / 后续评估会因尺寸混杂崩溃——这是 PoC `_fit_all` 踩过的坑。参考帧默认已是工作分辨率、不上采样（对齐 `KleinReceiver.process` 契约）。
- **prev 链失败隔离**：生成失败（`img is None`）时 `prev_out` 保持上一成功帧，不把 None 传进下一帧参考。
- **关键帧复位链首**：透传关键帧同时更新 `prev_out` 与 `last_kf` 为真关键帧，让紧随其后的生成帧被真实内容锚定。

## 5. VLM 跳过优化（关键帧不描述）

**透传关键帧不参与生成，因此不需要 prompt。** 而 VLM 是头号瓶颈（~20s/帧，瓶颈在 prefill）。时序路径对**透传关键帧下标跳过 `prompt_fn` 调用**：250 帧 @N12（21 个关键帧）可省 ~21×20s ≈ 7 分钟。

影响与取舍（已确认接受）：

- `prompts.json` 中透传关键帧**无描述条目**，改为标记 `passthrough: true`（或从 `frames` 列表省略并在 meta 注明关键帧下标）。语义码率统计仅计生成帧。
- 与 relay 语义对齐：relay 场景下关键帧发整帧、不发 prompt，本优化提前落实同一语义。
- `keyframe_passthrough=False`（关键帧也生成）时，关键帧照常需要 prompt，不跳过。

## 6. CLI 表面（`cli/video.py`）

新增 flag：

| flag | 类型 | 默认 |
|---|---|---|
| `--reference-mode` | `none\|prev\|keyframe\|prev_keyframe` | 按 backend 解析（见下） |
| `--keyframe-interval` | int | 12 |
| `--keyframe-passthrough / --no-keyframe-passthrough` | bool | on |

**默认解析与 backend 门控**：

- `--reference-mode` 默认值用哨兵，未显式指定时按 backend 解析：`klein` → `prev`；`diffusers` → `none`。
- 用户对 `--backend diffusers` **显式**传非 `none` 的 `--reference-mode` → `click.UsageError`「时序补偿仅 klein 后端支持」。
- `--reference-mode none` 等价关闭时序（走无状态路径），用于复现 drop-in baseline。

CLI 在 `--reference-mode != none` 时构造 `TemporalPolicyConfig` 并透传给 `pipeline.run(..., temporal_policy=...)`。

## 7. stats / 产物

`summary.json` 增字段：`keyframe_count`、`generated_frames`、`keyframe_indices`。透传帧计时 ~0、不计入生成均值（沿用 PoC `run_policy` 口径），使 `avg_s_per_generated` 反映真实生成开销。无状态路径的 summary 保持原样。

## 8. 错误处理

- 能力门控失败（receiver 不支持 `reference_images`）：抛明确错误，不静默降级。
- backend/flag 冲突：CLI 层 `UsageError`。
- 单帧生成失败：记为失败帧、`_fill_failed_frames` 兜底、prev 链不被污染（§4）。
- 全帧失败：`_fill_failed_frames` 抛 `ValueError`（现有行为）。

## 9. 测试

### 无 GPU 单测（沿用现有 fake receiver 模式，全链路无 GPU）

新增 `FakeReferenceReceiver`（`process` 接受并**记录**每帧收到的 `reference_images`、`prompt`），断言：

- prev 链构造正确：第 i 生成帧收到的 refs = 预期的 [prev_out]（prev 模式）/ [prev_out, last_kf]（prev_keyframe 模式）。
- 关键帧透传：`is_keyframe` 下标输出 = 原始帧（缩放后），未调用 `process`。
- 关键帧跳过 VLM：透传关键帧下标未调用 `prompt_fn`。
- 失败帧不污染链：某帧 `process` 抛异常 → 下一帧 refs 仍指向上一成功帧、非 None。
- **向后兼容**：`temporal_policy=None` 时输出与旧 `process_batch` 路径一致。
- 尺寸一致性：透传帧与生成帧输出尺寸相同。

### 策略纯逻辑单测

`tests/test_temporal_policy.py`：迁移/复用 `tests/poc/test_phase2_policy.py` 对 `is_keyframe` / `build_reference_images` 的断言。

### CLI 单测

`--backend diffusers` + 显式时序 flag → `UsageError`；默认解析（klein→prev, diffusers→none）正确。

### 手动 GPU 冒烟（不进 CI）

`semantic-tx video --backend klein --reference-mode prev --keyframe-interval 12`，少量帧真实行车视频，验证端到端跑通、帧数守恒、尺寸守恒、无 OOM。

## 10. 验收标准

- [ ] `temporal_policy.py` 落 `src/`，PoC 从 src 重导出，`run_phase2.py` 及其单测仍可跑。
- [ ] `VideoPipeline.run(temporal_policy=...)` 串行路径实现，`temporal_policy=None` 逐字节向后兼容。
- [ ] `semantic-tx video --backend klein` 默认走 prev-only@N12 时序策略（不再是 drop-in）。
- [ ] 关键帧透传 + 跳过 VLM + prev 链失败隔离 + 尺寸一致性，均有无 GPU 单测覆盖。
- [ ] backend/flag 门控有单测。
- [ ] `uv run ruff check .` / `uv run ruff format --check .` / `uv run pytest` 全绿。
- [ ] 手动 GPU 冒烟通过（单机端到端可演示）。

## 11. 后续（衔接第二个 spec）

- **relay productionize（C）**：`TransmissionPacket` 加 `frame_kind`（keyframe 整帧 / generated prompt+canny）；发送端按 `is_keyframe` 决定发整帧还是 prompt+canny；`VideoRelayReceiver` 从"全缓冲乱序独立还原"重构为"按 frame_index 严格串行、持 prev 状态"；压缩率账本纳入关键帧整帧成本。
- 速度轨（fp8 / 降步数 / TensorRT）、深度图升级（Video-Depth-Anything）、Qwen3-VL-4B、N 按运动幅度自适应等见 ROADMAP 阶段三中期。
