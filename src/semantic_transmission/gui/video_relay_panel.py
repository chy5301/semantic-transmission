"""双机视频 Tab：发送端触发 + 接收端后台线程监听。"""

from __future__ import annotations

from semantic_transmission.gui.video_panel import build_video_prompt_fn
from semantic_transmission.pipeline.temporal_policy import TemporalPolicyConfig
from semantic_transmission.pipeline.video_relay import VideoRelaySender
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
