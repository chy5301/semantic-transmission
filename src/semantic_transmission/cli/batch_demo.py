"""semantic-tx batch-demo 子命令：端到端批量语义传输演示。"""

import json
import sys
import time
from pathlib import Path

import click
from PIL import Image

from semantic_transmission.common.comfyui_client import ComfyUIClient
from semantic_transmission.common.config import ComfyUIConfig, get_default_vlm_path
from semantic_transmission.pipeline.batch_processor import (
    SUPPORTED_IMAGE_EXTS,
    BatchImageDiscoverer,
    BatchResult,
    SampleResult,
    make_sample_output_dir,
)
from semantic_transmission.receiver.comfyui_receiver import ComfyUIReceiver
from semantic_transmission.sender.comfyui_sender import ComfyUISender


def _make_comparison_image(
    original: Image.Image, edge: Image.Image, restored: Image.Image
) -> Image.Image:
    """横向拼接对比图：原图 | 边缘图 | 还原图。"""
    target_height = max(original.height, edge.height, restored.height)

    def resize_to_height(img: Image.Image, height: int) -> Image.Image:
        if img.height == height:
            return img
        ratio = height / img.height
        new_width = int(img.width * ratio)
        return img.resize((new_width, height), Image.LANCZOS)

    imgs = [resize_to_height(img, target_height) for img in [original, edge, restored]]
    total_width = sum(img.width for img in imgs)

    comparison = Image.new("RGB", (total_width, target_height))
    x = 0
    for img in imgs:
        if img.mode != "RGB":
            img = img.convert("RGB")
        comparison.paste(img, (x, 0))
        x += img.width

    return comparison


@click.command()
@click.option(
    "--input-dir",
    required=True,
    type=click.Path(exists=True, path_type=Path),
    help="输入图像目录",
)
@click.option(
    "--output-dir",
    default=Path("output/batch-demo"),
    type=click.Path(path_type=Path),
    help="输出根目录（默认 output/batch-demo）",
)
@click.option("--prompt", default=None, type=str, help="手动指定描述文本（所有图片共用）")
@click.option(
    "--auto-prompt",
    is_flag=True,
    default=False,
    help="使用 VLM (Qwen2.5-VL) 为每张图片自动生成描述",
)
@click.option(
    "--recursive",
    is_flag=True,
    default=False,
    help="递归扫描子目录中的图片",
)
@click.option(
    "--skip-errors",
    is_flag=True,
    default=False,
    help="跳过失败的图片，继续处理下一张",
)
@click.option(
    "--sender-host", default="127.0.0.1", help="发送端 ComfyUI 地址（默认 127.0.0.1）"
)
@click.option(
    "--sender-port", default=8188, type=int, help="发送端 ComfyUI 端口（默认 8188）"
)
@click.option(
    "--receiver-host", default="127.0.0.1", help="接收端 ComfyUI 地址（默认 127.0.0.1）"
)
@click.option(
    "--receiver-port", default=8188, type=int, help="接收端 ComfyUI 端口（默认 8188）"
)
@click.option(
    "--seed", default=None, type=int, help="KSampler 随机种子（可选，便于复现）"
)
@click.option(
    "--vlm-model",
    default=None,
    type=str,
    help="VLM 模型名称（默认 Qwen/Qwen2.5-VL-7B-Instruct）",
)
@click.option(
    "--vlm-model-path",
    default=None,
    type=str,
    help="VLM 模型本地路径（默认 $MODEL_CACHE_DIR/Qwen/Qwen2.5-VL-7B-Instruct）",
)
def batch_demo(
    input_dir,
    output_dir,
    prompt,
    auto_prompt,
    recursive,
    skip_errors,
    sender_host,
    sender_port,
    receiver_host,
    receiver_port,
    seed,
    vlm_model,
    vlm_model_path,
):
    """端到端批量演示：目录中所有图片 → 边缘提取 → 语义还原。"""
    import builtins
    import functools

    _print = functools.partial(builtins.print, flush=True)

    # 校验互斥参数
    if not prompt and not auto_prompt:
        raise click.UsageError("必须指定 --prompt 或 --auto-prompt 之一")
    if prompt and auto_prompt:
        raise click.UsageError("--prompt 和 --auto-prompt 不能同时使用")

    if vlm_model_path is None:
        vlm_model_path = get_default_vlm_path()

    # 创建输出根目录
    output_dir.mkdir(parents=True, exist_ok=True)

    # 扫描目录，发现所有图片
    _print("=" * 60)
    _print("  语义传输批量端到端 Demo")
    _print("=" * 60)
    _print(f"  输入目录: {input_dir}")
    _print(f"  输出目录: {output_dir}")
    _print(f"  递归扫描: {'是' if recursive else '否'}")
    _print(f"  跳过错误: {'是' if skip_errors else '否'}")
    _print()

    _print("[1/5] 扫描目录发现图片...")
    discoverer = BatchImageDiscoverer()
    discovery = discoverer.discover(input_dir, recursive=recursive)

    if not discovery:
        _print(f"  错误: 在 {input_dir} 中没有找到支持的图片文件")
        _print(f"  支持格式: {', '.join(SUPPORTED_IMAGE_EXTS)}")
        sys.exit(1)

    _print(f"  发现图片: {discovery.total_count} 张")
    for ext, count in discovery.formats_detected.items():
        _print(f"    {ext}: {count} 张")
    _print()

    # 构造配置和客户端
    sender_config = ComfyUIConfig(host=sender_host, port=sender_port)
    receiver_config = ComfyUIConfig(host=receiver_host, port=receiver_port)
    sender_client = ComfyUIClient(sender_config)
    receiver_client = ComfyUIClient(receiver_config)

    # 健康检查
    _print("[2/5] 检查 ComfyUI 连接...")
    try:
        sender_client.check_health()
        _print(f"  发送端 ({sender_config.base_url}): OK")
    except Exception as e:
        _print(f"  发送端连接失败: {e}")
        sys.exit(1)

    try:
        receiver_client.check_health()
        _print(f"  接收端 ({receiver_config.base_url}): OK")
    except Exception as e:
        _print(f"  接收端连接失败: {e}")
        sys.exit(1)

    # 初始化发送端和接收端
    sender = ComfyUISender(sender_client)
    receiver = ComfyUIReceiver(receiver_client)

    # 如果是 auto-prompt 模式，预先加载 VLM 模型
    vlm_sender = None
    if auto_prompt:
        import numpy as np

        from semantic_transmission.sender.qwen_vl_sender import QwenVLSender

        _print("\n[3/5] 加载 VLM 模型...")
        vlm_kwargs = {}
        if vlm_model:
            vlm_kwargs["model_name"] = vlm_model
        if vlm_model_path:
            vlm_kwargs["model_path"] = vlm_model_path
        vlm_sender = QwenVLSender(**vlm_kwargs)
        _print("  VLM 模型加载完成")

    # 开始批量处理
    _print("\n[4/5] 开始批量处理...")
    _print("-" * 60)

    total_start = time.time()
    batch_result = BatchResult(total=discovery.total_count)

    for idx, image_path in enumerate(discovery.images, 1):
        image_name = image_path.stem
        rel_path = image_path.relative_to(input_dir)
        _print(f"\n>> [{idx}/{discovery.total_count}] 处理: {rel_path}")

        # 为这张图片创建输出子目录
        sample_output_dir = make_sample_output_dir(output_dir, idx, image_name)

        try:
            # 发送端：提取 Canny 边缘图
            start = time.time()
            edge_image = sender.process(image_path)
            sender_elapsed = time.time() - start

            edge_path = sample_output_dir / "edge.png"
            edge_image.save(edge_path)
            _print(f"  ✓ 边缘提取完成: {edge_path} ({edge_image.size[0]}x{edge_image.size[1]}) "
                  f"耗时 {sender_elapsed:.1f}s")

            # 获取 prompt
            vlm_elapsed = 0.0
            if auto_prompt and vlm_sender is not None:
                original_img = Image.open(image_path).convert("RGB")
                image_array = np.array(original_img)
                start_vlm = time.time()
                sender_output = vlm_sender.describe(image_array)
                vlm_elapsed = time.time() - start_vlm
                prompt_text = sender_output.text
                _print(f"  ✓ VLM 生成完成: {len(prompt_text)} 字符 耗时 {vlm_elapsed:.1f}s")
                _print(f"    描述: {prompt_text[:100]}...")
            else:
                prompt_text = prompt if prompt is not None else ""
                _print(f"  ✓ 使用手动 prompt: {prompt_text[:60]}...")

            # 保存 prompt 文本
            prompt_path = sample_output_dir / "prompt.txt"
            prompt_path.write_text(prompt_text, encoding="utf-8")

            # 接收端：还原图像
            start = time.time()
            restored_image = receiver.process(edge_path, prompt_text, seed=seed)
            receiver_elapsed = time.time() - start

            restored_path = sample_output_dir / "restored.png"
            restored_image.save(restored_path)
            _print(f"  ✓ 还原完成: {restored_path} ({restored_image.size[0]}x{restored_image.size[1]}) "
                  f"耗时 {receiver_elapsed:.1f}s")

            # 生成对比图
            start = time.time()
            original_image = Image.open(image_path)
            comparison = _make_comparison_image(original_image, edge_image, restored_image)
            comparison_path = sample_output_dir / "comparison.png"
            comparison.save(comparison_path)
            comparison_elapsed = time.time() - start
            _print(f"  ✓ 对比图生成完成: {comparison_path} 耗时 {comparison_elapsed:.1f}s")

            # 记录结果
            sample_result = SampleResult(
                name=str(rel_path),
                status="success",
                timings={
                    "sender": sender_elapsed,
                    "vlm": vlm_elapsed,
                    "receiver": receiver_elapsed,
                    "comparison": comparison_elapsed,
                },
            )
            batch_result.add_sample(sample_result)

            # 保存元数据
            metadata = sample_result.to_dict()
            metadata_path = sample_output_dir / "metadata.json"
            with open(metadata_path, "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)

        except Exception as e:
            error_msg = str(e)
            _print(f"  ✗ 处理失败: {error_msg}")

            sample_result = SampleResult(
                name=str(rel_path),
                status="failed",
                error=error_msg,
            )
            batch_result.add_sample(sample_result)

            if not skip_errors:
                _print("\n  遇到错误且 --skip-errors 未启用，中止处理")
                break

            continue

    # 处理完成，卸载 VLM
    if vlm_sender is not None:
        vlm_sender.unload()
        _print("\n  VLM 模型已卸载，释放 GPU 显存")

    # 汇总统计
    total_time = time.time() - total_start
    batch_result.total_time = total_time

    # 保存汇总统计
    summary_path = output_dir / "batch_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(batch_result.to_dict(), f, indent=2, ensure_ascii=False)

    # 输出汇总
    _print("\n" + "=" * 60)
    _print("  批量处理完成")
    _print("=" * 60)
    _print(f"  总计图片: {batch_result.total:>10d} 张")
    _print(f"  处理成功: {batch_result.success:>10d} 张")
    _print(f"  处理失败: {batch_result.failed:>10d} 张")
    _print(f"  跳过: {batch_result.skipped:>10d} 张")
    _print(f"  成功率: {batch_result.success / batch_result.total * 100:>10.1f}%")
    _print(f"  总耗时: {batch_result.total_time:>10.1f}s")
    if batch_result.total > 0:
        _print(f"  单张平均: {batch_result.total_time / batch_result.total:>10.1f}s")
    _print()
    _print(f"  汇总统计: {summary_path}")
    _print(f"  输出目录: {output_dir}/")
