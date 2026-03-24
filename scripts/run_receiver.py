"""双机演示 — 接收端脚本。

在接收端机器上运行：监听端口接收边缘图 + 语义描述 → 还原图像。

用法：
    uv run python scripts/run_receiver.py
    uv run python scripts/run_receiver.py --relay-port 9000
    uv run python scripts/run_receiver.py --continuous
    uv run python scripts/run_receiver.py --relay-host 0.0.0.0 --relay-port 9000 --comfyui-host 127.0.0.1
"""

import argparse
import sys
import time
from pathlib import Path

from semantic_transmission.common.comfyui_client import ComfyUIClient
from semantic_transmission.common.config import ComfyUIConfig
from semantic_transmission.pipeline.relay import SocketRelayReceiver
from semantic_transmission.receiver.comfyui_receiver import ComfyUIReceiver


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="语义传输接收端：监听端口接收数据 → 还原图像"
    )

    parser.add_argument(
        "--relay-host", default="0.0.0.0", help="监听地址（默认 0.0.0.0，接受所有连接）"
    )
    parser.add_argument(
        "--relay-port", type=int, default=9000, help="监听端口（默认 9000）"
    )

    parser.add_argument(
        "--comfyui-host",
        default="127.0.0.1",
        help="本机 ComfyUI 地址（默认 127.0.0.1）",
    )
    parser.add_argument(
        "--comfyui-port", type=int, default=8188, help="本机 ComfyUI 端口（默认 8188）"
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output/received"),
        help="输出目录（默认 output/received）",
    )

    parser.add_argument(
        "--continuous",
        action="store_true",
        help="连续模式：持续监听，每次接收后等待下一次连接",
    )

    return parser.parse_args()


def process_packet(receiver: ComfyUIReceiver, packet, output_dir: Path, index: int):
    """处理接收到的数据包：还原图像并保存。"""
    import builtins
    import functools

    print = functools.partial(builtins.print, flush=True)  # noqa: A001

    prompt_text = packet.prompt_text
    edge_bytes = packet.edge_image
    seed = packet.metadata.get("seed")

    print(f"  Prompt 长度: {len(prompt_text)} 字符")
    print(f"  边缘图大小: {len(edge_bytes):,} bytes")
    if seed is not None:
        print(f"  种子: {seed}")

    # 保存边缘图
    sub_dir = output_dir / f"{index:04d}"
    sub_dir.mkdir(parents=True, exist_ok=True)

    edge_path = sub_dir / "edge.png"
    edge_path.write_bytes(edge_bytes)
    print(f"  边缘图已保存: {edge_path}")

    # 保存 prompt
    prompt_path = sub_dir / "prompt.txt"
    prompt_path.write_text(prompt_text, encoding="utf-8")
    print(f"  Prompt 已保存: {prompt_path}")

    # 还原图像
    print("  正在还原图像...")
    start = time.time()
    restored_image = receiver.process(edge_bytes, prompt_text, seed=seed)
    elapsed = time.time() - start

    restored_path = sub_dir / "restored.png"
    restored_image.save(restored_path)
    print(
        f"  还原图像: {restored_path} ({restored_image.size[0]}x{restored_image.size[1]})"
    )
    print(f"  还原耗时: {elapsed:.1f}s")

    return restored_image, elapsed


def main():
    import builtins
    import functools

    print = functools.partial(builtins.print, flush=True)  # noqa: A001

    args = parse_args()

    config = ComfyUIConfig(host=args.comfyui_host, port=args.comfyui_port)
    client = ComfyUIClient(config)

    print("=" * 60)
    print("  语义传输接收端")
    print("=" * 60)
    print(f"  监听地址: {args.relay_host}:{args.relay_port}")
    print(f"  ComfyUI: {config.base_url}")
    print(f"  输出目录: {args.output_dir}")
    print(f"  模式: {'连续' if args.continuous else '单次'}")

    # 健康检查
    print("\n[检查] ComfyUI 连接...")
    try:
        client.check_health()
        print(f"  ComfyUI ({config.base_url}): OK")
    except Exception as e:
        print(f"  ComfyUI 连接失败: {e}")
        sys.exit(1)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    receiver = ComfyUIReceiver(client)
    index = 1

    relay = SocketRelayReceiver(args.relay_host, args.relay_port)
    relay.start()
    print(f"\n[监听] 等待发送端连接 ({args.relay_host}:{args.relay_port})...")

    try:
        while True:
            # 等待连接
            relay.accept()
            print(f"\n[接收 #{index}] 发送端已连接，正在接收数据...")

            packet = relay.receive()
            print("  数据接收完成")

            # 关闭当前连接，准备下次
            if relay._conn is not None:
                relay._conn.close()
                relay._conn = None

            # 处理数据包
            _, elapsed = process_packet(receiver, packet, args.output_dir, index)

            print(f"\n  第 {index} 次接收处理完成（还原耗时 {elapsed:.1f}s）")

            if not args.continuous:
                break

            index += 1
            print("\n[监听] 等待下一次连接...")

    except KeyboardInterrupt:
        print("\n\n接收端已停止")
    finally:
        relay.close()


if __name__ == "__main__":
    main()
