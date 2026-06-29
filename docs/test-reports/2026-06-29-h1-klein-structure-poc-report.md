# H1 PoC 裁决报告：klein 结构遵循度 + 三方对比（2026-06-29）

> 上游 spec：[`docs/superpowers/specs/2026-06-28-h1-h2-klein-structure-poc-design.md`](../superpowers/specs/2026-06-28-h1-h2-klein-structure-poc-design.md)
> 计划：[`docs/superpowers/plans/2026-06-28-h1-h2-klein-structure-poc.md`](../superpowers/plans/2026-06-28-h1-h2-klein-structure-poc.md)
> 运行产物：`output/poc/h1-h2/`（gitignored，本地留存）；驱动脚本：`scripts/poc/h1_h2/`

## 0. 结论先行（go/no-go）

- **FLUX.2-klein-9B 否决为目标版关键帧主线**：它无结构条件控制，把 Canny 当参考图（`image=[...]`）几乎无效。
- **关键帧主线继续用现役 Z-Image-Turbo + ControlNet Union**：结构遵循够用、最快、已集成，质量/速度/工程平衡最佳。
- **qwen-Image + InstantX ControlNet 为质量天花板参考**：结构保真最强（IoU 是 klein 的 ~3.4x、Z-Image 的 ~1.8x），但 95s/帧（~9x 慢），需重度速度优化后才可能上主线。
- **H2（klein 速度三档）moot**：klein 已否决，且 fp8 加载受阻只能测 bf16，速度数据无决策价值，未单独跑。

## 1. 三方综合对比（核心结果）

同一组帧（10 帧真实行车视频）+ 同一份 Qwen-VL 逐帧 prompt + 同一张 Canny，唯一变量 = 模型与结构条件机制。

| 模型 | 均值边缘 IoU | 均值 s/帧 | 结构遵循（目视） |
|---|---|---|---|
| **klein**（bf16+offload, 4步, image=Canny 参考图） | **0.069** | 14.5（稳态~10s） | ❌ 自己构图，无视 Canny |
| **Z-Image-Turbo+ControlNet**（现役, GGUF Q8, 9步） | **0.130** | **10.5（最快）** | ✅ 物体方位贴合 Canny |
| **qwen-Image+InstantX ControlNet**（GGUF Q4, 30步, 全驻） | **0.238**（最强） | 95.0（~9x 慢） | ✅✅ 结构保真最强 |

> 逐帧明细见 `output/poc/h1-h2/compare3/compare3.md`；五联对比图 `compare3/grid_frame00-09.png`（input ｜ in-canny ｜ klein ｜ zimage ｜ qwen）。

**目视铁证**（`compare3/grid_frame00`、`grid_frame02`、`grid_frame05`）：输入中"车辆在左、路牌在右"的布局，Z-Image 和 qwen 都能还原物体方位（qwen 还原最丰富），而 **klein 把同样物体放正中、自己重新构图**。

## 2. klein 结构遵循 NO-GO（三重验证，对 prompt 质量鲁棒）

| 测试条件 | 均值 IoU | 最高帧 | 说明 |
|---|---|---|---|
| 固定通用 prompt | 0.046 | 0.069 | spec 原设计（隔离结构变量） |
| **VLM 准确 prompt**（最贴近生产） | 0.069 | 0.147 | Qwen-VL 逐帧描述，真实管道主信息源 |
| 三方对比（VLM prompt） | 0.069 | 0.147 | 同上，与 Z-Image/qwen 横向比 |

**机理**（`h1_vlm/grid_frame06`）：给 klein 准确 prompt，它能生成**场景类型正确**的图（沙漠路+牌+车），但**按自己的构图摆放、不靠 Canny 定位几何** → 边缘不重合。即 klein 把文本当主信息源生成合理场景，**但没有结构条件控制**——对需逐帧几何对齐（保证帧间一致、贴合真实画面）的视频语义传输不胜任。准确 prompt 让 IoU 相对提升 ~50%（场景对了、偶然部分重合），但绝对值仍远低。

## 3. 方法论修正：IoU 阈值

spec 设的 IoU>0.4 判据**定高了**——连能跟结构的现役 Z-Image 也只 0.130、最强的 qwen 也只 0.238。生成式重建的 re-Canny IoU 天花板本就低（生成图精细边缘多、与输入 Canny 差异大）。**正确的判据是「相对倍数 + 目视物体方位」，不是绝对 IoU**。按此尺子：qwen > Z-Image ≫ klein，klein 明确垫底且目视无结构遵循。

## 4. 工程留档

### 4.1 klein 加载（fp8 待解工程点）
- diffusers 0.37.1 已含 `Flux2KleinPipeline`，无需升级。
- **fp8 单文件加载受阻**：BFL 官方 fp8 为 scaled-fp8 布局，`Flux2Transformer2DModel.from_single_file` 转换器不认（`convert_flux2_double_stream_blocks` 对 fused_qkv 0-dim chunk 报错）。已回退 **bf16 全组件 + model CPU offload**（512² 峰值 ~20.7GB）。fp8 加载为待解工程点。
- `from_single_file` 默认拉 gated `FLUX.2-dev` config（401）→ 传本地 `config=` 解决。

### 4.2 qwen+InstantX 集成（已攻通，配方留给 7 月）
GGUF 量化的 Qwen-Image(20B) + InstantX 自定义 pipeline + 24GB，三条 offload 路全死：

| 方案 | 结果 |
|---|---|
| `model_cpu_offload` | RoPE 位置索引留 CPU → `index is on cpu vs cuda` |
| `sequential_cpu_offload` | 与 GGUF 不兼容 → `GGML_QUANT_SIZES[None]` KeyError |
| 全量 `.to("cuda")` | OOM（文本编码器 Qwen2.5-VL ~16GB + GGUF 13GB + controlnet） |

**可行配方（`qwen_resident.py`）**：仅文本编码器驻 cuda **预编码**所有 prompt+负向（手动编码绕开 `_get_qwen_prompt_embeds` 的 `.to(self.device)`）→ 释放文本编码器 → transformer(GGUF 13GB)+controlnet(3.5GB)+vae 驻 cuda 用预编码 embeds 跑。另：InstantX 自带的自定义 `QwenImageTransformer2DModel` 不在 GGUF 兼容表，须用 diffusers 原生类（其 forward 接受 `controlnet_block_samples`）；transformer config 本地缺，从 hf-mirror 补 `config.json`。

## 5. 对后续的影响

- 解锁 ROADMAP D4：关键帧主线选型 = **Z-Image+ControlNet**（klein 出局，qwen 备选）。
- 真正瓶颈是**速度**：三者 10–95s/帧都远离关键帧周期目标（~1-1.5s），速度优化（TensorRT/降步数/蒸馏/低分辨率）是 7 月主攻方向，与选哪个模型无关。
- 待后续：depth 第二条件、H3 帧间一致性（在选定模型上测）、qwen 速度优化。

## 6. 验收

- ✅ klein 结构遵循出逐帧 IoU + 均值 + 目视，给出明确 NO-GO（三重验证）。
- ✅ 三方质量(IoU)+速度(s/帧)横向对比，含现役 Z-Image 与 qwen+InstantX。
- ✅ 全部对比产物落盘（`output/poc/h1-h2/`），裁决报告 committed。
- ⏭ H2 速度三档 moot 未跑；qwen 速度优化、depth、H3 留作后续。
