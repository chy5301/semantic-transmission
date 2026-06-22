"""semantic-tx video 子命令：端到端视频语义传输 video→video。

发送端逐帧本地 Canny，接收端 Diffusers 本地推理。prompt 策略沿用 demo：
--prompt 整段共用 / --auto-prompt 逐帧 VLM，二者互斥。
"""

import json
from pathlib import Path

import click

from semantic_transmission.common.config import load_config
from semantic_transmission.pipeline.video_pipeline import VideoPipeline
from semantic_transmission.receiver import create_receiver
from semantic_transmission.sender.local_condition_extractor import LocalCannyExtractor


@click.command()
@click.option(
    "--input",
    "input_path",
    required=True,
    type=click.Path(exists=True, path_type=Path),
    help="输入视频路径",
)
@click.option(
    "--output",
    "output_path",
    default=Path("output/video/out.mp4"),
    type=click.Path(path_type=Path),
    help="输出视频路径（默认 output/video/out.mp4）",
)
@click.option("--prompt", default=None, type=str, help="手动描述文本（整段共用）")
@click.option(
    "--auto-prompt",
    is_flag=True,
    default=False,
    help="使用 VLM (Qwen2.5-VL) 为每帧自动生成描述",
)
@click.option(
    "--threshold1",
    default=None,
    type=int,
    help="Canny 低阈值（默认读 config.toml [sender].canny_low_threshold）",
)
@click.option(
    "--threshold2",
    default=None,
    type=int,
    help="Canny 高阈值（默认读 config.toml [sender].canny_high_threshold）",
)
@click.option("--seed", default=None, type=int, help="随机种子（透传给每帧）")
@click.option(
    "--fps", default=None, type=float, help="输出帧率（默认沿用输入视频 fps）"
)
def video(
    input_path,
    output_path,
    prompt,
    auto_prompt,
    threshold1,
    threshold2,
    seed,
    fps,
):
    """端到端视频语义传输：video → 逐帧语义还原 → video。"""
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
    receiver = create_receiver()

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

    pipeline = VideoPipeline(receiver, extractor)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    click.echo(f"处理视频: {input_path} → {output_path}")
    try:
        stats = pipeline.run(input_path, output_path, prompt_fn, seed=seed, fps=fps)
    except Exception as e:
        raise click.ClickException(f"视频处理失败: {e}") from e
    finally:
        if vlm_sender is not None:
            vlm_sender.unload()

    summary_path = output_path.parent / "summary.json"
    summary_path.write_text(
        json.dumps(stats.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
    )
    click.echo(
        f"完成：{stats.success}/{stats.total} 帧成功，"
        f"总耗时 {stats.total_time:.1f}s，统计写入 {summary_path}"
    )
