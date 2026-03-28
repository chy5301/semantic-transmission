"""semantic-tx check 子命令组：连通性测试和工作流验证。"""

import io
import json
import sys
import time
import uuid
from pathlib import Path

import click
import requests
from PIL import Image

from semantic_transmission.common.config import ComfyUIConfig


@click.group()
def check():
    """检查 ComfyUI 连接和工作流。"""


def _step(name: str, func, *args, **kwargs):
    """执行一个测试步骤，打印 PASS/FAIL。返回 (success, result)。"""
    print(f"\n{'=' * 50}")
    print(f"  {name}")
    print(f"{'=' * 50}")
    try:
        result = func(*args, **kwargs)
        print("  => PASS")
        return True, result
    except Exception as e:
        print(f"  => FAIL: {e}")
        return False, None


@check.command()
@click.option("--host", default=None, help="ComfyUI 主机地址")
@click.option("--port", default=None, type=int, help="ComfyUI 端口")
def connection(host, port):
    """测试 ComfyUI API 连通性（REST + WebSocket）。"""
    config = ComfyUIConfig.from_env()
    if host:
        config.host = host
    if port:
        config.port = port

    print("ComfyUI 连通性测试")
    print(f"目标: {config.base_url}")
    print(f"超时: {config.timeout}s")

    prompt_id = None

    # 1. 健康检查
    def test_health():
        resp = requests.get(f"{config.base_url}/queue", timeout=config.timeout)
        resp.raise_for_status()
        data = resp.json()
        running = len(data.get("queue_running", []))
        pending = len(data.get("queue_pending", []))
        print(f"  队列状态: 运行中={running}, 排队中={pending}")

    _step("1/6 健康检查 — GET /queue", test_health)

    # 2. 上传图像
    def test_upload():
        img = Image.new("RGB", (64, 64), color=(127, 200, 80))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        img_bytes = buf.getvalue()
        resp = requests.post(
            f"{config.base_url}/upload/image",
            files={"image": ("comfyui_test_upload.png", img_bytes, "image/png")},
            data={"overwrite": "true"},
            timeout=config.timeout,
        )
        resp.raise_for_status()
        result = resp.json()
        print(f"  上传结果: {result}")

    _step("2/6 上传图像 — POST /upload/image", test_upload)

    # 3. 提交工作流
    minimal_workflow = {
        "1": {
            "class_type": "LoadImage",
            "inputs": {"image": "comfyui_test_upload.png", "upload": "image"},
        },
        "2": {
            "class_type": "SaveImage",
            "inputs": {"images": ["1", 0], "filename_prefix": "comfyui_api_test"},
        },
    }

    def test_prompt():
        nonlocal prompt_id
        client_id = uuid.uuid4().hex
        payload = {"prompt": minimal_workflow, "client_id": client_id}
        resp = requests.post(
            f"{config.base_url}/prompt", json=payload, timeout=config.timeout
        )
        resp.raise_for_status()
        result = resp.json()
        prompt_id = result.get("prompt_id")
        print(f"  prompt_id: {prompt_id}")
        return prompt_id

    _step("3/6 提交工作流 — POST /prompt", test_prompt)

    # 4. WebSocket 连接
    def test_ws():
        import websocket

        ws = websocket.create_connection(config.ws_url, timeout=config.timeout)
        msg = ws.recv()
        ws.close()
        data = json.loads(msg) if isinstance(msg, str) else {}
        msg_type = data.get("type", "(binary)")
        print(f"  收到消息类型: {msg_type}")

    _step("4/6 WebSocket 连接", test_ws)

    # 5. 查询历史
    def test_history():
        if prompt_id is None:
            print("  (跳过: 无 prompt_id)")
            return
        for _ in range(10):
            resp = requests.get(
                f"{config.base_url}/history/{prompt_id}", timeout=config.timeout
            )
            resp.raise_for_status()
            data = resp.json()
            if prompt_id in data:
                outputs = data[prompt_id].get("outputs", {})
                print(f"  历史记录存在, 输出节点数: {len(outputs)}")
                return
            time.sleep(1)
        print("  等待超时，未获取到历史记录")

    _step("5/6 查询历史 — GET /history", test_history)

    # 6. 下载图像
    def test_view():
        if prompt_id is None:
            print("  (跳过: 无 prompt_id)")
            return
        resp = requests.get(
            f"{config.base_url}/history/{prompt_id}", timeout=config.timeout
        )
        resp.raise_for_status()
        data = resp.json()
        entry = data.get(prompt_id, {})
        outputs = entry.get("outputs", {})
        filename = None
        for node_output in outputs.values():
            images = node_output.get("images", [])
            if images:
                filename = images[0].get("filename")
                break
        if filename is None:
            print("  (跳过: 输出中未找到图像)")
            return
        resp = requests.get(
            f"{config.base_url}/view",
            params={"filename": filename},
            timeout=config.timeout,
        )
        resp.raise_for_status()
        size = len(resp.content)
        print(f"  下载图像: {filename} ({size} bytes)")

    _step("6/6 下载图像 — GET /view", test_view)

    print(f"\n{'=' * 50}")
    print("  测试完成")
    print(f"{'=' * 50}\n")


@check.command()
@click.option("--host", default=None, help="ComfyUI 主机地址")
@click.option("--port", default=None, type=int, help="ComfyUI 端口")
@click.option("--sender-only", is_flag=True, default=False, help="仅验证发送端")
@click.option("--receiver-only", is_flag=True, default=False, help="仅验证接收端")
@click.option("--edge-image", default=None, type=click.Path(exists=True, path_type=Path), help="接收端验证用的边缘图路径（--receiver-only 时使用）")
def workflows(host, port, sender_only, receiver_only, edge_image):
    """验证 ComfyUI 发送端和接收端工作流。"""
    from PIL import ImageDraw

    from semantic_transmission.common.comfyui_client import ComfyUIClient

    config = ComfyUIConfig.from_env()
    if host:
        config.host = host
    if port:
        config.port = port

    print("ComfyUI 工作流验证")
    print(f"目标: {config.base_url}")

    client = ComfyUIClient(config)

    try:
        client.check_health()
        print("连接状态: OK")
    except Exception as e:
        print(f"连接失败: {e}")
        print("请确认 ComfyUI 已启动。")
        sys.exit(1)

    sender_ok = False
    receiver_ok = False
    edge_path = edge_image

    if not receiver_only:
        from semantic_transmission.sender.comfyui_sender import ComfyUISender

        def _verify_sender():
            nonlocal edge_path
            img = Image.new("RGB", (256, 256))
            draw = ImageDraw.Draw(img)
            draw.rectangle([50, 50, 200, 200], fill=(255, 0, 0), outline=(255, 255, 255))
            draw.ellipse([80, 80, 180, 180], fill=(0, 0, 255), outline=(255, 255, 0))
            draw.line([(0, 0), (256, 256)], fill=(0, 255, 0), width=3)

            output_dir = Path("output/verify")
            output_dir.mkdir(parents=True, exist_ok=True)
            test_path = output_dir / "test_input.png"
            img.save(test_path)
            print(f"  测试图像: {test_path} (256x256)")

            sender = ComfyUISender(client)
            print("  提交发送端工作流...")
            start = time.time()
            edge_image_result = sender.process(test_path)
            elapsed = time.time() - start

            ep = output_dir / "sender_edge_output.png"
            edge_image_result.save(ep)
            print(f"  输出边缘图: {ep}")
            print(f"  图像尺寸: {edge_image_result.size}")
            print(f"  耗时: {elapsed:.1f}s")
            edge_path = ep

        sender_ok, _ = _step("验证发送端工作流", _verify_sender)

    if not sender_only:
        if edge_path is None:
            if receiver_only:
                print("\n错误：--receiver-only 需要指定 --edge-image")
            else:
                print("\n跳过接收端验证（发送端未产出边缘图）")
        else:
            from semantic_transmission.receiver.comfyui_receiver import ComfyUIReceiver

            def _verify_receiver():
                receiver = ComfyUIReceiver(client)
                prompt = "A simple geometric scene with a red rectangle and blue circle"
                print(f"  边缘图: {edge_path}")
                print(f"  Prompt: {prompt}")
                print("  提交接收端工作流...")
                start = time.time()
                result_image = receiver.process(edge_path, prompt, seed=42)
                elapsed = time.time() - start

                output_dir = Path("output/verify")
                result_path = output_dir / "receiver_result_output.png"
                result_image.save(result_path)
                print(f"  输出还原图: {result_path}")
                print(f"  图像尺寸: {result_image.size}")
                print(f"  耗时: {elapsed:.1f}s")

            receiver_ok, _ = _step("验证接收端工作流", _verify_receiver)

    # 汇总
    print("\n" + "=" * 50)
    print("  验证结果汇总")
    print("=" * 50)
    if not receiver_only:
        status = "PASS" if sender_ok else "FAIL"
        print(f"  发送端: {status}")
    if not sender_only:
        status = "PASS" if receiver_ok else "FAIL"
        print(f"  接收端: {status}")

    if receiver_only:
        success = receiver_ok
    elif sender_only:
        success = sender_ok
    else:
        success = sender_ok and receiver_ok

    if success:
        print("\n工作流验证通过！")
        print("输出文件在 output/verify/ 目录下")
    else:
        print("\n工作流验证未通过，请检查错误信息")
        sys.exit(1)
