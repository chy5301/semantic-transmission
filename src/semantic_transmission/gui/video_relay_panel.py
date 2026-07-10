"""双机视频 Tab：发送端触发 + 接收端后台线程监听。"""

from __future__ import annotations

import queue
import threading

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
            vlm_sender.unload()
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
