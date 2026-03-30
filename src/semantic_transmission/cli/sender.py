"""semantic-tx sender 子命令：双机演示发送端。"""

import io
import sys
import time
from pathlib import Path

import click
from PIL import Image

from semantic_transmission.common.comfyui_client import ComfyUIClient
from semantic_transmission.common.config import ComfyUIConfig, get_default_vlm_path
from semantic_transmission.pipeline.relay import SocketRelaySender, TransmissionPacket
from semantic_transmission.sender.comfyui_sender import ComfyUISender


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
@click.option("--vlm-model", default=None, type=str, help="VLM 模型名称")
@click.option(
    "--vlm-model-path",
    default=None,
    type=str,
    help="VLM 模型本地路径（默认 $MODEL_CACHE_DIR/Qwen/Qwen2.5-VL-7B-Instruct）",
)
@click.option(
    "--comfyui-host", default="127.0.0.1", help="本机 ComfyUI 地址（默认 127.0.0.1）"
)
@click.option(
    "--comfyui-port", default=8188, type=int, help="本机 ComfyUI 端口（默认 8188）"
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
    vlm_model,
    vlm_model_path,
    comfyui_host,
    comfyui_port,
    relay_host,
    relay_port,
    seed,
):
    """发送端：提取边缘图 + 语义描述 → 发送到接收端。"""
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

    config = ComfyUIConfig(host=comfyui_host, port=comfyui_port)
    client = ComfyUIClient(config)

    _print("=" * 60)
    _print("  语义传输发送端")
    _print("=" * 60)
    _print(f"  输入图像: {image}")
    _print(f"  ComfyUI: {config.base_url}")
    _print(f"  接收端: {relay_host}:{relay_port}")

    # 健康检查
    _print("\n[1/4] 检查 ComfyUI 连接...")
    try:
        client.check_health()
        _print(f"  ComfyUI ({config.base_url}): OK")
    except Exception as e:
        _print(f"  ComfyUI 连接失败: {e}")
        sys.exit(1)

    # 提取边缘图
    _print("\n[2/4] 提取 Canny 边缘图...")
    sender = ComfyUISender(client)
    start = time.time()
    edge_image = sender.process(image)
    sender_elapsed = time.time() - start
    _print(f"  边缘图: {edge_image.size[0]}x{edge_image.size[1]}")
    _print(f"  耗时: {sender_elapsed:.1f}s")

    # 获取 prompt
    vlm_elapsed = 0.0
    _print("\n[3/4] 获取语义描述...")
    if auto_prompt:
        import numpy as np

        from semantic_transmission.sender.qwen_vl_sender import QwenVLSender

        _print("  模式: VLM 自动描述 (Qwen2.5-VL)")
        vlm_kwargs = {}
        if vlm_model:
            vlm_kwargs["model_name"] = vlm_model
        if vlm_model_path:
            vlm_kwargs["model_path"] = vlm_model_path
        vlm_sender = QwenVLSender(**vlm_kwargs)
        _print("  正在加载 VLM 模型...")
        original_img = Image.open(image).convert("RGB")
        image_array = np.array(original_img)
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

    # 构造数据包并发送
    _print("\n[4/4] 发送数据到接收端...")
    buf = io.BytesIO()
    edge_image.save(buf, format="PNG")
    edge_bytes = buf.getvalue()
    metadata = {"timestamp": time.time(), "image_size": list(edge_image.size)}
    if seed is not None:
        metadata["seed"] = seed

    packet = TransmissionPacket(
        edge_image=edge_bytes, prompt_text=prompt_text, metadata=metadata
    )

    start = time.time()
    with SocketRelaySender(relay_host, relay_port) as relay:
        relay.send(packet)
    relay_elapsed = time.time() - start
    _print(f"  已发送到 {relay_host}:{relay_port}")
    _print(f"  传输耗时: {relay_elapsed:.1f}s")

    # 传输统计
    prompt_bytes = len(prompt_text.encode("utf-8"))
    total_bytes = len(edge_bytes) + prompt_bytes
    original_bytes = image.stat().st_size
    total_elapsed = sender_elapsed + vlm_elapsed + relay_elapsed

    _print("\n" + "=" * 60)
    _print("  传输统计")
    _print("=" * 60)
    _print(f"  原始图像大小:    {original_bytes:>10,} bytes")
    _print(f"  边缘图大小:      {len(edge_bytes):>10,} bytes")
    _print(f"  Prompt 大小:     {prompt_bytes:>10,} bytes")
    _print(f"  传输数据总量:    {total_bytes:>10,} bytes")
    _print(f"  压缩比:          {original_bytes / total_bytes:>10.2f}x")
    _print(f"  发送端耗时:      {sender_elapsed:>10.1f}s")
    if auto_prompt:
        _print(f"  VLM 耗时:        {vlm_elapsed:>10.1f}s")
    _print(f"  网络传输耗时:    {relay_elapsed:>10.1f}s")
    _print(f"  总耗时:          {total_elapsed:>10.1f}s")
