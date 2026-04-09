"""semantic-tx check 子命令组：VLM / Diffusers 模型与中继对端检查。"""

import socket

import click

from semantic_transmission.common.config import DiffusersReceiverConfig
from semantic_transmission.common.model_check import (
    check_diffusers_receiver_model,
    check_vlm_model,
)


@click.group()
def check():
    """检查 VLM / Diffusers 模型与中继对端连通性。"""


@check.command("vlm")
@click.option(
    "--model-path",
    default=None,
    type=str,
    help="VLM 模型本地路径（默认 $MODEL_CACHE_DIR/Qwen/Qwen2.5-VL-7B-Instruct）",
)
def vlm(model_path):
    """检查 VLM（Qwen2.5-VL）模型是否就绪（发送端用）。"""
    ok, message = check_vlm_model(model_path)
    click.echo(message)
    if not ok:
        raise SystemExit(1)


@check.command("diffusers")
def diffusers():
    """检查 Diffusers 接收端模型是否就绪（接收端用）。"""
    config = DiffusersReceiverConfig()
    ok, message = check_diffusers_receiver_model(config)
    click.echo(message)
    if not ok:
        raise SystemExit(1)


@check.command("relay")
@click.option("--host", required=True, type=str, help="对端主机地址")
@click.option("--port", required=True, type=int, help="对端端口")
@click.option("--timeout", default=5.0, type=float, help="连接超时秒数（默认 5.0）")
def relay(host, port, timeout):
    """检查双机部署下对端 TCP 端口的可达性。"""
    click.echo(f"测试对端连接：{host}:{port}（超时 {timeout}s）")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect((host, port))
        click.echo(f"✓ 连接成功：{host}:{port} 可达")
    except OSError as e:
        click.echo(f"✗ 连接失败：{host}:{port} - {e}")
        raise SystemExit(1) from e
    finally:
        sock.close()
