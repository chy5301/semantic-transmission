"""semantic-tx sender 子命令：双机演示发送端。

不依赖 ComfyUI，使用本地 OpenCV 提取 Canny 边缘。
"""

import io
import time
from pathlib import Path

import click
import numpy as np
from PIL import Image

from semantic_transmission.common.config import get_default_vlm_path
from semantic_transmission.pipeline.relay import SocketRelaySender, TransmissionPacket
from semantic_transmission.sender.local_condition_extractor import LocalCannyExtractor


@click.command()
@click.option(
    "--image",
    required=True,
    type=click.Path(exists=True, path_type=Path),
    help="输入图像路径",
)
@click.option("--prompt", default=None, type=str, help="手动指定描述文本")
@click.option(
    "--auto-prompt",
    is_flag=True,
    default=False,
    help="使用 VLM (Qwen2.5-VL) 自动生成描述",
)
@click.option(
    "--threshold1", default=100, type=int, help="Canny 低阈值（默认 100）"
)
@click.option(
    "--threshold2", default=200, type=int, help="Canny 高阈值（默认 200）"
)
@click.option("--vlm-model", default=None, type=str, help="VLM 模型名称")
@click.option(
    "--vlm-model-path",
    default=None,
    type=str,
    help="VLM 模型本地路径（默认 $MODEL_CACHE_DIR/Qwen/Qwen2.5-VL-7B-Instruct）",
)
@click.option(
    "--output-dir",
    default=Path("output/sender"),
    type=click.Path(path_type=Path),
    help="输出目录（保存边缘图和 prompt，默认 output/sender）",
)
@click.option("--relay-host", required=True, help="接收端机器 IP 地址")
@click.option(
    "--relay-port", default=9000, type=int, help="接收端监听端口（默认 9000）"
)
@click.option(
    "--seed", default=None, type=int, help="KSampler 随机种子（可选，传递给接收端）"
)
def sender(
    image,
    prompt,
    auto_prompt,
    threshold1,
    threshold2,
    vlm_model,
    vlm_model_path,
    output_dir,
    relay_host,
    relay_port,
    seed,
):
    """发送端：提取边缘图 + 语义描述 → 发送到接收端。

    不依赖 ComfyUI，使用本地 OpenCV 提取 Canny 边缘。
    即使接收端连接失败，结果也会保存到输出目录。
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

    # 创建输出目录
    output_dir.mkdir(parents=True, exist_ok=True)
    image_name = Path(image).stem

    _print("=" * 60)
    _print("  语义传输发送端（本地 Canny，不依赖 ComfyUI）")
    _print("=" * 60)
    _print(f"  输入图像: {image}")
    _print(f"  Canny 阈值: {threshold1}, {threshold2}")
    _print(f"  输出目录: {output_dir}")
    _print(f"  接收端: {relay_host}:{relay_port}")

    # 读取图像
    _print("\n[1/4] 读取图像...")
    original_img = Image.open(image).convert("RGB")
    image_array = np.array(original_img)
    _print(f"  图像尺寸: {original_img.width}x{original_img.height}")

    # 本地提取 Canny 边缘图
    _print("\n[2/4] 本地提取 Canny 边缘图...")
    extractor = LocalCannyExtractor(threshold1=threshold1, threshold2=threshold2)
    start = time.time()
    edge_np = extractor.extract(image_array)
    edge_image = Image.fromarray(edge_np)
    sender_elapsed = time.time() - start
    _print(f"  边缘图: {edge_image.size[0]}x{edge_image.size[1]}")
    _print(f"  耗时: {sender_elapsed:.3f}s")

    # 获取 prompt
    vlm_elapsed = 0.0
    _print("\n[3/4] 获取语义描述...")
    if auto_prompt:
        from semantic_transmission.sender.qwen_vl_sender import QwenVLSender

        _print("  模式: VLM 自动描述 (Qwen2.5-VL)")
        vlm_kwargs = {}
        if vlm_model:
            vlm_kwargs["model_name"] = vlm_model
        if vlm_model_path:
            vlm_kwargs["model_path"] = vlm_model_path
        vlm_sender = QwenVLSender(**vlm_kwargs)
        _print("  正在加载 VLM 模型...")
        start_vlm = time.time()
        sender_output = vlm_sender.describe(image_array)
        vlm_elapsed = time.time() - start_vlm
        prompt_text = sender_output.text
        _print(f"  VLM 耗时: {vlm_elapsed:.1f}s")
        _print(f"  描述长度: {len(prompt_text)} 字符")
        _print(f"  描述预览: {prompt_text[:200]}...")
        vlm_sender.unload()
        _print("  VLM 模型已卸载")
    else:
        prompt_text = prompt
        _print("  模式: 手动 prompt")
        _print(f"  文本: {prompt_text}")

    # 先保存到本地输出目录，即使发送失败也有结果
    edge_path = output_dir / f"{image_name}_edge.png"
    edge_image.save(edge_path)
    prompt_path = output_dir / f"{image_name}_prompt.txt"
    prompt_path.write_text(prompt_text, encoding="utf-8")
    _print("\n  [OK] 结果已保存到本地:")
    _print(f"    边缘图: {edge_path}")
    _print(f"    Prompt: {prompt_path}")

    # 构造数据包并发送
    _print("\n[4/4] 发送数据到接收端...")
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

    relay_elapsed = 0.0
    try:
        start = time.time()
        with SocketRelaySender(relay_host, relay_port) as relay:
            relay.send(packet)
        relay_elapsed = time.time() - start
        _print(f"  [OK] 已发送到 {relay_host}:{relay_port}")
        _print(f"  传输耗时: {relay_elapsed:.1f}s")
    except Exception as e:
        _print(f"  [WARN] 连接接收端失败: {e}")
        _print(f"  但是结果已经保存到 {output_dir}/ 目录，可以查看！")

    # 传输统计
    prompt_bytes = len(prompt_text.encode("utf-8"))
    total_bytes = len(edge_bytes) + prompt_bytes
    original_bytes = Path(image).stat().st_size
    total_elapsed = sender_elapsed + vlm_elapsed + relay_elapsed

    _print("\n" + "=" * 60)
    _print("  发送完成")
    _print("=" * 60)
    _print(f"  原始图像大小:    {original_bytes:>10,} bytes")
    _print(f"  边缘图大小:      {len(edge_bytes):>10,} bytes")
    _print(f"  Prompt 大小:     {prompt_bytes:>10,} bytes")
    _print(f"  传输数据总量:    {total_bytes:>10,} bytes")
    _print(f"  压缩比:          {original_bytes / total_bytes:>10.2f}x")
    _print(f"  发送端耗时:      {sender_elapsed:>10.3f}s")
    if auto_prompt:
        _print(f"  VLM 耗时:        {vlm_elapsed:>10.1f}s")
    _print(f"  网络传输耗时:    {relay_elapsed:>10.1f}s")
    _print(f"  总耗时:          {total_elapsed:>10.1f}s")
    _print()
    _print("  本地结果文件:")
    _print(f"    {edge_path}")
    _print(f"    {prompt_path}")
