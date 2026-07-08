"""semantic-tx video-receiver 子命令：视频流双机接收端。

监听端口逐帧接收 → Diffusers 还原 → 按帧序收齐合成视频，并写 summary
（含每帧 prompt，供 evaluate_video 算 CLIP）。
"""

import json
from pathlib import Path

import click

from semantic_transmission.pipeline.video_relay import VideoRelayReceiver
from semantic_transmission.receiver import create_receiver


@click.command(name="video-receiver")
@click.option("--relay-host", default="0.0.0.0", help="监听地址（默认 0.0.0.0）")
@click.option("--relay-port", default=9000, type=int, help="监听端口（默认 9000）")
@click.option(
    "--output",
    "output_path",
    default=Path("output/video_relay/out.mp4"),
    type=click.Path(path_type=Path),
    help="输出视频路径（默认 output/video_relay/out.mp4）",
)
@click.option(
    "--timeout",
    default=None,
    type=float,
    help="accept/receive 超时秒数（默认无限等待）",
)
@click.option(
    "--backend",
    type=click.Choice(["diffusers", "klein"]),
    default="klein",
    help="接收端后端（默认 klein，关键帧主线时序补偿；可选 diffusers 无状态逐帧）",
)
@click.option(
    "--reference-mode",
    type=click.Choice(["none", "prev", "keyframe", "prev_keyframe"]),
    default=None,
    help="时序参考帧模式（仅 klein）。缺省：klein→prev，diffusers→无时序",
)
def video_receiver(
    relay_host, relay_port, output_path, timeout, backend, reference_mode
):
    """视频流双机接收端：逐帧接收还原 → 收齐合成视频。"""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 时序参考帧默认解析与 backend 门控（对齐单机 video.py 口径）：
    # - 未显式指定 --reference-mode（None 哨兵）时：klein→prev，diffusers→无时序。
    # - diffusers 显式传非 none 时序参数直接报错。
    if reference_mode is None:
        reference_mode = "prev" if backend == "klein" else None
    elif backend != "klein" and reference_mode != "none":
        raise click.UsageError("时序补偿仅 klein 后端支持（--backend klein）")
    # none 归一为 None（无时序，走无状态路径）
    if reference_mode == "none":
        reference_mode = None

    click.echo(f"监听 {relay_host}:{relay_port}，输出 → {output_path}")
    recv = create_receiver(backend=backend)
    receiver = VideoRelayReceiver(recv)
    try:
        result = receiver.run(
            relay_host,
            relay_port,
            output_path,
            timeout=timeout,
            reference_mode=reference_mode,
        )
    except Exception as e:
        raise click.ClickException(f"接收失败: {e}") from e
    finally:
        if hasattr(recv, "unload"):
            try:
                recv.unload()
            except Exception as exc:
                click.echo(f"[WARN] receiver.unload() 失败: {exc}")

    summary = result.stats.to_dict()
    summary["fps"] = result.fps
    summary["frames"] = [
        {"index": i, "prompt": p} for i, p in enumerate(result.prompts)
    ]
    summary["failed_indices"] = result.failed_indices
    summary_path = output_path.parent / "receiver_summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    click.echo(
        f"完成：{result.stats.success}/{result.stats.total} 帧成功，"
        f"视频写入 {output_path}，统计写入 {summary_path}"
    )
