"""semantic-tx video-sender 子命令：视频流双机发送端。

逐帧本地 Canny + 可选 VLM，经 TCP relay 逐帧发送到接收端机器。
prompt 策略沿用 video：--prompt 整段共用 / --auto-prompt 逐帧 VLM，互斥。
"""

import json
from pathlib import Path

import click

from semantic_transmission.common.config import load_config
from semantic_transmission.pipeline.temporal_policy import (
    TemporalPolicyConfig,
    is_keyframe,
)
from semantic_transmission.pipeline.video_relay import VideoRelaySender
from semantic_transmission.sender.local_condition_extractor import LocalCannyExtractor


@click.command(name="video-sender")
@click.option(
    "--input",
    "input_path",
    required=True,
    type=click.Path(exists=True, path_type=Path),
    help="输入视频路径",
)
@click.option("--relay-host", required=True, help="接收端机器 IP 地址")
@click.option("--relay-port", default=9000, type=int, help="接收端端口（默认 9000）")
@click.option("--prompt", default=None, type=str, help="手动描述文本（整段共用）")
@click.option(
    "--auto-prompt",
    is_flag=True,
    default=False,
    help="使用 VLM (Qwen2.5-VL) 为每帧自动生成描述",
)
@click.option("--threshold1", default=None, type=int, help="Canny 低阈值")
@click.option("--threshold2", default=None, type=int, help="Canny 高阈值")
@click.option("--seed", default=None, type=int, help="随机种子（透传给每帧）")
@click.option("--fps", default=None, type=float, help="输出帧率（默认沿用输入 fps）")
@click.option(
    "--save-frames-dir",
    default=None,
    type=click.Path(path_type=Path),
    help="可选：把每帧边缘图存盘（调试用）",
)
@click.option(
    "--summary",
    "summary_path",
    default=Path("output/video_relay/sender_summary.json"),
    type=click.Path(path_type=Path),
    help="发送端统计 JSON 输出路径",
)
@click.option(
    "--prompts-json",
    "prompts_json",
    default=None,
    type=click.Path(exists=True, path_type=Path),
    help="从预生成 prompts.json 逐帧读取描述（不加载 VLM，供 loopback 测试）",
)
@click.option(
    "--keyframe-interval",
    default=12,
    type=int,
    help="关键帧间隔 N（每 N 帧一个关键帧透传整帧，默认 12；<=0 关闭时序退回逐帧）",
)
def video_sender(
    input_path,
    relay_host,
    relay_port,
    prompt,
    auto_prompt,
    threshold1,
    threshold2,
    seed,
    fps,
    save_frames_dir,
    summary_path,
    prompts_json,
    keyframe_interval,
):
    """视频流双机发送端：逐帧 Canny + 描述 → 经 relay 发送。"""
    sources = [prompt is not None, auto_prompt, prompts_json is not None]
    if sum(sources) == 0:
        raise click.UsageError(
            "必须指定 --prompt / --auto-prompt / --prompts-json 之一"
        )
    if sum(sources) > 1:
        raise click.UsageError("--prompt / --auto-prompt / --prompts-json 只能指定一个")

    cfg = load_config()
    if threshold1 is None:
        threshold1 = cfg.canny_low_threshold
    if threshold2 is None:
        threshold2 = cfg.canny_high_threshold

    extractor = LocalCannyExtractor(threshold1=threshold1, threshold2=threshold2)

    vlm_sender = None
    if auto_prompt:
        from semantic_transmission.sender.qwen_vl_sender import QwenVLSender

        vlm_sender = QwenVLSender(
            model_name=cfg.vlm_model_name,
            model_path=cfg.vlm_model_path or None,
        )

        def prompt_fn(index, frame):
            return vlm_sender.describe(frame).text
    elif prompts_json is not None:
        payload = json.loads(prompts_json.read_text(encoding="utf-8"))
        # 时序 prompts.json（_save_temporal_artifacts 产出）含顶层 keyframe_indices：
        # 若重放 --keyframe-interval 与生成时不一致，原关键帧下标会被误判为生成帧，
        # by_index.get(index, "") 对其静默返回空 prompt。此处校验关键帧集一致，
        # 不一致直接 fail-fast，而非静默送空 prompt 进生成。非时序 prompts.json
        # （无 keyframe_indices 字段，全帧有 prompt）跳过此项校验。
        if "keyframe_indices" in payload:
            total = payload.get("total_frames")
            if total is None:
                raise click.UsageError(
                    "prompts.json 含 keyframe_indices 但缺少 total_frames 字段，"
                    "无法校验 --keyframe-interval"
                )
            check_policy = TemporalPolicyConfig(keyframe_interval=keyframe_interval)
            expected_kf = {i for i in range(total) if is_keyframe(i, check_policy)}
            payload_kf = set(payload["keyframe_indices"])
            if payload_kf != expected_kf:
                raise click.UsageError(
                    "prompts.json 的关键帧集与 --keyframe-interval 不匹配，"
                    "请用生成时相同的 --keyframe-interval 重放"
                )
        # prompts.json 的 frames: [{index, prompt?, passthrough?}]；关键帧无 prompt。
        by_index = {f["index"]: f.get("prompt", "") for f in payload.get("frames", [])}

        def prompt_fn(index, frame):
            return by_index.get(index, "")
    else:

        def prompt_fn(index, frame):
            return prompt

    temporal_policy = None
    if keyframe_interval > 0:
        temporal_policy = TemporalPolicyConfig(
            keyframe_interval=keyframe_interval,
            reference_mode="prev",
            keyframe_passthrough=True,
        )

    click.echo(f"发送视频: {input_path} → {relay_host}:{relay_port}")
    sender = VideoRelaySender(extractor)
    try:
        stats = sender.run(
            input_path,
            relay_host,
            relay_port,
            prompt_fn,
            seed=seed,
            fps=fps,
            save_frames_dir=save_frames_dir,
            temporal_policy=temporal_policy,
        )
    except Exception as e:
        raise click.ClickException(f"发送失败: {e}") from e
    finally:
        if vlm_sender is not None:
            vlm_sender.unload()

    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(
        json.dumps(stats.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
    )
    click.echo(
        f"完成：发送 {stats.total_frames} 帧，"
        f"总耗时 {stats.total_time:.1f}s，统计写入 {summary_path}"
    )
