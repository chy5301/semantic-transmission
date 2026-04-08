"""Gradio 主应用：组装各 Tab 面板。"""

import gradio as gr

from semantic_transmission import __version__
from semantic_transmission.gui.batch_panel import build_batch_tab
from semantic_transmission.gui.batch_sender_panel import build_batch_sender_tab
from semantic_transmission.gui.config_panel import build_config_tab
from semantic_transmission.gui.pipeline_panel import build_pipeline_tab
from semantic_transmission.gui.receiver_panel import (
    append_external_item,
    build_receiver_tab,
)
from semantic_transmission.gui.sender_panel import build_sender_tab
from semantic_transmission.gui.theme import CUSTOM_CSS


def get_launch_kwargs() -> dict:
    """返回 Gradio launch() 所需参数。"""
    return {"css": CUSTOM_CSS}


def create_app() -> gr.Blocks:
    """创建语义传输系统的 Gradio 应用。"""
    with gr.Blocks(title="语义传输系统") as app:
        gr.Markdown(
            f"# 语义传输系统 Semantic Transmission\n"
            f"> v{__version__} &nbsp;|&nbsp; "
            f"基于 ComfyUI + VLM 的语义级图像压缩传输"
        )

        with gr.Tabs():
            with gr.TabItem("⚙ 配置"):
                config_components = build_config_tab()

            with gr.TabItem("▲ 单张发送"):
                sender_components = build_sender_tab(config_components)

            with gr.TabItem("📦 批量发送"):
                build_batch_sender_tab(config_components)

            with gr.TabItem("▼ 接收端"):
                receiver_components = build_receiver_tab(config_components)

            with gr.TabItem("◆ 端到端演示"):
                build_pipeline_tab(config_components)

            with gr.TabItem("◇ 批量端到端"):
                build_batch_tab(config_components)

        # Tab 间传递：发送端 → 接收端队列（M-13：append 到接收端 gr.State 队列）
        sender_components["send_to_receiver_btn"].click(
            fn=append_external_item,
            inputs=[
                sender_components["edge_output"],
                sender_components["prompt_result"],
                receiver_components["queue_state"],
            ],
            outputs=[
                receiver_components["queue_state"],
                receiver_components["queue_display"],
            ],
        )

    return app
