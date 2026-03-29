"""Gradio 主应用：组装各 Tab 面板。"""

import gradio as gr

from semantic_transmission import __version__
from semantic_transmission.gui.config_panel import build_config_tab
from semantic_transmission.gui.theme import CUSTOM_CSS, get_theme


def get_launch_kwargs() -> dict:
    """返回 Gradio launch() 所需的主题和样式参数（Gradio 6.x）。"""
    return {"theme": get_theme(), "css": CUSTOM_CSS}


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
                build_config_tab()

            with gr.TabItem("▲ 发送端"):
                gr.Markdown(
                    "### 发送端\n\n"
                    "> 此功能将在后续版本中实现。\n\n"
                    "发送端将支持：上传图像 → Canny 边缘提取 → VLM 语义描述生成"
                )

            with gr.TabItem("▼ 接收端"):
                gr.Markdown(
                    "### 接收端\n\n"
                    "> 此功能将在后续版本中实现。\n\n"
                    "接收端将支持：边缘图 + 语义描述 → 图像还原"
                )

            with gr.TabItem("◆ 端到端演示"):
                gr.Markdown(
                    "### 端到端演示\n\n"
                    "> 此功能将在后续版本中实现。\n\n"
                    "端到端演示将支持：一键完成 发送 → 传输 → 接收 全流程"
                )

    return app
