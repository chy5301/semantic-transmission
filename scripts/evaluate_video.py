"""批量评估视频还原质量：逐帧 PSNR/SSIM/LPIPS/CLIP + 整段汇总。

用法示例：
    uv run python scripts/evaluate_video.py \\
        --original input.mp4 --restored output/video_relay/out.mp4

    uv run python scripts/evaluate_video.py \\
        --original input.mp4 --restored out.mp4 \\
        --prompts output/video_relay/receiver_summary.json \\
        --output output/evaluation/video_results.json --device cuda
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from semantic_transmission.common.video_io import read_frames
from semantic_transmission.evaluation.video_eval import evaluate_video


def resolve_device(device: str | None) -> str | None:
    """解析计算设备，None 时自动检测 cuda。"""
    if device is not None:
        return device
    try:
        import torch

        if torch.cuda.is_available():
            return "cuda"
    except ImportError:
        pass
    return None


def load_prompts(prompts_path: Path) -> list[str] | None:
    """从 receiver_summary.json 读取逐帧 prompt（按 index 排序）。"""
    data = json.loads(prompts_path.read_text(encoding="utf-8"))
    frames = data.get("frames")
    if not frames:
        return None
    ordered = sorted(frames, key=lambda f: f["index"])
    return [f.get("prompt", "") for f in ordered]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="评估视频还原质量：逐帧 PSNR/SSIM/LPIPS/CLIP + 整段汇总",
    )
    parser.add_argument("--original", type=Path, required=True, help="原始视频路径")
    parser.add_argument("--restored", type=Path, required=True, help="还原视频路径")
    parser.add_argument(
        "--prompts",
        type=Path,
        default=None,
        help="receiver_summary.json，提供逐帧 prompt 以算 CLIP",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("video_evaluation_results.json"),
        help="JSON 报告输出路径",
    )
    parser.add_argument(
        "--device", type=str, default=None, help="cuda / cpu（默认自动）"
    )
    parser.add_argument("--no-lpips", action="store_true", help="跳过 LPIPS")
    parser.add_argument("--no-clip", action="store_true", help="跳过 CLIP Score")

    args = parser.parse_args(argv)

    if not args.original.is_file():
        print(f"错误: 原视频不存在: {args.original}", file=sys.stderr)
        return 1
    if not args.restored.is_file():
        print(f"错误: 还原视频不存在: {args.restored}", file=sys.stderr)
        return 1

    device = resolve_device(args.device)
    orig_frames, _ = read_frames(args.original)
    rest_frames, _ = read_frames(args.restored)

    prompts = None
    if args.prompts is not None and args.prompts.is_file():
        prompts = load_prompts(args.prompts)

    try:
        report = evaluate_video(
            orig_frames,
            rest_frames,
            prompts=prompts,
            device=device,
            with_lpips=not args.no_lpips,
            with_clip=not args.no_clip,
        )
    except ValueError as e:
        print(f"错误: {e}", file=sys.stderr)
        return 1

    report["metadata"] = {
        "original": str(args.original),
        "restored": str(args.restored),
        "device": device or "cpu",
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    s = report["summary"]
    print("=" * 60)
    print("  视频还原质量评估（整段汇总）")
    print("=" * 60)
    print(f"  帧数:        {report['frame_count']}")
    for name in ("psnr", "ssim", "lpips", "clip_score"):
        v = s[name]
        if v["mean"] is None:
            print(f"  {name:<12s} N/A")
        else:
            print(
                f"  {name:<12s} mean={v['mean']:.4f}  std={v['std']:.4f}  n={v['count']}"
            )
    print("=" * 60)
    print(f"  结果已保存至: {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
