"""semantic-tx batch-sender 子命令：批量发送端。"""

import io
import json
import sys
import time
from pathlib import Path

import click
import numpy as np
from PIL import Image

from semantic_transmission.common.config import get_default_vlm_path
from semantic_transmission.pipeline.relay import SocketRelaySender, TransmissionPacket
from semantic_transmission.pipeline.batch_processor import (
    SUPPORTED_IMAGE_EXTS,
    BatchImageDiscoverer,
    BatchResult,
    SampleResult,
    make_sample_output_dir,
)
from semantic_transmission.sender.local_condition_extractor import LocalCannyExtractor


@click.command()
@click.option(
    "--input-dir",
    required=True,
    type=click.Path(exists=True, path_type=Path),
    help="输入图像目录",
)
@click.option(
    "--output-dir",
    required=True,
    type=click.Path(path_type=Path),
    help="输出目录（保存处理结果，每张图片一个子目录）",
)
@click.option(
    "--prompt", default=None, type=str, help="手动指定描述文本（所有图片共用）"
)
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
    help="跳过失败的图片，继续发送",
)
@click.option("--threshold1", default=100, type=int, help="Canny 低阈值（默认 100）")
@click.option("--threshold2", default=200, type=int, help="Canny 高阈值（默认 200）")
@click.option("--relay-host", required=True, help="接收端机器 IP 地址")
@click.option(
    "--relay-port", default=9000, type=int, help="接收端监听端口（默认 9000）"
)
@click.option(
    "--seed", default=None, type=int, help="KSampler 随机种子（可选，传递给接收端）"
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
def batch_sender(
    input_dir,
    output_dir,
    prompt,
    auto_prompt,
    recursive,
    skip_errors,
    threshold1,
    threshold2,
    relay_host,
    relay_port,
    seed,
    vlm_model,
    vlm_model_path,
):
    """批量发送端：对目录中每张图片提取边缘 + 语义描述 → 发送到接收端。

    使用本地 OpenCV 提取 Canny 边缘。
    """
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
    _print("  语义传输批量发送端（本地 Canny + Qwen2.5-VL）")
    _print("=" * 60)
    _print(f"  输入目录: {input_dir}")
    _print(f"  输出目录: {output_dir}")
    _print(f"  接收端: {relay_host}:{relay_port}")
    _print(f"  Canny 阈值: {threshold1}, {threshold2}")
    _print(f"  递归扫描: {'是' if recursive else '否'}")
    _print(f"  跳过错误: {'是' if skip_errors else '否'}")
    _print()

    _print("[1/3] 扫描目录发现图片...")
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

    # 初始化本地边缘提取器
    extractor = LocalCannyExtractor(threshold1=threshold1, threshold2=threshold2)

    # 如果是 auto-prompt 模式，预先加载 VLM 模型
    vlm_sender = None
    if auto_prompt:
        from semantic_transmission.sender.qwen_vl_sender import QwenVLSender

        _print("[2/4] 加载 VLM 模型...")
        vlm_kwargs = {}
        if vlm_model:
            vlm_kwargs["model_name"] = vlm_model
        if vlm_model_path:
            vlm_kwargs["model_path"] = vlm_model_path
        vlm_sender = QwenVLSender(**vlm_kwargs)
        _print("  VLM 模型加载完成")

    # 先预处理所有图片：提取边缘并保存到输出目录
    # 即使后续连接接收端失败，边缘图已经保存在本地了
    _print("\n[3/4] 预处理图片：提取边缘...")
    _print("-" * 60)

    total_start = time.time()
    batch_result = BatchResult(total=discovery.total_count)

    # 存储处理好的数据待发送
    processed_images = []

    for idx, image_path in enumerate(discovery.images, 1):
        image_name = image_path.stem
        rel_path = image_path.relative_to(input_dir)
        _print(f"\n>> [{idx}/{discovery.total_count}] 处理: {rel_path}")

        # 为这张图片创建输出子目录
        sample_output_dir = make_sample_output_dir(output_dir, idx, image_name)

        try:
            # 读取图像
            original_img = Image.open(image_path).convert("RGB")
            image_array = np.array(original_img)

            # 发送端：本地提取 Canny 边缘图
            start = time.time()
            edge_np = extractor.extract(image_array)
            edge_image = Image.fromarray(edge_np)
            sender_elapsed = time.time() - start

            edge_path = sample_output_dir / "edge.png"
            edge_image.save(edge_path)
            _print(
                f"  [OK] 边缘提取完成: {edge_path} ({edge_image.size[0]}x{edge_image.size[1]}) "
                f"耗时 {sender_elapsed:.3f}s"
            )

            # 获取 prompt
            vlm_elapsed = 0.0
            if auto_prompt and vlm_sender is not None:
                start_vlm = time.time()
                sender_output = vlm_sender.describe(image_array)
                vlm_elapsed = time.time() - start_vlm
                prompt_text = sender_output.text
                _print(
                    f"  [OK] VLM 生成完成: {len(prompt_text)} 字符 耗时 {vlm_elapsed:.1f}s"
                )
                _print(f"    描述: {prompt_text[:100]}...")
            else:
                prompt_text = prompt if prompt is not None else ""
                _print(f"  [OK] 使用手动 prompt: {prompt_text[:60]}...")

            # 保存 prompt 文本
            prompt_path = sample_output_dir / "prompt.txt"
            prompt_path.write_text(prompt_text, encoding="utf-8")

            # 预处理数据包
            buf = io.BytesIO()
            edge_image.save(buf, format="PNG")
            edge_bytes = buf.getvalue()
            metadata = {"timestamp": time.time(), "image_size": list(edge_image.size)}
            if seed is not None:
                metadata["seed"] = seed
            if image_name:
                metadata["image_name"] = image_name

            packet = TransmissionPacket(
                edge_image=edge_bytes, prompt_text=prompt_text, metadata=metadata
            )

            processed_images.append(
                {
                    "packet": packet,
                    "sample_output_dir": sample_output_dir,
                    "edge_path": edge_path,
                    "edge_image": edge_image,
                    "prompt_text": prompt_text,
                    "sender_elapsed": sender_elapsed,
                    "vlm_elapsed": vlm_elapsed,
                    "rel_path": rel_path,
                    "original_bytes": image_path.stat().st_size,
                    "edge_bytes": edge_bytes,
                }
            )

            # 记录结果
            sample_result = SampleResult(
                name=str(rel_path),
                status="success",
                timings={
                    "sender": sender_elapsed,
                    "vlm": vlm_elapsed,
                },
            )
            batch_result.add_sample(sample_result)

            # 保存元数据
            metadata_dict = sample_result.to_dict()
            metadata_dict["packet_bytes"] = len(edge_bytes) + len(
                prompt_text.encode("utf-8")
            )
            metadata_path = sample_output_dir / "metadata.json"
            with open(metadata_path, "w", encoding="utf-8") as f:
                json.dump(metadata_dict, f, indent=2, ensure_ascii=False)

            # 打印压缩信息
            original_bytes = image_path.stat().st_size
            prompt_bytes = len(prompt_text.encode("utf-8"))
            total_bytes = len(edge_bytes) + prompt_bytes
            if original_bytes > 0:
                ratio = original_bytes / total_bytes
                _print(
                    f"    压缩比: {ratio:.2f}x  ({original_bytes:,} → {total_bytes:,} bytes)"
                )

        except Exception as e:
            error_msg = str(e)
            _print(f"  [ERR] 处理失败: {error_msg}")

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

    _print("\n[4/4] 连接接收端并发送...")

    try:
        relay = SocketRelaySender(relay_host, relay_port)
        relay.connect()
        _print(f"  已连接到 {relay_host}:{relay_port}")

        # 逐个发送预处理好的数据
        for data in processed_images:
            start = time.time()
            relay.send(data["packet"])
            relay_elapsed = time.time() - start
            _print(f"  [OK] 已发送 {data['rel_path']} 耗时 {relay_elapsed:.1f}s")
            # 更新 timing
            for sample in batch_result.samples:
                if sample.name == str(data["rel_path"]):
                    sample.timings["relay"] = relay_elapsed
                    break

    except Exception as e:
        _print(f"  [WARN] 连接接收端失败: {e}")
        _print("  但是所有边缘图已经提取保存到输出目录了！")

    finally:
        # 关闭连接
        try:
            relay.close()
        except NameError:
            pass
        # 卸载 VLM
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
    _print("  批量发送完成")
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
    if batch_result.success > 0:
        _print(f"  所有边缘图已保存到 {output_dir}/ 目录，即使发送失败也可以查看结果！")
