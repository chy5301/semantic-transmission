"""双机视频 Tab：发送端触发 + 接收端后台线程监听。"""

from __future__ import annotations

import queue
import threading

import gradio as gr

from semantic_transmission.common.config import load_config
from semantic_transmission.gui.video_panel import build_video_prompt_fn
from semantic_transmission.pipeline.temporal_policy import TemporalPolicyConfig
from semantic_transmission.pipeline.video_relay import (
    VideoRelayReceiver,
    VideoRelaySender,
)
from semantic_transmission.receiver import create_receiver
from semantic_transmission.sender.local_condition_extractor import LocalCannyExtractor


def run_video_sender(
    video_path, host, port, mode, prompt, kf_interval, seed, fps, project_config
):
    """发送端：构造 policy + prompt_fn，调 VideoRelaySender.run，yield 阶段进度与码率账本。"""
    if not video_path:
        yield "", [], "错误：请先上传视频\n"
        return
    extractor = LocalCannyExtractor(
        threshold1=project_config.canny_low_threshold,
        threshold2=project_config.canny_high_threshold,
    )
    vlm_sender = None
    if mode == "auto":
        from semantic_transmission.sender.qwen_vl_sender import QwenVLSender

        vlm_sender = QwenVLSender(
            model_name=project_config.vlm_model_name,
            model_path=project_config.vlm_model_path or None,
        )
    try:
        prompt_fn = build_video_prompt_fn(mode, prompt, vlm_sender)
        kf = int(kf_interval) if kf_interval not in (None, "") else 0
        policy = None
        if kf > 0:
            policy = TemporalPolicyConfig(
                keyframe_interval=kf,
                reference_mode="prev",
                keyframe_passthrough=True,
            )
        yield "发送中...", [], "开始发送...\n"
        stats = VideoRelaySender(extractor).run(
            video_path,
            host,
            int(port),
            prompt_fn,
            seed=(int(seed) if seed not in (None, "") else None),
            fps=(float(fps) if fps not in (None, "") else None),
            temporal_policy=policy,
        )
    except Exception as e:
        yield "失败", [], f"发送失败：{e}\n"
        return
    finally:
        if vlm_sender is not None:
            try:
                vlm_sender.unload()
            except Exception:
                pass
    d = stats.to_dict()
    ratio = (
        (d["keyframe_bytes"] / d["generated_bytes"]) if d.get("generated_bytes") else 0
    )
    rows = [
        ["总帧数", str(d["total_frames"])],
        ["关键帧数", str(d["keyframe_count"])],
        ["生成帧数", str(d["generated_count"])],
        ["关键帧字节", str(d["keyframe_bytes"])],
        ["生成帧字节", str(d["generated_bytes"])],
        ["关键帧∶生成帧倍率", f"{ratio:.1f}x"],
    ]
    yield "完成", rows, "发送完成\n"


def start_listening(state, host, port, backend, ref_mode, output_path, timeout):
    """起后台线程跑 VideoRelayReceiver.run，进度写队列。

    create_receiver（klein 加载可能失败/耗时）在 _worker 内执行并被 try 捕获，
    失败经 state["error"] 回填，避免在主线程裸抛堆栈（design §6.3）。
    """
    state = state or {}
    if state.get("thread") is not None and state["thread"].is_alive():
        return state, "已在监听中，请先停止"
    progress_q = queue.Queue()
    new_state = {
        "thread": None,
        # 与单机不同：每次监听重新加载 receiver（监听场景少见，不复用以简化状态）
        "receiver": None,
        "progress_q": progress_q,
        "result": None,
        "error": None,
        "done": False,
    }

    def _worker():
        try:
            receiver_obj = create_receiver(backend=backend)
            relay_receiver = VideoRelayReceiver(receiver_obj)
            new_state["receiver"] = relay_receiver
            result = relay_receiver.run(
                host,
                int(port),
                output_path,
                timeout=(float(timeout) if timeout not in (None, "") else None),
                reference_mode=(None if ref_mode == "none" else ref_mode),
                progress_callback=lambda i, t, info: progress_q.put((i, t, info)),
            )
            new_state["result"] = result
        except Exception as e:  # 含 stop() 触发的 ConnectionError、模型加载失败
            new_state["error"] = str(e)
        finally:
            new_state["done"] = True

    t = threading.Thread(target=_worker, daemon=True)
    new_state["thread"] = t
    t.start()
    return new_state, f"开始监听 {host}:{port}（backend={backend}）"


def poll_listening(state):
    """轮询进度队列，返回 (进度文本, 输出视频或None)。"""
    if not state:
        return "未监听", None
    q = state.get("progress_q")
    last = None
    if q is not None:
        while not q.empty():
            last = q.get()
    if state.get("error"):
        return f"已停止/出错：{state['error']}", None
    if state.get("done") and state.get("result") is not None:
        if state.get("_emitted"):
            # 已推送过完成结果：返回无变更，避免 Timer 每 tick 重复 re-fetch 视频
            return gr.update(), gr.update()
        state["_emitted"] = True
        return "接收完成", str(state["result"].output_path)
    if last is not None:
        return f"接收中 {last[0] + 1}/{last[1]}", None
    return "监听中，等待发送端连接...", None


def stop_listening(state):
    """中断监听：调用 receiver.stop() 关闭 socket。"""
    if not state or state.get("receiver") is None:
        return state or {}, "当前无监听任务"
    try:
        state["receiver"].stop()
        return state, "已请求停止监听"
    except Exception as e:
        return state, f"停止出错：{e}"


def build_video_relay_tab(config_components: dict, project_config=None) -> dict:
    """双机 video→video relay Tab：发送端上传 + 接收端后台监听 + Timer 轮询。"""
    config = project_config if project_config is not None else load_config()
    gr.Markdown(
        "### 双机视频传输\n"
        "发送端：上传视频 → 发送到对端接收机（TCP）。"
        "接收端：后台线程监听 → 还原视频。"
    )

    sender_state = gr.State(value={})
    receiver_state = gr.State(value={})

    with gr.Row():
        with gr.Column(scale=1):
            gr.Markdown("#### 发送端")
            video_input = gr.Video(label="输入视频")
            sender_host = gr.Textbox(
                value="127.0.0.1",
                label="接收机地址（host）",
            )
            sender_port = gr.Number(
                value=9000,
                precision=0,
                label="接收机端口",
            )
            sender_mode = gr.Radio(
                choices=[("VLM 自动生成", "auto"), ("手动输入", "manual")],
                value="manual",
                label="描述模式",
            )
            sender_prompt = gr.Textbox(label="描述文本", lines=2)
            sender_kf_interval = gr.Number(value=12, precision=0, label="关键帧间隔 N")
            sender_seed = gr.Number(label="随机种子", precision=0, value=None)
            sender_fps = gr.Number(label="输出帧率（空=沿用）", value=None)
            send_btn = gr.Button("▶ 发送视频", variant="primary")

        with gr.Column(scale=1):
            gr.Markdown("#### 接收端")
            receiver_host = gr.Textbox(
                value="0.0.0.0",
                label="监听地址（host）",
            )
            receiver_port = gr.Number(
                value=9000,
                precision=0,
                label="监听端口",
            )
            backend_radio = gr.Radio(
                choices=[
                    ("klein（关键帧主线）", "klein"),
                    ("diffusers（Z-Image 备选）", "diffusers"),
                ],
                value="klein",
                label="接收端后端",
            )
            ref_mode = gr.Dropdown(
                choices=["none", "prev", "keyframe", "prev_keyframe"],
                value="prev",
                label="参考帧模式（仅 klein）",
            )
            output_path_input = gr.Textbox(
                value="output/video_relay/gui_out.mp4", label="输出路径"
            )
            timeout_input = gr.Number(label="监听超时（秒）", value=None)
            listen_btn = gr.Button("▶ 开始监听", variant="primary")
            stop_btn = gr.Button("■ 停止监听", variant="secondary")

    progress_box = gr.Textbox(label="发送进度", interactive=False)
    sender_stats = gr.Dataframe(headers=["指标", "值"], interactive=False)
    sender_log = gr.Textbox(label="发送日志", lines=3, interactive=False)

    receiver_progress = gr.Textbox(label="接收进度", interactive=False)
    video_output = gr.Video(label="输出视频", interactive=False)

    timer = gr.Timer(value=1.5, active=True)

    def _sender_bound(state, video_path, host, port, mode, prompt, kf, seed, fps):
        # port 由 run_video_sender 内部统一 int() 归一，此处不重复转换
        gen = run_video_sender(
            video_path,
            host,
            port,
            mode,
            prompt,
            kf,
            seed,
            fps,
            config,
        )
        for progress, stats_rows, log in gen:
            yield state, progress, stats_rows, log

    def _receiver_bound(state, host, port, backend, rm, output_path, timeout):
        # port 由 start_listening 内部统一 int() 归一，此处不重复转换
        return start_listening(state, host, port, backend, rm, output_path, timeout)

    send_btn.click(
        _sender_bound,
        inputs=[
            sender_state,
            video_input,
            sender_host,
            sender_port,
            sender_mode,
            sender_prompt,
            sender_kf_interval,
            sender_seed,
            sender_fps,
        ],
        outputs=[sender_state, progress_box, sender_stats, sender_log],
    )

    listen_btn.click(
        _receiver_bound,
        inputs=[
            receiver_state,
            receiver_host,
            receiver_port,
            backend_radio,
            ref_mode,
            output_path_input,
            timeout_input,
        ],
        outputs=[receiver_state, receiver_progress],
    )

    stop_btn.click(
        stop_listening,
        inputs=[receiver_state],
        outputs=[receiver_state, receiver_progress],
    )

    timer.tick(
        poll_listening,
        inputs=[receiver_state],
        outputs=[receiver_progress, video_output],
    )

    return {}
