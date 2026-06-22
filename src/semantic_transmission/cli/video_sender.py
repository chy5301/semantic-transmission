"""semantic-tx video-sender 子命令：视频流双机发送端。

逐帧本地 Canny + 可选 VLM，经 TCP relay 逐帧发送到接收端机器。
prompt 策略沿用 video：--prompt 整段共用 / --auto-prompt 逐帧 VLM，互斥。
"""

import json
from pathlib import Path

import click

from semantic_transmission.common.config import load_config
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
):
    """视频流双机发送端：逐帧 Canny + 描述 → 经 relay 发送。"""
    if not prompt and not auto_prompt:
        raise click.UsageError("必须指定 --prompt 或 --auto-prompt 之一")
    if prompt and auto_prompt:
        raise click.UsageError("--prompt 和 --auto-prompt 不能同时使用")

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
    else:

        def prompt_fn(index, frame):
            return prompt

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
        )
    except Exception as e:
        raise click.ClickException(f"发送失败: {e}") from e
    finally:
        if vlm_sender is not None:
            vlm_sender.unload()

    summary_path = Path(summary_path)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(
        json.dumps(stats.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
    )
    click.echo(
        f"完成：发送 {stats.total_frames} 帧，"
        f"总耗时 {stats.total_time:.1f}s，统计写入 {summary_path}"
    )
