"""Gradio 主应用：组装各 Tab 面板。

启动时调用 ``load_config()`` 获取 ``ProjectConfig`` 实例，传递给各 panel
作为控件默认值的单一来源，取代分散的硬编码默认值（R-11）。
"""

import gradio as gr

from semantic_transmission import __version__
from semantic_transmission.common.config import ProjectConfig, load_config
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


def create_app(project_config: ProjectConfig | None = None) -> gr.Blocks:
    """创建语义传输系统的 Gradio 应用。

    Args:
        project_config: 项目配置实例。``None`` 时调用 ``load_config()`` 自动加载。
            注入此参数主要用于测试场景，正常使用无需显式传入。
    """
    config = project_config if project_config is not None else load_config()

    with gr.Blocks(title="语义传输系统") as app:
        gr.Markdown(
            f"# 语义传输系统 Semantic Transmission\n"
            f"> v{__version__} &nbsp;|&nbsp; "
            f"基于 Diffusers + VLM 的语义级图像压缩传输"
        )

        with gr.Tabs():
            with gr.TabItem("⚙ 配置"):
                config_components = build_config_tab(config)

            with gr.TabItem("◈ 视频流演示"):
                gr.Markdown("_单机 video→video 面板（Task A6 接入）_")

            with gr.TabItem("⇄ 双机视频"):
                gr.Markdown("_双机 relay 视频面板（Task B5 接入）_")

            with gr.TabItem("🖼 图像工具（单帧）"):
                gr.Markdown(
                    "### 图像工具（单帧）\n单帧图像的端到端演示、发送与接收，供调试/对照。"
                )
                with gr.Accordion("端到端演示", open=True):
                    build_pipeline_tab(config_components, config)
                with gr.Accordion("单张发送", open=False):
                    sender_components = build_sender_tab(config_components, config)
                with gr.Accordion("接收端队列", open=False):
                    receiver_components = build_receiver_tab(config_components)

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
