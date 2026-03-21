"""ComfyUI API 连通性测试脚本。

逐步测试 ComfyUI 的 REST API 和 WebSocket 端点，
每步输出 PASS/FAIL，失败时给出错误信息但不中断后续测试。

用法：
    uv run python scripts/test_comfyui_connection.py [--host HOST] [--port PORT]
"""

import argparse
import io
import json
import time
import uuid

import requests
from PIL import Image

from semantic_transmission.common.config import ComfyUIConfig


def make_test_image() -> bytes:
    """生成一张 64x64 的纯色测试图像（PNG 格式）。"""
    img = Image.new("RGB", (64, 64), color=(127, 200, 80))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


MINIMAL_WORKFLOW = {
    "1": {
        "class_type": "LoadImage",
        "inputs": {"image": "comfyui_test_upload.png", "upload": "image"},
    },
    "2": {
        "class_type": "SaveImage",
        "inputs": {"images": ["1", 0], "filename_prefix": "comfyui_api_test"},
    },
}


def step(name: str):
    """打印步骤标题的装饰器。"""

    def decorator(func):
        def wrapper(*args, **kwargs):
            print(f"\n{'=' * 50}")
            print(f"  {name}")
            print(f"{'=' * 50}")
            try:
                result = func(*args, **kwargs)
                print("  => PASS")
                return result
            except Exception as e:
                print(f"  => FAIL: {e}")
                return None

        return wrapper

    return decorator


def run_tests(config: ComfyUIConfig) -> None:
    print("ComfyUI 连通性测试")
    print(f"目标: {config.base_url}")
    print(f"超时: {config.timeout}s")

    prompt_id: str | None = None

    # ── 1. 健康检查 ──
    @step("1/6 健康检查 — GET /queue")
    def test_health():
        resp = requests.get(f"{config.base_url}/queue", timeout=config.timeout)
        resp.raise_for_status()
        data = resp.json()
        running = len(data.get("queue_running", []))
        pending = len(data.get("queue_pending", []))
        print(f"  队列状态: 运行中={running}, 排队中={pending}")

    test_health()

    # ── 2. 上传图像 ──
    @step("2/6 上传图像 — POST /upload/image")
    def test_upload():
        img_bytes = make_test_image()
        resp = requests.post(
            f"{config.base_url}/upload/image",
            files={"image": ("comfyui_test_upload.png", img_bytes, "image/png")},
            data={"overwrite": "true"},
            timeout=config.timeout,
        )
        resp.raise_for_status()
        result = resp.json()
        print(f"  上传结果: {result}")

    test_upload()

    # ── 3. 提交工作流 ──
    @step("3/6 提交工作流 — POST /prompt")
    def test_prompt() -> str | None:
        nonlocal prompt_id
        client_id = uuid.uuid4().hex
        payload = {"prompt": MINIMAL_WORKFLOW, "client_id": client_id}
        resp = requests.post(
            f"{config.base_url}/prompt",
            json=payload,
            timeout=config.timeout,
        )
        resp.raise_for_status()
        result = resp.json()
        prompt_id = result.get("prompt_id")
        print(f"  prompt_id: {prompt_id}")
        return prompt_id

    test_prompt()

    # ── 4. WebSocket 连接 ──
    @step("4/6 WebSocket 连接")
    def test_ws():
        import websocket

        ws = websocket.create_connection(config.ws_url, timeout=config.timeout)
        # 读取初始状态消息
        msg = ws.recv()
        ws.close()
        data = json.loads(msg) if isinstance(msg, str) else {}
        msg_type = data.get("type", "(binary)")
        print(f"  收到消息类型: {msg_type}")

    test_ws()

    # ── 5. 查询历史 ──
    @step("5/6 查询历史 — GET /history")
    def test_history():
        if prompt_id is None:
            print("  (跳过: 无 prompt_id)")
            return

        # 等待执行完成
        for i in range(10):
            resp = requests.get(
                f"{config.base_url}/history/{prompt_id}",
                timeout=config.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            if prompt_id in data:
                outputs = data[prompt_id].get("outputs", {})
                print(f"  历史记录存在, 输出节点数: {len(outputs)}")
                return
            time.sleep(1)
        print("  等待超时，未获取到历史记录")

    test_history()

    # ── 6. 下载图像 ──
    @step("6/6 下载图像 — GET /view")
    def test_view():
        if prompt_id is None:
            print("  (跳过: 无 prompt_id)")
            return

        resp = requests.get(
            f"{config.base_url}/history/{prompt_id}",
            timeout=config.timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        entry = data.get(prompt_id, {})
        outputs = entry.get("outputs", {})

        # 查找 SaveImage 节点的输出
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

    test_view()

    print(f"\n{'=' * 50}")
    print("  测试完成")
    print(f"{'=' * 50}\n")


def main():
    parser = argparse.ArgumentParser(description="ComfyUI API 连通性测试")
    parser.add_argument("--host", default=None, help="ComfyUI 主机地址")
    parser.add_argument("--port", type=int, default=None, help="ComfyUI 端口")
    args = parser.parse_args()

    config = ComfyUIConfig.from_env()
    if args.host:
        config.host = args.host
    if args.port:
        config.port = args.port

    run_tests(config)


if __name__ == "__main__":
    main()
