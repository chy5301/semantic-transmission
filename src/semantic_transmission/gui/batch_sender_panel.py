"""批量发送 Tab 面板：双机演示发送端，批量处理目录中所有图片并发送到接收端。

发送端使用本地 OpenCV 提取 Canny 边缘；中继对端地址在本 Tab 内配置。
"""

import json
import socket
import time
from pathlib import Path
from typing import Iterator

import gradio as gr
import numpy as np
from PIL import Image

from semantic_transmission.pipeline.batch_processor import (
    BatchImageDiscoverer,
    BatchResult,
    SampleResult,
    make_sample_output_dir,
)
from semantic_transmission.pipeline.relay import SocketRelaySender, TransmissionPacket
from semantic_transmission.sender.local_condition_extractor import LocalCannyExtractor
from semantic_transmission.sender.qwen_vl_sender import QwenVLSender


def _test_relay_connection(host: str, port: float | int) -> str:
    """测试到对端接收端的 TCP 可达性，返回带颜色的 Markdown 状态文本。

    使用 stdlib socket 做纯 TCP 握手测试，与 cli/check.py 的 `check relay`
    实现保持一致。失败时给出具体错误（ConnectionRefusedError / TimeoutError 等）。
    """
    if not host:
        return '<span style="color:#DC2626">● 请输入接收端 IP 地址</span>'
    try:
        port_int = int(port)
    except (TypeError, ValueError):
        return '<span style="color:#DC2626">● 端口必须是整数</span>'

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(3.0)
    try:
        start = time.time()
        sock.connect((host, port_int))
        elapsed_ms = (time.time() - start) * 1000
        return (
            f'<span style="color:#16A34A">● 可达 ({host}:{port_int}, '
            f"延迟 {elapsed_ms:.0f}ms)</span>"
        )
    except OSError as e:
        return f'<span style="color:#DC2626">● 连接失败: {e}</span>'
    finally:
        sock.close()


def build_batch_sender_tab(config_components):
    """构建批量发送 Tab（双机发送端）。"""

    def run_batch_sender(
        input_dir: str,
        output_dir: str,
        prompt_mode: str,
        manual_prompt: str,
        threshold1: int,
        threshold2: int,
        recursive: bool,
        skip_errors: bool,
        seed: int | None,
        vlm_model_name: str,
        vlm_model_path: str,
        relay_host: str,
        relay_port: int,
    ) -> Iterator[str]:
        """运行批量发送。"""
        if not input_dir or not output_dir:
            yield "请填写输入目录和输出目录"
            return

        input_path = Path(input_dir)
        output_path = Path(output_dir)

        if prompt_mode == "manual" and not manual_prompt:
            yield "请输入手动 prompt 或选择自动模式"
            return

        yield f"开始扫描目录: {input_path}\n"
        time.sleep(0.1)

        # 扫描目录
        discoverer = BatchImageDiscoverer()
        discovery = discoverer.discover(input_path, recursive=recursive)

        if not discovery:
            yield f"在 {input_path} 中没有找到支持的图片文件\n支持格式: {', '.join(discoverer.supported_exts)}"
            return

        log_text = f"发现图片: {discovery.total_count} 张\n"
        for ext, count in discovery.formats_detected.items():
            log_text += f"  {ext}: {count} 张\n"
        yield log_text
        time.sleep(0.1)

        # 创建输出目录
        output_path.mkdir(parents=True, exist_ok=True)

        # 初始化本地边缘提取器
        extractor = LocalCannyExtractor(threshold1=threshold1, threshold2=threshold2)
        log_text += f"\nCanny 阈值: {threshold1}, {threshold2}\n"
        yield log_text
        time.sleep(0.1)

        # 加载 VLM 如果需要
        vlm_sender = None
        if prompt_mode == "auto":
            from semantic_transmission.common.config import get_default_vlm_path

            yield log_text + "\n正在加载 VLM 模型...\n"
            time.sleep(0.1)
            vlm_kwargs = {}
            if vlm_model_name:
                vlm_kwargs["model_name"] = vlm_model_name
            vlm_path = vlm_model_path or get_default_vlm_path() or ""
            if vlm_path:
                vlm_kwargs["model_path"] = vlm_path
            vlm_sender = QwenVLSender(**vlm_kwargs)
            log_text += "[OK] VLM 模型加载完成\n"
            yield log_text
            time.sleep(0.1)

        # 预处理所有图片：提取边缘并保存到输出目录
        total_start = time.time()
        batch_result = BatchResult(total=discovery.total_count)
        processed_data = []

        for idx, image_path in enumerate(discovery.images, 1):
            image_name = image_path.stem
            rel_path = image_path.relative_to(input_path)

            current_log = log_text
            current_log += f"\n[{idx}/{discovery.total_count}] 处理: {rel_path}\n"
            yield current_log
            time.sleep(0.1)

            # 创建输出子目录
            sample_output_dir = make_sample_output_dir(output_path, idx, image_name)

            try:
                # 读取图像
                original_img = Image.open(image_path).convert("RGB")
                image_array = np.array(original_img)

                # 本地提取 Canny 边缘图
                start = time.time()
                edge_np = extractor.extract(image_array)
                edge_image = Image.fromarray(edge_np)
                sender_elapsed = time.time() - start

                edge_path = sample_output_dir / "edge.png"
                edge_image.save(edge_path)
                current_log += f"  [OK] 边缘提取完成 ({edge_image.size[0]}x{edge_image.size[1]}) 耗时 {sender_elapsed:.3f}s\n"
                yield current_log
                time.sleep(0.05)

                # 获取 prompt
                vlm_elapsed = 0.0
                if prompt_mode == "auto" and vlm_sender is not None:
                    start_vlm = time.time()
                    sender_output = vlm_sender.describe(image_array)
                    vlm_elapsed = time.time() - start_vlm
                    prompt_text = sender_output.text
                    current_log += f"  [OK] VLM 生成完成 ({len(prompt_text)} 字符) 耗时 {vlm_elapsed:.1f}s\n"
                    yield current_log
                    time.sleep(0.05)
                else:
                    prompt_text = manual_prompt
                    current_log += "  [OK] 使用手动 prompt\n"
                    yield current_log
                    time.sleep(0.05)

                # 保存 prompt
                prompt_path = sample_output_dir / "prompt.txt"
                prompt_path.write_text(prompt_text, encoding="utf-8")

                # 预处理数据包
                import io

                buf = io.BytesIO()
                edge_image.save(buf, format="PNG")
                edge_bytes = buf.getvalue()
                metadata = {
                    "timestamp": time.time(),
                    "image_size": list(edge_image.size),
                }
                if seed is not None:
                    metadata["seed"] = seed
                if image_name:
                    metadata["image_name"] = image_name

                packet = TransmissionPacket(
                    edge_image=edge_bytes, prompt_text=prompt_text, metadata=metadata
                )

                processed_data.append(
                    {
                        "packet": packet,
                        "sample_output_dir": sample_output_dir,
                        "edge_path": edge_path,
                        "prompt_text": prompt_text,
                        "sender_elapsed": sender_elapsed,
                        "vlm_elapsed": vlm_elapsed,
                        "rel_path": rel_path,
                        "original_bytes": image_path.stat().st_size,
                        "edge_bytes": edge_bytes,
                    }
                )

                # 记录结果
                sample_result = SampleResult(
                    name=str(rel_path),
                    status="success",
                    timings={
                        "sender": sender_elapsed,
                        "vlm": vlm_elapsed,
                    },
                )
                batch_result.add_sample(sample_result)

                # 保存元数据
                metadata_dict = sample_result.to_dict()
                metadata_dict["packet_bytes"] = len(edge_bytes) + len(
                    prompt_text.encode("utf-8")
                )
                metadata_path = sample_output_dir / "metadata.json"
                with open(metadata_path, "w", encoding="utf-8") as f:
                    json.dump(metadata_dict, f, indent=2, ensure_ascii=False)

                # 打印压缩信息
                original_bytes = image_path.stat().st_size
                prompt_bytes = len(prompt_text.encode("utf-8"))
                total_bytes = len(edge_bytes) + prompt_bytes
                if original_bytes > 0:
                    ratio = original_bytes / total_bytes
                    current_log += f"    压缩比: {ratio:.2f}x  ({original_bytes:,} → {total_bytes:,} bytes)\n"
                yield current_log
                time.sleep(0.05)

            except Exception as e:
                error_msg = str(e)
                current_log += f"  [ERR] 处理失败: {error_msg}\n"
                sample_result = SampleResult(
                    name=str(rel_path),
                    status="failed",
                    error=error_msg,
                )
                batch_result.add_sample(sample_result)

                if not skip_errors:
                    yield current_log
                    break

                continue

        # 连接接收端并发送
        if processed_data:
            log_text = current_log
            log_text += f"\n连接接收端 {relay_host}:{relay_port} 并发送...\n"
            yield log_text
            time.sleep(0.1)

            try:
                relay = SocketRelaySender(relay_host, int(relay_port))
                relay.connect()
                log_text += f"  [OK] 已连接到 {relay_host}:{relay_port}\n"
                yield log_text
                time.sleep(0.1)

                # 逐个发送
                for idx, data in enumerate(processed_data, 1):
                    start = time.time()
                    relay.send(data["packet"])
                    relay_elapsed = time.time() - start
                    log_text += f"  [OK] 已发送 [{idx}/{len(processed_data)}] {data['rel_path']} 耗时 {relay_elapsed:.1f}s\n"
                    yield log_text
                    time.sleep(0.05)

                relay.close()
            except Exception as e:
                log_text += f"  [WARN] 连接或发送失败: {e}\n"
                log_text += (
                    "  但是所有边缘图和 prompt 已经保存到输出目录，可以手动检查!\n"
                )
                yield log_text

        # 收尾
        if vlm_sender is not None:
            vlm_sender.unload()
            log_text += "\n  VLM 模型已卸载，释放 GPU 显存\n"
            yield log_text
            time.sleep(0.1)

        # 汇总
        total_time = time.time() - total_start
        batch_result.total_time = total_time

        # 保存汇总
        summary_path = output_path / "batch_summary.json"
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(batch_result.to_dict(), f, indent=2, ensure_ascii=False)

        # 生成汇总文本
        summary_text = (
            f"=== 批量发送完成 ===\n"
            f"总计图片: {batch_result.total}\n"
            f"处理成功: {batch_result.success}\n"
            f"处理失败: {batch_result.failed}\n"
            f"成功率: {batch_result.success / batch_result.total * 100:.1f}%\n"
            f"总耗时: {batch_result.total_time:.1f}s\n"
            f"单张平均: {batch_result.total_time / batch_result.total:.1f}s\n"
            f"\n汇总保存: {summary_path}\n"
            f"输出目录: {output_path}/\n"
            f"\n所有边缘图和 prompt 已保存到输出目录，即使发送失败也可以查看!"
        )

        final_log = log_text + "\n" + summary_text
        yield final_log
        return

    with gr.Column():
        gr.Markdown(
            "### 批量发送\n批量提取目录下所有图片的边缘图与语义描述，发送到对端接收端。"
        )

        input_dir = gr.Textbox(
            label="输入图片目录",
            placeholder="/path/to/input/images",
            info="包含多张图片的文件夹路径",
        )
        output_dir = gr.Textbox(
            label="输出目录",
            placeholder="/path/to/output",
            info="处理结果保存目录，每张图片一个子目录",
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
            lines=2,
        )

        with gr.Row():
            threshold1 = gr.Number(
                label="Canny 低阈值",
                value=100,
                precision=0,
            )
            threshold2 = gr.Number(
                label="Canny 高阈值",
                value=200,
                precision=0,
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

        with gr.Row():
            seed = gr.Number(
                label="随机种子（可选）",
                value=None,
                precision=0,
                info="留空使用随机种子，传递给接收端",
            )

        # --- 中继对端配置（M-12：从全局 config_panel 挪到本 Tab 内部） ---
        gr.Markdown("### 接收端对端")
        with gr.Row():
            relay_host = gr.Textbox(
                value="",
                label="接收端 IP 地址",
                placeholder="如 192.168.1.100 或 127.0.0.1",
                info="对端接收端的 IP 地址（非本机监听地址）",
            )
            relay_port = gr.Number(
                value=9000,
                label="接收端端口",
                precision=0,
                info="对端接收端监听的 TCP 端口",
            )
        with gr.Row():
            test_relay_btn = gr.Button("测试对端连接", variant="secondary", size="sm")
            relay_status = gr.Markdown(
                '<span style="color:#94A3B8">● 未检测</span>',
                elem_classes=["status-text"],
            )

        run_btn = gr.Button("开始批量发送", variant="primary")

        output_log = gr.Textbox(
            label="处理日志",
            lines=25,
            interactive=False,
        )

        # 显示/隐藏手动 prompt 输入框
        def on_prompt_mode_change(mode):
            return gr.update(visible=mode == "manual")

        prompt_mode.change(
            on_prompt_mode_change, inputs=[prompt_mode], outputs=[manual_prompt]
        )

        # 测试对端连接
        test_relay_btn.click(
            fn=_test_relay_connection,
            inputs=[relay_host, relay_port],
            outputs=relay_status,
        )

        # 运行处理
        run_btn.click(
            run_batch_sender,
            inputs=[
                input_dir,
                output_dir,
                prompt_mode,
                manual_prompt,
                threshold1,
                threshold2,
                recursive,
                skip_errors,
                seed,
                config_components["vlm_model_name"],
                config_components["vlm_model_path"],
                relay_host,
                relay_port,
            ],
            outputs=[output_log],
        )

    return {
        "input_dir": input_dir,
        "output_dir": output_dir,
        "prompt_mode": prompt_mode,
        "manual_prompt": manual_prompt,
        "run_btn": run_btn,
        "output_log": output_log,
    }
