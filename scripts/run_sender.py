"""双机演示 — 发送端脚本。

在发送端机器上运行：提取边缘图 + 生成语义描述 → 通过网络发送给接收端。

用法：
    uv run python scripts/run_sender.py --image photo.jpg --prompt "A red car" --relay-host 192.168.1.20
    uv run python scripts/run_sender.py --image photo.jpg --auto-prompt --relay-host 192.168.1.20
    uv run python scripts/run_sender.py --image photo.jpg --prompt "..." --relay-host 192.168.1.20 --relay-port 9000
"""

import argparse
import io
import sys
import time
from pathlib import Path

from PIL import Image

from semantic_transmission.common.comfyui_client import ComfyUIClient
from semantic_transmission.common.config import ComfyUIConfig
from semantic_transmission.pipeline.relay import SocketRelaySender, TransmissionPacket
from semantic_transmission.sender.comfyui_sender import ComfyUISender


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="语义传输发送端：提取边缘图 + 语义描述 → 发送到接收端"
    )
    parser.add_argument("--image", type=Path, required=True, help="输入图像路径")

    prompt_group = parser.add_mutually_exclusive_group(required=True)
    prompt_group.add_argument("--prompt", type=str, help="手动指定描述文本")
    prompt_group.add_argument(
        "--auto-prompt",
        action="store_true",
        help="使用 VLM (Qwen2.5-VL) 自动生成描述",
    )

    parser.add_argument("--vlm-model", type=str, default=None, help="VLM 模型名称")
    parser.add_argument(
        "--vlm-model-path",
        type=str,
        default=r"D:\Downloads\Models\Qwen\Qwen2.5-VL-7B-Instruct",
        help="VLM 模型本地路径",
    )

    parser.add_argument(
        "--comfyui-host",
        default="127.0.0.1",
        help="本机 ComfyUI 地址（默认 127.0.0.1）",
    )
    parser.add_argument(
        "--comfyui-port", type=int, default=8188, help="本机 ComfyUI 端口（默认 8188）"
    )

    parser.add_argument("--relay-host", required=True, help="接收端机器 IP 地址")
    parser.add_argument(
        "--relay-port", type=int, default=9000, help="接收端监听端口（默认 9000）"
    )

    parser.add_argument(
        "--seed", type=int, default=None, help="KSampler 随机种子（可选，传递给接收端）"
    )

    return parser.parse_args()


def image_to_png_bytes(img: Image.Image) -> bytes:
    """将 PIL Image 转为 PNG 编码的 bytes。"""
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def main():
    import builtins
    import functools

    print = functools.partial(builtins.print, flush=True)  # noqa: A001

    args = parse_args()

    if not args.image.exists():
        print(f"错误：输入图像不存在: {args.image}")
        sys.exit(1)

    config = ComfyUIConfig(host=args.comfyui_host, port=args.comfyui_port)
    client = ComfyUIClient(config)

    print("=" * 60)
    print("  语义传输发送端")
    print("=" * 60)
    print(f"  输入图像: {args.image}")
    print(f"  ComfyUI: {config.base_url}")
    print(f"  接收端: {args.relay_host}:{args.relay_port}")

    # 健康检查
    print("\n[1/4] 检查 ComfyUI 连接...")
    try:
        client.check_health()
        print(f"  ComfyUI ({config.base_url}): OK")
    except Exception as e:
        print(f"  ComfyUI 连接失败: {e}")
        sys.exit(1)

    # 提取边缘图
    print("\n[2/4] 提取 Canny 边缘图...")
    sender = ComfyUISender(client)
    start = time.time()
    edge_image = sender.process(args.image)
    sender_elapsed = time.time() - start
    print(f"  边缘图: {edge_image.size[0]}x{edge_image.size[1]}")
    print(f"  耗时: {sender_elapsed:.1f}s")

    # 获取 prompt
    vlm_elapsed = 0.0
    print("\n[3/4] 获取语义描述...")
    if args.auto_prompt:
        import numpy as np

        from semantic_transmission.sender.qwen_vl_sender import QwenVLSender

        print("  模式: VLM 自动描述 (Qwen2.5-VL)")
        vlm_kwargs = {}
        if args.vlm_model:
            vlm_kwargs["model_name"] = args.vlm_model
        if args.vlm_model_path:
            vlm_kwargs["model_path"] = args.vlm_model_path
        vlm_sender = QwenVLSender(**vlm_kwargs)
        print("  正在加载 VLM 模型...")
        original_img = Image.open(args.image).convert("RGB")
        image_array = np.array(original_img)
        start_vlm = time.time()
        sender_output = vlm_sender.describe(image_array)
        vlm_elapsed = time.time() - start_vlm
        prompt_text = sender_output.text
        print(f"  VLM 耗时: {vlm_elapsed:.1f}s")
        print(f"  描述长度: {len(prompt_text)} 字符")
        print(f"  描述预览: {prompt_text[:200]}...")
        vlm_sender.unload()
        print("  VLM 模型已卸载")
    else:
        prompt_text = args.prompt
        print("  模式: 手动 prompt")
        print(f"  文本: {prompt_text}")

    # 构造数据包并发送
    print("\n[4/4] 发送数据到接收端...")
    edge_bytes = image_to_png_bytes(edge_image)
    metadata = {"timestamp": time.time(), "image_size": list(edge_image.size)}
    if args.seed is not None:
        metadata["seed"] = args.seed

    packet = TransmissionPacket(
        edge_image=edge_bytes, prompt_text=prompt_text, metadata=metadata
    )

    start = time.time()
    with SocketRelaySender(args.relay_host, args.relay_port) as relay:
        relay.send(packet)
    relay_elapsed = time.time() - start
    print(f"  已发送到 {args.relay_host}:{args.relay_port}")
    print(f"  传输耗时: {relay_elapsed:.1f}s")

    # 传输统计
    prompt_bytes = len(prompt_text.encode("utf-8"))
    total_bytes = len(edge_bytes) + prompt_bytes
    original_bytes = args.image.stat().st_size
    total_elapsed = sender_elapsed + vlm_elapsed + relay_elapsed

    print("\n" + "=" * 60)
    print("  传输统计")
    print("=" * 60)
    print(f"  原始图像大小:    {original_bytes:>10,} bytes")
    print(f"  边缘图大小:      {len(edge_bytes):>10,} bytes")
    print(f"  Prompt 大小:     {prompt_bytes:>10,} bytes")
    print(f"  传输数据总量:    {total_bytes:>10,} bytes")
    print(f"  压缩比:          {original_bytes / total_bytes:>10.2f}x")
    print(f"  发送端耗时:      {sender_elapsed:>10.1f}s")
    if args.auto_prompt:
        print(f"  VLM 耗时:        {vlm_elapsed:>10.1f}s")
    print(f"  网络传输耗时:    {relay_elapsed:>10.1f}s")
    print(f"  总耗时:          {total_elapsed:>10.1f}s")


if __name__ == "__main__":
    main()
