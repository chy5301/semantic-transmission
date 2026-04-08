"""配置 Tab：VLM 与 Diffusers 接收端模型就绪检测。"""

import gradio as gr

from semantic_transmission.common.config import (
    DiffusersReceiverConfig,
    get_default_vlm_path,
)
from semantic_transmission.common.model_check import (
    check_diffusers_receiver_model,
    check_vlm_model,
)


def _format_status(ok: bool, message: str) -> str:
    """根据检查结果生成带颜色的 Markdown 状态文本。"""
    color = "#16A34A" if ok else "#DC2626"
    # 将纯文本的多行消息转为 Markdown 预格式化块，避免 ✓/✗ 被误解析
    body = message.replace("\n", "<br>")
    return f'<span style="color:{color}">● {body}</span>'


def _gui_check_vlm(_model_name: str, model_path: str) -> str:
    """GUI 包装：调用 common.model_check.check_vlm_model。"""
    ok, message = check_vlm_model(model_path or None)
    return _format_status(ok, message)


def _gui_check_diffusers() -> str:
    """GUI 包装：调用 common.model_check.check_diffusers_receiver_model（使用默认配置）。"""
    ok, message = check_diffusers_receiver_model(DiffusersReceiverConfig())
    return _format_status(ok, message)


def build_config_tab() -> dict:
    """构建配置 Tab 的 UI 组件并绑定事件，返回组件引用字典。"""
    gr.Markdown(
        "### 接收端后端\n"
        "本项目已完全采用 **Diffusers 本地推理**（Z-Image-Turbo + ControlNet Union，GGUF Q8_0 量化）。"
        "接收端无需外部服务。"
    )

    # --- VLM 模型 ---
    gr.Markdown("### VLM 模型（发送端 auto-prompt 使用）")
    vlm_model_name = gr.Textbox(value="Qwen/Qwen2.5-VL-7B-Instruct", label="模型名称")
    vlm_model_path = gr.Textbox(
        value=get_default_vlm_path() or "",
        label="本地路径",
        placeholder="留空则使用 HuggingFace 在线加载",
    )
    with gr.Row():
        vlm_check_btn = gr.Button("检查 VLM 模型", variant="secondary", size="sm")
        vlm_status = gr.Markdown(
            '<span style="color:#94A3B8">● 未检测</span>',
            elem_classes=["status-text"],
        )

    # --- Diffusers 接收端模型 ---
    gr.Markdown(
        "### Diffusers 接收端模型\n"
        "检查 transformer GGUF、ControlNet 权重和 HF cache 下 pipeline base 组件是否就绪。"
    )
    with gr.Row():
        diffusers_check_btn = gr.Button(
            "检查 Diffusers 模型", variant="secondary", size="sm"
        )
        diffusers_status = gr.Markdown(
            '<span style="color:#94A3B8">● 未检测</span>',
            elem_classes=["status-text"],
        )

    # --- 事件绑定 ---
    vlm_check_btn.click(
        fn=_gui_check_vlm,
        inputs=[vlm_model_name, vlm_model_path],
        outputs=vlm_status,
    )
    diffusers_check_btn.click(
        fn=_gui_check_diffusers,
        inputs=None,
        outputs=diffusers_status,
    )

    return {
        "vlm_model_name": vlm_model_name,
        "vlm_model_path": vlm_model_path,
    }
