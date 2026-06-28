# D2 主线设计：保底闭环接 relay 双机 + 视频质量评估

> 工作分支 `feature/video-relay-and-eval` | 编制 2026-06-22 | 6 天冲刺 D2（6/23）
> 上游依据：[6 天冲刺规划](2026-06-21-video-stream-6day-plan-design.md) D2 行、[D1 保底骨架设计](2026-06-22-d1-video-skeleton-design.md)
> D1 产出（PR #46）：单机 video→video 闭环 `VideoPipeline`，本设计在其基础上拆双机 + 加评估。

## 1. 背景与目标

6 天冲刺 D2 主线两块：

1. **保底闭环接 `relay` 双机路径**：把 D1 的单机 `VideoPipeline`（单进程内 read→生成→write）拆成双机——发送端机器只做轻量的 Canny + 可选 VLM，逐帧经 TCP relay 传给接收端机器做 Diffusers 生成并合视频。
2. **视频质量评估（逐帧 + 整段）**：新增视频版评估，逐帧算 PSNR/SSIM/LPIPS/CLIP，整段做均值/标准差汇总。

二者共同支撑 M1 保底版验收（D3，6/24）：「单机与双机(relay)各演示一次 + evaluation 出逐帧+整段指标」。

## 2. 范围边界（守保底优先）

**做**：

- 双机 relay 的发送端/接收端编排 + CLI 子命令；
- 视频帧序对齐、失败帧填充、收齐合视频、收发两端 summary；
- 视频版评估脚本（逐帧四指标 + 整段汇总）。

**不做**（明确划界，避免挤占保底时间）：

- 流式 I/O（收齐再合即可；流式是 7 月目标版，已挂 issue #49）；
- 帧间一致性 / 时间维度指标（属 D3 H3 PoC 与中期规划）；
- klein 主线模型（D4）、真实行车视频测试（D3）；
- 协议帧格式变更（仅复用现有 `metadata` 字段，见 §4）。

## 3. 架构与数据流

```mermaid
flowchart LR
    subgraph S["发送端机器（轻量，无生成模型）"]
        V1[输入视频] --> RF[read_frames]
        RF --> PO["逐帧 process_one<br/>Canny + 可选 VLM"]
        PO --> PK["TransmissionPacket<br/>+ frame_index/total_frames/fps"]
        PK --> TX[SocketRelaySender]
    end
    TX -.TCP 逐帧.-> RX
    subgraph R["接收端机器（Diffusers 生成）"]
        RX[SocketRelayReceiver] --> BUF["按 frame_index 缓冲"]
        BUF --> PR["receiver.process 逐帧还原"]
        PR --> FILL["收齐后失败帧填充"]
        FILL --> WF[write_frames 合视频]
        WF --> SUM[接收端 summary.json]
    end
    SUM --> EV["scripts/evaluate_video.py<br/>原视频帧 vs 输出视频帧"]
```

数据流与 D1 的差异：D1 在单进程内把 `receiver.process_batch` 当整批黑盒调用；D2 改为发送端逐帧打包发送、接收端逐帧收包还原，二者跨进程/跨机器，靠帧序号对齐。

## 4. 组件设计

| 组件 | 位置 | 职责 | 可单测 |
|---|---|---|---|
| `VideoRelaySender` | `pipeline/video_relay.py` | 编排：`read_frames` → 逐帧 `process_one` → 逐帧 `SocketRelaySender.send` + 发送端 summary | 是（relay 用 127.0.0.1 + 线程） |
| `VideoRelayReceiver` | `pipeline/video_relay.py` | 编排：`SocketRelayReceiver` 收包 → 按 `frame_index` 缓冲 → `receiver.process` → 收齐 `_fill_failed_frames` → `write_frames` + 接收端 summary | 是（fake receiver） |
| `video-sender` CLI | `cli/video_sender.py` | 薄封装：`--input`、`--prompt`/`--auto-prompt`、Canny 阈值、`--relay-host/--relay-port`、`--seed`、`--fps`、`--save-frames` | — |
| `video-receiver` CLI | `cli/video_receiver.py` | 薄封装：`--relay-host/--relay-port`、`--output`、写 summary | — |
| 协议扩展 | `pipeline/relay.py` | `TransmissionPacket.metadata` 约定新增 `frame_index` / `total_frames` / `fps` 字段；**不改二进制帧格式**，向后兼容 | 现有测试覆盖 |
| `evaluate_video()` | `evaluation/video_eval.py` | 拆帧对齐 → 逐帧四指标 → 整段汇总；复用 `evaluation` 包内 `compute_*` 与汇总逻辑 | 是（合成小帧序列） |
| 评估脚本 | `scripts/evaluate_video.py` | argparse 脚本，**对称现有 `scripts/evaluate.py`**：`--original`、`--restored`、`--output`、`--device`、`--no-lpips/--no-clip` | — |

**设计原则**（沿用 D1）：核心编排逻辑放 `pipeline/` 与 `evaluation/` 包内、保证无 GPU 可单测（VLM 经 `prompt_fn` / 参数注入、receiver 经抽象基类）；CLI / scripts 只做参数解析的薄封装。

**复用点**：

- 发送端复用 `cli/sender.py::process_one`（已封装「图 → Canny + 可选 VLM → `TransmissionPacket`」）；
- 接收端复用 `cli/receiver.py` 的收包 + `receiver.process` 模式；
- 失败帧复用 `pipeline/video_pipeline.py::_fill_failed_frames`（建议提取为可共享函数）；
- 合视频复用 `common/video_io.py::write_frames`；
- 评估复用 `evaluation/{pixel,perceptual,semantic}_metrics.py` 的 `compute_*` 与 `scripts/evaluate.py` 的 `compute_summary`/`format_table`（可考虑抽到 `evaluation/video_eval.py` 或公共模块，避免复制粘贴）。

## 5. 关键处理细节

- **帧序对齐**：TCP 单连接顺序到达即帧序；接收端仍按 `metadata.frame_index` 排序缓冲，防御乱序/丢帧。
- **收尾信号**：发送端在每个包（至少首包）的 `metadata` 带 `total_frames` + `fps`；接收端收齐 `total_frames` 即触发合成，不依赖连接关闭，更稳健。
- **失败帧**：双机下某帧 `process` 失败 → 复用 D1 `_fill_failed_frames`（前导用首个成功帧、中间用上一成功帧），保证输出帧数守恒；全帧失败则报错。
- **发送端落盘**：默认纯流式不落零散帧（视频帧多），仅写发送端 summary（帧数、逐帧 Canny/VLM/relay 耗时、压缩比汇总）；`--save-frames` 调试时可选落帧。
- **接收端 summary**：帧数、逐帧 `process` 耗时与成功/失败状态、总耗时、每帧 prompt（供评估算 CLIP）。
- **评估帧数校验**：D2 恒等无插帧，原视频与输出视频帧数应一致；不一致直接报错（插帧改帧数是 D5 的事，超出 D2 范围）。
- **CLIP prompt 来源**：接收端 summary 落每帧 prompt，`evaluate_video.py` 读取算 CLIP；无 prompt 时跳过 CLIP（与现有 `evaluate.py` 行为一致）。

## 6. 错误处理

- **连接失败**：发送端连不上接收端时，沿用现有 `sender` 的兜底语气——若启用 `--save-frames` 则提示本地产物仍可用；否则明确报错退出。
- **传输中断**：`SocketRelay` 已有 `ConnectionError`；接收端未收齐 `total_frames` 即连接断开 → 报错并提示已收帧数，不产出残缺视频。
- **超时**：接收端 `accept`/`receive` 支持 timeout（现有能力），CLI 暴露合理默认值。
- **模型/显存**：接收端 Diffusers 加载失败沿用现有错误路径；收尾 `unload` 释放显存。

## 7. 测试策略

**单元/集成测试**（无 GPU，沿用 D1 风格）：

- `VideoRelaySender` + `VideoRelayReceiver` 端到端：127.0.0.1 + 线程起接收端，fake receiver 还原，验证帧序对齐、失败帧填充、收齐合成、收发 summary 帧数守恒；
- `total_frames` 收齐触发合成、未收齐中断报错；
- `frame_index` 乱序到达仍正确排序；
- `evaluate_video()`：合成小帧序列验四指标计算、整段汇总、帧数不一致报错、无 prompt 跳过 CLIP。

**GPU 冒烟 + 验收**：

- 单卡 RTX 5090 用 **127.0.0.1 同机双进程**模拟双机（发送端走 `--prompt` 整段、不加载 VLM，规避同机显存争用）；
- 跑 5~8 帧小分辨率短片，验证：输出视频帧数守恒 + 接收端 summary 成功率 + `evaluate_video.py` 出逐帧/整段指标；
- 记录端到端耗时（保底版允许慢）。

## 8. 验收口径（对齐 §7 冲刺验收）

D2 完成标准：

- 双机（127.0.0.1 双进程模拟）跑通 video→video，输出视频帧数守恒、收发 summary 完整；
- `scripts/evaluate_video.py` 对一段输出视频出逐帧四指标 + 整段均值/标准差，写 JSON；
- `uv run ruff check .` / `ruff format --check .` / `uv run pytest` 全绿；
- 为 D3「单机+双机各演示一次 + 真实行车视频测试 → M1」铺好双机与评估两块基础。

## 9. 后续衔接

- D3：本设计的双机路径 + 评估直接用于 M1 真实行车视频测试与裁决会；
- D5 插帧会改变帧数 → 届时 `evaluate_video` 的帧数校验需放宽 / 改对齐策略（已挂 #48 相关）；
- 7 月：流式 I/O（#49）替换「收齐再合」；图片版与视频版评估入口未来可考虑统一（当前 D2 保持二者都走 `scripts/` 的对称风格）。
