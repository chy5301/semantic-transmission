"""semantic-tx sender 子命令：发送端（单图 + 批量统一入口）。

合并自旧 ``sender`` + ``batch-sender`` 子命令（R-08）。通过互斥选项
``--image`` / ``--input-dir`` 区分两条路径：

- ``--image``：单图模式，扁平输出 + fail-fast；
- ``--input-dir``：批量模式，``NN-name/`` 子目录 + ``batch_summary.json``，
  continue-on-error 由 ``--skip-errors`` 控制。

两条路径共享 ``process_one()`` 核心函数，仅在输出适配器与错误策略层分叉。
共享参数（Canny 阈值、VLM 选项等）默认值从 ``ProjectConfig`` 读取，CLI options
作为运行时 override。
"""

from __future__ import annotations

import builtins
import functools
import io
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import click
import numpy as np
from PIL import Image

from semantic_transmission.common.config import ProjectConfig, load_config
from semantic_transmission.common.model_loader import QwenVLModelLoader
from semantic_transmission.pipeline.batch_processor import (
    SUPPORTED_IMAGE_EXTS,
    BatchImageDiscoverer,
    BatchResult,
    SampleResult,
    make_sample_output_dir,
)
from semantic_transmission.pipeline.relay import SocketRelaySender, TransmissionPacket
from semantic_transmission.sender.local_condition_extractor import LocalCannyExtractor
from semantic_transmission.sender.qwen_vl_sender import QwenVLSender

_print = functools.partial(builtins.print, flush=True)


# ---------------------------------------------------------------------------
# 核心数据结构与共享处理函数
# ---------------------------------------------------------------------------


@dataclass
class SenderResult:
    """单张图片的发送端处理产物（不含输出文件，由外层适配器负责落盘）。"""

    image_name: str
    edge_image: Image.Image
    edge_bytes: bytes
    prompt_text: str
    packet: TransmissionPacket
    sender_elapsed: float
    vlm_elapsed: float
    original_bytes: int


def _build_vlm_sender(
    project_config: ProjectConfig,
    vlm_model: str | None,
    vlm_model_path: str | None,
) -> QwenVLSender:
    """构造 QwenVLSender，CLI override 优先于 ProjectConfig 默认。"""
    loader_config = project_config.to_vlm_loader_config()
    # CLI override
    overrides: dict[str, object] = {}
    if vlm_model:
        overrides["model_name"] = vlm_model
    if vlm_model_path is not None:
        overrides["model_path"] = vlm_model_path
    if overrides:
        from dataclasses import replace

        loader_config = replace(loader_config, **overrides)
    return QwenVLSender(loader=QwenVLModelLoader(loader_config))


def process_one(
    image_path: Path,
    extractor: LocalCannyExtractor,
    vlm_sender: QwenVLSender | None,
    prompt: str | None,
    seed: int | None,
) -> SenderResult:
    """核心处理：读图 → Canny → 取 prompt（手动或 VLM）→ 打包 TransmissionPacket。

    Args:
        image_path: 输入图片路径
        extractor: 已构造的 Canny 提取器
        vlm_sender: 已构造的 VLM 实例（auto-prompt 模式必传，否则可为 None）
        prompt: 手动 prompt（与 vlm_sender 二选一）
        seed: 透传到 metadata 的种子，可选

    Returns:
        SenderResult: 包含边缘图、prompt、打包好的 TransmissionPacket 与耗时
    """
    image_name = image_path.stem
    original_img = Image.open(image_path).convert("RGB")
    image_array = np.array(original_img)

    # Canny 边缘
    start = time.time()
    edge_np = extractor.extract(image_array)
    edge_image = Image.fromarray(edge_np)
    sender_elapsed = time.time() - start

    # Prompt
    vlm_elapsed = 0.0
    if vlm_sender is not None:
        start_vlm = time.time()
        sender_output = vlm_sender.describe(image_array)
        vlm_elapsed = time.time() - start_vlm
        prompt_text = sender_output.text
    else:
        prompt_text = prompt if prompt is not None else ""

    # 打包
    buf = io.BytesIO()
    edge_image.save(buf, format="PNG")
    edge_bytes = buf.getvalue()
    metadata: dict[str, object] = {
        "timestamp": time.time(),
        "image_size": list(edge_image.size),
    }
    if seed is not None:
        metadata["seed"] = seed
    if image_name:
        metadata["image_name"] = image_name

    packet = TransmissionPacket(
        edge_image=edge_bytes,
        prompt_text=prompt_text,
        metadata=metadata,
    )

    return SenderResult(
        image_name=image_name,
        edge_image=edge_image,
        edge_bytes=edge_bytes,
        prompt_text=prompt_text,
        packet=packet,
        sender_elapsed=sender_elapsed,
        vlm_elapsed=vlm_elapsed,
        original_bytes=image_path.stat().st_size,
    )


# ---------------------------------------------------------------------------
# CLI 入口
# ---------------------------------------------------------------------------


@click.command()
@click.option(
    "--image",
    default=None,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="输入单张图像路径（与 --input-dir 互斥）",
)
@click.option(
    "--input-dir",
    default=None,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="输入图像目录，批量模式（与 --image 互斥）",
)
@click.option(
    "--output-dir",
    default=None,
    type=click.Path(path_type=Path),
    help="输出目录（单图默认 output/sender，批量必填）",
)
@click.option("--prompt", default=None, type=str, help="手动指定描述文本")
@click.option(
    "--auto-prompt",
    is_flag=True,
    default=False,
    help="使用 VLM (Qwen2.5-VL) 自动生成描述",
)
@click.option(
    "--threshold1",
    default=None,
    type=int,
    help="Canny 低阈值（默认读 config.toml [sender].canny_low_threshold）",
)
@click.option(
    "--threshold2",
    default=None,
    type=int,
    help="Canny 高阈值（默认读 config.toml [sender].canny_high_threshold）",
)
@click.option(
    "--vlm-model",
    default=None,
    type=str,
    help="VLM 模型名称（默认读 config.toml [models.vlm].model_name）",
)
@click.option(
    "--vlm-model-path",
    default=None,
    type=str,
    help="VLM 模型本地路径（默认读 config.toml [models.vlm].model_path）",
)
@click.option(
    "--recursive",
    is_flag=True,
    default=False,
    help="批量模式：递归扫描子目录中的图片（单图模式忽略）",
)
@click.option(
    "--skip-errors",
    is_flag=True,
    default=False,
    help="批量模式：跳过失败的图片继续处理（单图模式忽略）",
)
@click.option("--relay-host", required=True, help="接收端机器 IP 地址")
@click.option(
    "--relay-port",
    default=9000,
    type=int,
    help="接收端监听端口（默认 9000）",
)
@click.option(
    "--seed",
    default=None,
    type=int,
    help="KSampler 随机种子（可选，传递给接收端）",
)
def sender(
    image: Path | None,
    input_dir: Path | None,
    output_dir: Path | None,
    prompt: str | None,
    auto_prompt: bool,
    threshold1: int | None,
    threshold2: int | None,
    vlm_model: str | None,
    vlm_model_path: str | None,
    recursive: bool,
    skip_errors: bool,
    relay_host: str,
    relay_port: int,
    seed: int | None,
) -> None:
    """发送端：提取边缘图 + 语义描述 → 发送到接收端。

    使用本地 OpenCV 提取 Canny 边缘 + Qwen2.5-VL 生成语义描述，通过 TCP 中继发送。
    即使接收端连接失败，结果也会保存到输出目录。

    \b
    模式选择（必须二选一）：
      --image <file>      单图模式，扁平输出（<name>_edge.png + <name>_prompt.txt）
      --input-dir <dir>   批量模式，子目录输出（NN-name/edge.png + prompt.txt）+ batch_summary.json
    """
    # 互斥校验
    if image is None and input_dir is None:
        raise click.UsageError("必须指定 --image 或 --input-dir 之一")
    if image is not None and input_dir is not None:
        raise click.UsageError("--image 和 --input-dir 不能同时使用")

    if not prompt and not auto_prompt:
        raise click.UsageError("必须指定 --prompt 或 --auto-prompt 之一")
    if prompt and auto_prompt:
        raise click.UsageError("--prompt 和 --auto-prompt 不能同时使用")

    # 解析共享参数默认值（CLI override > ProjectConfig）
    project_config = load_config()
    if threshold1 is None:
        threshold1 = project_config.canny_low_threshold
    if threshold2 is None:
        threshold2 = project_config.canny_high_threshold

    if input_dir is not None and output_dir is None:
        raise click.UsageError("批量模式必须指定 --output-dir")

    if image is not None:
        if output_dir is None:
            output_dir = Path("output/sender")
        _run_single(
            image=image,
            output_dir=output_dir,
            prompt=prompt,
            auto_prompt=auto_prompt,
            threshold1=threshold1,
            threshold2=threshold2,
            vlm_model=vlm_model,
            vlm_model_path=vlm_model_path,
            relay_host=relay_host,
            relay_port=relay_port,
            seed=seed,
            project_config=project_config,
        )
    else:
        assert input_dir is not None
        assert output_dir is not None
        _run_batch(
            input_dir=input_dir,
            output_dir=output_dir,
            prompt=prompt,
            auto_prompt=auto_prompt,
            recursive=recursive,
            skip_errors=skip_errors,
            threshold1=threshold1,
            threshold2=threshold2,
            vlm_model=vlm_model,
            vlm_model_path=vlm_model_path,
            relay_host=relay_host,
            relay_port=relay_port,
            seed=seed,
            project_config=project_config,
        )


# ---------------------------------------------------------------------------
# 单图模式：扁平输出，fail-fast
# ---------------------------------------------------------------------------


def _run_single(
    *,
    image: Path,
    output_dir: Path,
    prompt: str | None,
    auto_prompt: bool,
    threshold1: int,
    threshold2: int,
    vlm_model: str | None,
    vlm_model_path: str | None,
    relay_host: str,
    relay_port: int,
    seed: int | None,
    project_config: ProjectConfig,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    _print("=" * 60)
    _print("  语义传输发送端（本地 Canny + Qwen2.5-VL）")
    _print("=" * 60)
    _print(f"  输入图像: {image}")
    _print(f"  Canny 阈值: {threshold1}, {threshold2}")
    _print(f"  输出目录: {output_dir}")
    _print(f"  接收端: {relay_host}:{relay_port}")

    _print("\n[1/4] 读取图像...")
    extractor = LocalCannyExtractor(threshold1=threshold1, threshold2=threshold2)
    vlm_sender: QwenVLSender | None = None
    if auto_prompt:
        _print("\n[2/4] 加载 VLM 模型 (Qwen2.5-VL)...")
        vlm_sender = _build_vlm_sender(project_config, vlm_model, vlm_model_path)

    _print("\n[3/4] 提取边缘图 + 生成 prompt...")
    result = process_one(
        image_path=image,
        extractor=extractor,
        vlm_sender=vlm_sender,
        prompt=prompt,
        seed=seed,
    )
    _print(
        f"  边缘图: {result.edge_image.size[0]}x{result.edge_image.size[1]} "
        f"耗时 {result.sender_elapsed:.3f}s"
    )
    if auto_prompt:
        _print(
            f"  VLM 耗时: {result.vlm_elapsed:.1f}s "
            f"描述长度: {len(result.prompt_text)} 字符"
        )
        _print(f"  描述预览: {result.prompt_text[:200]}...")
    else:
        _print(f"  手动 prompt: {result.prompt_text}")

    # 扁平输出
    edge_path = output_dir / f"{result.image_name}_edge.png"
    prompt_path = output_dir / f"{result.image_name}_prompt.txt"
    result.edge_image.save(edge_path)
    prompt_path.write_text(result.prompt_text, encoding="utf-8")
    _print("\n  [OK] 结果已保存到本地:")
    _print(f"    边缘图: {edge_path}")
    _print(f"    Prompt: {prompt_path}")

    if vlm_sender is not None:
        vlm_sender.unload()
        _print("  VLM 模型已卸载")

    # 发送
    _print("\n[4/4] 发送数据到接收端...")
    relay_elapsed = 0.0
    try:
        start = time.time()
        with SocketRelaySender(relay_host, relay_port) as relay:
            relay.send(result.packet)
        relay_elapsed = time.time() - start
        _print(f"  [OK] 已发送到 {relay_host}:{relay_port}")
        _print(f"  传输耗时: {relay_elapsed:.1f}s")
    except Exception as e:
        _print(f"  [WARN] 连接接收端失败: {e}")
        _print(f"  但是结果已经保存到 {output_dir}/ 目录，可以查看！")

    # 统计
    prompt_bytes = len(result.prompt_text.encode("utf-8"))
    total_bytes = len(result.edge_bytes) + prompt_bytes
    total_elapsed = result.sender_elapsed + result.vlm_elapsed + relay_elapsed

    _print("\n" + "=" * 60)
    _print("  发送完成")
    _print("=" * 60)
    _print(f"  原始图像大小:    {result.original_bytes:>10,} bytes")
    _print(f"  边缘图大小:      {len(result.edge_bytes):>10,} bytes")
    _print(f"  Prompt 大小:     {prompt_bytes:>10,} bytes")
    _print(f"  传输数据总量:    {total_bytes:>10,} bytes")
    if total_bytes > 0:
        _print(f"  压缩比:          {result.original_bytes / total_bytes:>10.2f}x")
    _print(f"  发送端耗时:      {result.sender_elapsed:>10.3f}s")
    if auto_prompt:
        _print(f"  VLM 耗时:        {result.vlm_elapsed:>10.1f}s")
    _print(f"  网络传输耗时:    {relay_elapsed:>10.1f}s")
    _print(f"  总耗时:          {total_elapsed:>10.1f}s")
    _print()
    _print("  本地结果文件:")
    _print(f"    {edge_path}")
    _print(f"    {prompt_path}")


# ---------------------------------------------------------------------------
# 批量模式：子目录输出 + batch_summary.json，continue-on-error
# ---------------------------------------------------------------------------


def _run_batch(
    *,
    input_dir: Path,
    output_dir: Path,
    prompt: str | None,
    auto_prompt: bool,
    recursive: bool,
    skip_errors: bool,
    threshold1: int,
    threshold2: int,
    vlm_model: str | None,
    vlm_model_path: str | None,
    relay_host: str,
    relay_port: int,
    seed: int | None,
    project_config: ProjectConfig,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    _print("=" * 60)
    _print("  语义传输批量发送端（本地 Canny + Qwen2.5-VL）")
    _print("=" * 60)
    _print(f"  输入目录: {input_dir}")
    _print(f"  输出目录: {output_dir}")
    _print(f"  接收端: {relay_host}:{relay_port}")
    _print(f"  Canny 阈值: {threshold1}, {threshold2}")
    _print(f"  递归扫描: {'是' if recursive else '否'}")
    _print(f"  跳过错误: {'是' if skip_errors else '否'}")
    _print()

    _print("[1/4] 扫描目录发现图片...")
    discoverer = BatchImageDiscoverer()
    discovery = discoverer.discover(input_dir, recursive=recursive)

    if not discovery:
        _print(f"  错误: 在 {input_dir} 中没有找到支持的图片文件")
        _print(f"  支持格式: {', '.join(SUPPORTED_IMAGE_EXTS)}")
        sys.exit(1)

    _print(f"  发现图片: {discovery.total_count} 张")
    for ext, count in discovery.formats_detected.items():
        _print(f"    {ext}: {count} 张")
    _print()

    extractor = LocalCannyExtractor(threshold1=threshold1, threshold2=threshold2)

    vlm_sender: QwenVLSender | None = None
    if auto_prompt:
        _print("[2/4] 加载 VLM 模型...")
        vlm_sender = _build_vlm_sender(project_config, vlm_model, vlm_model_path)
        _print("  VLM 模型加载完成")

    _print("\n[3/4] 预处理图片：提取边缘 + prompt...")
    _print("-" * 60)

    total_start = time.time()
    batch_result = BatchResult(total=discovery.total_count)
    processed: list[dict] = []

    for idx, image_path in enumerate(discovery.images, 1):
        image_name = image_path.stem
        rel_path = image_path.relative_to(input_dir)
        _print(f"\n>> [{idx}/{discovery.total_count}] 处理: {rel_path}")

        sample_output_dir = make_sample_output_dir(output_dir, idx, image_name)

        try:
            result = process_one(
                image_path=image_path,
                extractor=extractor,
                vlm_sender=vlm_sender,
                prompt=prompt,
                seed=seed,
            )

            edge_path = sample_output_dir / "edge.png"
            result.edge_image.save(edge_path)
            _print(
                f"  [OK] 边缘提取: {edge_path} "
                f"({result.edge_image.size[0]}x{result.edge_image.size[1]}) "
                f"耗时 {result.sender_elapsed:.3f}s"
            )

            if auto_prompt:
                _print(
                    f"  [OK] VLM 生成: {len(result.prompt_text)} 字符 "
                    f"耗时 {result.vlm_elapsed:.1f}s"
                )
                _print(f"    描述: {result.prompt_text[:100]}...")
            else:
                _print(f"  [OK] 使用手动 prompt: {result.prompt_text[:60]}...")

            prompt_path = sample_output_dir / "prompt.txt"
            prompt_path.write_text(result.prompt_text, encoding="utf-8")

            sample_result = SampleResult(
                name=str(rel_path),
                status="success",
                timings={
                    "sender": result.sender_elapsed,
                    "vlm": result.vlm_elapsed,
                },
            )
            batch_result.add_sample(sample_result)

            metadata_dict = sample_result.to_dict()
            metadata_dict["packet_bytes"] = len(result.edge_bytes) + len(
                result.prompt_text.encode("utf-8")
            )
            metadata_path = sample_output_dir / "metadata.json"
            with open(metadata_path, "w", encoding="utf-8") as f:
                json.dump(metadata_dict, f, indent=2, ensure_ascii=False)

            # 压缩比
            prompt_bytes = len(result.prompt_text.encode("utf-8"))
            total_bytes = len(result.edge_bytes) + prompt_bytes
            if result.original_bytes > 0 and total_bytes > 0:
                ratio = result.original_bytes / total_bytes
                _print(
                    f"    压缩比: {ratio:.2f}x  "
                    f"({result.original_bytes:,} → {total_bytes:,} bytes)"
                )

            processed.append(
                {
                    "packet": result.packet,
                    "rel_path": rel_path,
                }
            )

        except Exception as e:
            error_msg = str(e)
            _print(f"  [ERR] 处理失败: {error_msg}")

            sample_result = SampleResult(
                name=str(rel_path),
                status="failed",
                error=error_msg,
            )
            batch_result.add_sample(sample_result)

            if not skip_errors:
                _print("\n  遇到错误且 --skip-errors 未启用，中止处理")
                break

            continue

    # VLM 在 relay finally 后卸载：避免 relay 资源占用期间过早释放 VLM 显存导致重入加载
    _print("\n[4/4] 连接接收端并发送...")
    relay: SocketRelaySender | None = None
    try:
        relay = SocketRelaySender(relay_host, relay_port)
        relay.connect()
        _print(f"  已连接到 {relay_host}:{relay_port}")

        for data in processed:
            start = time.time()
            relay.send(data["packet"])
            relay_elapsed = time.time() - start
            _print(f"  [OK] 已发送 {data['rel_path']} 耗时 {relay_elapsed:.1f}s")
            for sample in batch_result.samples:
                if sample.name == str(data["rel_path"]):
                    sample.timings["relay"] = relay_elapsed
                    break
    except Exception as e:
        _print(f"  [WARN] 连接接收端失败: {e}")
        _print("  但是所有边缘图已经提取保存到输出目录了！")
    finally:
        if relay is not None:
            try:
                relay.close()
            except Exception as e:
                _print(f"  [WARN] relay close 失败: {e}")
        if vlm_sender is not None:
            vlm_sender.unload()
            _print("\n  VLM 模型已卸载，释放 GPU 显存")

    # 汇总
    total_time = time.time() - total_start
    batch_result.total_time = total_time

    summary_path = output_dir / "batch_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(batch_result.to_dict(), f, indent=2, ensure_ascii=False)

    _print("\n" + "=" * 60)
    _print("  批量发送完成")
    _print("=" * 60)
    _print(f"  总计图片: {batch_result.total:>10d} 张")
    _print(f"  处理成功: {batch_result.success:>10d} 张")
    _print(f"  处理失败: {batch_result.failed:>10d} 张")
    _print(f"  跳过: {batch_result.skipped:>10d} 张")
    if batch_result.total > 0:
        _print(f"  成功率: {batch_result.success / batch_result.total * 100:>10.1f}%")
    _print(f"  总耗时: {batch_result.total_time:>10.1f}s")
    if batch_result.total > 0:
        _print(f"  单张平均: {batch_result.total_time / batch_result.total:>10.1f}s")
    _print()
    _print(f"  汇总统计: {summary_path}")
    _print(f"  输出目录: {output_dir}/")
    if batch_result.success > 0:
        _print(f"  所有边缘图已保存到 {output_dir}/ 目录，即使发送失败也可以查看结果！")
