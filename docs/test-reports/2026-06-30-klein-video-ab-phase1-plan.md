# 阶段 1 测试方案：klein vs Z-Image video→video A/B（2026-06-30）

> 上游：[设计](../superpowers/specs/2026-06-30-klein-receiver-backend-design.md) §6 ｜ [实现计划](../superpowers/plans/2026-06-30-klein-receiver-backend.md) Task 7
> 结论报告（产出后另写）：`2026-06-30-klein-video-ab-phase1.md`
> Harness：`scripts/poc/klein_ab/run_ab.py`（PoC 工具，仿 `scripts/poc/h1_h2/` 先例提交）

## 0. 目标与判据

在**真实 video→video 流程**下公平对比 klein（关键帧主线候选）与 Z-Image（现役备选），回答：
klein 单帧结构弱（H1 IoU 0.069）在整段视频里表现如何——**帧间闪烁/构图漂移**有多重、**单帧视觉质量**是否优于 Z-Image。

- **主判据**：CLIP Score（prompt-图像对齐，维度无关）+ **目视并排**（闪烁/漂移/质量）。
- **参考记录**：PSNR/SSIM/LPIPS（对生成式近乎无意义，仅留档），每帧耗时、峰值显存。
- 本阶段**不含**参考帧补偿（阶段 2），结论用于决定是否进阶段 2。

## 1. 总体策略：受控 harness，而非裸 CLI

`scripts/poc/klein_ab/run_ab.py` 统一编排，确保三件事同时成立：

1. **冻结 prompt**：VLM 逐帧描述**只跑一次** → 存盘 → 两 backend **复用同一份** → prompt 不是变量。
2. **分辨率先锁后跑**：smoke 先锁定能扛的工作分辨率 R，再烘焙正式 fixture → **长跑不中途 OOM**。
3. **fixture 同源**：两 backend 喂同一份已降到 R 的输入 → 真·同分辨率公平对比。

## 2. 输入与 Fixture

- 源：`resources/test_videos/视频记录/20251109134829.mp4`（1920×1080，HEVC，~25fps）。
- 片段：**第 20–30s 这 10 秒**；**保留原生帧率 25fps** → ~250 帧。
- 空间：仅**降分辨率**到工作分辨率 R（长边 R、保宽高比、不在送端前预处理画质——这是实验夹具，
  规避 klein 1080p OOM；生产仍"输入原始视频"）。
- ffmpeg 烘焙（R 由 smoke 锁定后代入）：
  ```bash
  ffmpeg -ss 20 -t 10 -i <源> -vf "scale=R:-2" -r 25 -an -c:v libx264 -crf 18 fixture.mp4
  ```
  `scale=R:-2` 保宽高比、高取偶数；harness 内部 `fit_working_size` 再保证 16 倍数。

## 3. 执行流水

| 步 | 动作 | 产出 | 健壮性 |
|---|---|---|---|
| ① smoke | fixture 前 8 帧、仅 klein、`max_side` 从 768 起 | 锁定工作分辨率 R | OOM 有界回退：768→640→(开 vae_tiling)；3 档内不通则记录失败退出，**不无限重试** |
| ② fixture | 按 R 烘焙正式 10s/25fps 片段 | `fixture.mp4` + `fixture_frames/*.png` | 解码失败立即报错退出 |
| ③ 冻结 prompt | QwenVLSender 逐帧 describe | `prompts.json`（receiver_summary 格式） | 存盘后**立即 unload VLM** 释放显存 |
| ④ A/B 主跑 | klein、diffusers 各 `process_batch`（冻结 prompt，seed=0） | 各 `frames/*.png`+`out.mp4`+`summary.json` | **每 backend 独立 try/except**，一个崩不影响另一个；跑完即 unload |
| ⑤ 评估 | 各 backend `evaluate_video.py` + 目视网格 | `eval/*.json`、`compare/grid_*.png` | 评估失败仅记录、不阻断 |

**显存编排**：VLM→unload→klein→unload→Z-Image，任一刻只一个大模型驻 GPU。
**决定性**：seed=0 两 backend 一致；VLM greedy 解码。

## 4. 产物目录 `output/poc/klein-ab-phase1/`（gitignored）

```
fixture/fixture.mp4 + fixture_frames/*.png
prompts.json                                   # 冻结 prompt + 语义码率统计
klein/  {frames/*.png, out.mp4, summary.json}  # summary 含每帧耗时
zimage/ {frames/*.png, out.mp4, summary.json}
eval/   {klein_eval.json, zimage_eval.json}
compare/grid_*.png                             # orig｜canny｜klein｜zimage 抽样并排
run.log / err.log                              # 全程日志
results.json                                   # 总汇总（见 §5）
DONE                                           # sentinel：完成（或 DONE.partial 崩溃部分完成）
```

## 5. 记录的数据（`results.json`）

- 工作分辨率 R + OOM 处置历史（哪档通过/回退）
- 每 backend：总耗时、均 s/帧、逐帧耗时、**峰值显存** `torch.cuda.max_memory_reserved()`
- CLIP/PSNR/SSIM/LPIPS 均值（每 backend）
- 帧数、fps、冻结 prompt 的语义码率（总字节/均字节每帧）
- 每 backend 成功/失败状态 + 失败原因（若有）

## 6. 监控与完全托管

- harness 用 PowerShell **`Start-Process` 脱离运行**（绕过后台 2min 限制），stdout/err → `run.log`/`err.log`，
  结束写 **`DONE`** sentinel（崩溃部分完成写 `DONE.partial`）。
- 主控用 **`Monitor` 守候 sentinel 出现**；另设**长心跳 `ScheduleWakeup` 兜底**，确保 Monitor 窗口过期也会被唤醒收尾。
- **无人值守保证**：脚本零交互输入；OOM 有界回退；每 backend 独立 try/except；**崩溃也写 partial `results.json`
  + `DONE.partial` + traceback 进 `err.log`**。下次回看：要么完整结果+报告，要么 partial+明确失败原因，
  **绝不"卡住没动 / 无限重试"**。

## 7. 其他注意点

- 公平性细节：fixture 已降到 R，klein `fit_working_size` 在 R 上 no-op，Z-Image 按边缘图（=R）生成 → 同分辨率。
- PSNR/SSIM 对 klein 生成式近乎无意义，**CLIP 为主判据**，其余留档。
- harness 作为 PoC 工具提交，不写单测（仿 `scripts/poc/h1_h2/`）。
- 时间预估：VLM ~15min + klein ~42min + Z-Image ~44min + eval ~5min ≈ **~110min**（R=768/250 帧；退 640 更快）。
- 磁盘：~250 帧 ×2 PNG + 视频，约数百 MB，`output/` gitignored。

## 8. 跑完后

按设计 §6：**暂停**，与负责人看 `results.json` + 目视网格，定是否进阶段 2（参考帧补偿）及细节（间隔 N、参考帧来源、relay 透传）。结论写入 `2026-06-30-klein-video-ab-phase1.md`。
