"""semantic-tx video 子命令：端到端视频语义传输 video→video。

发送端逐帧本地 Canny，接收端 Diffusers 本地推理。prompt 策略沿用 demo：
--prompt 整段共用 / --auto-prompt 逐帧 VLM，二者互斥。
"""

import json
from pathlib import Path

import click

from semantic_transmission.common.config import load_config
from semantic_transmission.pipeline.temporal_policy import TemporalPolicyConfig
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
    "--vlm-max-tokens",
    default=512,
    type=int,
    help="auto-prompt 时 VLM 每帧描述的最大 token 数（默认 512；调小可显著提速，"
    "代价是描述更简略，仅 --auto-prompt 时生效）",
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
    "--backend",
    type=click.Choice(["diffusers", "klein"]),
    default="diffusers",
    help="接收端后端（默认 diffusers/Z-Image 备选；klein=FLUX.2-klein-9B 关键帧主线）",
)
@click.option(
    "--reference-mode",
    type=click.Choice(["none", "prev", "keyframe", "prev_keyframe"]),
    default=None,
    help="时序参考帧模式（仅 klein 支持）。缺省按 backend 解析："
    "klein→prev（默认时序补偿），diffusers→none（无时序）。none=复现 drop-in baseline。",
)
@click.option(
    "--keyframe-interval",
    default=12,
    type=int,
    help="关键帧间隔 N（每 N 帧一个关键帧，默认 12）",
)
@click.option(
    "--keyframe-passthrough/--no-keyframe-passthrough",
    default=True,
    help="关键帧是否直接透传原图（不生成、跳过 VLM 描述，默认开）",
)
@click.option(
    "--fps", default=None, type=float, help="输出帧率（默认沿用输入视频 fps）"
)
@click.option(
    "--save-artifacts/--no-save-artifacts",
    default=True,
    help="是否保存语义中间产物（prompts.json 逐帧描述+码率统计、edges/ 边缘图）"
    "到输出目录（默认保存）",
)
def video(
    input_path,
    output_path,
    prompt,
    auto_prompt,
    vlm_max_tokens,
    threshold1,
    threshold2,
    seed,
    backend,
    reference_mode,
    keyframe_interval,
    keyframe_passthrough,
    fps,
    save_artifacts,
):
    """端到端视频语义传输：video → 逐帧语义还原 → video。"""
    if not prompt and not auto_prompt:
        raise click.UsageError("必须指定 --prompt 或 --auto-prompt 之一")
    if prompt and auto_prompt:
        raise click.UsageError("--prompt 和 --auto-prompt 不能同时使用")

    # 时序参考帧默认解析与 backend 门控：
    # - 未显式指定 --reference-mode（None 哨兵）时：klein→prev，diffusers→none。
    # - diffusers 显式传非 none 时序参数直接报错（Z-Image 非多参考模型，不支持时序）。
    if reference_mode is None:
        reference_mode = "prev" if backend == "klein" else "none"
    elif backend != "klein" and reference_mode != "none":
        raise click.UsageError("时序补偿仅 klein 后端支持（--backend klein）")

    temporal_policy = None
    if reference_mode != "none":
        temporal_policy = TemporalPolicyConfig(
            keyframe_interval=keyframe_interval,
            reference_mode=reference_mode,
            keyframe_passthrough=keyframe_passthrough,
        )

    cfg = load_config()
    if threshold1 is None:
        threshold1 = cfg.canny_low_threshold
    if threshold2 is None:
        threshold2 = cfg.canny_high_threshold

    extractor = LocalCannyExtractor(threshold1=threshold1, threshold2=threshold2)
    receiver = create_receiver(backend=backend)

    vlm_sender = None
    if auto_prompt:
        from semantic_transmission.sender.qwen_vl_sender import QwenVLSender

        vlm_sender = QwenVLSender(
            model_name=cfg.vlm_model_name,
            model_path=cfg.vlm_model_path or None,
            max_new_tokens=vlm_max_tokens,
        )

        def prompt_fn(index, frame):
            return vlm_sender.describe(frame).text
    else:

        def prompt_fn(index, frame):
            return prompt

    pipeline = VideoPipeline(receiver, extractor)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # auto-prompt 时，让 VLM 在所有帧描述完成、接收端加载生成模型之前先卸载，
    # 避免 VLM 与 Diffusers 同驻 24GB 显存触发 OOM / CPU offload。
    on_prompts_ready = vlm_sender.unload if vlm_sender is not None else None

    click.echo(f"处理视频: {input_path} → {output_path}")
    try:
        stats = pipeline.run(
            input_path,
            output_path,
            prompt_fn,
            seed=seed,
            fps=fps,
            on_prompts_ready=on_prompts_ready,
            save_artifacts_to=output_path.parent if save_artifacts else None,
            temporal_policy=temporal_policy,
        )
    except Exception as e:
        raise click.ClickException(f"视频处理失败: {e}") from e
    finally:
        # 兜底卸载（unload 幂等）：on_prompts_ready 已释放时此处为空操作；
        # 若在描述阶段就异常退出，则由此处确保 VLM 显存被释放。
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
