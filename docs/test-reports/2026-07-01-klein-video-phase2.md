# 阶段 2 结论报告：klein 参考帧时间一致性补偿（prev-only / prev+key × N12 / N25，2026-07-01，完成于 2026-07-02）

> 设计：[../superpowers/specs/2026-07-01-klein-phase2-reference-frame-design.md](../superpowers/specs/2026-07-01-klein-phase2-reference-frame-design.md)
> 计划：[../superpowers/plans/2026-07-01-klein-phase2-reference-frame.md](../superpowers/plans/2026-07-01-klein-phase2-reference-frame.md)
> 上游：[阶段 1 报告](2026-06-30-klein-video-ab-phase1.md)（裁决点：drop-in 时间一致性极差，押在参考帧补偿上）
> Harness：`scripts/poc/klein_ab/run_phase2.py` ｜ 产物：`output/poc/klein-phase2/`（gitignored）

## 0. 结论先行

在真实 video→video 流程下，用 klein 原生 `image=[canny, 参考帧]` 通道做时间一致性补偿，对比阶段 1 的
drop-in baseline（逐帧独立生成），**核心结论**：

1. **参考帧补偿决定性有效**：4 种配置（prev-only/prev+key × N12/N25）的生成帧间相邻帧 MAE 全部落在 **5.1–5.6**，
   相对 baseline 的 **22.16 降约 76%**——阶段 1 那种「每帧重新想象场景」的剧烈漂移被压住。**klein 作关键帧
   主线的关键风险（阶段 1 §4 裁决点）被证否，主线成立**。
2. **平滑的核心成分是 prev 链**：4 配置生成帧间平滑度几乎一致（prev 上一帧输出锚定相邻帧），说明治闪烁靠
   的是「上一帧输出当参考」，而非关键帧本身。
3. **恒挂关键帧（prev+key）> 仅 prev（prev-only）**：prev+key 在保真（SSIM/LPIPS/PSNR）与近静止段稳定性上一致更优——真实关键帧
   把生成帧持续拉回现实内容。**prev+key@N12 全指标最优**。
4. **关键帧越密（N12）> 越疏（N25）**：N12 保真更好但透传 pop 更多（delivered 抖动略高、码率略高）；N25
   码率低但生成帧离真值更远。
5. **显存/速度**：4 路均在 896×496、峰值 ≤19.78GB / 24GB、失败 0；参考帧越多越慢（prev-only 14–16s、prev+key 17s/生成帧）。
   速度优化是 7 月独立工作，与本质量/一致性验证正交。

**推荐**：klein 主线进阶段 3 productionize，默认配置 **prev+key@N12**（质量最优）或 **prev-only@N12**（时序几乎打平、
快 ~24%、少 0.6GB，速度敏感时选它）；N 是「保真↔码率」旋钮、prev+key/prev-only 是「保真↔算力」旋钮，均可用。

## 1. 实验设置

| 项 | 值 |
|---|---|
| 源/fixture | 复用阶段 1：`视频记录/20251109134829.mp4` 第 20–30s，**250 帧 @ 896×496**（`fixture_frames/`）|
| prompt | 复用阶段 1 冻结 VLM（`prompts.json`，逐帧、两阶段同一份）|
| baseline | 复用阶段 1 klein **drop-in** 输出（`klein/frames`，同下标对照，不重跑）|
| 变量 | reference_mode ∈ {prev-only=`prev`, prev+key=`prev_keyframe`} × keyframe_interval ∈ {12, 25} |
| 关键帧 | **透传原始帧**（不生成，直接交付）；N=12→21 帧、N=25→10 帧 |
| seed | 0（全配置一致）|
| 评估 | 时序：相邻帧 MAE + 光流 warp-error（两读：交付含关键帧边界 / 生成帧间排除边界，均并列原始对照）；质量：CLIP/SSIM/LPIPS/PSNR（两栏：全帧交付 / 仅生成帧同下标对比 baseline）；目视：逐帧网格 + 近静止 120–127 条带 |
| 公平性 | 同 fixture / 同 prompt / 同 seed / 同工作分辨率（896×496，smoke 锁定未回退）|

## 2. 时间一致性（决定性指标，gen_only = 仅生成帧、排除关键帧边界）

| 配置 | 相邻帧 MAE ↓ | warp-error ↓ | 相对 baseline 降幅 | 近静止 120–127 MAE ↓ |
|---|---|---|---|---|
| **baseline（drop-in）** | 22.16 | 22.13 | — | 23.20 |
| prev-only@N12 | 5.25 | 6.24 | **−76.3%** | 12.90 |
| prev-only@N25 | 5.19 | 6.24 | **−76.6%** | 13.27 |
| **prev+key@N12** | **5.13** | **6.02** | **−76.8%** | **11.13** |
| prev+key@N25 | 5.56 | 6.42 | −74.9% | 13.16 |
| *原始视频对照* | — | — | — | *1.11* |

- **生成帧间平滑度 4 配置基本打平**（5.13–5.56）：prev 链是治闪烁的主力，与 prev+key/prev-only、N 关系不大。
- **近静止段 prev+key@N12 最优（11.13）**：恒挂真实关键帧把该段拉得最稳；仍高于原始 1.11（残余闪烁存在，但较
  baseline 23.2 砍掉 **52%**）。
- 交付读数（含关键帧边界，见 §3）：N25 低于 N12（关键帧少→pop 边界少）。

## 3. 交付 vs 生成帧间（透传关键帧 pop 的量化）

| 配置 | 交付 MAE（含边界）| 生成帧间 MAE（排除边界）| 差值≈pop 贡献 |
|---|---|---|---|
| prev-only@N12 | 10.40 | 5.25 | 5.15 |
| prev+key@N12 | 9.77 | 5.13 | 4.64 |
| prev-only@N25 | 7.60 | 5.19 | 2.41 |
| prev+key@N25 | 7.66 | 5.56 | 2.10 |

- **透传关键帧带来周期性 pop**（真图↔生成帧外观跳变）：N12（21 帧）比 N25（10 帧）pop 更频、交付抖动更高。
- **prev+key 的恒定锚点略压 pop**（prev+key@N12 9.77 < prev-only@N12 10.40）：每帧都朝真关键帧靠，过渡更缓。
- 这是「密关键帧提保真」与「密关键帧增 pop」的权衡，目视条带 `strip_static_120-127.png` 可直观对照。

## 4. 质量指标（gen_only，与 baseline 同下标对比）

| 配置 | CLIP ↑ | SSIM ↑ | LPIPS ↓ | PSNR ↑ |
|---|---|---|---|---|
| baseline（drop-in） | 32.29 | 0.596 | 0.524 | 14.60 |
| prev-only@N12 | 32.70 | 0.605 | 0.440 | 15.65 |
| prev-only@N25 | 31.29 | 0.551 | 0.507 | 15.48 |
| **prev+key@N12** | **32.80** | **0.638** | **0.402** | **16.43** |
| prev+key@N25 | 31.11 | 0.601 | 0.462 | 16.11 |

- **prev+key@N12 全质量指标最优**：恒挂真实关键帧持续把生成帧拉向真实内容 → 保真最高。
- **N12 > N25**：密关键帧 = 生成帧离最近真值更近 = 保真更好；N25 的生成帧漂离更多。
- 全部配置 PSNR/LPIPS 均优于 baseline（drop-in）——参考帧补偿不仅治闪烁，也提升逐帧保真。

## 5. 速度 / 显存（896×496，smoke 锁定未回退）

| 配置 | 生成帧 | 透传帧 | 失败 | s/生成帧 | 峰值显存 | 总耗时 |
|---|---|---|---|---|---|---|
| prev-only@N12 | 229 | 21 | 0 | 14.03 | 19.15GB | 53.5min |
| prev-only@N25 | 240 | 10 | 0 | 15.99 | 19.15GB | 64.0min |
| prev+key@N12 | 229 | 21 | 0 | 17.41 | 19.78GB | 66.5min |
| prev+key@N25 | 240 | 10 | 0 | 17.27 | 19.78GB | 69.1min |

- 参考帧越多越慢：prev-only（2 参考）14–16s、prev+key（3 参考）17s/生成帧；显存 prev-only 19.15GB、prev+key 19.78GB，**均远低于 24GB**，
  多参考未触发 OOM/回退，之前的显存担忧进一步被推翻。
- 速度远未达关键帧周期实时目标（~1–1.5s），速度优化（fp8/降步数/TensorRT）是 7 月独立工作，与本结论正交。

## 6. 目视产物（gitignored，本地 `output/poc/klein-phase2/<label>/compare/`）

- `strip_static_120-127.png`：近静止段 orig / drop-in / 输出 三行并排连续帧条带——最直观看闪烁缓解与 pop。
- `grid_0000/0062/0124/0187/0249.png`：逐帧 `orig｜canny｜drop-in｜输出` 4 列并排。
- `out.mp4` + `frames/`：整段还原视频与逐帧 PNG。
- 四个 label：`prev_only_n12` / `prev_only_n25` / `prev_key_n12` / `prev_key_n25`。

## 7. 对 klein 主线决策的影响 + 下一步

- **裁决点已回答**：参考帧补偿把 drop-in 的剧烈漂移压到可用（时序降 ~76%、近静止砍 ~44–52%、质量不降反升）。
  **klein 作关键帧主线成立**，进阶段 3 productionize。
- **配置建议**：
  - **质量优先 → prev+key@N12**（`--reference-mode prev_keyframe --keyframe-interval 12`）：全指标最优。
  - **速度/算力优先 → prev-only@N12**：时序几乎打平 prev+key@N12，质量略低，快 ~24%、省 0.6GB。
  - **码率优先 → N25**：关键帧减半，但保真下降，仅在关键帧带宽是硬约束时选。
- **阶段 3 productionize（本报告不做）**：把选定时序策略从 harness 毕业到 `VideoPipeline` + relay 协议
  （关键帧低频传输），并接入 `semantic-tx video --backend klein`。
- **残余问题**：近静止段仍有残余闪烁（11–13 vs 原始 1.11）、透传关键帧周期 pop（尤其 N12）——可作 H3 帧间
  一致性专项后续优化。

## 8. 验收

- ✅ 4 配置真实 video→video（250 帧、原生 fps、896×496）公平跑通，冻结 prompt + 同 fixture + seed=0，失败 0。
- ✅ 定量（时序 MAE + warp-error 两读 + 质量四指标两栏 + 显存/速度）+ 目视（条带 + 网格）双证据。
- ✅ 回答裁决点：**参考帧补偿有效、klein 主线成立**；给出 prev-only/prev+key × N 的完整权衡与配置建议。
- ✅ 显存实测：多参考（含 3 参考 prev+key）峰值 ≤19.78GB / 24GB，无 OOM、无分辨率回退。
