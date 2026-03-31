"""接收端 Tab：边缘图 + 语义描述 → 图像还原。"""

import random
import time

import gradio as gr

from semantic_transmission.common.comfyui_client import ComfyUIClient
from semantic_transmission.common.config import ComfyUIConfig
from semantic_transmission.receiver.comfyui_receiver import ComfyUIReceiver


def _random_seed():
    return random.randint(0, 2**32 - 1)


def _run_receiver(edge_image_path, prompt, seed, receiver_host, receiver_port):
    """运行接收端流程，generator 逐步 yield 更新 UI。"""
    log = ""
    restored_img = None

    if not edge_image_path:
        log = "错误：请先上传边缘图\n"
        yield restored_img, log
        return

    if not prompt or not prompt.strip():
        log = "错误：请输入语义描述文本\n"
        yield restored_img, log
        return

    # [1] 连接检查
    log += "[1/2] 检查 ComfyUI 连接...\n"
    yield restored_img, log

    config = ComfyUIConfig(host=receiver_host, port=int(receiver_port))
    client = ComfyUIClient(config)
    try:
        if not client.check_health():
            log += f"  连接失败: {config.base_url} 服务异常\n"
            yield restored_img, log
            return
        log += f"  {config.base_url}: OK\n"
    except Exception as e:
        log += f"  连接失败: {e}\n"
        yield restored_img, log
        return

    # [2] 还原图像
    seed_int = int(seed) if seed is not None and seed != "" else None
    seed_info = f", seed={seed_int}" if seed_int is not None else ""
    log += f"[2/2] 接收端还原图像{seed_info}...\n"
    yield restored_img, log

    try:
        receiver = ComfyUIReceiver(client)
        start = time.time()
        restored_pil = receiver.process(edge_image_path, prompt.strip(), seed=seed_int)
        elapsed = time.time() - start
        restored_img = restored_pil
        log += (
            f"  完成 ({restored_pil.size[0]}x{restored_pil.size[1]}, {elapsed:.1f}s)\n"
        )
    except Exception as e:
        log += f"  失败: {e}\n"
        yield restored_img, log
        return

    log += "─" * 30 + "\n"
    log += f"接收端完成！还原图 {restored_pil.size[0]}x{restored_pil.size[1]}，耗时 {elapsed:.1f}s\n"
    yield restored_img, log


def build_receiver_tab(config_components: dict) -> dict:
    """构建接收端 Tab 的 UI 组件并绑定事件。"""
    # --- 输入区 ---
    with gr.Row():
        with gr.Column():
            edge_input = gr.Image(label="边缘图", type="filepath")
        with gr.Column():
            prompt_input = gr.Textbox(
                label="语义描述",
                lines=4,
                placeholder="输入图像描述文本...",
            )
            with gr.Row():
                seed_input = gr.Number(label="随机种子", precision=0, value=None)
                seed_btn = gr.Button("🎲", variant="secondary", size="sm")

    run_btn = gr.Button("▶ 运行接收端", variant="primary")

    # --- 输出区 ---
    gr.Markdown("### 输出")
    restored_output = gr.Image(label="还原图像", interactive=False)

    log_output = gr.Textbox(
        label="运行日志",
        lines=6,
        interactive=False,
        elem_classes=["log-output"],
    )

    # --- 事件绑定 ---
    seed_btn.click(fn=_random_seed, outputs=seed_input)

    run_btn.click(
        fn=_run_receiver,
        inputs=[
            edge_input,
            prompt_input,
            seed_input,
            config_components["receiver_host"],
            config_components["receiver_port"],
        ],
        outputs=[restored_output, log_output],
    )

    return {
        "edge_input": edge_input,
        "prompt_input": prompt_input,
    }
