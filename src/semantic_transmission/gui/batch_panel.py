"""批量端到端 Tab 面板：逐组 Accordion 展示 + 可选质量评估。

M-15 在 M-12 清理后进一步改造结果展示层：
- 每张图片的结果（原图 / 边缘图 / 还原图 / prompt / 可选 metrics）
  通过 ``@gr.render`` 动态渲染为独立的 Accordion 折叠块
- 勾选"运行质量评估"时逐样本计算 PSNR/SSIM/LPIPS，
  结束后汇总总体平均展示
"""

import json
import time
from pathlib import Path
from typing import Any, Iterator

import gradio as gr
import numpy as np
from PIL import Image

from semantic_transmission.pipeline.batch_processor import (
    BatchImageDiscoverer,
    BatchResult,
    SampleResult,
    make_sample_output_dir,
)
from semantic_transmission.receiver import create_receiver
from semantic_transmission.sender.local_condition_extractor import LocalCannyExtractor


def compute_sample_metrics(
    original: Image.Image | str | Path,
    restored: Image.Image | str | Path,
    lpips_model: Any | None = None,
) -> dict[str, float]:
    """计算单对图像的 PSNR / SSIM / LPIPS 指标。

    LPIPS 需要预加载模型，未传入时只计算 PSNR 和 SSIM。这个拆分
    让上层在批量评估时只加载一次 LPIPS 模型，避免重复开销。
    """
    from semantic_transmission.evaluation import compute_psnr, compute_ssim

    if isinstance(original, (str, Path)):
        original = Image.open(original).convert("RGB")
    if isinstance(restored, (str, Path)):
        restored = Image.open(restored).convert("RGB")

    metrics: dict[str, float] = {
        "psnr": compute_psnr(original, restored),
        "ssim": compute_ssim(original, restored),
    }
    if lpips_model is not None:
        from semantic_transmission.evaluation import compute_lpips

        metrics["lpips"] = compute_lpips(original, restored, loss_fn=lpips_model)
    return metrics


def aggregate_metrics(
    samples: list[SampleResult],
) -> list[list[str]]:
    """汇总所有成功样本的 metrics 平均值，返回 Dataframe 行列表。

    没有任何样本带 metrics 时返回空列表（上层据此隐藏总体评估区）。
    """
    collected: dict[str, list[float]] = {}
    for s in samples:
        if s.status != "success" or not s.metrics:
            continue
        for key, value in s.metrics.items():
            collected.setdefault(key, []).append(float(value))

    if not collected:
        return []

    rows: list[list[str]] = []
    for key in ("psnr", "ssim", "lpips"):
        if key in collected:
            values = collected[key]
            avg = sum(values) / len(values)
            fmt = f"{avg:.2f} dB" if key == "psnr" else f"{avg:.4f}"
            rows.append([key.upper(), fmt, str(len(values))])
    return rows


def _make_comparison_image(
    original: Image.Image, edge: Image.Image, restored: Image.Image
) -> Image.Image:
    """横向拼接对比图：原图 | 边缘图 | 还原图。"""
    target_height = max(original.height, edge.height, restored.height)

    def resize_to_height(img: Image.Image, height: int) -> Image.Image:
        if img.height == height:
            return img
        ratio = height / img.height
        new_width = int(img.width * ratio)
        return img.resize((new_width, height), Image.LANCZOS)

    imgs = [resize_to_height(img, target_height) for img in [original, edge, restored]]
    total_width = sum(img.width for img in imgs)

    comparison = Image.new("RGB", (total_width, target_height))
    x = 0
    for img in imgs:
        if img.mode != "RGB":
            img = img.convert("RGB")
        comparison.paste(img, (x, 0))
        x += img.width

    return comparison


def build_batch_tab(config_components):
    """构建批量端到端 Tab。"""

    def run_batch_process(
        input_dir: str,
        output_dir: str,
        prompt_mode: str,
        manual_prompt: str,
        recursive: bool,
        skip_errors: bool,
        seed: int | None,
        run_eval: bool,
        vlm_model_name: str,
        vlm_model_path: str,
    ) -> Iterator[tuple[str, list[dict], list[list[str]]]]:
        """运行批量端到端处理。

        Yields:
            ``(log_text, results_list, overall_metrics_rows)``
            - ``results_list``：每项含 original_path / edge_path / restored_path /
              prompt / metrics，供 Accordion 动态渲染
            - ``overall_metrics_rows``：总体平均 metrics 表格行
        """
        results: list[dict] = []
        overall_rows: list[list[str]] = []

        if not input_dir or not output_dir:
            yield "请填写输入目录和输出目录", results, overall_rows
            return

        input_path = Path(input_dir)
        output_path = Path(output_dir)

        if prompt_mode == "manual" and not manual_prompt:
            yield "请输入手动 prompt 或选择自动模式", results, overall_rows
            return

        yield f"开始扫描目录: {input_path}\n", results, overall_rows

        # 扫描目录
        discoverer = BatchImageDiscoverer()
        discovery = discoverer.discover(input_path, recursive=recursive)

        if not discovery:
            yield (
                f"在 {input_path} 中没有找到支持的图片文件",
                results,
                overall_rows,
            )
            return

        log_text = f"发现图片: {discovery.total_count} 张\n"
        for ext, count in discovery.formats_detected.items():
            log_text += f"  {ext}: {count} 张\n"
        yield log_text, results, overall_rows

        # 创建输出目录
        output_path.mkdir(parents=True, exist_ok=True)

        # 初始化发送端（本地 Canny 提取）和接收端
        extractor = LocalCannyExtractor()
        receiver = create_receiver()
        log_text += "\n发送端：本地 Canny 提取\n接收端：Diffusers 本地推理\n"
        if run_eval:
            log_text += "质量评估：已启用（每组 PSNR/SSIM/LPIPS + 总体平均）\n"
        yield log_text, results, overall_rows

        # 加载 VLM 如果需要
        vlm_sender = None
        if prompt_mode == "auto":
            from semantic_transmission.common.config import get_default_vlm_path
            from semantic_transmission.sender.qwen_vl_sender import QwenVLSender

            yield log_text + "\n正在加载 VLM 模型...\n", results, overall_rows
            vlm_kwargs = {}
            if vlm_model_name:
                vlm_kwargs["model_name"] = vlm_model_name
            vlm_path = vlm_model_path or get_default_vlm_path() or ""
            if vlm_path:
                vlm_kwargs["model_path"] = vlm_path
            vlm_sender = QwenVLSender(**vlm_kwargs)
            log_text += "✓ VLM 模型加载完成\n"
            yield log_text, results, overall_rows

        # 加载 LPIPS 模型（如启用评估）
        lpips_model = None
        if run_eval:
            try:
                from semantic_transmission.evaluation import load_lpips_model

                yield (
                    log_text + "\n正在加载 LPIPS 评估模型...\n",
                    results,
                    overall_rows,
                )
                lpips_model = load_lpips_model()
                log_text += "✓ LPIPS 模型加载完成\n"
                yield log_text, results, overall_rows
            except Exception as e:
                log_text += f"⚠ LPIPS 加载失败（将跳过 LPIPS 指标）: {e}\n"
                yield log_text, results, overall_rows

        # 开始批量处理
        total_start = time.time()
        batch_result = BatchResult(total=discovery.total_count)

        for idx, image_path in enumerate(discovery.images, 1):
            image_name = image_path.stem
            rel_path = image_path.relative_to(input_path)

            current_log = log_text
            current_log += f"\n[{idx}/{discovery.total_count}] 处理: {rel_path}\n"
            yield current_log, results, overall_rows

            # 创建输出子目录
            sample_output_dir = make_sample_output_dir(output_path, idx, image_name)

            try:
                # 提取边缘图（本地 OpenCV）
                original_image = Image.open(image_path).convert("RGB")
                image_array = np.array(original_image)
                start = time.time()
                edge_np = extractor.extract(image_array)
                sender_elapsed = time.time() - start
                edge_image = Image.fromarray(edge_np)

                edge_path = sample_output_dir / "edge.png"
                edge_image.save(edge_path)
                current_log += f"  ✓ 边缘提取完成 ({edge_image.size[0]}x{edge_image.size[1]}) 耗时 {sender_elapsed:.1f}s\n"
                yield current_log, results, overall_rows

                # 获取 prompt
                vlm_elapsed = 0.0
                if prompt_mode == "auto" and vlm_sender is not None:
                    start_vlm = time.time()
                    sender_output = vlm_sender.describe(image_array)
                    vlm_elapsed = time.time() - start_vlm
                    prompt_text = sender_output.text
                    current_log += f"  ✓ VLM 生成完成 ({len(prompt_text)} 字符) 耗时 {vlm_elapsed:.1f}s\n"
                    yield current_log, results, overall_rows
                else:
                    prompt_text = manual_prompt
                    current_log += "  ✓ 使用手动 prompt\n"

                # 保存 prompt
                prompt_path = sample_output_dir / "prompt.txt"
                prompt_path.write_text(prompt_text, encoding="utf-8")

                # 还原图像
                start = time.time()
                restored_image = receiver.process(edge_image, prompt_text, seed=seed)
                receiver_elapsed = time.time() - start

                restored_path = sample_output_dir / "restored.png"
                restored_image.save(restored_path)
                current_log += f"  ✓ 还原完成 ({restored_image.size[0]}x{restored_image.size[1]}) 耗时 {receiver_elapsed:.1f}s\n"
                yield current_log, results, overall_rows

                # 可选质量评估
                sample_metrics: dict[str, float] = {}
                if run_eval:
                    try:
                        start_eval = time.time()
                        sample_metrics = compute_sample_metrics(
                            original_image, restored_image, lpips_model=lpips_model
                        )
                        eval_elapsed = time.time() - start_eval
                        parts = [
                            f"PSNR={sample_metrics['psnr']:.2f}dB",
                            f"SSIM={sample_metrics['ssim']:.4f}",
                        ]
                        if "lpips" in sample_metrics:
                            parts.append(f"LPIPS={sample_metrics['lpips']:.4f}")
                        current_log += f"  ✓ 评估完成 ({', '.join(parts)}) 耗时 {eval_elapsed:.1f}s\n"
                    except Exception as eval_err:
                        current_log += f"  ⚠ 评估失败: {eval_err}\n"

                # 生成对比图
                start = time.time()
                comparison = _make_comparison_image(
                    original_image, edge_image, restored_image
                )
                comparison_path = sample_output_dir / "comparison.png"
                comparison.save(comparison_path)
                comparison_elapsed = time.time() - start

                # 记录结果
                sample_result = SampleResult(
                    name=str(rel_path),
                    status="success",
                    timings={
                        "sender": sender_elapsed,
                        "vlm": vlm_elapsed,
                        "receiver": receiver_elapsed,
                        "comparison": comparison_elapsed,
                    },
                    metrics=sample_metrics,
                )
                batch_result.add_sample(sample_result)

                # 保存元数据
                metadata = sample_result.to_dict()
                metadata_path = sample_output_dir / "metadata.json"
                with open(metadata_path, "w", encoding="utf-8") as f:
                    json.dump(metadata, f, indent=2, ensure_ascii=False)

                # 追加到展示结果
                results.append(
                    {
                        "name": str(rel_path),
                        "original_path": str(image_path),
                        "edge_path": str(edge_path),
                        "restored_path": str(restored_path),
                        "prompt": prompt_text,
                        "metrics": sample_metrics,
                    }
                )
                current_log += "  ✓ 所有步骤完成\n"
                yield current_log, results, overall_rows

            except Exception as e:
                error_msg = str(e)
                current_log += f"  ✗ 处理失败: {error_msg}\n"
                sample_result = SampleResult(
                    name=str(rel_path),
                    status="failed",
                    error=error_msg,
                )
                batch_result.add_sample(sample_result)

                if not skip_errors:
                    yield current_log, results, overall_rows
                    break

                yield current_log, results, overall_rows
                continue

        # 汇总
        if vlm_sender is not None:
            vlm_sender.unload()

        total_time = time.time() - total_start
        batch_result.total_time = total_time

        # 保存汇总
        summary_path = output_path / "batch_summary.json"
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(batch_result.to_dict(), f, indent=2, ensure_ascii=False)

        # 计算总体评估汇总
        if run_eval:
            overall_rows = aggregate_metrics(batch_result.samples)

        # 生成汇总文本
        summary_text = (
            f"=== 批量处理完成 ===\n"
            f"总计图片: {batch_result.total}\n"
            f"处理成功: {batch_result.success}\n"
            f"处理失败: {batch_result.failed}\n"
            f"成功率: {batch_result.success / batch_result.total * 100:.1f}%\n"
            f"总耗时: {batch_result.total_time:.1f}s\n"
            f"单张平均: {batch_result.total_time / batch_result.total:.1f}s\n"
            f"\n汇总保存: {summary_path}\n"
            f"输出目录: {output_path}/"
        )

        final_log = log_text + "\n" + summary_text
        yield final_log, results, overall_rows
        return

    with gr.Column():
        gr.Markdown(
            "### 批量端到端\n一次性处理目录下所有图片的完整流程（边缘提取 → 语义描述 → 还原），逐组展示结果。"
        )

        input_dir = gr.Textbox(
            label="输入图片目录",
            placeholder="/path/to/input/images",
            info="包含多张图片的文件夹路径",
        )
        output_dir = gr.Textbox(
            label="输出目录",
            placeholder="/path/to/output",
            info="批量处理结果保存目录，每张图片一个子目录",
        )

        with gr.Row():
            prompt_mode = gr.Radio(
                choices=[
                    ("VLM 自动生成描述（每张独立）", "auto"),
                    ("手动指定统一描述", "manual"),
                ],
                value="auto",
                label="Prompt 模式",
            )

        manual_prompt = gr.Textbox(
            label="手动描述",
            placeholder="所有图片使用这个描述文本",
            visible=False,
        )

        with gr.Row():
            recursive = gr.Checkbox(
                label="递归扫描子目录",
                value=False,
                info="是否递归扫描子目录中的图片",
            )
            skip_errors = gr.Checkbox(
                label="跳过错误继续处理",
                value=False,
                info="单张失败时继续处理下一张",
            )
            run_eval_checkbox = gr.Checkbox(
                label="运行质量评估（会额外耗时）",
                value=False,
                info="勾选后每组计算 PSNR/SSIM/LPIPS 并输出总体平均",
            )

        seed = gr.Number(
            label="随机种子（可选）",
            value=None,
            precision=0,
            info="留空使用随机种子",
        )

        run_btn = gr.Button("开始批量处理", variant="primary")

        output_log = gr.Textbox(
            label="处理日志",
            lines=12,
            interactive=False,
        )

        # --- 结果展示区（@gr.render 动态 Accordion） ---
        gr.Markdown("#### 每组结果")
        results_state = gr.State(value=[])

        @gr.render(inputs=results_state)
        def render_sample_accordions(results):
            if not results:
                gr.Markdown("*暂无结果，运行批量处理后会逐组展示。*")
                return
            for i, item in enumerate(results, 1):
                title = f"[{i}] {item['name']}"
                metrics = item.get("metrics") or {}
                if metrics:
                    metric_bits = [f"PSNR={metrics.get('psnr', 0):.2f}"]
                    metric_bits.append(f"SSIM={metrics.get('ssim', 0):.4f}")
                    if "lpips" in metrics:
                        metric_bits.append(f"LPIPS={metrics['lpips']:.4f}")
                    title += "  (" + ", ".join(metric_bits) + ")"
                with gr.Accordion(title, open=False):
                    with gr.Row():
                        gr.Image(
                            value=item["original_path"],
                            label="原图",
                            interactive=False,
                            type="filepath",
                        )
                        gr.Image(
                            value=item["edge_path"],
                            label="边缘图",
                            interactive=False,
                            type="filepath",
                        )
                        gr.Image(
                            value=item["restored_path"],
                            label="还原图",
                            interactive=False,
                            type="filepath",
                        )
                    gr.Textbox(
                        value=item.get("prompt", ""),
                        label="Prompt",
                        lines=2,
                        interactive=False,
                    )
                    if metrics:
                        metric_rows = []
                        for key in ("psnr", "ssim", "lpips"):
                            if key in metrics:
                                fmt = (
                                    f"{metrics[key]:.2f} dB"
                                    if key == "psnr"
                                    else f"{metrics[key]:.4f}"
                                )
                                metric_rows.append([key.upper(), fmt])
                        gr.Dataframe(
                            value=metric_rows,
                            headers=["指标", "值"],
                            interactive=False,
                        )

        gr.Markdown("#### 总体评估")
        overall_metrics_df = gr.Dataframe(
            headers=["指标", "平均值", "样本数"],
            value=[],
            interactive=False,
        )

        # 显示/隐藏手动 prompt 输入框
        def on_prompt_mode_change(mode):
            return gr.update(visible=mode == "manual")

        prompt_mode.change(
            on_prompt_mode_change, inputs=[prompt_mode], outputs=[manual_prompt]
        )

        # 运行处理
        run_btn.click(
            run_batch_process,
            inputs=[
                input_dir,
                output_dir,
                prompt_mode,
                manual_prompt,
                recursive,
                skip_errors,
                seed,
                run_eval_checkbox,
                config_components["vlm_model_name"],
                config_components["vlm_model_path"],
            ],
            outputs=[output_log, results_state, overall_metrics_df],
        )

    return {
        "input_dir": input_dir,
        "output_dir": output_dir,
        "prompt_mode": prompt_mode,
        "manual_prompt": manual_prompt,
        "run_btn": run_btn,
        "output_log": output_log,
        "run_eval_checkbox": run_eval_checkbox,
        "results_state": results_state,
        "overall_metrics_df": overall_metrics_df,
    }
