"""视频流演示 Tab（单机 video→video）：后台线程 + queue + gr.Timer 轮询。

Gradio 生成器无法从内部同步阻塞的 VideoPipeline.run() 转发进度，故与双机接收端
同构：daemon 线程跑 run(progress_callback=写队列)，gr.Timer 轮询刷新。
"""

from __future__ import annotations

from typing import Callable

from semantic_transmission.receiver.base import BaseReceiver


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
