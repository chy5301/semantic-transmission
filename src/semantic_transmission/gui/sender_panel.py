"""发送端 Tab：图像上传 → Canny 边缘提取 → VLM 语义描述。"""

import time

import gradio as gr
import numpy as np
from PIL import Image

from semantic_transmission.common.comfyui_client import ComfyUIClient
from semantic_transmission.common.config import ComfyUIConfig, get_default_vlm_path
from semantic_transmission.gui import MODE_MANUAL, MODE_VLM_AUTO
from semantic_transmission.sender.comfyui_sender import ComfyUISender


def _on_mode_change(mode: str):
    return gr.update(visible=(mode == MODE_MANUAL))


def _run_sender(
    image_path,
    mode,
    prompt,
    sender_host,
    sender_port,
    vlm_model_name,
    vlm_model_path,
):
    """运行发送端流程，generator 逐步 yield 更新 UI。"""
    log = ""
    edge_img = None
    prompt_result = ""
    send_btn_visible = False

    if not image_path:
        log = "错误：请先上传图像\n"
        yield edge_img, log, prompt_result, gr.update(visible=send_btn_visible)
        return

    # [1] 连接检查
    log += "[1/3] 检查 ComfyUI 连接...\n"
    yield edge_img, log, prompt_result, gr.update(visible=send_btn_visible)

    config = ComfyUIConfig(host=sender_host, port=int(sender_port))
    client = ComfyUIClient(config)
    try:
        if not client.check_health():
            log += f"  连接失败: {config.base_url} 服务异常\n"
            yield edge_img, log, prompt_result, gr.update(visible=send_btn_visible)
            return
        log += f"  {config.base_url}: OK\n"
    except Exception as e:
        log += f"  连接失败: {e}\n"
        yield edge_img, log, prompt_result, gr.update(visible=send_btn_visible)
        return

    # [2] 提取边缘图
    log += "[2/3] 提取 Canny 边缘图...\n"
    yield edge_img, log, prompt_result, gr.update(visible=send_btn_visible)

    try:
        sender = ComfyUISender(client)
        start = time.time()
        edge_pil = sender.process(image_path)
        elapsed = time.time() - start
        edge_img = edge_pil
        log += f"  完成 ({edge_pil.size[0]}x{edge_pil.size[1]}, {elapsed:.1f}s)\n"
    except Exception as e:
        log += f"  失败: {e}\n"
        yield edge_img, log, prompt_result, gr.update(visible=send_btn_visible)
        return

    yield edge_img, log, prompt_result, gr.update(visible=send_btn_visible)

    # [3] 获取语义描述
    if mode == MODE_VLM_AUTO:
        log += "[3/3] VLM 生成语义描述...\n"
        log += "  正在加载 VLM 模型（首次加载可能需要几分钟）...\n"
        yield edge_img, log, prompt_result, gr.update(visible=send_btn_visible)

        try:
            from semantic_transmission.sender.qwen_vl_sender import QwenVLSender

            vlm_kwargs = {}
            if vlm_model_name:
                vlm_kwargs["model_name"] = vlm_model_name
            vlm_path = vlm_model_path or get_default_vlm_path() or ""
            if vlm_path:
                vlm_kwargs["model_path"] = vlm_path

            vlm_sender = QwenVLSender(**vlm_kwargs)
            original_img = Image.open(image_path).convert("RGB")
            image_array = np.array(original_img)
            start = time.time()
            sender_output = vlm_sender.describe(image_array)
            elapsed = time.time() - start
            prompt_result = sender_output.text
            vlm_sender.unload()

            char_count = len(prompt_result)
            byte_count = len(prompt_result.encode("utf-8"))
            log += f"  完成 ({elapsed:.1f}s, {char_count} 字符 / {byte_count} 字节)\n"
            log += "  VLM 模型已卸载\n"
        except Exception as e:
            log += f"  VLM 失败: {e}\n"
            yield edge_img, log, prompt_result, gr.update(visible=send_btn_visible)
            return
    else:
        log += "[3/3] 使用手动 Prompt\n"
        prompt_result = prompt or ""
        if not prompt_result:
            log += "  警告：Prompt 为空\n"

    send_btn_visible = True
    log += "─" * 30 + "\n"
    log += "发送端完成！\n"
    yield edge_img, log, prompt_result, gr.update(visible=send_btn_visible)


def build_sender_tab(config_components: dict) -> dict:
    """构建发送端 Tab 的 UI 组件并绑定事件。"""
    # --- 输入区 ---
    with gr.Row():
        with gr.Column():
            image_input = gr.Image(label="原始图像", type="filepath")
        with gr.Column():
            edge_output = gr.Image(label="边缘图 (Canny)", interactive=False)

    mode_radio = gr.Radio(
        choices=[MODE_MANUAL, MODE_VLM_AUTO],
        value=MODE_MANUAL,
        label="描述模式",
    )
    prompt_input = gr.Textbox(
        label="Prompt",
        lines=3,
        placeholder="输入图像描述文本...",
        visible=True,
    )

    with gr.Row():
        run_btn = gr.Button("▶ 运行发送端", variant="primary")
        send_to_receiver_btn = gr.Button(
            "→ 发送到接收端", variant="secondary", visible=False
        )

    # --- 输出区 ---
    log_output = gr.Textbox(
        label="运行日志",
        lines=8,
        interactive=False,
        elem_classes=["log-output"],
    )
    prompt_result = gr.Textbox(
        label="语义描述结果",
        lines=4,
        interactive=False,
    )

    # --- 事件绑定 ---
    mode_radio.change(fn=_on_mode_change, inputs=mode_radio, outputs=prompt_input)

    run_btn.click(
        fn=_run_sender,
        inputs=[
            image_input,
            mode_radio,
            prompt_input,
            config_components["sender_host"],
            config_components["sender_port"],
            config_components["vlm_model_name"],
            config_components["vlm_model_path"],
        ],
        outputs=[edge_output, log_output, prompt_result, send_to_receiver_btn],
    )

    return {
        "edge_output": edge_output,
        "prompt_result": prompt_result,
        "send_to_receiver_btn": send_to_receiver_btn,
    }
