"""端到端语义传输 Demo 脚本。

演示完整流程：输入图像 → 发送端提取 Canny 边缘图 → 接收端从边缘图 + prompt 还原图像。

支持两种 prompt 模式：
    --prompt TEXT        手动指定描述文本（无 VLM 依赖，快速调试）
    --auto-prompt        使用 VLM 自动生成描述（需 P2-13 完成后可用）

用法：
    uv run python scripts/demo_e2e.py --image photo.jpg --prompt "A cat sitting on a sofa"
    uv run python scripts/demo_e2e.py --image photo.jpg --auto-prompt
    uv run python scripts/demo_e2e.py --image photo.jpg --prompt "..." --sender-host 192.168.1.10 --receiver-host 192.168.1.20
"""

import argparse
import io
import sys
import time
from pathlib import Path

from PIL import Image

from semantic_transmission.common.comfyui_client import ComfyUIClient
from semantic_transmission.common.config import ComfyUIConfig
from semantic_transmission.receiver.comfyui_receiver import ComfyUIReceiver
from semantic_transmission.sender.comfyui_sender import ComfyUISender


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="语义传输端到端 Demo：图像 → 边缘提取 → 语义还原"
    )
    parser.add_argument("--image", type=Path, required=True, help="输入图像路径")

    prompt_group = parser.add_mutually_exclusive_group(required=True)
    prompt_group.add_argument("--prompt", type=str, help="手动指定描述文本")
    prompt_group.add_argument(
        "--auto-prompt",
        action="store_true",
        help="使用 VLM 自动生成描述（需 VLM 模型，P2-13 实现）",
    )

    parser.add_argument(
        "--sender-host",
        default="127.0.0.1",
        help="发送端 ComfyUI 地址（默认 127.0.0.1）",
    )
    parser.add_argument(
        "--sender-port", type=int, default=8188, help="发送端 ComfyUI 端口（默认 8188）"
    )
    parser.add_argument(
        "--receiver-host",
        default="127.0.0.1",
        help="接收端 ComfyUI 地址（默认 127.0.0.1）",
    )
    parser.add_argument(
        "--receiver-port",
        type=int,
        default=8188,
        help="接收端 ComfyUI 端口（默认 8188）",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output/demo"),
        help="输出目录（默认 output/demo）",
    )
    parser.add_argument(
        "--seed", type=int, default=None, help="KSampler 随机种子（可选，便于复现）"
    )

    return parser.parse_args()


def make_comparison_image(
    original: Image.Image, edge: Image.Image, restored: Image.Image
) -> Image.Image:
    """横向拼接对比图：原图 | 边缘图 | 还原图。

    三张图缩放到相同高度后拼接。
    """
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
        # 边缘图可能是灰度图，转为 RGB 以便拼接
        if img.mode != "RGB":
            img = img.convert("RGB")
        comparison.paste(img, (x, 0))
        x += img.width

    return comparison


def get_image_bytes_size(img: Image.Image) -> int:
    """获取图像 PNG 编码后的字节大小。"""
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.tell()


def main():
    args = parse_args()

    # 校验输入图像
    if not args.image.exists():
        print(f"错误：输入图像不存在: {args.image}")
        sys.exit(1)

    # 创建输出目录
    args.output_dir.mkdir(parents=True, exist_ok=True)

    # 构造配置和客户端
    sender_config = ComfyUIConfig(host=args.sender_host, port=args.sender_port)
    receiver_config = ComfyUIConfig(host=args.receiver_host, port=args.receiver_port)
    sender_client = ComfyUIClient(sender_config)
    receiver_client = ComfyUIClient(receiver_config)

    print("=" * 60)
    print("  语义传输端到端 Demo")
    print("=" * 60)
    print(f"  输入图像: {args.image}")
    print(f"  发送端: {sender_config.base_url}")
    print(f"  接收端: {receiver_config.base_url}")
    print(f"  输出目录: {args.output_dir}")

    # 健康检查
    print("\n[1/5] 检查 ComfyUI 连接...")
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

    # 发送端：提取 Canny 边缘图
    print("\n[2/5] 发送端：提取 Canny 边缘图...")
    sender = ComfyUISender(sender_client)
    start = time.time()
    edge_image = sender.process(args.image)
    sender_elapsed = time.time() - start

    edge_path = args.output_dir / "edge.png"
    edge_image.save(edge_path)
    print(f"  边缘图: {edge_path} ({edge_image.size[0]}x{edge_image.size[1]})")
    print(f"  耗时: {sender_elapsed:.1f}s")

    # 获取 prompt
    print("\n[3/5] 获取语义描述...")
    if args.auto_prompt:
        print("  错误：--auto-prompt 模式尚未实现，需要 P2-13（VLM 集成）完成。")
        print("  请使用 --prompt 手动指定描述文本。")
        sys.exit(1)
    else:
        prompt_text = args.prompt
        print("  模式: 手动 prompt")
        print(f"  文本: {prompt_text}")

    # 接收端：从边缘图 + prompt 还原图像
    print("\n[4/5] 接收端：还原图像...")
    receiver = ComfyUIReceiver(receiver_client)
    start = time.time()
    restored_image = receiver.process(edge_path, prompt_text, seed=args.seed)
    receiver_elapsed = time.time() - start

    restored_path = args.output_dir / "restored.png"
    restored_image.save(restored_path)
    print(
        f"  还原图: {restored_path} ({restored_image.size[0]}x{restored_image.size[1]})"
    )
    print(f"  耗时: {receiver_elapsed:.1f}s")

    # 生成对比图
    print("\n[5/5] 生成对比图...")
    original_image = Image.open(args.image)
    comparison = make_comparison_image(original_image, edge_image, restored_image)
    comparison_path = args.output_dir / "comparison.png"
    comparison.save(comparison_path)
    print(f"  对比图: {comparison_path} ({comparison.size[0]}x{comparison.size[1]})")

    # 传输统计
    edge_bytes = get_image_bytes_size(edge_image)
    prompt_bytes = len(prompt_text.encode("utf-8"))
    total_bytes = edge_bytes + prompt_bytes
    original_bytes = args.image.stat().st_size

    print("\n" + "=" * 60)
    print("  传输统计")
    print("=" * 60)
    print(f"  原始图像大小:    {original_bytes:>10,} bytes")
    print(f"  边缘图大小:      {edge_bytes:>10,} bytes")
    print(f"  Prompt 大小:     {prompt_bytes:>10,} bytes")
    print(f"  传输数据总量:    {total_bytes:>10,} bytes")
    print(f"  压缩比:          {original_bytes / total_bytes:>10.2f}x")
    print(f"  发送端耗时:      {sender_elapsed:>10.1f}s")
    print(f"  接收端耗时:      {receiver_elapsed:>10.1f}s")
    print(f"  总耗时:          {sender_elapsed + receiver_elapsed:>10.1f}s")

    print(f"\n输出文件在 {args.output_dir}/ 目录下：")
    print("  edge.png       — Canny 边缘图")
    print("  restored.png   — 还原图像")
    print("  comparison.png — 对比图（原图 | 边缘图 | 还原图）")


if __name__ == "__main__":
    main()
