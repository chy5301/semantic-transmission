"""semantic-tx demo 子命令：端到端语义传输演示。"""

import io
import time
from pathlib import Path

import click
import numpy as np
from PIL import Image

from semantic_transmission.common.config import get_default_vlm_path
from semantic_transmission.receiver import create_receiver
from semantic_transmission.sender.local_condition_extractor import LocalCannyExtractor


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


@click.command()
@click.option(
    "--image",
    required=True,
    type=click.Path(exists=True, path_type=Path),
    help="输入图像路径",
)
@click.option("--prompt", default=None, type=str, help="手动指定描述文本")
@click.option(
    "--auto-prompt",
    is_flag=True,
    default=False,
    help="使用 VLM (Qwen2.5-VL) 自动生成描述",
)
@click.option("--threshold1", default=100, type=int, help="Canny 低阈值（默认 100）")
@click.option("--threshold2", default=200, type=int, help="Canny 高阈值（默认 200）")
@click.option(
    "--output-dir",
    default=Path("output/demo"),
    type=click.Path(path_type=Path),
    help="输出目录（默认 output/demo）",
)
@click.option(
    "--seed", default=None, type=int, help="KSampler 随机种子（可选，便于复现）"
)
@click.option(
    "--vlm-model",
    default=None,
    type=str,
    help="VLM 模型名称（默认 Qwen/Qwen2.5-VL-7B-Instruct）",
)
@click.option(
    "--vlm-model-path",
    default=None,
    type=str,
    help="VLM 模型本地路径（默认 $MODEL_CACHE_DIR/Qwen/Qwen2.5-VL-7B-Instruct）",
)
def demo(
    image,
    prompt,
    auto_prompt,
    threshold1,
    threshold2,
    output_dir,
    seed,
    vlm_model,
    vlm_model_path,
):
    """端到端演示：图像 → 边缘提取 → 语义还原。

    发送端使用本地 OpenCV 提取 Canny 边缘，接收端使用 Diffusers 本地推理。
    """
    import builtins
    import functools

    _print = functools.partial(builtins.print, flush=True)

    # 校验互斥参数
    if not prompt and not auto_prompt:
        raise click.UsageError("必须指定 --prompt 或 --auto-prompt 之一")
    if prompt and auto_prompt:
        raise click.UsageError("--prompt 和 --auto-prompt 不能同时使用")

    if vlm_model_path is None:
        vlm_model_path = get_default_vlm_path()

    # 创建输出目录
    output_dir.mkdir(parents=True, exist_ok=True)

    _print("=" * 60)
    _print("  语义传输端到端 Demo（发送端本地 Canny）")
    _print("=" * 60)
    _print(f"  输入图像: {image}")
    _print(f"  Canny 阈值: {threshold1}, {threshold2}")
    _print(f"  输出目录: {output_dir}")

    # 发送端：本地提取 Canny 边缘图
    _print("\n[1/4] 本地提取 Canny 边缘图...")
    original_img = Image.open(image).convert("RGB")
    image_array = np.array(original_img)
    extractor = LocalCannyExtractor(threshold1=threshold1, threshold2=threshold2)
    start = time.time()
    edge_np = extractor.extract(image_array)
    edge_image = Image.fromarray(edge_np)
    sender_elapsed = time.time() - start

    edge_path = output_dir / "edge.png"
    edge_image.save(edge_path)
    _print(f"  边缘图: {edge_path} ({edge_image.size[0]}x{edge_image.size[1]})")
    _print(f"  耗时: {sender_elapsed:.3f}s")

    # 获取 prompt
    vlm_elapsed = 0.0
    _print("\n[2/4] 获取语义描述...")
    if auto_prompt:
        from semantic_transmission.sender.qwen_vl_sender import QwenVLSender

        _print("  模式: VLM 自动描述 (Qwen2.5-VL)")
        vlm_kwargs = {}
        if vlm_model:
            vlm_kwargs["model_name"] = vlm_model
        if vlm_model_path:
            vlm_kwargs["model_path"] = vlm_model_path
        vlm_sender = QwenVLSender(**vlm_kwargs)
        _print("  正在加载 VLM 模型（首次加载可能需要几分钟）...")
        start_vlm = time.time()
        sender_output = vlm_sender.describe(image_array)
        vlm_elapsed = time.time() - start_vlm
        prompt_text = sender_output.text
        _print(f"  VLM 耗时: {vlm_elapsed:.1f}s")
        _print(
            f"  描述长度: {len(prompt_text)} 字符, {len(prompt_text.encode('utf-8'))} 字节"
        )
        _print(f"  生成描述: {prompt_text[:200]}...")
        vlm_sender.unload()
        _print("  VLM 模型已卸载，释放 GPU 显存")
    else:
        prompt_text = prompt
        _print("  模式: 手动 prompt")
        _print(f"  文本: {prompt_text}")

    # 保存 prompt 文本
    prompt_path = output_dir / "prompt.txt"
    prompt_path.write_text(prompt_text, encoding="utf-8")
    _print(f"  Prompt 已保存: {prompt_path}")

    # 接收端：从边缘图 + prompt 还原图像
    _print("\n[3/4] 接收端：还原图像（diffusers）...")
    receiver = create_receiver()
    start = time.time()
    restored_image = receiver.process(edge_path, prompt_text, seed=seed)
    receiver_elapsed = time.time() - start

    restored_path = output_dir / "restored.png"
    restored_image.save(restored_path)
    _print(
        f"  还原图: {restored_path} ({restored_image.size[0]}x{restored_image.size[1]})"
    )
    _print(f"  耗时: {receiver_elapsed:.1f}s")

    # 生成对比图
    _print("\n[4/4] 生成对比图...")
    start = time.time()
    comparison = _make_comparison_image(original_img, edge_image, restored_image)
    comparison_path = output_dir / "comparison.png"
    comparison.save(comparison_path)
    comparison_elapsed = time.time() - start
    _print(f"  对比图: {comparison_path} ({comparison.size[0]}x{comparison.size[1]})")
    _print(f"  耗时: {comparison_elapsed:.1f}s")

    # 传输统计
    total_elapsed = sender_elapsed + vlm_elapsed + receiver_elapsed + comparison_elapsed
    buf = io.BytesIO()
    edge_image.save(buf, format="PNG")
    edge_bytes = buf.tell()
    prompt_bytes = len(prompt_text.encode("utf-8"))
    total_bytes = edge_bytes + prompt_bytes
    original_bytes = image.stat().st_size

    _print("\n" + "=" * 60)
    _print("  传输统计")
    _print("=" * 60)
    _print(f"  原始图像大小:    {original_bytes:>10,} bytes")
    _print(f"  边缘图大小:      {edge_bytes:>10,} bytes")
    _print(f"  Prompt 大小:     {prompt_bytes:>10,} bytes")
    _print(f"  传输数据总量:    {total_bytes:>10,} bytes")
    _print(f"  压缩比:          {original_bytes / total_bytes:>10.2f}x")
    _print(f"  发送端耗时:      {sender_elapsed:>10.3f}s")
    if auto_prompt:
        _print(f"  VLM 耗时:        {vlm_elapsed:>10.1f}s")
    _print(f"  接收端耗时:      {receiver_elapsed:>10.1f}s")
    _print(f"  对比图耗时:      {comparison_elapsed:>10.1f}s")
    _print(f"  总耗时:          {total_elapsed:>10.1f}s")

    _print(f"\n输出文件在 {output_dir}/ 目录下：")
    _print("  edge.png       — Canny 边缘图")
    _print("  restored.png   — 还原图像")
    _print("  comparison.png — 对比图（原图 | 边缘图 | 还原图）")
    _print("  prompt.txt     — 语义描述文本")
