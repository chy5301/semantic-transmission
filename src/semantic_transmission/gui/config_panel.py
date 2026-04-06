"""配置 Tab：ComfyUI 连接管理、VLM 模型检查、中继传输配置。"""

import time
from pathlib import Path

import gradio as gr

from semantic_transmission.common.comfyui_client import ComfyUIClient
from semantic_transmission.common.config import ComfyUIConfig, get_default_vlm_path


def _test_comfyui_connection(host: str, port: float) -> str:
    """测试 ComfyUI 连接，返回带颜色的状态文本。"""
    if not host:
        return '<span style="color:#DC2626">● 请输入主机地址</span>'
    config = ComfyUIConfig(host=host, port=int(port))
    client = ComfyUIClient(config)
    try:
        start = time.time()
        ok = client.check_health()
        elapsed_ms = (time.time() - start) * 1000
        if ok:
            return f'<span style="color:#16A34A">● 已连接 ({config.base_url}, 延迟: {elapsed_ms:.0f}ms)</span>'
        return '<span style="color:#DC2626">● 连接失败: 服务返回异常</span>'
    except Exception as e:
        return f'<span style="color:#DC2626">● 连接失败: {e}</span>'


def _check_vlm_model(_model_name: str, model_path: str) -> str:
    """检查 VLM 模型是否就绪，返回带颜色的状态文本。"""
    if not model_path:
        return '<span style="color:#94A3B8">● 未配置本地路径</span>'
    p = Path(model_path)
    if p.is_dir() and (p / "config.json").exists():
        return '<span style="color:#16A34A">● 模型已就绪</span>'
    if p.is_dir():
        return '<span style="color:#CA8A04">● 目录存在但未找到 config.json</span>'
    return f'<span style="color:#DC2626">● 路径不存在: {model_path}</span>'


def build_config_tab() -> dict:
    """构建配置 Tab 的 UI 组件并绑定事件，返回组件引用字典。"""
    sender_cfg = ComfyUIConfig.from_env(prefix="SENDER")
    receiver_cfg = ComfyUIConfig.from_env(prefix="RECEIVER")

    # --- 接收端后端 ---
    gr.Markdown("### 接收端后端")
    receiver_backend = gr.Radio(
        choices=[
            ("Diffusers（本地推理）", "diffusers"),
            ("ComfyUI（远程服务）", "comfyui"),
        ],
        value="diffusers",
        label="接收端后端",
    )

    # --- ComfyUI 连接 ---
    gr.Markdown("### ComfyUI 连接")
    with gr.Row():
        with gr.Column():
            gr.Markdown("**发送端**")
            sender_host = gr.Textbox(
                value=sender_cfg.host, label="主机地址", placeholder="127.0.0.1"
            )
            sender_port = gr.Number(value=sender_cfg.port, label="端口", precision=0)
            sender_test_btn = gr.Button("测试连接", variant="secondary", size="sm")
            sender_status = gr.Markdown(
                '<span style="color:#94A3B8">● 未检测</span>',
                elem_classes=["status-text"],
            )

        with gr.Column():
            gr.Markdown("**接收端（ComfyUI 模式）**")
            receiver_host = gr.Textbox(
                value=receiver_cfg.host, label="主机地址", placeholder="127.0.0.1"
            )
            receiver_port = gr.Number(
                value=receiver_cfg.port, label="端口", precision=0
            )
            receiver_test_btn = gr.Button("测试连接", variant="secondary", size="sm")
            receiver_status = gr.Markdown(
                '<span style="color:#94A3B8">● 未检测</span>',
                elem_classes=["status-text"],
            )

    # --- VLM 模型 ---
    gr.Markdown("### VLM 模型")
    vlm_model_name = gr.Textbox(value="Qwen/Qwen2.5-VL-7B-Instruct", label="模型名称")
    vlm_model_path = gr.Textbox(
        value=get_default_vlm_path() or "",
        label="本地路径",
        placeholder="留空则使用 HuggingFace 在线加载",
    )
    with gr.Row():
        vlm_check_btn = gr.Button("检查模型", variant="secondary", size="sm")
        vlm_status = gr.Markdown(
            '<span style="color:#94A3B8">● 未检测</span>',
            elem_classes=["status-text"],
        )

    # --- 中继传输 ---
    gr.Markdown("### 中继传输")
    with gr.Row():
        relay_host = gr.Textbox(
            value="0.0.0.0", label="监听地址", placeholder="0.0.0.0"
        )
        relay_port = gr.Number(value=9000, label="监听端口", precision=0)

    # --- 事件绑定 ---
    sender_test_btn.click(
        fn=_test_comfyui_connection,
        inputs=[sender_host, sender_port],
        outputs=sender_status,
    )
    receiver_test_btn.click(
        fn=_test_comfyui_connection,
        inputs=[receiver_host, receiver_port],
        outputs=receiver_status,
    )
    vlm_check_btn.click(
        fn=_check_vlm_model,
        inputs=[vlm_model_name, vlm_model_path],
        outputs=vlm_status,
    )

    return {
        "receiver_backend": receiver_backend,
        "sender_host": sender_host,
        "sender_port": sender_port,
        "receiver_host": receiver_host,
        "receiver_port": receiver_port,
        "vlm_model_name": vlm_model_name,
        "vlm_model_path": vlm_model_path,
        "relay_host": relay_host,
        "relay_port": relay_port,
    }
