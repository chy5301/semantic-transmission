"""批量处理 Tab 面板。"""

import json
import time
from pathlib import Path
from typing import Iterator

import gradio as gr
from PIL import Image

from semantic_transmission.common.comfyui_client import ComfyUIClient
from semantic_transmission.common.config import ComfyUIConfig
from semantic_transmission.pipeline.batch_processor import (
    BatchImageDiscoverer,
    BatchResult,
    SampleResult,
    make_sample_output_dir,
)
from semantic_transmission.receiver.comfyui_receiver import ComfyUIReceiver
from semantic_transmission.sender.comfyui_sender import ComfyUISender

# Prompt 模式常量
MODE_MANUAL = "手动指定统一描述"
MODE_AUTO = "VLM 自动生成描述（每张独立）"


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
    """构建批量处理 Tab。"""

    def run_batch_process(
        input_dir: str,
        output_dir: str,
        prompt_mode: str,
        manual_prompt: str,
        recursive: bool,
        skip_errors: bool,
        seed: int | None,
        vlm_model_name: str,
        vlm_model_path: str,
    ) -> Iterator[tuple[str, str | None]]:
        """运行批量处理。"""
        if not input_dir or not output_dir:
            yield "请填写输入目录和输出目录", None
            return

        input_path = Path(input_dir)
        output_path = Path(output_dir)

        if prompt_mode == "manual" and not manual_prompt:
            yield "请输入手动 prompt 或选择自动模式", None
            return

        # 获取配置
        comfyui_host = config_components["sender_host"].value
        comfyui_port = int(config_components["sender_port"].value)

        yield f"开始扫描目录: {input_path}\n", None
        time.sleep(0.1)

        # 扫描目录
        discoverer = BatchImageDiscoverer()
        discovery = discoverer.discover(input_path, recursive=recursive)

        if not discovery:
            yield f"在 {input_path} 中没有找到支持的图片文件", None
            return

        log_text = f"发现图片: {discovery.total_count} 张\n"
        for ext, count in discovery.formats_detected.items():
            log_text += f"  {ext}: {count} 张\n"
        yield log_text, None
        time.sleep(0.1)

        # 创建输出目录
        output_path.mkdir(parents=True, exist_ok=True)

        # 检查连接
        yield log_text + f"\n检查 ComfyUI 连接 ({comfyui_host}:{comfyui_port})...\n", None
        time.sleep(0.1)

        try:
            config = ComfyUIConfig(host=comfyui_host, port=comfyui_port)
            client = ComfyUIClient(config)
            client.check_health()
            yield log_text + "✓ ComfyUI 连接正常\n", None
        except Exception as e:
            yield log_text + f"✗ ComfyUI 连接失败: {e}\n", None
            return

        # 初始化发送端和接收端
        sender = ComfyUISender(client)
        receiver = ComfyUIReceiver(client)

        # 加载 VLM 如果需要
        vlm_sender = None
        if prompt_mode == "auto":
            from semantic_transmission.common.config import get_default_vlm_path
            from semantic_transmission.sender.qwen_vl_sender import QwenVLSender

            yield log_text + "\n正在加载 VLM 模型...\n", None
            time.sleep(0.1)
            vlm_kwargs = {}
            if vlm_model_name:
                vlm_kwargs["model_name"] = vlm_model_name
            vlm_path = vlm_model_path or get_default_vlm_path() or ""
            if vlm_path:
                vlm_kwargs["model_path"] = vlm_path
            vlm_sender = QwenVLSender(**vlm_kwargs)
            yield log_text + "✓ VLM 模型加载完成\n", None

        # 开始批量处理
        total_start = time.time()
        batch_result = BatchResult(total=discovery.total_count)
        processed = 0

        for idx, image_path in enumerate(discovery.images, 1):
            image_name = image_path.stem
            rel_path = image_path.relative_to(input_path)

            current_log = log_text
            current_log += f"\n[{idx}/{discovery.total_count}] 处理: {rel_path}\n"
            yield current_log, None
            time.sleep(0.1)

            # 创建输出子目录
            sample_output_dir = make_sample_output_dir(output_path, idx, image_name)

            try:
                # 提取边缘图
                start = time.time()
                edge_image = sender.process(image_path)
                sender_elapsed = time.time() - start

                edge_path = sample_output_dir / "edge.png"
                edge_image.save(edge_path)
                current_log += f"  ✓ 边缘提取完成 ({edge_image.size[0]}x{edge_image.size[1]}) 耗时 {sender_elapsed:.1f}s\n"
                yield current_log, None
                time.sleep(0.05)

                # 获取 prompt
                vlm_elapsed = 0.0
                if prompt_mode == "auto" and vlm_sender is not None:
                    import numpy as np

                    original_img = Image.open(image_path).convert("RGB")
                    image_array = np.array(original_img)
                    start_vlm = time.time()
                    sender_output = vlm_sender.describe(image_array)
                    vlm_elapsed = time.time() - start_vlm
                    prompt_text = sender_output.text
                    current_log += f"  ✓ VLM 生成完成 ({len(prompt_text)} 字符) 耗时 {vlm_elapsed:.1f}s\n"
                    yield current_log, None
                    time.sleep(0.05)
                else:
                    prompt_text = manual_prompt
                    current_log += "  ✓ 使用手动 prompt\n"
                    yield current_log, None
                    time.sleep(0.05)

                # 保存 prompt
                prompt_path = sample_output_dir / "prompt.txt"
                prompt_path.write_text(prompt_text, encoding="utf-8")

                # 还原图像
                start = time.time()
                restored_image = receiver.process(edge_path, prompt_text, seed=seed)
                receiver_elapsed = time.time() - start

                restored_path = sample_output_dir / "restored.png"
                restored_image.save(restored_path)
                current_log += f"  ✓ 还原完成 ({restored_image.size[0]}x{restored_image.size[1]}) 耗时 {receiver_elapsed:.1f}s\n"
                yield current_log, None
                time.sleep(0.05)

                # 生成对比图
                start = time.time()
                original_image = Image.open(image_path)
                comparison = _make_comparison_image(original_image, edge_image, restored_image)
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
                )
                batch_result.add_sample(sample_result)
                processed += 1

                # 保存元数据
                metadata = sample_result.to_dict()
                metadata_path = sample_output_dir / "metadata.json"
                with open(metadata_path, "w", encoding="utf-8") as f:
                    json.dump(metadata, f, indent=2, ensure_ascii=False)

                current_log += "  ✓ 所有步骤完成\n"
                yield current_log, str(comparison_path)
                time.sleep(0.1)

            except Exception as e:
                error_msg = str(e)
                current_log += f"  ✗ 处理失败: {error_msg}\n"
                sample_result = SampleResult(
                    name=str(rel_path),
                    status="failed",
                    error=error_msg,
                )
                batch_result.add_sample(sample_result)
                processed += 1

                if not skip_errors:
                    yield current_log, None
                    break

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
        yield final_log, None
        return

    with gr.Column():
        gr.Markdown("### 批量端到端处理\n一次性处理目录中所有图片，自动生成对比图。")

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
                    ("手动指定统一描述", "manual"),
                    ("VLM 自动生成描述（每张独立）", "auto"),
                ],
                value="manual",
                label="Prompt 模式",
            )

        manual_prompt = gr.Textbox(
            label="手动描述",
            placeholder="所有图片使用这个描述文本",
            visible=True,
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

        seed = gr.Number(
            label="随机种子（可选）",
            value=None,
            precision=0,
            info="留空使用随机种子",
        )

        run_btn = gr.Button("开始批量处理", variant="primary")

        output_log = gr.Textbox(
            label="处理日志",
            lines=20,
            interactive=False,
        )

        last_comparison = gr.Image(
            label="最后一张对比图",
            type="filepath",
            interactive=False,
        )

        # 显示/隐藏手动 prompt 输入框
        def on_prompt_mode_change(mode):
            return gr.update(visible=mode == "manual")

        prompt_mode.change(on_prompt_mode_change, inputs=[prompt_mode], outputs=[manual_prompt])

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
                config_components["vlm_model_name"],
                config_components["vlm_model_path"],
            ],
            outputs=[output_log, last_comparison],
        )

    return {
        "input_dir": input_dir,
        "output_dir": output_dir,
        "prompt_mode": prompt_mode,
        "manual_prompt": manual_prompt,
        "run_btn": run_btn,
        "output_log": output_log,
        "last_comparison": last_comparison,
    }
