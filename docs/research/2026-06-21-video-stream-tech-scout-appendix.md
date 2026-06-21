# 视频流技术调研·四线原始结果（附录）

> docs/research/2026-06-21-video-stream-tech-scout.md 的溯源附录。

---

# 线1 帧生成模型实操

I have sufficient verified material. Writing the report now.

---

# 帧生成模型实操接入调研：FLUX.2-klein-9B 主线 + Qwen-Image-Edit-2511 对照

> 核实说明：以下"已核实"指有 HuggingFace 官方仓库 / GitHub / 模型卡直接佐证；"未核实/需 PoC"指仅有二手博客或社区说法、或我搜索未找到硬证据。今天 2026-06-21。

---

## 0. 一条贯穿全文的关键结论（先看这个）

**主线 klein-9B 的最大风险点，不是速度，而是"结构/几何约束的注入通道"。** 调研硬结果：

- **FLUX.2 klein 官方没有 ControlNet / Canny / depth 输入通道**（已核实：klein-9B 模型卡、官方 flux2 GitHub README 均无任何 Canny/depth/ControlNet 字样；它只有 `image=[...]` 的多参考图通道）。
- 唯一存在的 FLUX.2 ControlNet 是 `alibaba-pai/FLUX.2-dev-Fun-Controlnet-Union`，**官方只声明对 `FLUX.2-dev`，未声明支持 step-distilled 的 klein**（已核实模型卡）。你们现在 Z-Image 接收端用的正是同系列 `Z-Image-Turbo-Fun-Controlnet-Union`，但那是 Z-Image 的、不能直接迁到 klein。
- 反观对照组 **Qwen-Image 生态有成熟的 InstantX ControlNet-Union（canny/softedge/depth/pose 四合一）**，这是 klein 没有的能力。

→ 这直接动摇了任务背景里设定的"一致性核心思路 = 上一帧 + Canny + depth 引导 klein 生成当前帧"。**klein 路线下，Canny/depth 只能"当参考图塞进 `image=[...]` 列表里",靠模型自己理解,而不是经过专门训练的 ControlNet 注入——这条必须第一周 PoC 验证，找不到现成证据(我没找到)。** 详见第 1.4 节。

---

## 1. FLUX.2-klein-9B 接入实操

### 1.1 Pipeline 类与基础调用（已核实）

- Pipeline 类：**`Flux2KleinPipeline`**（klein-9B 模型卡）。
- KV-cache 优化变体：**`Flux2KleinKVPipeline`**（来自 `FLUX.2-klein-9b-kv` 仓库）。
- 蒸馏配置：**4 步、`guidance_scale=1.0`**（step-distilled + guidance-distilled）。基座非蒸馏版是 50 步。
- 文本编码器：8B Qwen3 text embedder（注意，这本身就要占显存）。
- 示例分辨率 `height=1024, width=1024`，模型卡未给出官方支持分辨率清单。

来源：[klein-9B 模型卡](https://huggingface.co/black-forest-labs/FLUX.2-klein-9B)、[flux2 官方仓库](https://github.com/black-forest-labs/flux2)

### 1.2 Multi-reference 调用 API（已核实，但有重要限制）

官方 discussion 给出的 verbatim 用法 —— **多张参考图就是塞进一个 list 传给 `image=`**：

```python
image = pipe(
    prompt="A man standing next to a mascot",
    image=[init_img, init_img2],      # 多参考图 = list
    height=1024, width=1024,
    guidance_scale=1.0,
    num_inference_steps=4,
    generator=torch.Generator(device=device).manual_seed(0)
).images[0]
```

**关键限制（已核实）**：

- **没有 per-image 权重参数，没有 reference vs base 的角色区分**。所有图在 list 里是平权的，模型自己从 prompt + 图判断每张图的作用。这意味着你无法用 API 显式说"第 1 张是上一帧基底、第 2 张是 Canny 约束、各占多少权重"——只能靠 prompt 描述 + 图本身排序。
- 角色控制只能在 **prompt 工程** 层做（社区做法：在 prompt 里点名 "the first image / the second image"）。

来源：[klein-9B multi-image discussion #6](https://huggingface.co/black-forest-labs/FLUX.2-klein-9B/discussions/6)

### 1.3 GGUF/fp8 量化与 24GB 配置（已核实）

- **fp8 官方仓库**：`black-forest-labs/FLUX.2-klein-9b-fp8`（官方出品，非社区）。
- **GGUF 仓库**：`unsloth/FLUX.2-klein-9B-GGUF`（Unsloth Dynamic 2.0，重要层升精度）。
- **24GB 可行性**：FP16 即可装进 24GB；FP8 配文本编码器 offload 可降到 16GB 级。RTX 4090 24GB 跑 fp8 + 全文本编码器在 GPU，峰值约 14–16GB。
- 你们的 RTX 5090 24GB 跑 **fp8 无压缩妥协**完全够用。建议起步直接用官方 `klein-9b-fp8`，而不是 GGUF（GGUF 主要为 8–12GB 小卡省显存，5090 没必要牺牲质量/速度）。

来源：[fp8 仓库](https://huggingface.co/black-forest-labs/FLUX.2-klein-9b-fp8)、[GGUF 仓库](https://huggingface.co/unsloth/FLUX.2-klein-9B-GGUF)、[VRAM 指南](https://willitrunai.com/blog/flux-2-klein-9b-vram-requirements)（VRAM 数字为二手博客，**未核实**，建议 PoC 实测）

### 1.4 单帧延迟数据（部分核实，部分需 PoC）

| 配置 | 单帧延迟 | 核实度 |
|---|---|---|
| 9B 蒸馏，RTX 5090，4 步 | **~1.2–2.0 s** | 二手博客（LucasGraphic / GLM-Image），**未核实**，但与任务背景的 "1-2s/帧" 一致 |
| 9B，RTX 4090 | "< 0.5s"（多处宣称） | 二手博客，**存疑**——与 5090 的 1.2-2s 矛盾，"<0.5s" 很可能是 4B 或纯 t2i / 低分辨率，**勿采信，需实测** |

来源：[LucasGraphic klein-KV](https://lucasgraphic.com/posts/flux2-klein-9b-kv-explained-speed-quality-gpus)、[GLM-Image](https://glm-image.cc/blog/flux-2-klein-english/)

**务实判断**：以 **5090 上 ~1.5s/帧** 作为规划基线（与背景已知值吻合）。这意味着大模型层 ≈ 0.6–0.8 fps，离 ≥10fps 差 10–15 倍——**保底版（离线视频文件）这个速度可接受；目标版必须靠插帧/超分补足，见 DLSS 部分（另一份调研）**。

### 1.5 ⭐ 最关键：Canny/depth "当参考图喂进去"的结构遵循度

**搜索结论：没有找到任何官方说明、社区评测或案例，证明把 Canny/depth 图塞进 klein 的 `image=[...]` 能产生 ControlNet 级的结构/几何约束遵循。标记为「无证据，需 PoC」。**

具体证据链：

1. klein 模型卡、官方 flux2 GitHub README **均无 Canny/depth/ControlNet 任何字样**（已核实）。klein 的 `image=` 通道是为"参考图编辑/多图融合"训练的，**不是为"线稿→图"这类结构条件训练的**。
2. 唯一的 FLUX.2 ControlNet（`alibaba-pai/FLUX.2-dev-Fun-Controlnet-Union`，支持 Canny/HED/Depth/Pose/MLSD，`controlnet_conditioning_scale` 0.65–0.80）**官方只对 dev，未声明 klein 兼容**（已核实模型卡）。dev 是 50 步非蒸馏，单帧远慢于 klein，把它当 klein 主线不现实。
3. 因此 klein 路线下，结构约束有两条不确定路径，都需 PoC：
   - **(A) 把 Canny/depth 当普通参考图塞进 list**：能不能让模型"照着边缘画"——无证据，凭直觉遵循度会明显弱于专用 ControlNet。
   - **(B) 改用 FLUX.2-dev + Fun-ControlNet**：结构遵循有保障，但慢、且偏离"klein 主线"。

来源：[FLUX.2-dev-Fun-Controlnet-Union](https://huggingface.co/alibaba-pai/FLUX.2-dev-Fun-Controlnet-Union)、[klein-9B 模型卡](https://huggingface.co/black-forest-labs/FLUX.2-klein-9B)

**这一条是主线成败关键。建议第一周 PoC 第一优先级就验证 (A)，不通过则触发回退（见第 4 节）。**

---

## 2. Qwen-Image-Edit-2511 对照

### 2.1 接入要点（已核实）

- Pipeline 类：**`QwenImageEditPlusPipeline`**（Plus 版支持多图）。
- 多图输入：同样是 **list** —— `"image": [image1, image2]`。
- 推理参数：示例 **`num_inference_steps=40`、`true_cfg_scale=4.0`**（注意：非蒸馏，比 klein 慢一个量级，这是 klein 的最大优势）。
- GGUF：`unsloth/Qwen-Image-Edit-2511-GGUF` 可用。
- 2511 相对 2509 的改进点（官方）：**抑制 image drift、角色一致性、几何推理增强、内置 LoRA**——这些"减少漂移/几何推理"特性对帧间一致性是利好。

来源：[Qwen-Image-Edit-2511 模型卡](https://huggingface.co/Qwen/Qwen-Image-Edit-2511)

### 2.2 ⭐ Qwen 相对 klein 的决定性优势：原生结构条件生态

- Qwen-Image 有成熟的 **`InstantX/Qwen-Image-ControlNet-Union`**，Pipeline `QwenImageControlNetPipeline` + `QwenImageControlNetModel`，**原生 canny / soft edge / depth / pose 四合一**，`controlnet_conditioning_scale` 推荐 0.8–1.0。这正是任务背景里需要的"Canny + depth 引导"能力，klein 没有对应物。已核实代码：

```python
from diffusers import QwenImageControlNetPipeline, QwenImageControlNetModel
controlnet = QwenImageControlNetModel.from_pretrained(controlnet_model, torch_dtype=torch.bfloat16)
pipe = QwenImageControlNetPipeline.from_pretrained(base_model, controlnet=controlnet, torch_dtype=torch.bfloat16)
```

- **但有一个必须 PoC 验证的兼容性缺口**：InstantX ControlNet-Union 模型卡明确写的是 **Qwen-Image（文生图基座），未声明支持 Qwen-Image-Edit / Edit-2511**。也就是说"ControlNet + Edit 编辑（上一帧基底）"能否同时用，**diffusers 里需要实测**。有二手博客（RunComfy 称 2511 "supports ControlNet-based conditioning with depth/edges/keypoints"），但**未在官方核实**，标"需 PoC"。

来源：[InstantX Qwen-Image-ControlNet-Union](https://huggingface.co/InstantX/Qwen-Image-ControlNet-Union)、[Qwen ControlNet 教程](https://www.stablediffusiontutorials.com/2025/09/qwen-image-controlnets.html)、[RunComfy 2511](https://www.runcomfy.com/models/qwen/qwen-image/qwen-image-edit-2511)（后者未核实）

### 2.3 逐项对比表

| 维度 | FLUX.2-klein-9B | Qwen-Image-Edit-2511 |
|---|---|---|
| Pipeline | `Flux2KleinPipeline` / `Flux2KleinKVPipeline` | `QwenImageEditPlusPipeline` |
| 多图输入 | `image=[...]` list，**无 per-image 权重** | `image=[...]` list，**双通道可分别控制**（VL 语义 + VAE 外观，见 3.3） |
| 推理步数 | **4 步**（蒸馏） | **40 步**（非蒸馏） |
| 单帧速度(5090) | **~1.5s（快 ~10x，主线核心理由）** | 数秒~十几秒（未核实，按 40 步推断显著慢） |
| 原生 Canny/depth 条件 | **无**（需 PoC 当参考图塞，或退 dev+Fun-CN） | **有生态**（InstantX ControlNet-Union），但与 Edit 变体的联用需 PoC |
| 一致性专项 | Consistency LoRA（社区，减 pixel drift） | 官方 2511 主打 anti-drift / 几何推理 |
| 许可 | 非商用（内部预研可接受） | Apache-2.0 类（更宽松，未逐字核实） |

**一句话定位**：klein 用速度换条件可控性；Qwen-Edit-2511 用速度换条件可控性 + 一致性。两者恰好互补，**强烈建议第一周双线并跑 PoC，而不是只赌 klein**。

---

## 3. "上一帧为基底"的实现机制

### 3.1 两种机制的本质区别

- **img2img（latent 初始化）**：把上一帧 VAE encode 成 latent，作为采样起点，配 `strength`（0–1，越高越偏离原图）。优点：天然继承上一帧的像素布局，帧间一致性好、运动幅度小；缺点：高 strength 才能跟上大运动，低 strength 又容易"贴死"。
- **reference-image 通道**：上一帧作为 `image=[...]` 里的一张参考，latent 从 **空白** 初始化，模型靠 cross-attention 参考它。优点：能接受多张条件图（上一帧 + Canny + depth 同时进），不"贴死"；缺点：像素级一致性弱于 latent init，易有 drift/flicker。

来源：[Qwen multi-image 工作流](https://stable-diffusion-art.com/qwen-image-edit-multiple-images/)、[Qwen 双通道架构](https://help.scenario.com/articles/5117943220-advanced-editing-with-qwen-models)

### 3.2 klein 的机制现状（已核实有坑）

- klein **9B 支持 img2img（带 strength）**，但 **4B 实测"卡在 edit 模式、refine/strength 不生效"**（krita-ai-diffusion issue #2392）。你们用 9B，没踩这个坑，但说明 klein 系列的 img2img 行为不稳定、需实测确认 strength 真的起作用。
- klein 的多参考是 **reference 通道**（空白 latent + list），不是 latent init。所以若要"上一帧 latent init + Canny/depth 参考"混用，需要在 diffusers 里自己拼（img2img 起点 + 额外参考图），**这条组合 API 不是开箱即用，需 PoC**。

来源：[krita issue #2392](https://github.com/Acly/krita-ai-diffusion/issues/2392)

### 3.3 Qwen-Edit 的机制现状（更适合本场景）

Qwen-Image-Edit 是**双通道并行**：输入图同时进 (a) Qwen2.5-VL 走 ~384px 语义 token、(b) VAE encoder 走输出分辨率像素 latent，**两路可按图分别控制**。这天然契合本场景——上一帧走 VAE 外观保真、Canny/depth + prompt 走语义/结构。这是比 klein "平权 list" 更精细的控制粒度。

来源：[Qwen 双通道](https://help.scenario.com/articles/5117943220-advanced-editing-with-qwen-models)（架构描述为二手，**未逐字核实**，建议读 diffusers 源码确认）

### 3.4 对帧间一致性的建议

遥操作场景运动幅度通常不大（车辆平移/小转向），**优先 latent-init（img2img）+ 低 strength** 抓一致性，再叠 Canny/depth 参考约束结构。"锚定首帧/上一帧编辑结果作基底"是社区公认抗 flicker 手段（FLUX 系亦有 Consistency LoRA 专门压 pixel drift）。

来源：[Civitai klein Consistency LoRA](https://civitai.com/articles/27410/flux2-klein-9b-consistency-lora)

---

## 4. 主线 klein-9B 第一周 PoC 最小验证清单

目标：用最少实验证伪/证实 klein 主线的 4 个核心假设。**任一红线不通过 → 当周切 Qwen-Image-Edit-2511 对照线。**

| # | 验证假设 | 实验做法 | 指标 | 通过线 / 回退线 |
|---|---|---|---|---|
| **H1（最高优先）** | klein 能把 Canny/depth 当参考图实现结构约束 | 固定一帧，把它的 Canny（你们已有 `LocalCannyExtractor`）+ depth(depth-anything) 塞进 `image=[...]`，prompt 描述场景，看生成图是否贴合边缘/几何 | 生成图 Canny 与输入 Canny 的**边缘 IoU / 重投影误差**；目视结构吻合 | 通过：边缘明显跟随（IoU 可量化设阈，如 >0.4）。**不通过（大概率）→ 立即上 Qwen InstantX ControlNet-Union，或 klein 退 dev+Fun-ControlNet** |
| **H2** | 5090 上单帧延迟 ≤2s | klein-9b-fp8，4 步，512×512 与 1024×1024 各测，含/不含冷加载分别计时 | 稳态单帧 ms（排除冷加载） | 通过：≤2s/帧；不通过：先压分辨率到 512、cap 输出，再不行说明背景里"非模型上限"判断有误，重排期望 |
| **H3** | "上一帧 latent-init + 低 strength" 帧间一致 | 取连续 8–16 帧真实视频，逐帧用上一帧生成图作基底（img2img strength 0.3–0.6）+ 当前帧 Canny/depth + prompt | 相邻生成帧 **LPIPS / 你们已有的 SSIM**；目视 flicker | 通过：相邻帧 LPIPS 平滑、无明显抖动；不通过：叠 Consistency LoRA 重测，仍不行→Qwen-Edit-2511（官方主打 anti-drift） |
| **H4** | 还原语义质量达标 | 端到端跑你们现有 evaluate.py（PSNR/SSIM/LPIPS/CLIP） | CLIP Score（语义对齐）+ LPIPS（感知） | 通过：CLIP/LPIPS 优于现有 Z-Image 基线；不通过：作为对照数据保留，不阻塞 |

**回退判定规则（写死，避免纠结）**：
- **H1 不通过 = 主线红线触发**。klein 的"Canny/depth 引导"无法以参考图方式实现，而这是合同里"边缘+深度引导"的核心。此时两条路：① 切 Qwen-Image-Edit-2511 + InstantX ControlNet-Union（结构条件是其原生强项）；② klein 仅做"上一帧 + prompt 语义编辑"主线，结构约束改由轻量 ControlNet 后处理。**建议优先①**，因为它一次性解决结构条件 + 官方 anti-drift 一致性。
- H2/H3 不通过但 H1 通过：保留 klein 主线，靠降分辨率 + 插帧/超分（DLSS 思路，另一份调研）补速度，靠 Consistency LoRA 补一致性。

**第一周并行建议**：H1 同时在 klein 和 Qwen+InstantX 上各跑一遍（半天即可），用数据而非赌注决定主线。这是性价比最高的风险对冲。

---

## 5. 需向负责人核准/澄清的事项

1. **"Qwen3.6" 版本号**：已核实存在 **Qwen3.6 系列（2026-04 发布，27B / 35B-A3B，统一 VL 早融合）**，且更新的 Qwen3.7-Plus（2026-06-01）也是多模态 agent。但**用于"图生文"的具体是哪个量级、是否有适配 24GB 的小尺寸量化版，需进一步核**（[Qwen3.6 GitHub](https://github.com/QwenLM/Qwen3.6)、[Qwen3-VL 技术报告](https://arxiv.org/abs/2511.21631)）。建议先用你们已就绪的 Qwen2.5-VL-7B(int4) 跑通 PoC，VL 升级与帧生成主线解耦、不阻塞 6/30 保底版。
2. **klein 的结构约束硬伤（第 1.5 节）**：这是与"Canny+depth 引导"合同目标的直接张力，建议在 PoC 前就同步负责人，避免第一周后才暴露。

---

### 来源汇总（核实级别见正文标注）
- [FLUX.2-klein-9B 模型卡](https://huggingface.co/black-forest-labs/FLUX.2-klein-9B) · [multi-image discussion](https://huggingface.co/black-forest-labs/FLUX.2-klein-9B/discussions/6) · [fp8 仓库](https://huggingface.co/black-forest-labs/FLUX.2-klein-9b-fp8) · [GGUF 仓库](https://huggingface.co/unsloth/FLUX.2-klein-9B-GGUF) · [klein-9b-kv](https://huggingface.co/black-forest-labs/FLUX.2-klein-9b-kv) · [flux2 官方仓库](https://github.com/black-forest-labs/flux2)
- [FLUX.2-dev-Fun-Controlnet-Union](https://huggingface.co/alibaba-pai/FLUX.2-dev-Fun-Controlnet-Union) · [klein Consistency LoRA](https://civitai.com/articles/27410/flux2-klein-9b-consistency-lora) · [krita img2img issue](https://github.com/Acly/krita-ai-diffusion/issues/2392)
- [Qwen-Image-Edit-2511 模型卡](https://huggingface.co/Qwen/Qwen-Image-Edit-2511) · [InstantX Qwen-Image-ControlNet-Union](https://huggingface.co/InstantX/Qwen-Image-ControlNet-Union) · [Qwen ControlNet 教程](https://www.stablediffusiontutorials.com/2025/09/qwen-image-controlnets.html) · [Qwen 双通道架构](https://help.scenario.com/articles/5117943220-advanced-editing-with-qwen-models) · [Qwen 多图工作流](https://stable-diffusion-art.com/qwen-image-edit-multiple-images/)
- [Qwen3.6 GitHub](https://github.com/QwenLM/Qwen3.6) · [Qwen3-VL 技术报告 2511.21631](https://arxiv.org/abs/2511.21631)
- 速度二手参考（未核实）：[LucasGraphic](https://lucasgraphic.com/posts/flux2-klein-9b-kv-explained-speed-quality-gpus) · [VRAM 指南](https://willitrunai.com/blog/flux-2-klein-9b-vram-requirements)

---

# 线2 图生文最新

I have all verified information needed. Here is the research report.

---

# 图生文（VLM）最新状态调研 — 面向无人车遥操作语义传输场景

## 0. 一句话结论（先看这个）

- **"Qwen3.6" 确有其物**，但它不是负责人想要的那种"专用 VL 模型"——它是 2026 年 4 月发布的**统一多模态主线大模型**（文本+视觉融合，非独立 VL 分支）。**负责人把版本号记串了**，2026-06 时真正的多模态主力是两条线：①**专用线 Qwen3-VL**（2B/4B/8B/32B/30B-A3B/235B，2025-10～11）；②**统一线 Qwen3.5/Qwen3.6**（2026-02～04，视觉早融合进主干，无独立 VL 后缀）。
- **保底版（6/30）：不要动现有 Qwen2.5-VL-7B，零升级风险，直接交付。** 升级 VLM 不是 6/30 闭环的必要条件，且会引入 transformers/量化适配风险，得不偿失。
- **目标版（7 月起）：升级到 Qwen3-VL-4B/8B-Instruct（int4/AWQ）**，这是当前结构化描述+空间推理+车端实时性的最佳平衡点。统一线 Qwen3.5-9B 虽然能力更强但生态偏新、专用视觉工具链（grounding/视频对齐）反而不如 Qwen3-VL 成熟，**不建议本阶段冒进上 3.5/3.6**。

---

## 1. 版本核准："Qwen3.6" 到底指什么（已核实）

2026-06 时 Qwen 多模态有两条并行产品线，必须分清：

### 线 A：专用 VL 模型 Qwen3-VL（推荐本项目用）
| 型号 | 参数 | 发布时间 | 许可 |
|------|------|----------|------|
| Qwen3-VL-2B (Instruct/Thinking) | 2B dense | 2025-10-21 | Apache-2.0 |
| Qwen3-VL-4B (Instruct/Thinking) | 4B dense | 2025-10-15 | Apache-2.0 |
| Qwen3-VL-8B (Instruct/Thinking) | 8B dense | 2025-10-15 | Apache-2.0 |
| Qwen3-VL-32B (Instruct/Thinking) | 32B dense | 2025-10-21 | Apache-2.0 |
| Qwen3-VL-30B-A3B | 30B MoE(激活3B) | 2025-10-04 | Apache-2.0 |
| Qwen3-VL-235B-A22B | 235B MoE | 2025-09-23 | Apache-2.0 |

- 技术报告 arXiv:2511.21631（2025-11-27）。原生 256K 上下文（可扩到 1M），新增 interleaved-MRoPE（强化时空建模）、DeepStack（多层 ViT 特征）、文本时间戳对齐（视频）。**全系 Apache-2.0，可商用、无 MAU 限制**——比 FLUX.2 那条非商用线干净得多。
- 支持 **transformers 4.57.0+ 和 vLLM 0.11.0+**；HF + ModelScope 均可获取。2B/4B 共用 SigLIP2-Large(300M) 视觉编码器，8B 用更大的 SigLIP2-SO-400M。

### 线 B：统一多模态主线 Qwen3.5 / Qwen3.6（负责人口中的"3.6"）
- **Qwen3.5**：2026-02-16 起发布，"统一视觉-语言基座，文本+多模态 token 早融合（early fusion）单一主干"，官方称在推理/代码/agent/视觉理解上**超越 Qwen3-VL**。变体：0.8B/2B/4B/9B/27B dense + 35B-A3B/122B-A10B/397B-A17B MoE + Omni-Plus(~100B，加音视频)。**全系原生支持图像输入，没有独立的 "Qwen3.5-VL" 后缀**。
- **Qwen3.6**：2026-04 发布（35B-A3B 4/16，27B 4/22），定位"稳定性与实用性"，主打 agentic coding，**同样原生多模态（image+text）**，Apache-2.0。llama.cpp / mlx-vlm 已支持其 text+vision。

**核准裁定：** 负责人说的"Qwen3.6"**实际存在**，但它是统一线 LLM 而非专用 VL。对"把相机帧压成提示词"这种纯视觉理解任务，**专用线 Qwen3-VL 的视觉工具链（2D/3D grounding、视频时间对齐）更对口、生态更成熟**；统一线 3.5/3.6 的优势在 agent/coding/长文本推理，对本场景属于"用不上的过剩能力 + 偏新的生态风险"。

---

## 2. 面向本场景的能力匹配

需求：结构化、空间关系、可控描述 + 未来"关键帧差分描述"。

- **结构化/空间关系（核准）**：Qwen3-VL-4B-Instruct 官方卡明确列出 "Advanced Spatial Perception"（判断物体位置、视角、遮挡）、2D grounding（相对坐标框/点）、3D grounding（室内外物体）。这正是遥操作场景需要的——可以输出"前方 3m 有行人，左侧障碍物，道路向右弯"这类带空间关系的结构化描述，直接喂给 FLUX.2 的 Canny+depth 引导。
- **可控/结构化输出**：支持从图像生成 Draw.io/HTML/CSS（"Visual Coding Boost"），意味着可稳定输出 JSON/结构化字段——对"提示词+条件元数据"打包传输友好。
- **关键帧差分描述（未核实为官方特性，属工程实现）**：Qwen3-VL 原生 256K interleaved 上下文支持"图+文交错"，可把"上一关键帧图像 + 其描述 + 当前帧"一起喂入，让模型只描述**变化量**。这是上下文工程能力而非专门功能，需自己设计 prompt 模板，但 256K 交错上下文是该方案的硬支撑，**Qwen2.5-VL 也能做但上下文/时空建模弱一档**。
- **档位选择**：结构化描述质量 8B > 4B > 2B；车端延迟 2B < 4B < 8B。**4B-Instruct 是甜点档**——空间推理与 8B 接近，延迟和显存显著更低。**不要用 Thinking 版**（遥操作要低延迟，思维链会拖慢且对"描述帧"无收益）。

---

## 3. 车端实时性评估（已核实关键数据）

- **显存（核实）**：Qwen3-VL-4B 在 **Q4 量化下约 2.5 GB**，适配 4–6GB GPU。8B int4 约 5–6GB。对车端嵌入式 GPU（如 Jetson Orin 级）4B-int4 完全可落地；RTX 5090 24GB 跑 8B 余量充裕。
- **量化口径（核实，重要坑）**：**"int4" 不是 vLLM 合法值**，要用 **AWQ / GPTQ / FP8 / bitsandbytes**。社区已有 76+ 量化版（llama.cpp/Ollama/LM Studio）。注意官方提示：**transformers 里 FP8 性能未优化、SGLang 的 GPTQ-INT4 也待优化**——车端建议走 **vLLM+AWQ** 或 **llama.cpp GGUF Q4**，别用 transformers 原生 FP8。
- **延迟（部分核实）**：Qwen3-VL AWQ on vLLM 文本侧约 0.03s/题级；视觉预处理随分辨率剧烈变化——4B 模型 256² 仅 0.91ms，**4096² 高达 343ms**。**强提示：车端务必给输入帧做分辨率 cap（如 512²～768²）**，否则光预处理就破百毫秒。单次完整描述延迟（预处理+生成几十 token）4B-AWQ 在桌面级 GPU 量级约**几百 ms～1s**，与"低频关键帧描述"（非每帧）的分层架构匹配；**不要指望它跑每帧 ≥10fps**——VLM 只负责低频关键帧语义，高频帧靠插帧/超分补，这与任务背景的分层思路一致。
- **更轻量备选（车端高频）**：Qwen3-VL-2B（Q4 约 1.5GB）是车端最轻档；若连 2B 都嫌重，统一线的 Qwen3.5-0.8B/2B（GGUF 已出，需配 mmproj 多模态投影文件）可作极限轻量候选，但 2B 以下描述质量明显下降，**建议车端下限定在 Qwen3-VL-2B/4B**。

---

## 4. 结论与行动建议

### 该用哪个具体型号
- **保底版（6/30）**：**维持 Qwen2.5-VL-7B-int4 不动**。它已实测可用、流程已打通，6/30 合同要的是"语义传输闭环跑通"，换 VLM 对闭环无增益、纯增风险。
- **目标版（7 月起迭代）**：**Qwen3-VL-4B-Instruct（AWQ/GGUF-Q4）为主，8B-Instruct 为质量上限对照**。车端实测后在 2B/4B/8B 间定档。

### 升级成本（中等偏低，非阻塞）
- transformers 需升到 **4.57.0+**（项目现用版本需确认，可能要 bump；Qwen3-VL-4B 卡建议直接从源码装或等 4.57 正式版）。这是唯一硬依赖变更。
- prompt 模板需重写以发挥结构化输出 + 空间 grounding（投入 1–2 天工程）。
- 量化路线从现有方案切到 AWQ/GGUF（已有现成社区权重，无需自己量化）。
- **许可 Apache-2.0，比 FLUX.2 干净，无合规阻塞。**

### 是否阻塞 6/30
**不阻塞。** 明确建议：6/30 保底版冻结 Qwen2.5-VL-7B，VLM 升级排进 7 月目标版第一批迭代，与 FLUX.2 帧生成主线并行验证。

### 一个需要负责人拍板的点
是否在目标版后期评估**统一线 Qwen3.5-9B**？它官方称视觉理解超 Qwen3-VL，但①生态新（vLLM 0.7+ 才原生支持其混合架构，GGUF 需额外 mmproj）、②专用视觉 grounding/视频对齐工具链反不如 Qwen3-VL 成熟。**本阶段不建议**，留作 8 月后的能力上探选项。

---

### 来源（关键论断出处）
- [QwenLM/Qwen3-VL GitHub（型号/发布日/Apache-2.0/transformers 4.57+/vLLM 0.11+/grounding）](https://github.com/qwenlm/qwen3-vl)
- [Qwen3-VL Technical Report arXiv:2511.21631（interleaved-MRoPE/DeepStack/256K）](https://arxiv.org/abs/2511.21631)
- [Qwen/Qwen3-VL-4B-Instruct · HuggingFace（空间感知/256K-1M/Apache-2.0/transformers 版本）](https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct)
- [QwenLM/Qwen3.6 GitHub（3.6 多模态/27B/35B-A3B/4 月发布/Apache-2.0）](https://github.com/QwenLM/Qwen3.6)
- [Qwen3.5 完整指南 codersera（3.5 统一早融合多模态/变体/无独立 VL 后缀/许可）](https://codersera.com/blog/qwen-3-5-complete-guide-2026/)
- [Qwen3-VL 4B/8B FP8 低显存推理 Medium（Q4≈2.5GB/视觉预处理延迟随分辨率）](https://medium.com/@shouke.wei/alibaba-debuts-compact-dense-qwen3-vl-4b-8b-models-with-fp8-checkpoints-for-low-vram-inference-6941070c362d)
- [unsloth/Qwen3.5-9B-GGUF · HuggingFace（GGUF/mmproj 视觉投影文件需求）](https://huggingface.co/unsloth/Qwen3.5-9B-GGUF)

**核实状态说明**：型号/发布日/许可/参数档/transformers-vLLM 支持/Q4 显存/分辨率-预处理延迟关系，均已核实。单次端到端描述延迟（几百 ms～1s）为基于已核实分项的合理推算，标记为**部分核实**，需在 RTX 5090 上实测确认。"关键帧差分描述"为基于 256K 交错上下文能力的工程方案，非官方特性，标记**未核实**。

---

# 线3 DLSS式插帧超分

I now have comprehensive, cross-verified data. Writing the final research report.

---

# DLSS 式实时插帧 + 超分调研：把 1-2s/帧大模型生成变成 10-30fps 输出流

> 核实状态说明：本文性能/许可数字均标注来源。凡来自 NVIDIA 官方文档/博客的为「已核实-官方」；来自第三方实测/社区论坛的为「已核实-第三方」（数量级可信，绝对值需我方在 5090 上复测）；标「待我方实测」处务必落地前自测。RTX 5090 为 Blackwell 架构，多数公开实测是 4090(Ada)，5090 普遍快 1.3-1.7x，文中按保守同量级估算。

---

## 1. DLSS 本体边界：结论是「不能直接用，但思路可借鉴，且有官方视频流替代品」

### 1.1 DLSS 3/4 Frame Generation 与 Ray Reconstruction 原理

- **Frame Generation（DLSS 3）**：每渲染一真实帧，结合**游戏引擎提供的 motion vector + depth**，再加 **Ada 架构 Optical Flow Accelerator（OFA 硬件单元）**计算的光流场，由 AI 网络在两真实帧之间**生成 1 个插帧**。
- **Multi Frame Generation（DLSS 4，仅 Blackwell/50 系）**：从 1 个真实帧推断**多个**（最多 3 个）后续帧，用额外 AI 网络替代部分传统光流，降低伪影、提升时间一致性。DLSS 4 的超分还从 CNN 换成了 **Vision Transformer** 模型。
- **Ray Reconstruction**：用 AI 模型替代手调降噪器，重建光线追踪的反射/全局光照，与插帧是不同子系统，对本项目（无光追）基本无关。

来源（已核实-官方/媒体）：[NVIDIA GeForce News: DLSS4 Multi Frame Generation](https://www.nvidia.com/en-us/geforce/news/dlss4-multi-frame-generation-ai-innovations/)、[NVIDIA Research: DLSS4](https://research.nvidia.com/labs/adlr/DLSS4/)、[Wikipedia: DLSS](https://en.wikipedia.org/wiki/Deep_Learning_Super_Sampling)

### 1.2 能否用于摄像头/任意视频流？—— 不能直接用

**结论：DLSS Frame Generation 绑定渲染管线，不能喂摄像头/视频文件。** 核心原因：

- DLSS FG **强依赖游戏引擎逐帧产出的 motion vector + depth**，这些「中间表示」在自然视频里根本不存在。NVIDIA Streamline 编程指南明确 FG「基于来自游戏引擎/渲染管线的已渲染帧推断」，并要求**正确的 motion vector** 才能工作。
- 即便最新的 **DLSS 5**（NVIDIA 2026-03 透露，计划 2026 秋季上消费卡）号称「只取 2D 渲染帧 + motion vector 作为输入」（不再要 3D 引擎几何数据），**仍然要求 motion vector**——这对自然视频依然是缺失的，所以 **DLSS 5 也不能直接拿摄像头流来跑**。

来源（已核实）：[NVIDIA-RTX/Streamline ProgrammingGuideDLSS_G.md](https://github.com/NVIDIA-RTX/Streamline/blob/main/docs/ProgrammingGuideDLSS_G.md)、[TweakTown: DLSS 5 takes 2D frame + motion vectors](https://www.tweaktown.com/news/110569/dlss-5-only-takes-2d-rendered-frames-and-motion-vectors-as-input-not-3d-game-engine-data-confirms-nvidia/index.html)、[VideoCardz: DLSS 5 input confirmation](https://videocardz.com/newz/nvidia-confirms-dlss-5-uses-a-2d-frame-plus-motion-vectors-as-input)

> 给负责人的一句话：**DLSS 整套不能直接接进我们的相机视频流，它是渲染管线产品。但 DLSS「低分辨率渲染 → AI 超分 + 低帧率渲染 → AI 插帧」的分层思路 100% 可借鉴**，且 NVIDIA 自己就把这套思路里「不依赖 motion vector」的部分拆出来做成了面向视频流的独立 SDK（下节）——那才是我们能用的。

### 1.3 NVIDIA 面向视频流的官方替代方案（CUDA 可用）

| 方案 | 做什么 | 输入 | 硬件 | 许可 | 对本项目可用性 |
|---|---|---|---|---|---|
| **Optical Flow SDK 4.0 + NvOFFRUC（FRUC）** | 帧率提升（插帧） | **任意视频的两连续帧**（不需 motion vector！） | Ada/Blackwell 的 NVOFA 硬件单元 + CUDA | NVIDIA SDK 许可（内部预研可用，商用需查条款） | **高**：5090 有 NVOFA，硬件级插帧延迟极低 |
| **Maxine VFX SDK / Video Super Resolution** | 视频超分（90p–2160p 输入，1.33x/1.5x/2x/3x/4x），含去噪/去模糊 | 视频帧 | RTX GPU | 商用/非商用均可，需遵守 branding 指引 | **高**：直接做整体超分 |
| **RTX Video SDK（RTX VSR）** | 视频超分 + TrueHDR | 视频帧 | RTX GPU | NVIDIA 许可 | 中：偏消费端，可作对照 |

- **NvOFFRUC 关键事实（已核实-官方）**：API 接收**两连续帧**输出中间插帧，插值位置可**任意指定**（不必正中），用 NVOFA 硬件引擎，号称「比纯软件方法快得多」，明确支持「任意视频内容」的帧率提升——**这正是绕开 DLSS 引擎依赖的官方路径**。官方博客未给具体 fps 数字（待我方实测）。
- 来源（已核实-官方）：[NVIDIA Blog: Ada FRUC in Optical Flow SDK](https://developer.nvidia.com/blog/harnessing-the-nvidia-ada-architecture-for-frame-rate-up-conversion-in-the-nvidia-optical-flow-sdk/)、[NVIDIA Optical Flow SDK](https://developer.nvidia.com/optical-flow-sdk)、[Maxine VFX Super Resolution 文档](https://docs.nvidia.com/maxine/vfx/latest/Filters/VideoSuperResolution.html)、[RTX Video SDK](https://developer.nvidia.com/rtx-video-sdk)

> 取舍建议：NvOFFRUC（硬件 NVOFA）延迟最低、最省显存，但它是经典光流插帧，**大运动/遮挡质量不如学习型（RIFE/FILM）**。建议把它列为「目标版」延迟优化的候选，但**保底落地仍以开源 RIFE 为主**（生态成熟、Python 直接可调、调试快）。

---

## 2. 开源等价物（9 天可落地的重点）

### 2.1 插帧

| 模型 | 性质 | 速度（已核实-第三方，多为 4090） | 质量/特点 | CUDA/TensorRT |
|---|---|---|---|---|
| **RIFE 4.6**（hzwer/ECCV2022-RIFE） | 轻量光流插帧 | **PyTorch FP16: 1080p 50–100+ fps；TensorRT FP16: 1080p 288 fps**(4090) | 实时首选；大运动/遮挡易 ghosting/拉丝 | ✅ TensorRT 成熟（多个 ComfyUI-RIFE-TensorRT 实现） |
| **FILM**（google-research/frame-interpolation） | 大运动专用 | **720p 约 0.39s/帧（≈2.5fps）** | 大运动（>100px）质量明显优于 RIFE，但**远不够实时** | CUDA 可，无成熟 TRT 实时路径 |
| **IFRNet / SG-RIFE** 等 | RIFE 改进 | 接近 RIFE 量级 | SG-RIFE(2025) 用语义引导改善大运动感知质量 | 较新，生态弱 |

来源（已核实）：[RIFE GitHub](https://github.com/hzwer/ECCV2022-RIFE)、[ComfyUI-Rife-Tensorrt(yuvraj108c)](https://github.com/yuvraj108c/ComfyUI-Rife-Tensorrt)、[SVP 论坛 RIFE TRT 288fps@1080p RTX4090](https://www.svp-team.com/forum/viewtopic.php?id=6281&p=15)、[FILM 论文](https://arxiv.org/pdf/2202.04901)、[RIFE vs FILM 对比(Apatero)](https://apatero.com/blog/rife-vs-film-video-frame-interpolation-comparison-2025)

**结论：插帧主选 RIFE 4.6 + TensorRT FP16。** 它在 1080p 远超实时（4090 已 288fps，5090 更高），插一帧的延迟在亚毫秒~毫秒级，完全不是流水线瓶颈。FILM 仅在「大运动质量翻车时」作为离线对照，不进实时路径。

### 2.2 超分

| 模型 | 性质 | 速度（已核实-第三方，4090 fp16） | 质量/特点 |
|---|---|---|---|
| **Real-ESRGAN** | 单帧 GAN 超分 | **480p 输入 60–80 fps**；**1080p→4K 仅 6–10 fps** | 实时（小输入）；逐帧独立 → **帧间会闪烁/抖动** |
| **BasicVSR++** | 递归视频超分（用 5–7 邻帧） | 比 Real-ESRGAN 慢 **5–10x** | PSNR/VMAF 高 2–3dB，**时间一致性显著更好**，但难实时 |
| **NVIDIA Maxine VSR** | 视频超分（含时间一致性） | 待我方实测 | 官方优化、商用可用、含去噪去模糊 |

来源（已核实）：[Real-ESRGAN/BasicVSR++ 工程评测(Forasoft)](https://www.forasoft.com/learn/ai-for-video-engineering/articles-ai/real-esrgan-basicvsr-ott-archive-upscaling)、[BasicVSR++ 论文](https://arxiv.org/pdf/2104.13371)

**结论：超分主选「在低分辨率上生成 → 整体超分」的策略**。Real-ESRGAN 在**小输入（≤512p）实时可用**，但逐帧 GAN 会引入帧间闪烁；因此超分应放在**插帧之后、对最终低分辨率帧流**做，且优先评估 **Maxine VSR**（带时间一致性、官方优化）作为生产路径，Real-ESRGAN 作开源对照。**不要直接 1080p→4K（只有 6–10fps，会成瓶颈）**——要在更低分辨率生成、再小倍率超分。

---

## 3. 端到端延迟账与流水线设计

### 3.1 推荐流水线（分层「语义关键帧 + 插帧 + 超分」）

```
车端(发送)                         操控端(接收)
相机流 → 抽语义关键帧(每N帧)         ┌─ FLUX.2-klein 生成关键帧 K_t (低分辨率, ~512-768)
       → Qwen-VL 描述                │     用 上一帧K_{t-1} + 文本 + Canny + Depth 引导
       → Canny + Depth 提取   ──TCP──┤
       → (极低码率传输)              ├─ RIFE-TRT 在 K_{t-1}↔K_t 间插 N-1 帧
                                     └─ Real-ESRGAN / Maxine VSR 对整条帧流超分 → 显示
```

### 3.2 延迟估算（RTX 5090，保守）

设大模型 **klein 4 步蒸馏 ≈ 1.0–1.5s/关键帧**（低分辨率，4090 实测级，5090 更快；**注意现状 60s/帧是冷加载+无分辨率cap，非上限**，须先做：模型常驻、分辨率 cap≤768、FP8/GGUF）。

| N（关键帧间隔） | 关键帧生成 | 每个有效帧摊销大模型成本 | RIFE 插 N-1 帧(可忽略，<5ms/帧) | 超分(每帧, 小输入) | **有效输出帧率** | 显示延迟特征 |
|---|---|---|---|---|---|---|
| N=4 | 1.2s | 0.30s/帧 | ~0 | ~15ms | 受关键帧间隔门控，**有效 ~3–4fps** 实视觉更新 | 每 1.2s 一次「真更新」，中间补 3 帧 |
| **N=8** | 1.2s | **0.15s/帧** | ~0 | ~15ms | **~6–8fps 平滑流** | 平滑度好，语义滞后 ~1.2s |
| N=16 | 1.2s | 0.075s/帧 | ~0 | ~15ms | **~13–16fps 平滑流** | 平滑度优，但大运动下插帧 ghosting 风险↑ |

**关键洞察：插帧几乎免费（亚毫秒~毫秒），瓶颈永远是大模型关键帧。** 输出帧率 ≈ N / 关键帧周期。要 ≥10fps 平滑流，在 1.2s/关键帧下需 **N≥12**。

**N 取值建议：N=8 为甜区**（平滑度、一致性、大运动鲁棒性平衡）。运动剧烈场景动态降到 N=4，静止场景升到 N=16。

> 必须向负责人厘清的概念：**「平滑帧率」≠「语义延迟」。** 插帧能把视觉流做到 10–30fps 很平滑，但**真实场景信息的更新速率仍由关键帧周期（~1.2s）决定**——遥操作里这意味着「画面动作流畅，但对车前突发障碍的反应有约 1s 滞后」。这是本方案的根本物理约束，**靠插帧无法消除，只能靠加速大模型（更激进蒸馏/更低分辨率/TensorRT/未来 5090 多卡）缩短关键帧周期来改善**。目标版的核心 KPI 应是「关键帧周期」，而非「输出 fps」。

---

## 4. 一致性收益与失效模式

### 4.1 插帧相对「逐帧大模型生成」的天然一致性优势

- **逐帧扩散生成的致命伤是帧间抖动**：即便用上一帧做基底 + 同一提示词，扩散采样的随机性 + ControlNet 引导差异会导致纹理/光照在帧间「呼吸」「闪烁」。
- **插帧是对两个确定关键帧做光流形变**，中间帧在像素层与两端**强相关**，**时间一致性远好于独立采样**。等于把「一致性」从「祈祷扩散模型自己稳」转成「数学上保证中间帧由端点连续过渡」。这也是 KeyVID、DiffuseSlide 等「低帧率生成 + 插帧」两段式范式被广泛采用的原因。
- 来源（已核实）：[KeyVID 论文](https://arxiv.org/html/2504.09656)、[DiffuseSlide 论文](https://arxiv.org/html/2506.01454v1)

### 4.2 失效模式与缓解

| 失效场景 | 表现 | 缓解 |
|---|---|---|
| **大运动**（车快速转向、近景物体掠过） | ghosting、拉丝、物体撕裂 | 动态缩小 N（缩短关键帧周期）；大运动段落退回更密关键帧；备选 FILM 离线兜底 |
| **遮挡边界**（物体出/入画、前车遮挡） | 运动边界处鬼影、空洞 | RIFE 自带 occlusion mask 有限；关键帧引导（Canny/Depth）已传，可让接收端在遮挡区更信任新关键帧而非插帧 |
| **新物体突现**（关键帧间出现的障碍） | 插帧无法「无中生有」，要等下一关键帧才显现 | **这是安全相关硬约束**：遥操作场景必须把关键帧周期压到可接受反应时间内，不能靠 N 太大掩盖 |
| **超分闪烁**（Real-ESRGAN 逐帧独立） | 高频纹理帧间抖 | 用带时间一致性的 VSR（BasicVSR++/Maxine VSR），或对插帧后整条流做时序平滑 |

来源（已核实）：[RIFE 失效模式综述/SG-RIFE](https://arxiv.org/html/2512.18241v1)、[AceVFI 综述](https://arxiv.org/pdf/2506.01061)

---

## 5. 结论与建议

### 5.1 6/30 保底版：**不含插帧，但预留接口**

- 保底版定位是「离线 视频文件→逐帧生成→视频文件、跑通语义传输闭环」，**核心是验证压缩-传输-还原链路，不追实时**。插帧引入额外的光流模型、TensorRT 工程、大运动调参，**会挤占 9 天里本应保闭环的时间**。
- **架构上必须留好两个接口**：(a) 生成模块输出「关键帧序列 + 时间戳」而非「连续帧」；(b) 后处理阶段是可插拔的 `frame_postprocess(keyframes) → output_stream`，默认实现为「直接拼接/简单复制」，目标版替换为「RIFE 插帧 + 超分」。这样保底版到目标版无需重构。

### 5.2 目标版技术选型推荐

| 环节 | 首选 | 对照/备选 | 理由 |
|---|---|---|---|
| 插帧 | **RIFE 4.6 + TensorRT FP16** | NvOFFRUC（硬件 NVOFA，延迟更低）；FILM（大运动离线兜底） | 实时(1080p 远超 30fps)、生态成熟、Python 可调、TRT 现成 |
| 超分 | **NVIDIA Maxine VSR**（时间一致性 + 官方优化） | Real-ESRGAN（开源对照，小输入实时）；BasicVSR++（质量上限对照） | 视频超分需时间一致性；Real-ESRGAN 逐帧会闪 |
| 借鉴 DLSS 的「低分渲染+超分」 | **大模型在 512–768 低分辨率生成 → 整体 2x–3x 超分** | — | 直接把单帧生成成本降一个量级，是缩短关键帧周期最有效的杠杆 |
| 流水线参数 | **N=8（动态 4–16）**，目标关键帧周期 <1.5s | — | 平滑度/一致性/大运动鲁棒平衡 |

### 5.3 给负责人的三条核心结论

1. **DLSS 本体接不进相机流（绑渲染管线 + 强依赖 motion vector，DLSS 5 也一样）**，但它的「低分辨率生成 + AI 超分 + AI 插帧」分层思路正确且可借鉴；NVIDIA 已把这套思路里面向视频流的部分做成 **Optical Flow SDK(NvOFFRUC) + Maxine VSR** 官方 SDK，CUDA 可用，可作目标版加速候选。
2. **实时性矛盾用分层化解：插帧几乎免费（毫秒级），瓶颈永远是大模型关键帧。** 输出平滑帧率可达 10–30fps，但**语义/反应延迟由关键帧周期（现状目标 ~1.2s）决定，插帧消除不了**——目标版真正要打的 KPI 是「把关键帧周期压短」（蒸馏 + 低分辨率生成 + TensorRT），不是堆 fps。
3. **插帧对帧间一致性是净收益**（中间帧由端点形变而来，比逐帧独立扩散稳得多），代价是大运动/遮挡/突现物体处会鬼影——遥操作安全场景下，**关键帧周期必须压到可接受反应时间内，不能用大 N 掩盖**。

---

**待我方在 RTX 5090 上实测的关键数字**（公开资料缺失或仅有 4090 值）：RIFE-TRT 在我方目标分辨率的实际 fps；NvOFFRUC 单帧插值延迟；Maxine VSR 吞吐与质量；klein 4 步在 512–768 分辨率 + 常驻 + FP8/GGUF 下的真实 s/帧（决定关键帧周期，是全盘最关键变量）。

---

# 线4 流式架构与深度条件

-pr-review: Use when reviewing a pull request, when asked to do a code review of a branch or set of changes, or when finishing a body of work that will become a PR. Produces a written review document and a posted GitHub PR review.

Use the available skills when appropriate to satisfy the user's request, and otherwise follow their direct instructions.

I'll do my best to help with software engineering tasks while following all guidelines.
