# DCVC-RT 神经编解码实验设计

> 日期: 2026-07-11
> 状态: 已确认（经对抗性审核修正）
> 对应: EXPERIMENT_BRIEF.md ② DCVC-RT 神经编解码
> 可信度说明: #68 调研报告的对抗验证(Verify)阶段未跑完，其"高"就绪度评级是单源带引用发现 + 领域研判，非三票交叉验证定论

## 1. 背景与目标

基于 #68 调研报告将 DCVC-RT 列为就绪度"高"的候选方案，本实验验证 DCVC-RT 在驾驶视频素材上的实际表现，并与传统 H.265 编码做头对头对比。

**核心问题**：
1. DCVC-RT 在驾驶素材（大背景运动）上是否稳定？
2. ≤1Mbps 下的主观质量和 PSNR 与 H.265 对比如何？
3. 单卡 24GB（RTX 4090）上的实际吞吐（fps）？
4. 是否即插即用（预训练权重可下载、依赖可编译、CUDA 扩展可运行）？

## 2. 范围

| Phase | 内容 | 预计耗时 |
|-------|------|----------|
| Phase 1 | 前置门禁：仓库状态、预训练权重、CUDA 工具链与扩展编译、依赖兼容性、最小示例跑通 | 45-90 min |
| Phase 2 | 编解码管线 + H.265 头对头对比 | 1-2 h |

大运动稳定性评估融入 Phase 2：在测试素材中选取含有大背景运动的片段，使用量化指标（下述）而非"顺便观察"得出结论。若素材运动多样性不足，在结论中标注"单一片段，不具统计意义"。

## 3. 实施方案

采用方案 A：独立实验脚本，放在 `experiments/dcvc-rt/` 下，直接 import 项目现有 `evaluation` 模块。实验结束后如 DCVC-RT 可行，后续升级为 CLI 子命令。

DCVC-RT 通过 `subprocess` 包装其 CLI 脚本（`test_video.py`）调用，编解码延迟通过脚本内外分别计时拆分。选择 subprocess 而非 sys.path hack import 的原因：(1) DCVC-RT 无稳定 Python API；(2) 避免 import 路径污染和依赖冲突。

## 4. 目录结构

```
experiments/dcvc-rt/
├── README.md              # 实验说明：背景、使用步骤、结论
├── run_dcvc.py            # 主脚本：subprocess 调 DCVC-RT + 测量
├── compare_h265.py        # 对照脚本：ffmpeg H.265 同码率编码+评估
├── results/               # 实验结果（.gitignore）
│   ├── dcvc_metrics.json
│   ├── h265_metrics.json
│   └── frames/            # 解码帧抽样
└── .gitignore
```

## 5. 数据流

```
resources/test_videos/C104/20260115121711.h265 (裸码流)
    │
    └── [ffmpeg 解码为 PNG 帧序列]  ← 两条管线共享相同输入
         │
         ├──▶ run_dcvc.py
         │    1. subprocess: DCVC-RT 编码 → .bin（压缩码流）
         │    2. subprocess: DCVC-RT 解码 → 还原帧(.png)
         │    3. 测量：编码墙钟、解码墙钟、码率、PSNR/SSIM/LPIPS
         │    4. 输出 → results/dcvc_metrics.json
         │
         └──▶ compare_h265.py
              1. ffmpeg H.265 ABR 编码（-b:v 匹配 DCVC-RT 实际码率）
              2. ffmpeg 解码 → 还原帧
              3. 测量：编码墙钟、解码墙钟、码率、PSNR/SSIM/LPIPS
              4. 输出 → results/h265_metrics.json
```

## 6. 测量指标

| 指标 | 工具 | 说明 |
|------|------|------|
| PSNR-Y (dB) | `pixel_metrics.compute_psnr` | **仅 Y 通道**（亮度），与 DCVC-RT 论文一致，避免 RGB 色彩空间转换引入系统误差 |
| SSIM | `pixel_metrics.compute_ssim` | 结构相似度 |
| LPIPS | `perceptual_metrics.compute_lpips` | 感知质量，需确认与 PyTorch 2.9+ 兼容 |
| 码率 (Mbps) | 编码输出文件大小 ÷ 视频时长 | 实际比特率 |
| 编码延迟 (ms/frame) | wall-clock 计时（含文件 I/O） | DCVC-RT 侧用 subprocess 前后时间戳；H.265 侧用 ffmpeg 输出日志的 frame=xxx fps=xxx |
| 解码延迟 (ms/frame) | wall-clock 计时（含文件 I/O） | 同上 |

不使用 CLIP Score — 像素级编解码不涉及语义理解。延迟测量口径在 README 中标注各管线的起止点。

## 7. 对比方法

### 7.1 基线选择说明
选择 H.265/HEVC 而非 VVC/H.266 作为基线，原因是工具链可用性（ffmpeg 内建 libx265，无需额外编解码器）。注意 DCVC-RT 论文宣称的是"比 VTM/H.266 省 21% 码率"（非 H.265），本实验对比结果不直接等于论文声称。结论中标注对比对象为 H.265。

### 7.2 编码参数对齐

| 参数 | DCVC-RT | H.265 |
|------|---------|-------|
| 帧结构 | `--force_intra_period -1`（仅首帧 I，其余 P 帧）| `-g 9999`（超长 GOP，近似全 P 帧，对齐 DCVC-RT） |
| 码率控制 | 目标码率参数（lambda 控制）| `-b:v` ABR + `-maxrate` + `-bufsize`（不用 CRF 扫档，低码率时非线性严重） |
| 预设 | 默认 | `-preset medium`（作为基准点，另加 `-preset slow` 作为质量上限参考） |
| 输入 | PNG 帧序列（无二次编码损失） | PNG 帧序列（与 DCVC-RT 共用同一组 PNG 帧，消除二次编码污染） |

### 7.3 码率匹配策略
1. 先跑 DCVC-RT，记录实际码率 R_dcvc
2. H.265 用 `-b:v R_dcvc` ABR 模式编码，记录实际码率 R_h265
3. 若 |R_dcvc - R_h265| / R_dcvc > 5%，微调 `-b:v` 重跑一次
4. 最终对比以实际码率为准（不强制完全相等，标注偏差百分比）

### 7.4 H.265 二次编码污染处理
源素材 `20260115121711.h265` 本身是 H.265 裸码流。两条管线均从同一组 ffmpeg 解码的 PNG 帧序列开始，因此 DCVC-RT 和 H.265 基线的输入起点相同（均为解码后的无损帧），消除了起点不对等的问题。

## 8. 测试素材

首选：`resources/test_videos/C104/20260115121711.h265` 及其 prepared 10s 片段。

素材限制说明：
- 单个片段无法覆盖全部驾驶场景多样性（急转弯、隧道、快速接近等）
- 若该片段的大运动场景不足，结论需标注"单一片段、场景受限"
- 大运动判定标准：计算帧间光流幅度（Farneback 或 RAFT），连续 30 帧以上光流均值超过全视频均值的 1.5 倍标记为"大运动片段"

## 9. Phase 1 门禁检查清单

### 9.1 环境准备
- [ ] 确认系统 CUDA 工具链版本（`nvcc --version`），记录与 CUDA 13.0 的差异
- [ ] 确认 g++/cmake/pybind11 可用（DCVC-RT CUDA 扩展编译依赖）
- [ ] 若 CUDA 13.0 编译失败，准备降级方案：独立 conda/uv 环境使用 CUDA 12.6 PyTorch

### 9.2 仓库与权重
- [ ] clone DCVC 官方仓库（`git clone https://github.com/microsoft/DCVC`），记录 commit hash
- [ ] 确认预训练权重下载链接可用（OneDrive），记录文件大小和下载耗时
- [ ] 确认 License（报告标注 MIT，以仓库实际 LICENSE 文件为准）

### 9.3 编译与兼容
- [ ] 安装 DCVC-RT Python 依赖（`pip install -r requirements.txt`），检查与项目 `pyproject.toml` 的版本冲突
- [ ] 编译 CUDA 扩展（`src/layers/extensions/inference/setup.py`），记录编译是否成功及耗时
- [ ] 编译产物 `inference_extensions_cuda` 可 import，确认使用自定义内核而非纯 PyTorch 回退

### 9.4 最小示例
- [ ] 跑通 `test_video.py` 单张图或短视频片段编解码，确认输出可解析
- [ ] 测量最小示例的编码+解码墙钟，作为后续全量测试的参考基线
- [ ] 若纯 PyTorch 回退性能已在最小示例中暴露明显慢，记录 fps 差值

四项全部绿灯 → 进入 Phase 2。任一红灯 → 记录到 `results/errors.log`，产出"可行性受阻"备忘（含具体错误信息和已尝试的解决方案）。

## 10. 性能预期校准

| 项目 | 论文值 | 本实验预期 | 校准理由 |
|------|--------|-----------|----------|
| 编码 fps (1080p) | 125.2 | 60-100 | A100→RTX 4090：显存带宽 2039→1008 GB/s，DCVC-RT 论文自述 memory I/O 是瓶颈；CC 8.0→8.9 调度差异 |
| 解码 fps (1080p) | 112.8 | 55-90 | 同上 |
| 码率节省 vs H.265 | -21%（vs VVC） | ≤21% | 对比对象从 VVC 退到 H.265，码率节省预期降低 |

## 11. 容错策略

- CUDA 扩展编译失败 → 尝试纯 PyTorch 回退实现，在结论中标注"未使用优化内核，性能不可比论文"
- DCVC-RT 安装/运行失败 → 记录完整错误信息，不阻断 H.265 对照管线
- OOM → 降分辨率重试（1080p → 720p → 480p），记录实际运行配置
- LPIPS 加载失败 → 跳过 LPIPS，仅输出 PSNR-Y + SSIM
- ffmpeg 对照管线独立于 DCVC-RT，任一条挂不影响另一

## 12. 关键约束

| 维度 | 目标 |
|------|------|
| 带宽 | ≤1Mbps |
| 延迟 | 实时（论文 A100 1080p 100+fps，本实验 RTX 4090 预期 60-100 fps） |
| 部署 | 单卡 24GB（RTX 4090） |
| 许可 | MIT（待确认） |
| 场景 | 驾驶视频，大背景运动 |

## 13. 关键资源

- DCVC 官方仓库：https://github.com/microsoft/DCVC
- #68 调研报告 §6.4（神经编解码细目），注意 §0 可信度说明
- 项目评估模块：`src/semantic_transmission/evaluation/`
