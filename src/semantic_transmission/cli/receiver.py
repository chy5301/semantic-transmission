"""semantic-tx receiver 子命令：双机演示接收端。"""

import sys
import time
from pathlib import Path

import click

from semantic_transmission.common.comfyui_client import ComfyUIClient
from semantic_transmission.common.config import ComfyUIConfig
from semantic_transmission.pipeline.relay import SocketRelayReceiver
from semantic_transmission.receiver.comfyui_receiver import ComfyUIReceiver


def _process_packet(
    receiver: ComfyUIReceiver, packet, output_dir: Path, index: int, _print
):
    """处理接收到的数据包：还原图像并保存。"""
    prompt_text = packet.prompt_text
    edge_bytes = packet.edge_image
    seed = packet.metadata.get("seed")

    _print(f"  Prompt 长度: {len(prompt_text)} 字符")
    _print(f"  边缘图大小: {len(edge_bytes):,} bytes")
    if seed is not None:
        _print(f"  种子: {seed}")

    # 保存边缘图
    sub_dir = output_dir / f"{index:04d}"
    sub_dir.mkdir(parents=True, exist_ok=True)

    edge_path = sub_dir / "edge.png"
    edge_path.write_bytes(edge_bytes)
    _print(f"  边缘图已保存: {edge_path}")

    # 保存 prompt
    prompt_path = sub_dir / "prompt.txt"
    prompt_path.write_text(prompt_text, encoding="utf-8")
    _print(f"  Prompt 已保存: {prompt_path}")

    # 还原图像
    _print("  正在还原图像...")
    start = time.time()
    restored_image = receiver.process(edge_bytes, prompt_text, seed=seed)
    elapsed = time.time() - start

    restored_path = sub_dir / "restored.png"
    restored_image.save(restored_path)
    _print(
        f"  还原图像: {restored_path} ({restored_image.size[0]}x{restored_image.size[1]})"
    )
    _print(f"  还原耗时: {elapsed:.1f}s")

    return restored_image, elapsed


@click.command()
@click.option(
    "--relay-host", default="0.0.0.0", help="监听地址（默认 0.0.0.0，接受所有连接）"
)
@click.option("--relay-port", default=9000, type=int, help="监听端口（默认 9000）")
@click.option(
    "--comfyui-host", default="127.0.0.1", help="本机 ComfyUI 地址（默认 127.0.0.1）"
)
@click.option(
    "--comfyui-port", default=8188, type=int, help="本机 ComfyUI 端口（默认 8188）"
)
@click.option(
    "--output-dir",
    default=Path("output/received"),
    type=click.Path(path_type=Path),
    help="输出目录（默认 output/received）",
)
@click.option(
    "--continuous",
    is_flag=True,
    default=False,
    help="连续模式：持续监听，每次接收后等待下一次连接",
)
def receiver(
    relay_host, relay_port, comfyui_host, comfyui_port, output_dir, continuous
):
    """接收端：监听端口接收数据 → 还原图像。"""
    import builtins
    import functools

    _print = functools.partial(builtins.print, flush=True)

    config = ComfyUIConfig(host=comfyui_host, port=comfyui_port)
    client = ComfyUIClient(config)

    _print("=" * 60)
    _print("  语义传输接收端")
    _print("=" * 60)
    _print(f"  监听地址: {relay_host}:{relay_port}")
    _print(f"  ComfyUI: {config.base_url}")
    _print(f"  输出目录: {output_dir}")
    _print(f"  模式: {'连续' if continuous else '单次'}")

    # 健康检查
    _print("\n[检查] ComfyUI 连接...")
    try:
        client.check_health()
        _print(f"  ComfyUI ({config.base_url}): OK")
    except Exception as e:
        _print(f"  ComfyUI 连接失败: {e}")
        sys.exit(1)

    output_dir.mkdir(parents=True, exist_ok=True)
    receiver = ComfyUIReceiver(client)
    index = 1

    relay = SocketRelayReceiver(relay_host, relay_port)
    relay.start()
    _print(f"\n[监听] 等待发送端连接 ({relay_host}:{relay_port})...")

    try:
        while True:
            relay.accept()
            _print(f"\n[接收 #{index}] 发送端已连接，正在接收数据...")

            packet = relay.receive()
            _print("  数据接收完成")

            relay.close_connection()

            _, elapsed = _process_packet(receiver, packet, output_dir, index, _print)

            _print(f"\n  第 {index} 次接收处理完成（还原耗时 {elapsed:.1f}s）")

            if not continuous:
                break

            index += 1
            _print("\n[监听] 等待下一次连接...")

    except KeyboardInterrupt:
        _print("\n\n接收端已停止")
    finally:
        relay.close()
