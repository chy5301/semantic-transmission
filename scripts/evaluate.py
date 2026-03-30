"""批量评估还原图像质量：计算 PSNR、SSIM、LPIPS、CLIP Score。

读取已生成的还原结果目录，与原始图像逐一比对，计算四类质量指标并生成评估报告。

用法示例：
    uv run python scripts/evaluate.py \\
        --input-dir output/demo/round-03 \\
        --original-dir resources/test_images

    uv run python scripts/evaluate.py \\
        --input-dir output/demo/round-03 \\
        --original-dir resources/test_images \\
        --output output/evaluation/results.json --device cuda
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
import textwrap
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image

from semantic_transmission.evaluation.perceptual_metrics import (
    compute_lpips,
    load_lpips_model,
)
from semantic_transmission.evaluation.pixel_metrics import compute_psnr, compute_ssim
from semantic_transmission.evaluation.semantic_metrics import (
    compute_clip_score,
    load_clip_model,
)

IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff")


def find_original_image(sample_name: str, original_dir: Path) -> Path | None:
    """根据样本目录名查找原始图像。

    去掉 'NN-' 或 'NN_' 前缀后在 original_dir 中匹配。
    例如 '01-canyon_jeep' → 查找 'canyon_jeep.*'
    """
    stem = re.sub(r"^\d+[-_]", "", sample_name)
    for ext in IMAGE_EXTENSIONS:
        candidate = original_dir / f"{stem}{ext}"
        if candidate.exists():
            return candidate
    return None


def discover_samples(
    input_dir: Path, restored_name: str = "restored.png"
) -> list[dict]:
    """扫描输入目录，发现所有含还原图的样本子目录。"""
    samples = []
    for entry in sorted(input_dir.iterdir()):
        if not entry.is_dir():
            continue
        restored = entry / restored_name
        if restored.exists():
            samples.append({"name": entry.name, "dir": entry, "restored": restored})
    return samples


def evaluate_sample(
    original_path: Path,
    restored_path: Path,
    prompt_text: str | None,
    *,
    lpips_model=None,
    clip_model=None,
    clip_processor=None,
    device: str | None = None,
) -> dict:
    """评估单个样本，返回指标字典。"""
    original = Image.open(original_path).convert("RGB")
    restored = Image.open(restored_path).convert("RGB")

    original_arr = np.array(original)
    restored_arr = np.array(restored)

    result = {
        "psnr": compute_psnr(original_arr, restored_arr),
        "ssim": compute_ssim(original_arr, restored_arr),
        "lpips": None,
        "clip_score": None,
    }

    if lpips_model is not None:
        result["lpips"] = compute_lpips(
            original_arr, restored_arr, loss_fn=lpips_model, device=device
        )

    if clip_model is not None and clip_processor is not None and prompt_text:
        result["clip_score"] = compute_clip_score(
            restored_arr,
            prompt_text,
            model=clip_model,
            processor=clip_processor,
            device=device,
        )

    return result


def compute_summary(results: list[dict]) -> dict:
    """计算汇总统计（均值、标准差）。"""
    metric_names = ["psnr", "ssim", "lpips", "clip_score"]
    summary = {}

    for metric in metric_names:
        values = [
            r["metrics"][metric] for r in results if r["metrics"][metric] is not None
        ]
        if values:
            mean = statistics.mean(values)
            std = statistics.pstdev(values) if len(values) > 1 else 0.0
            summary[metric] = {"mean": mean, "std": std, "count": len(values)}
        else:
            summary[metric] = {"mean": None, "std": None, "count": 0}

    return summary


def format_table(results: list[dict], summary: dict) -> str:
    """生成终端对齐表格。"""
    lines = []
    header = f"  {'样本':<24s} {'PSNR (dB)':>10s} {'SSIM':>8s} {'LPIPS ↓':>10s} {'CLIP Score ↑':>14s}"
    separator = f"  {'─' * 24} {'─' * 10} {'─' * 8} {'─' * 10} {'─' * 14}"

    lines.append(header)
    lines.append(separator)

    for r in results:
        m = r["metrics"]
        psnr_str = f"{m['psnr']:.2f}" if m["psnr"] is not None else "N/A"
        ssim_str = f"{m['ssim']:.4f}" if m["ssim"] is not None else "N/A"
        lpips_str = f"{m['lpips']:.4f}" if m["lpips"] is not None else "N/A"
        clip_str = f"{m['clip_score']:.2f}" if m["clip_score"] is not None else "N/A"
        lines.append(
            f"  {r['name']:<24s} {psnr_str:>10s} {ssim_str:>8s} {lpips_str:>10s} {clip_str:>14s}"
        )

    lines.append(separator)

    def _fmt(s, key, fmt):
        v = s[key]
        if v["mean"] is None:
            return "N/A"
        return f"{v['mean']:{fmt}}"

    def _fmt_std(s, key, fmt):
        v = s[key]
        if v["std"] is None:
            return "N/A"
        return f"{v['std']:{fmt}}"

    lines.append(
        f"  {'均值':<24s} {_fmt(summary, 'psnr', '.2f'):>10s} "
        f"{_fmt(summary, 'ssim', '.4f'):>8s} {_fmt(summary, 'lpips', '.4f'):>10s} "
        f"{_fmt(summary, 'clip_score', '.2f'):>14s}"
    )
    lines.append(
        f"  {'标准差':<24s} {_fmt_std(summary, 'psnr', '.2f'):>10s} "
        f"{_fmt_std(summary, 'ssim', '.4f'):>8s} {_fmt_std(summary, 'lpips', '.4f'):>10s} "
        f"{_fmt_std(summary, 'clip_score', '.2f'):>14s}"
    )

    return "\n".join(lines)


def resolve_device(device: str | None) -> str | None:
    """解析计算设备，None 时自动检测。"""
    if device is not None:
        return device
    try:
        import torch

        if torch.cuda.is_available():
            return "cuda"
    except ImportError:
        pass
    return None


def build_report(
    results: list[dict],
    summary: dict,
    *,
    input_dir: Path,
    original_dir: Path,
    device: str | None,
) -> dict:
    """构建 JSON 报告结构。"""
    return {
        "metadata": {
            "input_dir": str(input_dir),
            "original_dir": str(original_dir),
            "device": device or "cpu",
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "sample_count": len(results),
        },
        "samples": results,
        "summary": summary,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="批量评估还原图像质量：计算 PSNR、SSIM、LPIPS、CLIP Score",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            用法示例:
              uv run python scripts/evaluate.py \\
                  --input-dir output/demo/round-03 \\
                  --original-dir resources/test_images

              uv run python scripts/evaluate.py \\
                  --input-dir output/demo/round-03 \\
                  --original-dir resources/test_images \\
                  --output results.json --device cuda
        """),
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        required=True,
        help="包含样本子目录的输入目录（每个子目录含 restored.png）",
    )
    parser.add_argument(
        "--original-dir",
        type=Path,
        required=True,
        help="原始图像所在目录",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("evaluation_results.json"),
        help="JSON 报告输出路径（默认: evaluation_results.json）",
    )
    parser.add_argument(
        "--device",
        type=str,
        default=None,
        help="计算设备: cuda / cpu（默认: 自动检测）",
    )
    parser.add_argument(
        "--no-lpips",
        action="store_true",
        help="跳过 LPIPS 计算",
    )
    parser.add_argument(
        "--no-clip",
        action="store_true",
        help="跳过 CLIP Score 计算",
    )

    args = parser.parse_args(argv)

    if not args.input_dir.is_dir():
        print(f"错误: 输入目录不存在: {args.input_dir}", file=sys.stderr)
        return 1
    if not args.original_dir.is_dir():
        print(f"错误: 原图目录不存在: {args.original_dir}", file=sys.stderr)
        return 1

    device = resolve_device(args.device)

    # 发现样本
    samples = discover_samples(args.input_dir)
    if not samples:
        print(f"错误: 输入目录中未发现样本: {args.input_dir}", file=sys.stderr)
        return 1

    # 匹配原图并检查 prompt
    eval_tasks = []
    has_any_prompt = False
    for sample in samples:
        original = find_original_image(sample["name"], args.original_dir)
        if original is None:
            print(f"  警告: 跳过 {sample['name']}，未找到匹配的原始图像")
            continue
        prompt_path = sample["dir"] / "prompt.txt"
        prompt_text = None
        if prompt_path.exists():
            prompt_text = prompt_path.read_text(encoding="utf-8").strip()
            has_any_prompt = True
        eval_tasks.append(
            {
                "name": sample["name"],
                "original": original,
                "restored": sample["restored"],
                "prompt_text": prompt_text,
            }
        )

    if not eval_tasks:
        print("错误: 没有可评估的样本（所有样本均未匹配到原图）", file=sys.stderr)
        return 1

    # 加载模型（仅加载一次）
    lpips_model = None
    clip_model = None
    clip_processor = None

    if not args.no_lpips:
        print("  加载 LPIPS 模型...", flush=True)
        try:
            lpips_model = load_lpips_model(device=device)
        except Exception as e:
            print(f"  警告: LPIPS 模型加载失败（{e}），跳过 LPIPS 指标")

    if not args.no_clip and has_any_prompt:
        print("  加载 CLIP 模型...", flush=True)
        try:
            clip_model, clip_processor = load_clip_model(device=device)
        except Exception as e:
            print(f"  警告: CLIP 模型加载失败（{e}），跳过 CLIP Score 指标")
    elif not args.no_clip and not has_any_prompt:
        print("  无 prompt 文件，跳过 CLIP Score")

    # 逐样本评估
    print(f"\n  评估 {len(eval_tasks)} 个样本...\n", flush=True)
    results = []
    for task in eval_tasks:
        print(f"  评估 {task['name']}...", end="", flush=True)
        metrics = evaluate_sample(
            task["original"],
            task["restored"],
            task["prompt_text"],
            lpips_model=lpips_model,
            clip_model=clip_model,
            clip_processor=clip_processor,
            device=device,
        )
        results.append(
            {
                "name": task["name"],
                "original": str(task["original"]),
                "restored": str(task["restored"]),
                "prompt": task["prompt_text"],
                "metrics": metrics,
            }
        )
        psnr = metrics["psnr"]
        ssim = metrics["ssim"]
        print(f" PSNR={psnr:.2f} SSIM={ssim:.4f}", flush=True)

    # 汇总统计
    summary = compute_summary(results)

    # 终端报告
    sep = "=" * 80
    print(f"\n{sep}")
    print("  语义传输还原质量评估报告")
    print(sep)
    print(f"  输入目录:  {args.input_dir}")
    print(f"  原图目录:  {args.original_dir}")
    print(f"  设备:      {device or 'cpu'}")
    print(f"  样本数:    {len(results)}")
    print(sep)
    print()
    print(format_table(results, summary))
    print()

    # 写入 JSON
    args.output.parent.mkdir(parents=True, exist_ok=True)
    report = build_report(
        results,
        summary,
        input_dir=args.input_dir,
        original_dir=args.original_dir,
        device=device,
    )
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"{sep}")
    print(f"  结果已保存至: {args.output}")
    print(sep)

    return 0


if __name__ == "__main__":
    sys.exit(main())
