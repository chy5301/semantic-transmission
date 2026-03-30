"""语义传输系统 Gradio GUI。"""

MODE_MANUAL = "手动输入"
MODE_VLM_AUTO = "VLM 自动生成"

from semantic_transmission.gui.app import create_app, get_launch_kwargs  # noqa: E402

__all__ = ["create_app", "get_launch_kwargs", "MODE_MANUAL", "MODE_VLM_AUTO"]
