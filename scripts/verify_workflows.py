"""验证 ComfyUI 发送端和接收端工作流是否能正常执行。

前置条件：
    1. ComfyUI 已启动（--listen 模式），模型已加载
    2. scripts/test_comfyui_connection.py 连通性测试已通过

用法：
    uv run python scripts/verify_workflows.py [--host HOST] [--port PORT]
    uv run python scripts/verify_workflows.py --sender-only
    uv run python scripts/verify_workflows.py --receiver-only --edge-image path/to/edge.png
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


def make_test_image(width: int = 256, height: int = 256) -> Path:
    """生成测试图像并保存到临时文件。"""
    img = Image.new("RGB", (width, height))
    # 画一些简单图形便于边缘检测
    from PIL import ImageDraw

    draw = ImageDraw.Draw(img)
    draw.rectangle([50, 50, 200, 200], fill=(255, 0, 0), outline=(255, 255, 255))
    draw.ellipse([80, 80, 180, 180], fill=(0, 0, 255), outline=(255, 255, 0))
    draw.line([(0, 0), (256, 256)], fill=(0, 255, 0), width=3)

    output_dir = Path("output/verify")
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "test_input.png"
    img.save(path)
    print(f"  测试图像: {path} ({width}x{height})")
    return path


def verify_sender(client: ComfyUIClient) -> Path | None:
    """验证发送端工作流。"""
    print("\n" + "=" * 50)
    print("  验证发送端工作流")
    print("=" * 50)

    try:
        sender = ComfyUISender(client)
        test_image = make_test_image()

        print("  提交发送端工作流...")
        start = time.time()
        edge_image = sender.process(test_image)
        elapsed = time.time() - start

        # 保存边缘图
        output_dir = Path("output/verify")
        edge_path = output_dir / "sender_edge_output.png"
        edge_image.save(edge_path)

        print(f"  输出边缘图: {edge_path}")
        print(f"  图像尺寸: {edge_image.size}")
        print(f"  耗时: {elapsed:.1f}s")
        print("  => PASS")
        return edge_path
    except Exception as e:
        print(f"  => FAIL: {e}")
        return None


def verify_receiver(client: ComfyUIClient, edge_image_path: Path) -> bool:
    """验证接收端工作流。"""
    print("\n" + "=" * 50)
    print("  验证接收端工作流")
    print("=" * 50)

    try:
        receiver = ComfyUIReceiver(client)
        prompt = "A simple geometric scene with a red rectangle and blue circle"

        print(f"  边缘图: {edge_image_path}")
        print(f"  Prompt: {prompt}")
        print("  提交接收端工作流...")
        start = time.time()
        result_image = receiver.process(edge_image_path, prompt, seed=42)
        elapsed = time.time() - start

        # 保存还原图像
        output_dir = Path("output/verify")
        result_path = output_dir / "receiver_result_output.png"
        result_image.save(result_path)

        print(f"  输出还原图: {result_path}")
        print(f"  图像尺寸: {result_image.size}")
        print(f"  耗时: {elapsed:.1f}s")
        print("  => PASS")
        return True
    except Exception as e:
        print(f"  => FAIL: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="验证 ComfyUI 工作流")
    parser.add_argument("--host", default=None, help="ComfyUI 主机地址")
    parser.add_argument("--port", type=int, default=None, help="ComfyUI 端口")
    parser.add_argument("--sender-only", action="store_true", help="仅验证发送端")
    parser.add_argument("--receiver-only", action="store_true", help="仅验证接收端")
    parser.add_argument(
        "--edge-image", type=Path, default=None,
        help="接收端验证用的边缘图路径（--receiver-only 时使用）",
    )
    args = parser.parse_args()

    config = ComfyUIConfig.from_env()
    if args.host:
        config.host = args.host
    if args.port:
        config.port = args.port

    print(f"ComfyUI 工作流验证")
    print(f"目标: {config.base_url}")

    client = ComfyUIClient(config)

    # 健康检查
    try:
        client.check_health()
        print(f"连接状态: OK")
    except Exception as e:
        print(f"连接失败: {e}")
        print("请确认 ComfyUI 已启动。")
        sys.exit(1)

    sender_ok = False
    receiver_ok = False

    if not args.receiver_only:
        edge_path = verify_sender(client)
        sender_ok = edge_path is not None
    else:
        edge_path = args.edge_image

    if not args.sender_only:
        if edge_path is None:
            if args.receiver_only:
                print("\n错误：--receiver-only 需要指定 --edge-image")
            else:
                print("\n跳过接收端验证（发送端未产出边缘图）")
        else:
            receiver_ok = verify_receiver(client, edge_path)

    # 汇总
    print("\n" + "=" * 50)
    print("  验证结果汇总")
    print("=" * 50)
    if not args.receiver_only:
        status = "PASS" if sender_ok else "FAIL"
        print(f"  发送端: {status}")
    if not args.sender_only:
        status = "PASS" if receiver_ok else "FAIL"
        print(f"  接收端: {status}")

    if args.receiver_only:
        success = receiver_ok
    elif args.sender_only:
        success = sender_ok
    else:
        success = sender_ok and receiver_ok

    if success:
        print("\n工作流验证通过！")
        print("输出文件在 output/verify/ 目录下")
    else:
        print("\n工作流验证未通过，请检查错误信息")
        sys.exit(1)


if __name__ == "__main__":
    main()
