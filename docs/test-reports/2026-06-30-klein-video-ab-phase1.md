# 阶段 1 结论报告：klein vs Z-Image video→video A/B（2026-06-30，完成于 2026-07-01）

> 测试方案：[2026-06-30-klein-video-ab-phase1-plan.md](2026-06-30-klein-video-ab-phase1-plan.md)
> 设计：[../superpowers/specs/2026-06-30-klein-receiver-backend-design.md](../superpowers/specs/2026-06-30-klein-receiver-backend-design.md)
> Harness：`scripts/poc/klein_ab/run_ab.py` ｜ 产物：`output/poc/klein-ab-phase1/`（gitignored）

## 0. 结论先行

在真实 video→video 流程下对比 klein（关键帧主线候选）与 Z-Image（现役备选），**核心结论**：

1. **klein 单帧质量优、显存友好，但 drop-in（逐帧独立生成）下时间一致性极差**——连续帧严重闪烁/漂移（天空云层、车辆、山形每帧重构），明显劣于 Z-Image。
2. **这正是 H1 §0/§2 预判的关键风险被证实**：klein 无视 Canny 精细结构，逐帧独立生成 → 视频里表现为剧烈帧间漂移。
3. **klein 作关键帧主线，drop-in 形态不可用**；是否可行**取决于阶段 2 的参考帧时间一致性补偿能否压住闪烁**。建议进入阶段 2。
4. **意外利好**：klein 在 896×496 仅占 18.5GB / 24GB，分辨率显存余量大，之前的 OOM 担忧被推翻——后续可上更高分辨率/更优超分余量。

## 1. 实验设置

| 项 | 值 |
|---|---|
| 源视频 | `resources/test_videos/视频记录/20251109134829.mp4`（1920×1080, HEVC, 25fps） |
| 片段 | 第 20–30s，**原生 25fps，250 帧** |
| 工作分辨率 | **896×496**（smoke 锁定；保宽高比、round 16；输入原始、receiver 内部降采样） |
| prompt | Qwen2.5-VL 逐帧描述**冻结一次**，两 backend 复用同一份（均 1872 B/帧）|
| 公平性 | 同一 fixture、同分辨率、同 prompt、seed=0；唯一变量 = 接收端模型 |
| 评估 | CLIP（主判据）+ PSNR/SSIM/LPIPS（参考）+ 目视连续帧 |
| 总耗时 | ~3.33h（VLM 冻结 ~84min + klein 49min + Z-Image 61min + 评估） |

## 2. 定量结果（250 帧）

| 指标 | klein | Z-Image | 解读 |
|---|---|---|---|
| **CLIP Score** ↑ | **32.22** | 30.03 | klein 语义/prompt 对齐更高 |
| SSIM ↑ | 0.623 | **0.812** | Z-Image 结构保真显著更高 |
| LPIPS ↓ | 0.516 | **0.408** | Z-Image 感知上更贴原图 |
| PSNR ↑ | 14.67 | **15.39** | 同上（生成式下均偏低，仅参考） |
| 速度 s/帧 | **11.73** | 14.71 | klein 4 步 vs Z-Image 9 步 |
| 峰值显存 | **18.53GB** | 20.3GB | klein 更省（24GB 余量大） |
| 失败帧 | 0/250 | 0/250 | 两路全成功 |

> 指标画像与 H1 单帧结论高度一致：**klein「语义对、结构飘、画质艳」，Z-Image「结构稳、更贴原、画质平」**。CLIP 衡量「画得像不像 prompt 描述的场景」，klein 赢；SSIM/LPIPS 衡量「像不像原始那一帧」，Z-Image 赢。

## 3. 关键发现：时间一致性（klein 作主线的决定性问题）

抽连续 8 帧（120–127，此段原始视频近乎静止）拼条带对比，**这是单帧 IoU/CLIP 指标无法暴露、却决定 klein 能否作主线的维度**：

- 原始（`compare/strip_orig_120-127.png`）：场景静止，帧间平滑。
- **klein（`compare/strip_klein_120-127.png`）：剧烈闪烁**——天空在「晴空 ↔ 大片积云」间狂跳、车辆数量与位置跳变、远山形状与地面纹理每帧重构。**原始静止，klein 输出却像在「每帧重新想象一遍这个场景」。**
- Z-Image（`compare/strip_zimage_120-127.png`）：**也有闪烁但明显更轻**——构图/车辆位置较稳定（ControlNet 锚定 Canny 结构），主要变化在光照/天空（偶有突现强光帧）。

**机理**：两者都逐帧独立生成、都会闪；但 Z-Image 的 ControlNet 把每帧锚到 Canny 结构上，构图被钉住、漂移受限；klein 无视 Canny 精细结构、纯靠 prompt 重新构图，**缺少跨帧锚点 → 漂移失控**。

**逐帧 A/B**（`compare/grid_0000..0249.png`，orig｜canny｜klein｜zimage）：单帧看 klein 画质惊艳、构图常大致对（车辆方位偶尔贴），但正是「云/车貌/山纹」这些精细元素逐帧重构，连成视频即为闪烁源。

## 4. 对 klein 主线决策的影响

- **drop-in 形态：klein 不可用作视频主线**——时间一致性是视频的硬指标，当前 klein 漂移过重。
- **但不否决**：klein 的单帧质量与显存优势是真实的，H1 §2 与本报告 §0 的判据一致——**klein 是否可作主线，押在「时间一致性补偿」上**。
- **决定性下一步 = 阶段 2 参考帧**（设计 §4）：用 klein 原生 `image=[Canny, 参考帧]` 通道，把「间隔原始关键帧 / 上一帧输出」当锚，看能否把 §3 的剧烈漂移压到可用。**这是 klein 主线成立与否的真正裁决点**。
- 决策可逆：若阶段 2 参考帧仍压不住漂移，回退 Z-Image 备选（其结构稳定性本就更适合无补偿场景）。

## 5. 工程留档

- **显存**：klein bf16+offload 在 896×496 峰值仅 18.53GB（smoke 一次通过，无需 vae_tiling）。**24GB 上 klein 分辨率余量充足**，之前「768 已近 OOM」的估计偏保守——后续可上 1024+ 或为超分留更大余量。
- **速度**：klein 11.73s/帧（含 offload 搬运开销，4 步）；远未达关键帧周期目标（~1-1.5s），速度优化仍是 7 月主攻（与本结论正交）。
- **harness**：`run_ab.py` 完全托管单脚本（流式读窗口规避坏时间戳、smoke 有界锁分辨率、冻结 prompt 保 A/B 公平、每 backend 独立保护、崩溃写 partial+sentinel），可复用于阶段 2 对比。
- **坑**：源 mp4 容器 `Duration: N/A`，ffmpeg 基于时间的 `-ss/-to` 裁剪取不到帧 → 改 imageio 流式按帧号取窗口。

## 6. 验收

- ✅ 真实 video→video（250 帧、原生 fps）下 klein vs Z-Image 公平 A/B，冻结 prompt + 同分辨率 + 同 fixture。
- ✅ 定量（CLIP/PSNR/SSIM/LPIPS + 速度 + 显存）+ 目视（连续帧条带 + 逐帧网格）双重证据。
- ✅ 回答关键风险：**klein drop-in 时间一致性极差，需阶段 2 参考帧补偿**，给出明确裁决点。
- ⏭ 阶段 2（参考帧）：跑完暂停，与负责人据本报告定参考帧间隔 N、来源、relay 透传等细节后实现。
