# H1 PoC 评估报告：klein 结构遵循度 + 三方对比（2026-06-29）

> 上游 spec：[`docs/superpowers/specs/2026-06-28-h1-h2-klein-structure-poc-design.md`](../superpowers/specs/2026-06-28-h1-h2-klein-structure-poc-design.md)
> 计划：[`docs/superpowers/plans/2026-06-28-h1-h2-klein-structure-poc.md`](../superpowers/plans/2026-06-28-h1-h2-klein-structure-poc.md)
> 运行产物：`output/poc/h1-h2/`（gitignored，本地留存）；驱动脚本：`scripts/poc/h1_h2/`

## 0. 结论先行

**本 PoC 只记录「单帧 + Canny 参考图」条件下的结构遵循实测发现，不做最终主线裁决。** 关键帧主线选型留到 video→video 全流程评估（看帧间一致性、视觉质量、整段还原），**klein / Z-Image / qwen 三者均为在评候选**。

- **klein**：单帧边缘 IoU 最低（精细几何不贴 Canny），但**单帧视觉质量好、准确 prompt 下生成场景类型正确的图**（粗粒度跟随）。本 PoC 未量其视觉质量、也未测 video→video 时间一致性机制（上一帧 latent-init 等）的补偿——**仍是主线候选，待全流程实测再评**（接入路径见 §5.3）。
- **Z-Image-Turbo + ControlNet**：现役生产模型，结构遵循够用、最快、已集成，工程上现成可用的基线候选。
- **qwen-Image + InstantX ControlNet**：结构保真最强（IoU 是 klein ~3.4x、Z-Image ~1.8x），但 95s/帧（~9x 慢），需重度速度优化才可能上主线。
- **H2（klein 速度三档）未跑**：fp8 加载受阻只能测 bf16，当前无决策价值，moot。

> **重要口径**：下方所有「IoU」都是**单帧、固定一帧、Canny 当唯一条件**下的边缘对齐度，是一个对生成式重建天花板很低的指标（连现役 Z-Image 也只 0.13）。它衡量的是「逐帧几何精确对齐」，**不衡量视觉质量，也不代表 video→video 流程下的最终表现**。klein 的「弱」严格限定在这个指标语境内。

## 1. 三方综合对比（核心结果）

同一组帧（10 帧真实行车视频）+ 同一份 Qwen-VL 逐帧 prompt + 同一张 Canny，唯一变量 = 模型与结构条件机制。

| 模型 | 均值边缘 IoU | 均值 s/帧 | 结构遵循（目视） |
|---|---|---|---|
| **klein**（bf16+offload, 4步, image=Canny 参考图） | **0.069** | 14.5（稳态~10s） | ❌ 自己构图，无视 Canny |
| **Z-Image-Turbo+ControlNet**（现役, GGUF Q8, 9步） | **0.130** | **10.5（最快）** | ✅ 物体方位贴合 Canny |
| **qwen-Image+InstantX ControlNet**（GGUF Q4, 30步, 全驻） | **0.238**（最强） | 95.0（~9x 慢） | ✅✅ 结构保真最强 |

> 逐帧明细见 `output/poc/h1-h2/compare3/compare3.md`；五联对比图 `compare3/grid_frame00-09.png`（input ｜ in-canny ｜ klein ｜ zimage ｜ qwen）。

**目视铁证**（`compare3/grid_frame00`、`grid_frame02`、`grid_frame05`）：输入中"车辆在左、路牌在右"的布局，Z-Image 和 qwen 都能还原物体方位（qwen 还原最丰富），而 **klein 把同样物体放正中、自己重新构图**。

## 2. klein 的已知问题：单帧精细结构对齐弱（三重验证，对 prompt 质量鲁棒）

| 测试条件 | 均值 IoU | 最高帧 | 说明 |
|---|---|---|---|
| 固定通用 prompt | 0.046 | 0.069 | spec 原设计（隔离结构变量） |
| **VLM 准确 prompt**（最贴近生产） | 0.069 | 0.147 | Qwen-VL 逐帧描述，真实管道主信息源 |
| 三方对比（VLM prompt） | 0.069 | 0.147 | 同上，与 Z-Image/qwen 横向比 |

**机理**（`h1_vlm/grid_frame06`）：给 klein 准确 prompt，它能生成**场景类型正确、视觉质量高**的图（沙漠路+牌+车），但**按自己的构图摆放、不靠 Canny 精确定位几何** → 单帧边缘不重合。即 klein 把文本当主信息源生成合理场景，**结构条件（`image=` 参考图通道）对几何的约束很弱**。准确 prompt 让 IoU 相对提升 ~50%（场景对了、偶然部分重合）。

**这是「问题」而非「否决」的原因**：①该弱点严格限定在「单帧逐帧几何精确对齐」语境，klein 的视觉质量是其优势、未被本指标衡量；②video→video 流程里还有时间一致性机制（上一帧 latent-init / img2img strength / Consistency LoRA 等）可能补偿几何漂移——这些**本 PoC 未测**；③对「保语义、不保像素」的语义传输定位，klein 的「合理生成」未必不可用。故保留候选，待全流程实测再裁。

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

- ROADMAP D4：关键帧主线选型**不在本 PoC 裁决**，klein / Z-Image / qwen 三者均为在评候选，待 video→video 全流程实测后再定。
- 真正瓶颈是**速度**：三者 10–95s/帧都远离关键帧周期目标（~1-1.5s），速度优化（TensorRT/降步数/蒸馏/低分辨率）是 7 月主攻方向，与选哪个模型无关。
- 待后续：depth 第二条件、H3 帧间一致性、qwen 速度优化。

### 5.3 klein 经接口接入 video→video 再测（推荐下一步）

本 PoC 只测了「单帧 + Canny 参考图」受限条件。接收端已抽象为 `BaseReceiver`
接口（`process(edge_image, prompt_text, seed) -> Image`），video→video 管道
（`video_pipeline.py`）只认该接口、经 `create_receiver()` 工厂构造，因此**任何
`BaseReceiver` 子类都能无缝切换跑全流程**。让 klein 公平再测只需三步小改动：

1. 新增 `KleinReceiver(BaseReceiver)`：`process()` 内用 klein pipeline（`image=[Canny]`
   + prompt，4 步），逻辑已在 `scripts/poc/h1_h2/klein_runner.py` 验证。
2. `create_receiver(backend=...)` 增加 `backend="klein"` 分支返回 `KleinReceiver`。
3. video CLI 加 `--backend {diffusers,klein}` 旗标透传。

如此可在**真实 video→video 流程**下对比 klein vs Z-Image：不仅看单帧 IoU，还看
**帧间一致性、视觉质量、整段还原**——这些才是 klein 是否可用的真正判据，本 PoC 的
单帧 IoU 只是第一道筛。

## 6. 验收

- ✅ klein 结构遵循出逐帧 IoU + 均值 + 目视，记录「单帧精细对齐弱」问题（三重验证），保留候选待全流程再测。
- ✅ 三方质量(IoU)+速度(s/帧)横向对比，含现役 Z-Image 与 qwen+InstantX。
- ✅ 全部对比产物落盘（`output/poc/h1-h2/`），裁决报告 committed。
- ⏭ H2 速度三档 moot 未跑；qwen 速度优化、depth、H3 留作后续。
