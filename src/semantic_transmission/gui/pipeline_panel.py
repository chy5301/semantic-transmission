"""端到端演示 Tab：一键完成发送 → 传输 → 接收全流程。"""

import io
import os
import time

import gradio as gr
import numpy as np
from PIL import Image

from semantic_transmission.common.comfyui_client import ComfyUIClient
from semantic_transmission.common.config import ComfyUIConfig
from semantic_transmission.receiver.comfyui_receiver import ComfyUIReceiver
from semantic_transmission.sender.comfyui_sender import ComfyUISender


def _default_vlm_path() -> str:
    cache_dir = os.environ.get("MODEL_CACHE_DIR", "")
    if cache_dir:
        return os.path.join(cache_dir, "Qwen", "Qwen2.5-VL-7B-Instruct")
    return ""


def _format_steps(steps, current_idx):
    """格式化步骤列表，标记 ✓/◉/○。"""
    lines = []
    for i, (name, info) in enumerate(steps):
        if i < current_idx:
            lines.append(f"✓ {name}  {info}")
        elif i == current_idx:
            lines.append(f"◉ {name}  进行中...")
        else:
            lines.append(f"○ {name}")
    return "\n".join(lines)


def _run_e2e(
    image_path,
    mode,
    prompt,
    seed,
    sender_host,
    sender_port,
    receiver_host,
    receiver_port,
    vlm_model_name,
    vlm_model_path,
):
    """端到端流程 generator，逐步 yield 更新 UI。"""
    # 输出槽位: original, edge, restored, steps, prompt_result, stats, log
    empty_stats = []
    steps = [
        ("[1/5] 连接检查", ""),
        ("[2/5] 提取边缘图", ""),
        ("[3/5] 获取语义描述", ""),
        ("[4/5] 还原图像", ""),
        ("[5/5] 生成对比图", ""),
    ]
    log = ""
    original_img = None
    edge_img = None
    restored_img = None
    prompt_result = ""

    if not image_path:
        log = "错误：请先上传图像\n"
        yield original_img, edge_img, restored_img, "", prompt_result, empty_stats, log
        return

    original_img = Image.open(image_path)
    original_bytes = os.path.getsize(image_path)

    # --- [1/5] 连接检查 ---
    steps[0] = ("[1/5] 连接检查", "")
    yield (
        original_img,
        edge_img,
        restored_img,
        _format_steps(steps, 0),
        prompt_result,
        empty_stats,
        log,
    )

    s_cfg = ComfyUIConfig(host=sender_host, port=int(sender_port))
    r_cfg = ComfyUIConfig(host=receiver_host, port=int(receiver_port))
    s_client = ComfyUIClient(s_cfg)
    r_client = ComfyUIClient(r_cfg)

    log += "[1/5] 连接检查\n"
    try:
        if not s_client.check_health():
            log += f"  发送端连接失败: {s_cfg.base_url}\n"
            steps[0] = ("[1/5] 连接检查", "失败")
            yield (
                original_img,
                edge_img,
                restored_img,
                _format_steps(steps, 5),
                prompt_result,
                empty_stats,
                log,
            )
            return
        log += f"  发送端 ({s_cfg.base_url}): OK\n"
    except Exception as e:
        log += f"  发送端连接失败: {e}\n"
        yield (
            original_img,
            edge_img,
            restored_img,
            _format_steps(steps, 5),
            prompt_result,
            empty_stats,
            log,
        )
        return

    try:
        if not r_client.check_health():
            log += f"  接收端连接失败: {r_cfg.base_url}\n"
            yield (
                original_img,
                edge_img,
                restored_img,
                _format_steps(steps, 5),
                prompt_result,
                empty_stats,
                log,
            )
            return
        log += f"  接收端 ({r_cfg.base_url}): OK\n"
    except Exception as e:
        log += f"  接收端连接失败: {e}\n"
        yield (
            original_img,
            edge_img,
            restored_img,
            _format_steps(steps, 5),
            prompt_result,
            empty_stats,
            log,
        )
        return

    steps[0] = ("[1/5] 连接检查", "OK")

    # --- [2/5] 提取边缘图 ---
    yield (
        original_img,
        edge_img,
        restored_img,
        _format_steps(steps, 1),
        prompt_result,
        empty_stats,
        log,
    )

    log += "[2/5] 提取 Canny 边缘图...\n"
    try:
        sender = ComfyUISender(s_client)
        t0 = time.time()
        edge_pil = sender.process(image_path)
        sender_elapsed = time.time() - t0
        edge_img = edge_pil
        log += (
            f"  完成 ({edge_pil.size[0]}x{edge_pil.size[1]}, {sender_elapsed:.1f}s)\n"
        )
        steps[1] = ("[2/5] 提取边缘图", f"{sender_elapsed:.1f}s")
    except Exception as e:
        log += f"  失败: {e}\n"
        yield (
            original_img,
            edge_img,
            restored_img,
            _format_steps(steps, 5),
            prompt_result,
            empty_stats,
            log,
        )
        return

    yield (
        original_img,
        edge_img,
        restored_img,
        _format_steps(steps, 2),
        prompt_result,
        empty_stats,
        log,
    )

    # --- [3/5] 获取语义描述 ---
    vlm_elapsed = 0.0
    log += "[3/5] 获取语义描述...\n"
    if mode == "VLM 自动生成":
        log += "  正在加载 VLM 模型...\n"
        yield (
            original_img,
            edge_img,
            restored_img,
            _format_steps(steps, 2),
            prompt_result,
            empty_stats,
            log,
        )

        try:
            from semantic_transmission.sender.qwen_vl_sender import QwenVLSender

            vlm_kwargs = {}
            if vlm_model_name:
                vlm_kwargs["model_name"] = vlm_model_name
            vlm_path = vlm_model_path or _default_vlm_path()
            if vlm_path:
                vlm_kwargs["model_path"] = vlm_path

            vlm_sender = QwenVLSender(**vlm_kwargs)
            img_rgb = original_img.convert("RGB")
            img_array = np.array(img_rgb)
            t0 = time.time()
            sender_output = vlm_sender.describe(img_array)
            vlm_elapsed = time.time() - t0
            prompt_result = sender_output.text
            vlm_sender.unload()

            char_count = len(prompt_result)
            byte_count = len(prompt_result.encode("utf-8"))
            log += (
                f"  完成 ({vlm_elapsed:.1f}s, {char_count} 字符 / {byte_count} 字节)\n"
            )
            log += "  VLM 模型已卸载\n"
            steps[2] = ("[3/5] 获取语义描述", f"{vlm_elapsed:.1f}s (VLM)")
        except Exception as e:
            log += f"  VLM 失败: {e}\n"
            yield (
                original_img,
                edge_img,
                restored_img,
                _format_steps(steps, 5),
                prompt_result,
                empty_stats,
                log,
            )
            return
    else:
        prompt_result = prompt or ""
        if not prompt_result:
            log += "  警告：Prompt 为空\n"
        log += f"  手动 Prompt ({len(prompt_result)} 字符)\n"
        steps[2] = ("[3/5] 获取语义描述", "手动")

    yield (
        original_img,
        edge_img,
        restored_img,
        _format_steps(steps, 3),
        prompt_result,
        empty_stats,
        log,
    )

    # --- [4/5] 还原图像 ---
    log += "[4/5] 接收端还原图像...\n"
    yield (
        original_img,
        edge_img,
        restored_img,
        _format_steps(steps, 3),
        prompt_result,
        empty_stats,
        log,
    )

    seed_int = int(seed) if seed else None
    try:
        receiver = ComfyUIReceiver(r_client)
        # 将边缘图转为 bytes 传给接收端
        buf = io.BytesIO()
        edge_pil.save(buf, format="PNG")
        edge_bytes = buf.getvalue()

        t0 = time.time()
        restored_pil = receiver.process(edge_bytes, prompt_result, seed=seed_int)
        receiver_elapsed = time.time() - t0
        restored_img = restored_pil
        log += f"  完成 ({restored_pil.size[0]}x{restored_pil.size[1]}, {receiver_elapsed:.1f}s)\n"
        steps[3] = ("[4/5] 还原图像", f"{receiver_elapsed:.1f}s")
    except Exception as e:
        log += f"  失败: {e}\n"
        yield (
            original_img,
            edge_img,
            restored_img,
            _format_steps(steps, 5),
            prompt_result,
            empty_stats,
            log,
        )
        return

    yield (
        original_img,
        edge_img,
        restored_img,
        _format_steps(steps, 4),
        prompt_result,
        empty_stats,
        log,
    )

    # --- [5/5] 对比图 + 统计 ---
    log += "[5/5] 生成对比图与统计...\n"
    t0 = time.time()
    # 对比图生成留给前端展示（三张图已 yield），此处计算统计
    comp_elapsed = time.time() - t0

    edge_size = len(edge_bytes)
    prompt_bytes = len(prompt_result.encode("utf-8"))
    total_tx = edge_size + prompt_bytes
    total_elapsed = sender_elapsed + vlm_elapsed + receiver_elapsed + comp_elapsed

    stats = [
        ["原始图像大小", f"{original_bytes:,} bytes"],
        ["边缘图大小", f"{edge_size:,} bytes"],
        ["Prompt 大小", f"{prompt_bytes:,} bytes"],
        ["传输数据总量", f"{total_tx:,} bytes"],
        ["压缩比", f"{original_bytes / total_tx:.2f}x" if total_tx > 0 else "N/A"],
        ["发送端耗时", f"{sender_elapsed:.1f}s"],
        ["VLM 耗时", f"{vlm_elapsed:.1f}s" if vlm_elapsed > 0 else "—"],
        ["接收端耗时", f"{receiver_elapsed:.1f}s"],
        ["总耗时", f"{total_elapsed:.1f}s"],
    ]

    steps[4] = ("[5/5] 生成对比图", f"{comp_elapsed:.1f}s")
    log += "─" * 30 + "\n"
    log += f"端到端完成！总耗时 {total_elapsed:.1f}s，压缩比 {original_bytes / total_tx:.2f}x\n"

    yield (
        original_img,
        edge_img,
        restored_img,
        _format_steps(steps, 5),
        prompt_result,
        stats,
        log,
    )


def _run_evaluation(original_path, restored_img):
    """运行质量评估，返回指标表格和日志。"""
    if not original_path or restored_img is None:
        return [], "错误：需要先完成端到端演示\n"

    log = "运行质量评估...\n"
    original = Image.open(original_path).convert("RGB")
    original_np = np.array(original)

    if isinstance(restored_img, Image.Image):
        restored = restored_img.convert("RGB")
    else:
        restored = Image.open(restored_img).convert("RGB")
    restored_np = np.array(restored)

    # 调整尺寸一致
    if original_np.shape[:2] != restored_np.shape[:2]:
        restored = restored.resize((original.width, original.height), Image.LANCZOS)
        restored_np = np.array(restored)
        log += f"  还原图已缩放至 {original.width}x{original.height}\n"

    metrics = []

    try:
        from semantic_transmission.evaluation import compute_psnr

        val = compute_psnr(original_np, restored_np)
        metrics.append(["PSNR", f"{val:.2f} dB"])
        log += f"  PSNR: {val:.2f} dB\n"
    except Exception as e:
        metrics.append(["PSNR", f"错误: {e}"])

    try:
        from semantic_transmission.evaluation import compute_ssim

        val = compute_ssim(original_np, restored_np)
        metrics.append(["SSIM", f"{val:.4f}"])
        log += f"  SSIM: {val:.4f}\n"
    except Exception as e:
        metrics.append(["SSIM", f"错误: {e}"])

    try:
        from semantic_transmission.evaluation import compute_lpips

        val = compute_lpips(original_np, restored_np)
        metrics.append(["LPIPS", f"{val:.4f}"])
        log += f"  LPIPS: {val:.4f}\n"
    except Exception as e:
        metrics.append(["LPIPS", f"错误: {e}"])

    log += "质量评估完成\n"
    return metrics, log


def build_pipeline_tab(config_components: dict) -> dict:
    """构建端到端演示 Tab 的 UI 组件并绑定事件。"""
    # --- 输入区 ---
    with gr.Row():
        with gr.Column(scale=1):
            image_input = gr.Image(label="原始图像", type="filepath")
        with gr.Column(scale=1):
            mode_radio = gr.Radio(
                choices=["手动输入", "VLM 自动生成"],
                value="手动输入",
                label="描述模式",
            )
            prompt_input = gr.Textbox(
                label="Prompt",
                lines=3,
                placeholder="输入图像描述文本...",
            )
            seed_input = gr.Number(label="随机种子（可选）", precision=0)

    run_btn = gr.Button("▶ 运行端到端演示", variant="primary")

    # --- 进度区 ---
    steps_display = gr.Textbox(
        label="流程进度",
        lines=5,
        interactive=False,
        elem_classes=["log-output"],
    )

    # --- 结果展示 ---
    gr.Markdown("### 结果对比")
    with gr.Row():
        original_display = gr.Image(label="原始图像", interactive=False)
        edge_display = gr.Image(label="边缘图 (Canny)", interactive=False)
        restored_display = gr.Image(label="还原图像", interactive=False)

    prompt_result = gr.Textbox(
        label="语义描述",
        lines=3,
        interactive=False,
    )

    # --- 传输统计 ---
    gr.Markdown("### 传输统计")
    stats_table = gr.Dataframe(
        headers=["指标", "值"],
        interactive=False,
        elem_classes=["stats-table"],
    )

    # --- 质量评估 ---
    with gr.Accordion("质量评估（可选）", open=False):
        eval_btn = gr.Button("运行质量评估", variant="secondary")
        eval_table = gr.Dataframe(
            headers=["指标", "值"],
            interactive=False,
        )
        eval_log = gr.Textbox(
            label="评估日志",
            lines=4,
            interactive=False,
            elem_classes=["log-output"],
        )

    # --- 日志区 ---
    with gr.Accordion("运行日志", open=False):
        log_output = gr.Textbox(
            label="详细日志",
            lines=10,
            interactive=False,
            elem_classes=["log-output"],
        )

    # --- 描述模式切换 ---
    mode_radio.change(
        fn=lambda m: gr.update(visible=(m == "手动输入")),
        inputs=mode_radio,
        outputs=prompt_input,
    )

    # --- 运行端到端 ---
    run_btn.click(
        fn=_run_e2e,
        inputs=[
            image_input,
            mode_radio,
            prompt_input,
            seed_input,
            config_components["sender_host"],
            config_components["sender_port"],
            config_components["receiver_host"],
            config_components["receiver_port"],
            config_components["vlm_model_name"],
            config_components["vlm_model_path"],
        ],
        outputs=[
            original_display,
            edge_display,
            restored_display,
            steps_display,
            prompt_result,
            stats_table,
            log_output,
        ],
    )

    # --- 质量评估 ---
    eval_btn.click(
        fn=_run_evaluation,
        inputs=[image_input, restored_display],
        outputs=[eval_table, eval_log],
    )

    return {}
