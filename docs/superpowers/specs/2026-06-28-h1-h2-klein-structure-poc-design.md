# H1+H2 PoC：klein 结构遵循度 + 速度三档（设计）

> 工作分支 `feature/poc-h1-h2-klein-structure` | 编制 2026-06-28
> 上游依据：技术方案 [`docs/research/2026-06-21-video-stream-tech-scout.md`](../../research/2026-06-21-video-stream-tech-scout.md) §2.2/§2.3/§6（H1/H2 验证清单与回退判据）；6 天冲刺规划 [`docs/superpowers/specs/2026-06-21-video-stream-6day-plan-design.md`](2026-06-21-video-stream-6day-plan-design.md) §3 PoC 编排
> 目标版主线裁决（klein vs Qwen）依赖本 PoC 结论；本 PoC 在关键路径上。

## 1. 背景与定位

目标版关键帧主线选 **FLUX.2-klein-9B** 还是 **Qwen-Image + InstantX ControlNet**，卡在一个零证据的赌注上：klein 官方确认**无 ControlNet 支持**，只能赌「把 Canny/depth 当参考图塞进 `image=[...]`」能产生结构级遵循。技术方案把它列为第一红线（P0），必须第一周用数据证伪/证实。

ROADMAP D4「目标版起步：按裁决落地关键帧主线」的依赖正是「PoC 裁决」——**本 PoC 是目标版主线的上游，二者串行依赖而非并行竞争**。因此本 PoC 会话此刻独占 GPU 直接跑即可，无需错峰机制；主线会话并行做不吃 GPU 的架构契约工作（定义关键帧输出契约、替换 `frame_postprocess` 空钩子）。

## 2. 范围

| PoC | 内容 | 本轮做 |
|---|---|---|
| **H1**（最高优先） | klein 结构遵循度：Canny 当参考图能否实现结构约束，与 Qwen-Image+InstantX 严格并行对照 | ✅ 本轮主体 |
| **H2** | klein-9b-fp8 单帧速度三档（512/768/1024） | ✅ 搭车（klein 已在显存，纯计时，且不依赖任何裁决） |
| H3（帧间一致性） | 相邻帧 LPIPS/SSIM flicker | ❌ 推迟，必须在 H1 裁决出的模型上测 |

**明确不做**：视频级时间一致性度量（属 H3）；depth 条件（第一刀只用 Canny，跟得上再补 `Depth-Anything-V2-Small`）；Qwen-Image-Edit-2511（H1 用基座 + InstantX 是原生组合，Edit-2511 留给后续回退主线/一致性）。

## 3. 模型与环境

### 3.1 模型清单（均已就位于 `D:\Downloads\Models`，ModelScope 下载）

| 角色 | 路径 | 形态 |
|---|---|---|
| klein 完整 pipeline（bf16） | `black-forest-labs\FLUX.2-klein-9B\` | diffusers 整目录（vae/text_encoder/transformer/scheduler/tokenizer） |
| klein fp8 transformer | `black-forest-labs\FLUX.2-klein-9b-fp8\flux-2-klein-9b-fp8.safetensors` | 单文件（H2 首选，分组件加载：klein-9B 其余组件 + 此 fp8 transformer） |
| Qwen-Image 基座 | `Qwen\Qwen-Image\` | diffusers 整目录（缺 transformer，由下方 GGUF 充当） |
| Qwen-Image transformer | `QuantStack\Qwen-Image-GGUF\Qwen_Image-Q4_K_M.gguf` | 单文件 GGUF |
| InstantX ControlNet-Union | `InstantX\Qwen-Image-ControlNet-Union\` | 整目录（含自定义 `pipeline_qwenimage_controlnet.py` / `controlnet_qwenimage.py`） |
| depth（暂缺，推迟） | — | 后续补 `depth-anything/Depth-Anything-V2-Small`（~100MB） |

### 3.2 环境阻塞（H1 真正的前置）

- **diffusers 升级**：现 `diffusers>=0.33.0` 大概率不含 `Flux2KleinPipeline`（FLUX.2）。需升级到支持 FLUX.2 的版本并验证 klein 能加载+出基础图。**这是 H1 的第一道关卡，先于任何 IoU 测试。**
- **隔离**：升级在独立分支/worktree 内进行；PoC 脚本不改 `src/` 主线代码，避免污染保底版与主线会话。InstantX 自带 pipeline 代码以本地导入方式使用，不进 `src/`。
- 单卡 24GB：klein fp8（9.4GB）+ Qwen3-8B 文本编码器为显存紧点（H2 顺带记录峰值显存）；klein 与 Qwen 两套模型**串行**测（load→测→卸载→换下一套）。

## 4. 实验设计

### 4.1 测试输入

复用 M1 已标定的真实行车视频（`resources/test_videos/prepared/`，10s/6fps/60 帧/640×480）。从 3 组已端到端验证视频中按**结构丰富度**（Canny 边缘密度 + 目视）选定抽帧方案：

| 视频 | 画面 | Canny 边缘密度 | 角色 |
|---|---|---|---|
| `C1X_20250721112728`（C1X_112728） | 跑道/道路：道路灭点 + 标牌 + 装甲车 + SUV + 远处建筑 | 0.0134（最高） | **主测**：取中段连续 8 帧（约 26–33 帧），逐帧 IoU + 拼连续对比条 |
| `C104_20260115093008`（C104_093008） | 雾天越野：行人 + 细旗杆 + 土路弯道，overlay-free | 0.0114 | **多样性单帧**：取 1–2 帧，换场景类型佐证 IoU；且无 HUD，作绝对 IoU 旁证 |
| `C104_20260115093113`（C104_093113） | 扬尘遮蔽、沙地稀疏 | 0.0024（最低） | **跳过**（Canny 无信号，测结构遵循无意义）；至多留 1 帧当退化硬样本 |

合计约 8 + 2 = 10 帧 × 2 模型（klein/Qwen）= ~20 次生成，go/no-go 够用且不烧 GPU。抽帧分辨率 resize/crop 到 512² 或 768²。

> **HUD 坑（须记报告）**：C1X_112728 带叠加层（中央十字准星、左车检测框、文字标签），Canny 会把它们当边缘，而生成图复现不出来 → **人为压低绝对 IoU**。但 H1 本质是 klein vs Qwen 的**相对对比**，两臂吃同一张输入 Canny，叠加层对两者影响相同——**相对裁决不受影响**，仅绝对 IoU 对 0.4 阈值略偏低。缓解：必要时裁掉准星区域，或以 overlay-free 的 C104_093008 单帧作绝对 IoU 旁证。

### 4.2 H1 流程（每帧、klein 与 Qwen 各跑一遍）

1. 原始帧 → `LocalCannyExtractor`（阈值复用 config：100/200）→ 输入 Canny。
2. 原始帧 → VLM/或预置文本描述场景（H1 聚焦结构，prompt 可固定简述，避免 prompt 变量干扰对比）。
3. **klein 臂**：Canny 图塞进 `image=[...]` + prompt → klein-9B（fp8）生成。
4. **Qwen 臂**：Canny 图走 InstantX ControlNet（`controlnet_conditioning_scale` 取官方区间 0.8–1.0）+ prompt → Qwen-Image 生成。
5. 两臂输出各自**重提 Canny**（同阈值）→ 与输入 Canny 算**边缘 IoU**（二值 mask 交并比；为容忍 1px 错位，可对 mask 做轻微膨胀后再算，膨胀核大小在报告中标注）。
6. 目视检查几何吻合。

**判据**（技术方案 §2.2/§6）：IoU > 0.4 且目视几何跟随 → klein 主线成立；klein 不过而 Qwen 过 → 切 Qwen+InstantX 回退主线；两者都不过 → 升级会上报。

### 4.3 H2 流程

klein-9b-fp8、4 步、`guidance_scale=1.0`，512²/768²/1024² 三档，每档跑数帧取稳态、**排除冷加载首帧**，记录 ms/帧与显存峰值。判据：≤1.5s/帧（512–768）；若验到 <1s 则关键帧周期账全面上修。

## 5. 产物与交付（须保留给负责人看）

落盘到 `output/poc/h1-h2/`（gitignored 运行产物），最终报告committed 到 `docs/test-reports/`。

- **逐帧产物**（每帧一组）：原图 / 输入Canny / klein输出 / klein重提Canny / Qwen输出 / Qwen重提Canny。
- **对比网格**：每帧拼成 `原图 | 输入Canny | klein | klein-Canny | Qwen | Qwen-Canny` 一张图，IoU 数值叠在图上。
- **连续帧对比条 / gif**：klein vs Qwen vs 原图，目视时间行为预览。
- **IoU 表**：逐帧 + 均值，JSON + 可读 md。
- **H2 速度表**：三档 ms/帧 + 显存峰值。
- **裁决报告**（`docs/test-reports/`）：IoU 汇总 + 目视结论 + 速度 + **go/no-go 建议**（保 klein / 切 Qwen），附关键对比图。

## 6. 风险与回退

| 风险 | 兆头 | 处置 |
|---|---|---|
| diffusers 不支持 klein 加载 | `Flux2KleinPipeline` 不存在 / 加载报错 | 先解决环境（升级版本/查官方加载方式），不通则 H1 阻塞、立即上报——这本身是有价值的负面结论 |
| klein 结构遵循失败（高概率） | IoU<0.4 / 目视不跟随 | 按 §4.2 切 Qwen+InstantX，本 PoC 仍交出完整裁决 |
| Qwen-Image GGUF transformer 接 InstantX 自定义 pipeline 不顺 | 加载/前向报错 | 退而用 Qwen-Image 基座非量化 transformer（若显存允许）或记录为待解工程点 |
| 24GB 显存不足（klein fp8 + Qwen3-8B 编码器） | OOM | 降分辨率至 512²、文本编码器 offload、必要时 CPU offload；H2 顺带量化此风险 |
| 单卡与主线 GPU 争用 | — | 当前无：H1 在关键路径、主线下游等裁决；主线并行做不吃卡的输出契约工作 |

## 7. 验收

- H1 出**逐帧 IoU + 均值 + 目视结论**，给出 klein 保/切的明确 go/no-go。
- H2 出**512/768/1024 三档 ms/帧 + 显存峰值**。
- 全部对比产物落盘可查；裁决报告 committed 到 `docs/test-reports/`。
- 通过 = klein 与 Qwen 在同组帧上有可比 IoU 数据 + 速度数据 + 一句话主线建议。

## 8. 后续

- 本 PoC 裁决 → 解锁 ROADMAP D4 目标版关键帧主线落地。
- depth 补测、H3 帧间一致性、Edit-2511 回退验证为后续独立会话，均在 H1 裁决之后。
