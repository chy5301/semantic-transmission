"""语义传输系统 Gradio GUI。"""

from semantic_transmission.gui.app import create_app, get_launch_kwargs

MODE_MANUAL = "手动输入"
MODE_VLM_AUTO = "VLM 自动生成"

__all__ = ["create_app", "get_launch_kwargs", "MODE_MANUAL", "MODE_VLM_AUTO"]
