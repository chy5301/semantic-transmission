# 语义传输项目评估报告（草稿）

调研综合日期：2026-06-10 | 基于六线调研（接收端模型生态 / 连续帧解码 / 视频生成路线 / VLM 与领域进展 / 架构审计 / Issue Triage）

---

## 1. 执行摘要

**一句话结论：不换架构、先在现有 Z-Image-Turbo 栈上打通"img2img 链式 + 关键帧重置"的连续帧 demo，同时修掉两个被误诊为模型问题的工程缺陷（2048px 分辨率失控导致的 60s/帧、PNG 边缘图导致的 130KB/帧）；编辑型模型迁移目标定为 Qwen-Image-Edit-2511（而非组员提议的 FLUX.2-klein-9B），视频生成路线作为 3-6 个月的并行 PoC 而非立即切换。**

三条最重要的行动建议：

1. **立即修工程，不动模型**：分辨率 cap 到 1024（预计 60s→10s 量级）+ 边缘图转 1-bit/JBIG2（130KB→约 10KB，压缩比 1.8x→20x+）——两项合计几天工作量，收益超过任何换模型方案。
2. **连续帧走两阶段**：Phase A 现栈 img2img 链式 + 周期性关键帧重置（~1 周，零新模型）；Phase B 试点 Qwen-Image-Edit-2511（Apache 2.0、原生"上一帧+边缘图"双输入、ModelScope 可得）。FLUX.2-klein-9B 因**非商用许可 + 无 ControlNet** 两个硬伤不作主线。
3. **#41 改写后作为下一个 workflow 主轴**，把 #40 的 VRAM/生命周期约束作为输入；#30 文档死链单独开 docs PR 立即处理。

---

## 2. 接收端模型选型结论

### 2.1 24GB 主推荐：Qwen-Image-Edit-2511（GGUF Q5/Q6 + Lightning 4 步 LoRA）

线 1 与线 2 独立得出同一结论，理由高度一致：

- **唯一原生同时满足两个硬约束的模型**："上一帧（参考图）+ Canny 边缘图（sketch 条件）+ 文本"可直接作为多图输入，边缘/草图条件是 2509 起官方训练过的原生能力，无需外挂 ControlNet（[2509 模型卡](https://huggingface.co/Qwen/Qwen-Image-Edit-2509)、[官方 repo](https://github.com/QwenLM/Qwen-Image/blob/main/Qwen-Image-Edit-2509.md)）；2511 官方明确宣称缓解 image drift、强化多图一致性（[Qwen 博客](https://qwen.ai/blog?id=qwen-image-edit-2511)、[HF](https://huggingface.co/Qwen/Qwen-Image-Edit-2511)）。
- **Apache 2.0 + ModelScope 一方托管**，国内获取最顺；文本编码器是 Qwen2.5-VL-7B，与发送端 VLM 同款，有部署协同潜力。
- Diffusers `QwenImageEditPlusPipeline` + GGUF 分组件加载，与现有 `DiffusersReceiver` 技术栈同构（[GGUF 仓库](https://huggingface.co/QuantStack/Qwen-Image-Edit-2509-GGUF)、[diffusers issue #12891](https://github.com/huggingface/diffusers/issues/12891)）。

**待 PoC 验证的风险**（两线均标注）：① Canny 风格边缘图是否在 sketch 条件训练分布内；② "参考上一帧"是否导致运动幅度低估；③ GGUF + Lightning LoRA 在 diffusers（非 ComfyUI）下的组合兼容性；④ 速度——线 1 估 5-15s/帧（Lightning），线 2 估 30s~数分钟，**两者均为推测且不一致，PoC 第一件事就是实测**。

### 2.2 对组员 FLUX.2-klein-9B 提议的裁决

组员"更快"的说法**已核实属实**（4 步蒸馏，4090 上 1-2s/张），且确有原生多参考编辑能力。但三线一致确认两个硬伤：

1. **9B 为 FLUX.2-dev 非商用许可**，Apache 2.0 的只有 4B（[LICENSE](https://huggingface.co/black-forest-labs/FLUX.2-klein-9B/blob/main/LICENSE.md)）；
2. **无 ControlNet 生态**——alibaba-pai 的 Fun-Controlnet-Union 只兼容 FLUX.2-dev（32B），不兼容 klein（[官方 discussion #3](https://huggingface.co/alibaba-pai/FLUX.2-dev-Fun-Controlnet-Union/discussions/3)），"边缘图当参考图喂"属未验证推测。

显存口径说明（线 1 与线 3 表面冲突，实为精度不同）：bf16 约 29GB 确实放不下；但 GGUF Q8_0 transformer 仅 ~10GB（[unsloth GGUF](https://huggingface.co/unsloth/FLUX.2-klein-9B-GGUF)）或官方 fp8，24GB 可行。**裁决：klein 不作主线；若团队坚持要试，用 4B 版（Apache 2.0、~8.4GB）作 Phase B 的低成本对照组，验证"边缘图作参考图"的遵循度即可。**

### 2.3 对比表

| 维度 | Z-Image-Turbo（现状） | Qwen-Image-Edit-2511（主推荐） | FLUX.2-klein-9B（备选/对照） | FLUX.2-dev 32B（64GB+ 首选） |
|---|---|---|---|---|
| 参考图/编辑 | 无（Z-Image-Edit 至今未发布） | 原生 1-3 图输入，2511 主打一致性 | 原生多参考 | 原生多参考 |
| 边缘结构控制 | ControlNet Union 成熟（在用） | **原生 sketch/keypoint 条件** | 无（推测可用参考图替代，未验证） | Fun-Controlnet-Union（Canny） |
| 许可 | Apache 2.0 | Apache 2.0 | **非商用** | 非商用 |
| 24GB 可行性 | 宽裕（已验证） | Q4/Q5 GGUF 可行（20B，较紧） | Q8/fp8 可行 | 不可行（实质 64GB 档） |
| Diffusers | 成熟（已落地） | 官方 pipeline，GGUF 路径待 PoC | 0.37.1+ 官方支持 | 0.36+ |
| 国内获取 | ModelScope 一方 | ModelScope 一方 | ModelScope 官方仓库 | ModelScope |
| 速度 | 现 60s/帧（工程问题为主，见 §6） | 推测 5-30s/帧，需实测 | 最快（4 步，秒级） | 中 |

### 2.4 64GB+ 备选升级路径

1. **首选 FLUX.2-dev 32B + Fun-Controlnet-Union**：多参考编辑 + 成熟 Canny ControlNet 兼得，质量天花板最高（接受非商用许可）；
2. **次选 Qwen-Image-Edit-2511 FP8/BF16**：与 24GB 主线同栈零迁移，仅消除量化损失；
3. 观察项：HiDream-O1-Image（MIT，无 diffusers，1-2 季度后复查）；Z-Image-Edit（一旦发布即评估，切换成本最低，[官方 repo 仍标 "To be released"](https://github.com/Tongyi-MAI/Z-Image)）。

### 2.5 留在 Z-Image-Turbo 的机会成本

纯 T2I，"上一帧参考"这一规划核心功能**无法实现**；Z-Image-Edit 预告 7 个月未发布，社区已质疑其是否还会开源。但它仍有价值：ControlNet Canny 链路已验证、显存最宽裕、且是 Phase A img2img 链式的载体。**折中：Z-Image-Turbo 不退役，作为首帧生成/回退方案与 Qwen-Edit-2511 在 `DiffusersReceiver` 架构下按配置共存。**

---

## 3. 连续帧解码策略推荐

### 3.1 推荐路径：两阶段（采纳线 2 方案）

**Phase A（立即，~1 周，零新模型下载）**：现栈 img2img 链式
- 参照 `ZImageImg2ImgPipeline.prepare_latents`（diffusers 0.38 已收录，[官方文档](https://huggingface.co/docs/diffusers/api/pipelines/z_image)）自写"上一帧 latent 初始化 + strength 截断 + ControlNet 边缘条件"组合逻辑，约 50-100 行；社区有整合先例可借鉴（[z-image-control-turbo-unified](https://huggingface.co/elismasilva/z-image-control-turbo-unified-8-steps-v2)）。
- 附带收益：strength<1 时实跑步数按比例缩短，单帧时间反而下降。
- 上一帧参考采用**接收端本地状态方案**（线 5 推荐）：relay 协议零改动，Receiver 加 `reference_image` 关键字参数 + `last_frame` 状态 + `reset_sequence()`，metadata 加 `sequence_id`/`frame_index`。

**Phase B（2-3 周，可并行预研）**：Qwen-Image-Edit-2511 双参考 PoC，验证 §2.1 的四个风险点；klein-4B 作对照组可选。

**不推荐**：IP-Adapter/reference-only（Z-Image 无适配器，且只传语义风格不传空间布局，性价比低于直方图匹配 + 关键帧重置）。

### 3.2 漂移抑制（按成本递增）

1. **周期性关键帧重置（核心手段）**：每 N 帧发送端传真实压缩关键帧重置链条，N 即"码率 vs 一致性"工作点旋钮——与语义传输系统设计天然契合，也是学界"首帧锚 + 滚动窗口"主流配方（Rolling Forcing/LongLive）的工程化简化版；
2. strength 调参（经验区间 0.4-0.7，可按距关键帧帧数递增调度）；
3. 直方图匹配色彩校正（几行代码，抑制最常见的色偏漂移）;
4. 天然优势：每帧 Canny 来自真实视频帧，结构维度不随链条漂移（[FramePack 漂移机理](https://arxiv.org/abs/2504.12626)）。

### 3.3 实验设计（采纳线 2）

- 数据：3-5 段 16-64 帧连续片段（相机平移 + 物体运动两类）；
- 对照组：baseline 逐帧独立 / img2img 链 strength∈{0.4,0.55,0.7} / +关键帧重置 N∈{8,16,32} / Qwen-Edit-2511 双参考 / GT 视频（度量上界校准）；
- 指标（扩展现有 `evaluation/` 模块）：相邻帧 LPIPS + 光流 warping error（RAFT，永远报告相对 GT 的比值）；漂移速率 = 逐帧 LPIPS/PSNR 对帧序号的回归斜率；沿用 CLIP Score；系统指标含每帧字节数，画"码率 vs 漂移"权衡曲线；
- 判定标准：链式方案帧间指标显著优于 baseline，N=16 重置下漂移斜率接近零。

---

## 4. 视频生成路线建议

**这是六线中最大的结论冲突**：线 3 主张"主线立即切换到视频生成路线 A"，线 1/线 2 主张图像编辑路线为主线。

**我的裁决：现在不切换主线，视频路线作为 3-6 个月窗口的并行 PoC，设决策门。** 理由：

1. **延迟形态与目标场景冲突**：项目未来场景是无人车遥操作，块式 I2V 的首片段延迟 1 分钟+（HunyuanVideo 1.5 蒸馏版 75s/5s 片段，已核实）对操控端不可接受；逐帧流式是该场景的正确形态，线 3 自己的对比表也承认 B 路线"流式性好"。
2. **与 demo-first 原则冲突**：切视频模型是 pipeline 级架构大改（视频 VAE、片段 I/O、协议改造），而 Phase A 一周即可出连续帧 demo。
3. 线 3 最有力的论据是**码率**（每 5s 一个关键帧 vs 逐帧边缘图）——但该论据的前提"逐帧条件锁死码率下限"被线 4 部分削弱：边缘图压到 ~10KB/帧 + 低清缩略图 2-5KB 后，逐帧路线码率仍可降一个数量级以上，叙事并不破产。

**何时切换/并行启动**：满足任一条件即启动视频路线 PoC——① Phase A/B 实验显示逐帧路线漂移无法压到可接受水平；② 项目叙事需要"两个数量级压缩比"的展示；③ 64GB 硬件到位。届时按线 3 路径：先 HunyuanVideo 1.5 蒸馏版（14GB 起、Diffusers + ModelScope，[GitHub](https://github.com/Tencent-Hunyuan/HunyuanVideo-1.5)）打通"首帧+文本→5s 片段"，漂移则换 **Wan2.2-Fun-Control**（唯一"Canny 控制 + Diffusers + GGUF + ModelScope"四要素齐全方案，[Wan2.2](https://github.com/Wan-Video/Wan2.2)、[VideoX-Fun](https://github.com/aigc-apps/VideoX-Fun)）。不碰 CogVideoX（停滞）；勿采信"Wan 2.5/2.6 开源"传言（已核实为 SEO 垃圾内容）。

64GB+ 解锁：Wan2.2-I2V-A14B bf16 + VACE-Fun-14B（质量上限）或 LTX-2 全量（速度上限）。

---

## 5. 发送端 VLM 结论 + 条件压缩优化

### 5.1 VLM：升级到 Qwen3-VL-8B-Instruct，但排在工程修复之后

- 迁移成本极低（同 Qwen 系、transformers ≥4.57 稳定版、bitsandbytes int4 路径不变、ModelScope 可得）；收益对口：DeepStack 细粒度描述、Text-Timestamp Alignment 正是未来"关键帧差分描述"所需（[Qwen3-VL](https://github.com/QwenLM/Qwen3-VL)、[技术报告](https://arxiv.org/abs/2511.21631)）。
- 单机共存场景用 int4 8B 或直接 4B。Qwen3.5 观望（需 transformers main 分支）；MiniCPM-V 4.5 作"高帧率差分"专项备选。
- **优先级判断**：VLM 升级不挡任何主线功能，放在 1-2 月窗口末尾或顺带做。

### 5.2 130KB/帧 问题：分级压缩 + 缩略图 A/B

根因（待本地确认）：二值稀疏的 Canny 边缘图被存成 8-bit PNG。分级方案：

| 级别 | 方案 | 预期体积 | 时机 |
|---|---|---|---|
| L0+L1 | 1-bit PNG → JBIG2/CCITT G4 | ~10KB（130KB→13x） | **立即，一天内** |
| L2 | 降分辨率传输 + 接收端上采样 | 2-5KB | 与 §6 分辨率 cap 联动，顺带 |
| 替代/补充 | **低清彩色缩略图（64-128px WebP，2-5KB）** | — | 与 Phase A 实验并行 A/B |
| L3/L4 | 矢量化 / 学习式 NTC codec | KB 级以下 | 研究向，暂缓 |

**重点吸收线 4 的领域证据**：GVSC 实验表明"低清 RGB 首帧 + 文本"优于"边缘图 + 文本"（[arXiv 2502.13838](https://arxiv.org/html/2502.13838v1)），DiSCo 也以降质视频为主、sketch 为辅（[arXiv 2512.00408](https://arxiv.org/abs/2512.00408)）——本项目"边缘图为主"的条件设计应通过 A/B 实验重新检验，缩略图可能既省码率又补色彩。另：因果少步生成 + 上一帧条件已有学术背书（[arXiv 2602.13837](https://arxiv.org/abs/2602.13837)），与 §3 路线同向。

---

## 6. 架构评估

### 6.1 三个新需求的支撑度

| 需求 | 支撑度 | 关键缺口 |
|---|---|---|
| 接入新模型 | 中：`ModelLoader` 泛型接口干净，但 `DiffusersModelLoader` 实为 Z-Image 专用（`model_loader.py:65-104` 硬编码三个 Z-Image 类） | 新增 1 Loader + 1 Receiver 子类 + `create_receiver(backend=...)` 分发 + config 段，约 2-4 天 |
| 上一帧参考 | 中：`process()` 签名不容纳参考图，但加关键字参数向后兼容；`FrameInput.metadata` 有现成槽位 | **选"接收端本地状态"方案则 relay 协议零改动**；`TransmissionPacket` 字段数硬编码（`relay.py:78`），若走传输则是不兼容协议变更 |
| 视频帧序列 | 低（约 3/10）：无任何抽帧代码；"批量"是字典序目录批处理 | `VideoFrameExtractor`（cv2）+ metadata 加 frame_index + **修 `cli/receiver.py:102` 每包断连问题**（与发送端批量单连接连发疑似不匹配，强嫌疑 bug，需实测） |

### 6.2 #40 挡路判定

真正挡路的是**子问题 4（通信架构）× 子问题 2（生命周期）的交集**，且只挡视频帧序列；子问题 1（VRAM 临界）在换 9B/量化模型后压力反而减小。**结论：#40 不必前置整体解决，其子问题 1/2 作为 #41 brainstorm 的硬约束输入即可，通信架构统一留给下下个 workflow。**

### 6.3 60s/帧 性能疑点：大概率是工程问题而非模型问题

社区基准 Z-Image-Turbo 4090 上 1024²/8 步约 2.3s（[Thunder Compute](https://www.thundercompute.com/blog/z-image-turbo-comfyui)），与现状差 5-25 倍。嫌疑排序：① **生成分辨率失控**——`diffusers_receiver.py:74-78` 跟随边缘图原尺寸无 cap，测试报告自述跑在 2048px；② 计时窗口混入模型加载（`cli/demo.py:193-196`）；③ GGUF 在线反量化固有开销（约 1.5-3 倍，推测）。

> **本地核实补充（2026-06-10）**：当日 demo 实测（canyon_jeep.jpg，还原图 688×1216 ≈ 0.84MP，9 步）接收端耗时 60.9s——分辨率并未失控但耗时仍超基准 ~25 倍，且该计时确认包含模型冷加载。说明对小尺寸输入而言嫌疑 ②（计时混入加载）+ ③（GGUF 开销）是主因，嫌疑 ① 在大尺寸输入（如 2048px 测试报告场景）下叠加恶化。结论不变：先做计时打点分离（清单第 2 项），再判断分辨率 cap 与 GGUF 的真实占比。

**最小改动清单（性价比序）**：
1. 分辨率 cap 长边 ≤1024（预期降到 10s 量级，同时降低边缘图体积，一石二鸟）；
2. load 与推理分开打点（`SampleResult.timings` 有现成槽位）；
3. 实验"bf16 全精度 vs GGUF Q8"（6B bf16 约 12GB，24GB 放得下）；
4. Receiver 加 `reference_image` 参数 + 本地状态（为 Phase A 铺路）；
5. 修接收循环每包断连；metadata 加帧序字段。

---

## 7. Issue 处置清单

收录线 6 triage 表（16 个 open issue），按综合结论做两处微调（见表后注）：

| 编号 | 标题（缩写） | 分类 | 处置时机 |
|---|---|---|---|
| #41 | 换模型 + 连续帧双参考解码 | **A 主线** | 下一个 workflow 主轴；**启动前改写正文**（注 1） |
| #40 | 通信架构 + VRAM + 双端演示综合议题 | **A 主线** | 子问题 1/2 作 #41 约束输入；架构部分下下个 workflow |
| #30 | 用户文档死链 + 事实错误 | B（高紧迫） | A 类**立即独立 docs PR**（半天）；B 类两个 workflow 后统一刷 |
| #26 | HF 下载层不稳定 | B | #41 拉新模型时顺带做 ModelScope fallback |
| #28 | 输出路径无运行级隔离 | B | #41 连续帧实验前做最小版 `output/<task>/<timestamp>/` |
| #29 | GUI 缺接收端监听 Tab | B | 等 #40 架构定案，下下个 workflow |
| #17 | 量化依赖 platform markers | B | #41 动 pyproject 时顺带 |
| #36 | PSNR divide-by-zero warning | B | #41 跑评估前顺带（几分钟） |
| #37 | Windows 测试 UnicodeDecodeError | B | 下次动该测试文件时顺带 |
| #38 | batch_panel 参数 sprawl | B | #40 GUI 重构时顺带 |
| #39 | status/torch_dtype 裸字符串 | B | 下次改 receiver config 时顺带 |
| #32 | GUI 批量 Tab 无目录选择器 | B | #40 GUI 重构时顺带 |
| #35 | Relay 来源白名单 | B | 作 #40 relay 重构验收项 |
| #5 | GUI 运行记录持久化 | C | 建议关闭，#40 留备注 |
| #13 | 端到端面板日志冗余 | C | 建议关闭或 #40 顺手消除 |
| #34 | Relay 指定源端口 | C | 建议关闭（YAGNI） |

注 1（微调）：#41 正文需两处修正——① "在 ComfyUI 中的接入方式"已过时，改为 Diffusers 接入；② 候选模型从 FLUX.2-klein-9B 单一焦点改为"Qwen-Image-Edit-2511 主候选 + klein-4B 对照"，并补充 Phase A（现栈 img2img）为第一阶段交付物。
注 2（微调）：#36 从"顺带"升半级——Phase A 实验依赖评估输出干净，应在实验启动前完成。

---

## 8. 修订版 ROADMAP 草案（阶段三任务重排）

### 1-2 个月窗口（主题：工程修复 + 连续帧 demo 打通）

| 周 | 任务 | 对应 issue |
|---|---|---|
| W1 | 独立 docs PR 修死链；分辨率 cap + 计时打点 + 边缘图 1-bit/JBIG2 压缩（quick wins 三连） | #30A、(#41 前置) |
| W1-W2 | 输出运行级隔离最小版；PSNR warning 修复；视频抽帧 `VideoFrameExtractor` + frame_index metadata + 接收循环修复 | #28、#36 |
| W2-W3 | **Phase A：img2img 链式 + 关键帧重置 + 色彩校正**；评估模块扩展（帧间 LPIPS、warping error、漂移斜率） | #41 |
| W3-W5 | Phase A 对照实验（strength × N 扫描）+ "缩略图 vs 边缘图"A/B；产出测试报告 | #41 |
| W5-W8 | **Phase B：Qwen-Image-Edit-2511 GGUF PoC**（四个风险点验证）；klein-4B 对照可选；顺带 #26 ModelScope fallback、#17 | #41、#26、#17 |

里程碑：M1（W3）连续帧 demo 可演示且单帧 ≤15s、≤15KB/帧；M2（W8）Phase B 选型结论 + 决策门评审。

### 3-6 个月窗口（主题：架构收口 + 路线决策）

- **决策门（M2）**：依 Phase A/B 数据决定主线模型（Z-Image 链式 / Qwen-Edit-2511 / 触发视频路线 PoC 条件，见 §4）；
- #40 主轴 workflow：通信架构统一（单机=回环 socket）+ 模型生命周期收敛 + GUI 接收端监听 Tab（顺带 #29/#35/#38/#32/#13）；
- 视频路线 PoC（若决策门触发）：HunyuanVideo 1.5 → Wan2.2-Fun-Control；
- VLM 升级 Qwen3-VL-8B（差分描述预研一并做）；
- #30 B 类文档统一刷新；64GB+ 采购建议输出（依据 §2.4/§4 升级路径）；
- 持续观察：Z-Image-Edit 发布、Qwen3.5 进 transformers 稳定版、HiDream-O1、LTX-2 国内获取。

### 风险提示

Phase B 若四个风险点中 ①（Canny 不在 sketch 训练分布内）或 ②（运动幅度低估）实测不过关，回退路径是"Phase A 现栈链式 + 等 Z-Image-Edit"，不影响 demo 主线——这是两阶段设计的核心保险。

---

## 9. 下一个实施 workflow 启动建议

**主轴**：#41（改写后）——"连续帧解码 Phase A + 性能/码率工程修复"。

**范围切片（按依赖序）**：
1. Quick wins：分辨率 cap、load/推理计时分离、边缘图 1-bit + JBIG2、PSNR warning（#36）；
2. 帧序列基础：视频抽帧、frame_index/sequence_id metadata、接收循环每包断连修复、输出运行级隔离（#28 最小版）；
3. Phase A 核心：img2img + ControlNet 组合逻辑、接收端 `last_frame` 状态 + `reset_sequence()`、关键帧重置协议（metadata 标记）、直方图色彩校正；
4. 评估扩展：帧间 LPIPS、warping error、漂移斜率、码率统计；
5. 实验与报告：对照组矩阵 + 缩略图 A/B + 测试报告。

**明确不放进去的东西**：
- Qwen-Image-Edit-2511 迁移（Phase B 独立 workflow，避免"新模型下载/调参黑洞"拖死 Phase A 交付）；
- #40 通信架构统一、GUI 任何重构（#29/#32/#38）——等 Phase A 定型帧序列形态后再 brainstorm；
- 视频生成模型路线（决策门后才启动）；
- VLM 升级（不挡主线，独立小任务）；
- relay 协议 v2/握手（本 workflow 协议零改动是刻意设计）。

**启动前置动作**：改写 #41 正文（去 ComfyUI 表述、更新候选模型结论）；把 #40 子问题 1（24GB VRAM 临界）作为 brainstorm 硬约束输入；#30A docs PR 在 workflow 外先行合并。

---

### 附：核实状态总注

- **已核实**（来源见各节链接）：klein 发布/许可/无 ControlNet/显存档位；Qwen-Edit-2511 多图输入与原生 sketch 条件/ModelScope 可得；Z-Image-Edit 未发布；`ZImageImg2ImgPipeline` 存在；Wan2.2/HunyuanVideo 1.5/LTX-2 现状；Qwen3-VL transformers 支持；Z-Image-Turbo 社区速度基准；#40/#41 等 issue 内容；架构审计的全部代码行号证据。
- **已核实补充（2026-06-10 本地实测）**：边缘图确为 8-bit 灰度 PNG（L 模式，690×1227 约 100KB）——L0/L1 压缩建议成立；demo 计时含模型冷加载（见 §6.3 补充）。
- **未核实/推测（落地前必须实测）**：Qwen-Edit-2511 的 Canny 兼容性、运动幅度、GGUF+Lightning diffusers 兼容性与实际速度；klein"边缘图当参考图"可行性；60s/帧中模型加载占比；接收循环断连 bug（强嫌疑未复现）；Qwen3-VL-8B int4 实测显存；ControlNet Union 的 tile/低清条件支持。
