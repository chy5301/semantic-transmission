#!/usr/bin/env python3
"""端到端批量处理演示脚本。

示例:
    python scripts/batch_demo.py \\
      --input-dir ./resources/test_images \\
      --output-dir ./output/batch \\
      --auto-prompt
"""

import argparse
import json
import sys
import time
from pathlib import Path

from PIL import Image

from semantic_transmission.common.comfyui_client import ComfyUIClient
from semantic_transmission.common.config import ComfyUIConfig, get_default_vlm_path
from semantic_transmission.pipeline.batch_processor import (
    BatchImageDiscoverer,
    BatchResult,
    SampleResult,
    make_sample_output_dir,
)
from semantic_transmission.receiver.comfyui_receiver import ComfyUIReceiver
from semantic_transmission.sender.comfyui_sender import ComfyUISender


def make_comparison_image(
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


def main():
    parser = argparse.ArgumentParser(
        description="端到端批量处理演示：输入目录 → 逐张处理 → 输出目录"
    )
    parser.add_argument("--input-dir", required=True, help="输入图像目录")
    parser.add_argument(
        "--output-dir", default="output/batch-script", help="输出根目录"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--prompt", help="手动指定描述文本（所有图片共用）")
    group.add_argument(
        "--auto-prompt", action="store_true", help="使用 VLM 为每张图片自动生成描述"
    )
    parser.add_argument(
        "--recursive", action="store_true", help="递归扫描子目录"
    )
    parser.add_argument(
        "--skip-errors", action="store_true", help="跳过失败的图片，继续处理"
    )
    parser.add_argument(
        "--sender-host", default="127.0.0.1", help="发送端 ComfyUI 地址"
    )
    parser.add_argument("--sender-port", type=int, default=8188, help="发送端 ComfyUI 端口")
    parser.add_argument(
        "--receiver-host", default="127.0.0.1", help="接收端 ComfyUI 地址"
    )
    parser.add_argument("--receiver-port", type=int, default=8188, help="接收端 ComfyUI 端口")
    parser.add_argument("--seed", type=int, help="KSampler 随机种子")
    parser.add_argument("--vlm-model-path", help="VLM 模型本地路径")
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)

    if not input_dir.exists():
        print(f"错误：输入目录不存在: {input_dir}")
        sys.exit(1)

    output_dir.mkdir(parents=True, exist_ok=True)

    vlm_model_path = args.vlm_model_path or get_default_vlm_path()

    # 扫描目录
    print("=" * 60)
    print("  语义传输批量端到端 Demo (脚本版本)")
    print("=" * 60)
    print(f"  输入目录: {input_dir}")
    print(f"  输出目录: {output_dir}")
    print()

    print("[1/5] 扫描目录发现图片...")
    discoverer = BatchImageDiscoverer()
    discovery = discoverer.discover(input_dir, recursive=args.recursive)

    if not discovery:
        print(f"  错误: 在 {input_dir} 中没有找到支持的图片文件")
        sys.exit(1)

    print(f"  发现图片: {discovery.total_count} 张")
    for ext, count in discovery.formats_detected.items():
        print(f"    {ext}: {count} 张")
    print()

    # 构造客户端
    sender_config = ComfyUIConfig(host=args.sender_host, port=args.sender_port)
    receiver_config = ComfyUIConfig(host=args.receiver_host, port=args.receiver_port)
    sender_client = ComfyUIClient(sender_config)
    receiver_client = ComfyUIClient(receiver_config)

    # 健康检查
    print("[2/5] 检查 ComfyUI 连接...")
    try:
        sender_client.check_health()
        print(f"  发送端 ({sender_config.base_url}): OK")
    except Exception as e:
        print(f"  发送端连接失败: {e}")
        sys.exit(1)

    try:
        receiver_client.check_health()
        print(f"  接收端 ({receiver_config.base_url}): OK")
    except Exception as e:
        print(f"  接收端连接失败: {e}")
        sys.exit(1)

    # 初始化发送端和接收端
    sender = ComfyUISender(sender_client)
    receiver = ComfyUIReceiver(receiver_client)

    # 加载 VLM 如果需要
    vlm_sender = None
    if args.auto_prompt:
        import numpy as np

        from semantic_transmission.sender.qwen_vl_sender import QwenVLSender

        print("\n[3/5] 加载 VLM 模型...")
        vlm_kwargs = {"model_path": vlm_model_path}
        vlm_sender = QwenVLSender(**vlm_kwargs)
        print("  VLM 模型加载完成")

    # 开始批量处理
    print("\n[4/5] 开始批量处理...")
    print("-" * 60)

    total_start = time.time()
    batch_result = BatchResult(total=discovery.total_count)

    for idx, image_path in enumerate(discovery.images, 1):
        image_name = image_path.stem
        rel_path = image_path.relative_to(input_dir)
        print(f"\n>> [{idx}/{discovery.total_count}] 处理: {rel_path}")

        sample_output_dir = make_sample_output_dir(output_dir, idx, image_name)

        try:
            # 提取边缘
            start = time.time()
            edge_image = sender.process(image_path)
            sender_elapsed = time.time() - start

            edge_path = sample_output_dir / "edge.png"
            edge_image.save(edge_path)
            print(f"  ✓ 边缘提取完成: {edge_path} ({edge_image.size[0]}x{edge_image.size[1]}) "
                  f"耗时 {sender_elapsed:.1f}s")

            # 获取 prompt
            vlm_elapsed = 0.0
            if args.auto_prompt and vlm_sender is not None:
                original_img = Image.open(image_path).convert("RGB")
                image_array = np.array(original_img)
                start_vlm = time.time()
                sender_output = vlm_sender.describe(image_array)
                vlm_elapsed = time.time() - start_vlm
                prompt_text = sender_output.text
                print(f"  ✓ VLM 生成完成: {len(prompt_text)} 字符 耗时 {vlm_elapsed:.1f}s")
                print(f"    描述: {prompt_text[:100]}...")
            else:
                prompt_text = args.prompt
                print(f"  ✓ 使用手动 prompt: {prompt_text[:60]}...")

            # 保存 prompt
            prompt_path = sample_output_dir / "prompt.txt"
            prompt_path.write_text(prompt_text, encoding="utf-8")

            # 还原图像
            start = time.time()
            restored_image = receiver.process(edge_path, prompt_text, seed=args.seed)
            receiver_elapsed = time.time() - start

            restored_path = sample_output_dir / "restored.png"
            restored_image.save(restored_path)
            print(f"  ✓ 还原完成: {restored_path} ({restored_image.size[0]}x{restored_image.size[1]}) "
                  f"耗时 {receiver_elapsed:.1f}s")

            # 生成对比图
            start = time.time()
            original_image = Image.open(image_path)
            comparison = make_comparison_image(original_image, edge_image, restored_image)
            comparison_path = sample_output_dir / "comparison.png"
            comparison.save(comparison_path)
            comparison_elapsed = time.time() - start
            print(f"  ✓ 对比图生成完成: {comparison_path} 耗时 {comparison_elapsed:.1f}s")

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
            print(f"  ✗ 处理失败: {error_msg}")

            sample_result = SampleResult(
                name=str(rel_path),
                status="failed",
                error=error_msg,
            )
            batch_result.add_sample(sample_result)

            if not args.skip_errors:
                print("\n  遇到错误且 --skip-errors 未启用，中止处理")
                break

            continue

    # 卸载 VLM
    if vlm_sender is not None:
        vlm_sender.unload()
        print("\n  VLM 模型已卸载，释放 GPU 显存")

    # 汇总统计
    total_time = time.time() - total_start
    batch_result.total_time = total_time

    # 保存汇总
    summary_path = output_dir / "batch_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(batch_result.to_dict(), f, indent=2, ensure_ascii=False)

    # 输出汇总
    print("\n" + "=" * 60)
    print("  批量处理完成")
    print("=" * 60)
    print(f"  总计图片: {batch_result.total:>10d} 张")
    print(f"  处理成功: {batch_result.success:>10d} 张")
    print(f"  处理失败: {batch_result.failed:>10d} 张")
    print(f"  跳过: {batch_result.skipped:>10d} 张")
    print(f"  成功率: {batch_result.success / batch_result.total * 100:>10.1f}%")
    print(f"  总耗时: {batch_result.total_time:>10.1f}s")
    if batch_result.total > 0:
        print(f"  单张平均: {batch_result.total_time / batch_result.total:>10.1f}s")
    print()
    print(f"  汇总统计: {summary_path}")
    print(f"  输出目录: {output_dir}/")


if __name__ == "__main__":
    main()
