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

from semantic_transmission.common.config import ProjectConfig
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
    resolved = resolve_reference_mode(backend, None if ref_mode == "none" else ref_mode)
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
