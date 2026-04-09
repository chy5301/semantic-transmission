"""接收端 Tab：队列模式的 Diffusers 还原。

与 M-12 及之前的"单张即时触发"模式不同，本 Tab 采用 **队列 + 批量运行** 模式：

- 用户通过"加入队列"按钮积累多个 (edge_image, prompt, seed) 三元组
- "运行队列"一次性创建 ``DiffusersReceiver`` 并调用 ``process_batch``，
  模型只加载一次；运行后保留 receiver 引用以便后续复用
- "卸载模型"按钮显式释放显存（调用 ``receiver.unload()``）
- 单张场景作为"队列含 1 项"的特例，不需要额外 UI

发送端 Tab 的"→ 加入接收端队列"按钮通过 ``append_external_item`` 函数
跨 Tab 向本队列追加一项。
"""

from __future__ import annotations

import random
import tempfile
import time
from pathlib import Path
from typing import Any

import gradio as gr
from PIL import Image

from semantic_transmission.receiver import create_receiver
from semantic_transmission.receiver.base import BaseReceiver, FrameInput


def _random_seed() -> int:
    return random.randint(0, 2**32 - 1)


def _persist_edge(edge_value: Any) -> str:
    """把 Gradio 传入的边缘图规范化为临时文件路径。

    Gradio 的 gr.Image 根据 ``type`` 参数可能返回 ndarray / PIL Image / filepath，
    为了队列存储的一致性，这里统一落盘到临时 PNG。
    """
    if edge_value is None:
        raise ValueError("边缘图为空")
    if isinstance(edge_value, (str, Path)) and Path(edge_value).exists():
        return str(edge_value)
    # ndarray 或 PIL.Image：落盘到临时文件
    if isinstance(edge_value, Image.Image):
        img = edge_value
    else:
        try:
            import numpy as np

            if isinstance(edge_value, np.ndarray):
                img = Image.fromarray(edge_value)
            else:
                raise TypeError(f"不支持的边缘图类型: {type(edge_value).__name__}")
        except ImportError as e:  # pragma: no cover
            raise TypeError("边缘图类型异常且 numpy 不可用") from e

    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    tmp_path = tmp.name
    tmp.close()
    img.save(tmp_path)
    return tmp_path


def _format_queue_df(queue: list[dict]) -> list[list[str]]:
    """将队列转换为 Dataframe 显示行。"""
    rows = []
    for i, item in enumerate(queue, 1):
        prompt = item.get("prompt", "") or ""
        prompt_preview = prompt if len(prompt) <= 60 else prompt[:57] + "..."
        seed_val = item.get("seed")
        seed_str = str(seed_val) if seed_val is not None else "(随机)"
        rows.append([str(i), prompt_preview, seed_str])
    return rows


def add_to_queue(
    edge_value: Any,
    prompt: str,
    seed: int | None,
    queue: list[dict] | None,
) -> tuple[list[dict], list[list[str]], str]:
    """追加一项到队列，返回更新后的队列、Dataframe 显示和状态文本。"""
    queue = list(queue or [])
    if edge_value is None:
        return queue, _format_queue_df(queue), "错误：请先上传边缘图"
    if not prompt or not prompt.strip():
        return queue, _format_queue_df(queue), "错误：请输入语义描述"
    try:
        edge_path = _persist_edge(edge_value)
    except (ValueError, TypeError) as e:
        return queue, _format_queue_df(queue), f"错误：{e}"

    seed_int = int(seed) if seed is not None and seed != "" else None
    queue.append({"edge_path": edge_path, "prompt": prompt.strip(), "seed": seed_int})
    return queue, _format_queue_df(queue), f"已加入队列，当前 {len(queue)} 项"


def append_external_item(
    edge_value: Any,
    prompt: str,
    queue: list[dict] | None,
) -> tuple[list[dict], list[list[str]]]:
    """供其他 Tab（如发送端）调用，追加一项到接收端队列。

    该函数不强制校验 prompt 非空（发送端可能传空字符串），失败时静默
    返回原队列 —— UI 一致性由调用方控制。
    """
    queue = list(queue or [])
    if edge_value is None:
        return queue, _format_queue_df(queue)
    try:
        edge_path = _persist_edge(edge_value)
    except (ValueError, TypeError):
        return queue, _format_queue_df(queue)
    queue.append({"edge_path": edge_path, "prompt": prompt or "", "seed": None})
    return queue, _format_queue_df(queue)


def clear_queue() -> tuple[list[dict], list[list[str]], list, str]:
    """清空队列和还原图片展示。"""
    return [], _format_queue_df([]), [], "队列已清空"


def unload_model(
    receiver: BaseReceiver | None,
) -> tuple[BaseReceiver | None, str]:
    """显式卸载模型，释放 GPU 显存。"""
    if receiver is None:
        return None, "当前无已加载模型"
    try:
        unload = getattr(receiver, "unload", None)
        if callable(unload):
            unload()
        return None, "模型已卸载"
    except Exception as e:
        return None, f"卸载过程出错：{e}"


def run_queue(
    queue: list[dict] | None,
    receiver: BaseReceiver | None,
):
    """运行队列：模型只加载一次，逐条 process 并 yield 进度。

    Generator 产出元组 ``(receiver_state, gallery, log)``：
    - ``receiver_state``：保持加载的 receiver 引用（复用下次运行）
    - ``gallery``：已完成的还原图像列表
    - ``log``：累积日志文本
    """
    queue = list(queue or [])
    if not queue:
        yield receiver, [], "错误：队列为空，请先加入至少一项"
        return

    log = f"开始运行队列（共 {len(queue)} 项）...\n"
    gallery: list[Image.Image] = []
    yield receiver, gallery, log

    # 模型加载（首次运行或已卸载）
    if receiver is None:
        log += "加载 Diffusers 接收端模型（首次约 1~2 分钟）...\n"
        yield receiver, gallery, log
        try:
            receiver = create_receiver()
            log += "模型加载完成\n"
        except Exception as e:
            log += f"模型加载失败：{e}\n"
            yield None, gallery, log
            return
    else:
        log += "复用已加载的模型\n"
    yield receiver, gallery, log

    # 构造 FrameInput 列表
    frames = [
        FrameInput(
            edge_image=item["edge_path"],
            prompt_text=item["prompt"],
            seed=item.get("seed"),
            metadata={"name": f"queue_{idx:03d}"},
        )
        for idx, item in enumerate(queue, 1)
    ]

    # 逐条运行（直接调 process 以便 yield 中间进度），底层 pipeline 已加载，开销只在单帧推理
    total_start = time.time()
    for idx, frame in enumerate(frames, 1):
        log += f"[{idx}/{len(frames)}] 正在还原（prompt {len(frame.prompt_text)} 字符）...\n"
        yield receiver, gallery, log
        try:
            t0 = time.time()
            img = receiver.process(frame.edge_image, frame.prompt_text, seed=frame.seed)
            elapsed = time.time() - t0
            gallery.append(img)
            log += f"  完成 ({img.size[0]}x{img.size[1]}, {elapsed:.1f}s)\n"
        except Exception as e:
            log += f"  失败：{e}\n"
        yield receiver, gallery, log

    total_elapsed = time.time() - total_start
    log += "─" * 30 + "\n"
    log += (
        f"队列运行结束：{len(gallery)}/{len(frames)} 成功，"
        f"总耗时 {total_elapsed:.1f}s\n"
        '模型保持加载；如需释放显存请点击"卸载模型"\n'
    )
    yield receiver, gallery, log


def build_receiver_tab(config_components: dict) -> dict:
    """构建接收端 Tab 的 UI 组件并绑定事件。

    Args:
        config_components: 全局配置字典（当前未直接使用，保留形参以便未来扩展）
    """
    del config_components  # M-13 目前未从全局配置读取任何字段

    gr.Markdown(
        "### 接收端\n积累多项 (边缘图 + 语义描述) 后一次性运行，模型只加载一次。"
    )

    # --- 队列与 receiver 状态 ---
    queue_state = gr.State(value=[])
    receiver_state = gr.State(value=None)

    # --- 单项输入区 ---
    gr.Markdown("#### 加入队列")
    with gr.Row():
        with gr.Column():
            edge_input = gr.Image(label="边缘图", type="filepath")
        with gr.Column():
            prompt_input = gr.Textbox(
                label="语义描述",
                lines=4,
                placeholder="输入图像描述文本...",
            )
            with gr.Row():
                seed_input = gr.Number(label="随机种子", precision=0, value=None)
                seed_btn = gr.Button("🎲", variant="secondary", size="sm")
    add_btn = gr.Button("＋ 加入队列", variant="secondary")

    # --- 队列展示 ---
    gr.Markdown("#### 当前队列")
    queue_display = gr.Dataframe(
        headers=["#", "Prompt 摘要", "Seed"],
        interactive=False,
        value=[],
    )
    with gr.Row():
        run_btn = gr.Button("▶ 运行队列", variant="primary")
        clear_btn = gr.Button("清空队列", variant="secondary")
        unload_btn = gr.Button("卸载模型", variant="secondary")

    # --- 输出区 ---
    gr.Markdown("#### 还原结果")
    restored_gallery = gr.Gallery(
        label="还原图像",
        columns=3,
        height="auto",
        show_label=True,
    )
    log_output = gr.Textbox(
        label="运行日志",
        lines=8,
        interactive=False,
        elem_classes=["log-output"],
    )
    status_line = gr.Markdown("")

    # --- 事件绑定 ---
    seed_btn.click(fn=_random_seed, outputs=seed_input)

    add_btn.click(
        fn=add_to_queue,
        inputs=[edge_input, prompt_input, seed_input, queue_state],
        outputs=[queue_state, queue_display, status_line],
    )

    run_btn.click(
        fn=run_queue,
        inputs=[queue_state, receiver_state],
        outputs=[receiver_state, restored_gallery, log_output],
    )

    clear_btn.click(
        fn=clear_queue,
        inputs=None,
        outputs=[queue_state, queue_display, restored_gallery, status_line],
    )

    unload_btn.click(
        fn=unload_model,
        inputs=[receiver_state],
        outputs=[receiver_state, status_line],
    )

    return {
        "edge_input": edge_input,
        "prompt_input": prompt_input,
        "queue_state": queue_state,
        "queue_display": queue_display,
    }
