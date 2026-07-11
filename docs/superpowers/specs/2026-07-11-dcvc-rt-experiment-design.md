# DCVC-RT 神经编解码实验设计

> 日期: 2026-07-11
> 状态: 已确认
> 对应: EXPERIMENT_BRIEF.md ② DCVC-RT 神经编解码

## 1. 背景与目标

基于 #68 调研报告将 DCVC-RT 列为就绪度"高"的候选方案，本实验验证 DCVC-RT 在驾驶视频素材上的实际表现，并与传统 H.265 编码做头对头对比。

**核心问题**：
1. DCVC-RT 在驾驶素材（大背景运动）上是否稳定？
2. ≤1Mbps 下的主观质量和 PSNR 与 H.265 对比如何？
3. 单卡 24GB 上的实际吞吐（fps）？
4. 是否即插即用（预训练权重可下载、依赖无冲突）？

## 2. 范围

| Phase | 内容 | 预计耗时 |
|-------|------|----------|
| Phase 1 | 前置门禁：仓库状态、预训练权重、依赖兼容性、最小示例跑通 | 15 min |
| Phase 2 | 编解码管线 + H.265 头对头对比 | 1-2 h |

Phase 3（大运动稳定性深度评估）融入 Phase 2 — 测试素材选取时覆盖大背景运动片段，跑编解码时自然观察到稳定性表现。

## 3. 实施方案

采用方案 A：独立实验脚本，放在 `experiments/dcvc-rt/` 下，直接 import 项目现有 `evaluation` 模块。实验结束后如 DCVC-RT 可行，后续升级为 CLI 子命令。

## 4. 目录结构

```
experiments/dcvc-rt/
├── README.md              # 实验说明：背景、使用步骤、结论
├── run_dcvc.py            # 主脚本：编码+解码+测量
├── compare_h265.py        # 对照脚本：ffmpeg H.265 同码率编码+评估
├── results/               # 实验结果（.gitignore）
│   ├── dcvc_metrics.json
│   ├── h265_metrics.json
│   └── frames/            # 解码帧抽样
└── .gitignore
```

## 5. 数据流

```
测试视频(.h265 → ffmpeg → PNG 帧序列)
    │
    ├──▶ run_dcvc.py
    │    1. DCVC-RT 编码 → .bin（压缩码流）
    │    2. DCVC-RT 解码 → 还原帧(.png)
    │    3. 测量：编码延迟、解码延迟、码率、PSNR/SSIM/LPIPS
    │    4. 输出 → results/dcvc_metrics.json
    │
    └──▶ compare_h265.py
         1. ffmpeg H.265 编码（CRF 扫档匹配 DCVC-RT 实际码率）
         2. ffmpeg 解码 → 还原帧
         3. 测量：编码延迟、解码延迟、码率、PSNR/SSIM/LPIPS
         4. 输出 → results/h265_metrics.json
```

两条脚本各自独立运行，结果在 README 中汇总为对比表。

## 6. 测量指标

| 指标 | 工具 | 说明 |
|------|------|------|
| PSNR (dB) | `pixel_metrics.compute_psnr` | 像素级保真度 |
| SSIM | `pixel_metrics.compute_ssim` | 结构相似度 |
| LPIPS | `perceptual_metrics.compute_lpips` | 感知质量 |
| 码率 (Mbps) | 编码输出文件大小 ÷ 视频时长 | 实际比特率 |
| 编码延迟 (ms/frame) | wall-clock 计时 | 含预处理 |
| 解码延迟 (ms/frame) | wall-clock 计时 | 含后处理 |

不使用 CLIP Score — 像素级编解码不涉及语义理解。

## 7. 对比方法

- DCVC-RT 以目标码率参数编码，记录实际码率
- H.265 用 ffmpeg CRF 扫档找到与 DCVC-RT 实际码率最接近的配置，确保同码率对比
- 两条管线用相同帧序列输入，逐帧对齐算 PSNR/SSIM/LPIPS
- 输出格式：两个 JSON 文件 + 终端对比汇总表

## 8. 测试素材

首选：`resources/test_videos/C104/20260115121711.h265` 及其 prepared 10s 片段。

源文件为 .h265 裸码流，需先用 ffmpeg 解码为 PNG 帧序列作为 DCVC-RT 输入。

## 9. Phase 1 门禁检查清单

- [ ] 仓库状态：clone DCVC 官方仓库，确认最新 commit、release、README 质量
- [ ] 预训练权重：确认 checkpoint 下载链接可用
- [ ] 依赖兼容：与项目 PyTorch 2.9+/CUDA 13.0 无冲突
- [ ] 最小示例：5 分钟内跑通单张图编解码

四项全绿 → 进入 Phase 2。任一红灯 → 记录到 `results/errors.log`，产出"可行性受阻"备忘。

## 10. 容错策略

- DCVC-RT 安装失败 → 记录错误信息，不阻断后续
- OOM → 降分辨率重试（720p → 480p），记录实际配置
- ffmpeg 对照管线独立于 DCVC-RT，任一条挂不影响另一

## 11. 关键约束

| 维度 | 目标 |
|------|------|
| 带宽 | ≤1Mbps |
| 延迟 | 实时（论文宣称 1080p 100+fps，需实测） |
| 部署 | 单卡 24GB（RTX 4090） |
| 许可 | MIT（待确认） |
| 场景 | 驾驶视频，大背景运动 |

## 12. 关键资源

- DCVC 官方仓库：https://github.com/microsoft/DCVC
- #68 调研报告 §6.4（神经编解码细目）
- 项目评估模块：`src/semantic_transmission/evaluation/`
