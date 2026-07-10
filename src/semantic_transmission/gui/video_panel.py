"""视频流演示 Tab（单机 video→video）：后台线程 + queue + gr.Timer 轮询。

Gradio 生成器无法从内部同步阻塞的 VideoPipeline.run() 转发进度，故与双机接收端
同构：daemon 线程跑 run(progress_callback=写队列)，gr.Timer 轮询刷新。
"""

from __future__ import annotations

import queue
import tempfile
import threading
import time
from pathlib import Path
from typing import Callable

import gradio as gr

from semantic_transmission.common.config import ProjectConfig, load_config
from semantic_transmission.common.video_io import read_frames
from semantic_transmission.evaluation.video_eval import evaluate_video
from semantic_transmission.pipeline.temporal_policy import (
    TemporalPolicyConfig,
    resolve_reference_mode,
)
from semantic_transmission.pipeline.video_pipeline import VideoPipeline
from semantic_transmission.receiver import create_receiver
from semantic_transmission.receiver.base import BaseReceiver
from semantic_transmission.sender.local_condition_extractor import LocalCannyExtractor


def unload_video_receiver(
    receiver: BaseReceiver | None,
) -> tuple[BaseReceiver | None, str]:
    """显式卸载 receiver 释放显存；失败也清空 state。"""
    if receiver is None:
        return None, "当前无已加载模型"
    try:
        unload = getattr(receiver, "unload", None)
        if callable(unload):
            unload()
        return None, "Receiver 模型已卸载"
    except Exception as e:
        return None, f"卸载过程出错：{e}"


def build_video_prompt_fn(
    mode: str, prompt: str | None, vlm_sender
) -> Callable[[int, object], str]:
    """构造逐帧 prompt 函数：auto→VLM 描述每帧；manual→整段共用。"""
    if mode == "auto":

        def _auto(index, frame):
            return vlm_sender.describe(frame).text

        return _auto

    text = prompt or ""

    def _manual(index, frame):
        return text

    return _manual


def start_video(
    state,
    video_path,
    backend,
    mode,
    prompt,
    ref_mode,
    kf_interval,
    kf_passthrough,
    seed,
    fps,
    project_config: ProjectConfig,
):
    """起后台线程跑 VideoPipeline.run，进度写队列；receiver 经 state 跨次复用。"""
    state = state or {}
    if not video_path:
        return state, "错误：请先上传视频"
    if state.get("thread") is not None and state["thread"].is_alive():
        return state, "已在运行中，请等待完成"

    # H2 防崩：非 klein 后端强制无时序，避免 resolve_reference_mode 抛错
    if backend != "klein":
        ref_mode = "none"
    resolved = resolve_reference_mode(backend, ref_mode)
    policy = None
    if resolved is not None:
        policy = TemporalPolicyConfig(
            keyframe_interval=int(kf_interval),
            reference_mode=resolved,
            keyframe_passthrough=bool(kf_passthrough),
        )

    progress_q: "queue.Queue" = queue.Queue()
    new_state = {
        "thread": None,
        "receiver": state.get("receiver"),
        "progress_q": progress_q,
        "result": None,
        "error": None,
        "done": False,
    }
    out_path = str(Path(tempfile.mkdtemp()) / "out.mp4")
    extractor = LocalCannyExtractor(
        threshold1=project_config.canny_low_threshold,
        threshold2=project_config.canny_high_threshold,
    )

    def _worker():
        vlm_sender = None
        try:
            if mode == "auto":
                from semantic_transmission.sender.qwen_vl_sender import QwenVLSender

                vlm_sender = QwenVLSender(
                    model_name=project_config.vlm_model_name,
                    model_path=project_config.vlm_model_path or None,
                )
            prompt_fn = build_video_prompt_fn(mode, prompt, vlm_sender)
            receiver = new_state["receiver"]
            if receiver is None:
                receiver = create_receiver(backend=backend)
                new_state["receiver"] = receiver
            t0 = time.time()
            stats = VideoPipeline(receiver, extractor).run(
                video_path,
                out_path,
                prompt_fn,
                seed=(int(seed) if seed not in (None, "") else None),
                fps=(float(fps) if fps not in (None, "") else None),
                on_prompts_ready=(
                    vlm_sender.unload if vlm_sender is not None else None
                ),
                temporal_policy=policy,
                progress_callback=lambda i, t, info: progress_q.put((i, t, info)),
            )
            d = stats.to_dict()
            d["_elapsed"] = time.time() - t0
            new_state["result"] = {"out_path": out_path, "stats": d}
        except Exception as e:
            new_state["error"] = str(e)
        finally:
            if vlm_sender is not None:
                try:
                    vlm_sender.unload()
                except Exception:
                    pass
            new_state["done"] = True

    t = threading.Thread(target=_worker, daemon=True)
    new_state["thread"] = t
    t.start()
    return new_state, f"已开始生成（backend={backend}）"


def poll_video(state):
    """轮询进度队列，返回 (进度文本, 输出视频或None, 统计行, 日志)。"""
    if not state:
        return "未运行", None, [], ""
    q = state.get("progress_q")
    last = None
    if q is not None:
        while not q.empty():
            last = q.get()
    if state.get("error"):
        return f"失败：{state['error']}", None, [], state["error"]
    if state.get("done") and state.get("result") is not None:
        d = state["result"]["stats"]
        rows = [
            ["总帧数", str(d.get("total"))],
            ["成功帧", str(d.get("success"))],
            ["关键帧数", str(d.get("keyframe_count"))],
            ["生成帧数", str(d.get("generated_frames"))],
            ["总耗时", f"{d.get('_elapsed', 0):.1f}s"],
        ]
        return "完成", state["result"]["out_path"], rows, "生成完成\n"
    if last is not None:
        return f"生成中 {last[0] + 1}/{last[1]}", None, [], ""
    return "准备/加载模型中...", None, [], ""


def run_video_evaluation(input_video, output_video) -> tuple[list, str]:
    """输入视频 vs 输出视频逐帧评估（PSNR/SSIM/LPIPS）。

    CLIP 需逐帧 prompt（evaluate_video 的 with_clip 门控要求 prompts），单机路径
    未透出逐帧 prompt，故 with_clip=False、不列恒空的 CLIP 列。
    """
    if not input_video or not output_video:
        return [], "错误：需要先完成一次视频生成（缺输入或输出视频）\n"
    orig, _ = read_frames(input_video)
    rest, _ = read_frames(output_video)
    report = evaluate_video(orig, rest, with_lpips=True, with_clip=False)
    summary = report["summary"]
    label = {"psnr": "PSNR", "ssim": "SSIM", "lpips": "LPIPS"}
    rows = []
    for key, name in label.items():
        mean = summary.get(key, {}).get("mean")
        rows.append([name, f"{mean:.4f}" if mean is not None else "—"])
    return rows, "质量评估完成\n"


def build_video_tab(config_components: dict, project_config=None) -> dict:
    """单机 video→video 演示 Tab（后台线程 + gr.Timer 轮询）。"""
    config = project_config if project_config is not None else load_config()
    gr.Markdown("### 视频流演示（单机）\n上传视频，逐帧语义还原为 video→video 闭环。")

    run_state = gr.State(value={})

    with gr.Row():
        with gr.Column(scale=1):
            video_input = gr.Video(label="输入视频")
            backend_radio = gr.Radio(
                choices=[
                    ("klein（关键帧主线）", "klein"),
                    ("diffusers（Z-Image 备选）", "diffusers"),
                ],
                value="klein",
                label="接收端后端",
            )
        with gr.Column(scale=1):
            mode_radio = gr.Radio(
                choices=[("VLM 自动生成", "auto"), ("手动输入", "manual")],
                value="manual",
                label="描述模式",
            )
            prompt_input = gr.Textbox(label="描述文本（整段共用）", lines=2)
            ref_mode = gr.Dropdown(
                choices=["none", "prev", "keyframe", "prev_keyframe"],
                value="prev",
                label="参考帧模式（仅 klein）",
            )
            with gr.Row():
                kf_interval = gr.Number(value=12, precision=0, label="关键帧间隔 N")
                kf_passthrough = gr.Checkbox(value=True, label="关键帧透传")
            with gr.Row():
                seed_input = gr.Number(label="随机种子", precision=0, value=None)
                fps_input = gr.Number(label="输出帧率（空=沿用）", value=None)

    with gr.Row():
        run_btn = gr.Button("▶ 运行", variant="primary")
        unload_btn = gr.Button("卸载 Receiver 模型", variant="secondary")
    unload_status = gr.Markdown("")

    progress_box = gr.Textbox(label="进度", interactive=False)
    video_output = gr.Video(label="输出视频", interactive=False)
    stats_table = gr.Dataframe(headers=["指标", "值"], interactive=False)
    timer = gr.Timer(value=1.5, active=True)

    with gr.Accordion("质量评估（可选）", open=False):
        eval_btn = gr.Button("运行质量评估", variant="secondary")
        eval_table = gr.Dataframe(headers=["指标", "值"], interactive=False)
        eval_log = gr.Textbox(label="评估日志", lines=3, interactive=False)

    with gr.Accordion("运行日志", open=False):
        log_output = gr.Textbox(label="详细日志", lines=6, interactive=False)

    # backend 门控（H2）：diffusers 时禁用并把 ref_mode 值置 none
    def _toggle(b):
        on = b == "klein"
        return (
            gr.update(interactive=on, value=("prev" if on else "none")),
            gr.update(interactive=on),
            gr.update(interactive=on),
        )

    backend_radio.change(
        _toggle, inputs=backend_radio, outputs=[ref_mode, kf_interval, kf_passthrough]
    )
    mode_radio.change(
        lambda m: gr.update(visible=(m == "manual")),
        inputs=mode_radio,
        outputs=prompt_input,
    )

    def _start_bound(state, vp, backend, mode, prompt, rm, ki, kp, seed, fps):
        return start_video(
            state, vp, backend, mode, prompt, rm, ki, kp, seed, fps, config
        )

    run_btn.click(
        _start_bound,
        inputs=[
            run_state,
            video_input,
            backend_radio,
            mode_radio,
            prompt_input,
            ref_mode,
            kf_interval,
            kf_passthrough,
            seed_input,
            fps_input,
        ],
        outputs=[run_state, progress_box],
    )
    timer.tick(
        poll_video,
        inputs=[run_state],
        outputs=[progress_box, video_output, stats_table, log_output],
    )

    def _unload_bound(state):
        state = state or {}
        _, msg = unload_video_receiver(state.get("receiver"))
        state["receiver"] = None
        return state, msg

    unload_btn.click(
        _unload_bound, inputs=[run_state], outputs=[run_state, unload_status]
    )
    eval_btn.click(
        run_video_evaluation,
        inputs=[video_input, video_output],
        outputs=[eval_table, eval_log],
    )
    return {}
