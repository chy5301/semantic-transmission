"""semantic-tx gui 子命令：启动 Gradio 可视化界面。"""

import click


@click.command()
@click.option("--host", default="127.0.0.1", help="监听地址（默认 127.0.0.1）")
@click.option("--port", default=7860, type=int, help="监听端口（默认 7860）")
@click.option("--share", is_flag=True, default=False, help="生成 Gradio 公网分享链接")
def gui(host, port, share):
    """启动 Gradio 可视化界面。"""
    from semantic_transmission.gui.app import create_app, get_launch_kwargs

    app = create_app()
    app.launch(server_name=host, server_port=port, share=share, **get_launch_kwargs())
