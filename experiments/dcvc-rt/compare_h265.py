"""H.265 对照编码 + 与 DCVC-RT 的头对头对比。

从 dcvc_metrics.json 读取 DCVC-RT 实际码率，用 ffmpeg ABR 模式编码 H.265，
评估质量后输出对比表。
"""

from __future__ import annotations

import json
import statistics
import subprocess
import sys
import time
from pathlib import Path

import imageio_ffmpeg
import numpy as np
from PIL import Image
from skimage.metrics import peak_signal_noise_ratio

from semantic_transmission.evaluation.perceptual_metrics import (
    compute_lpips,
    load_lpips_model,
)
from semantic_transmission.evaluation.pixel_metrics import compute_psnr, compute_ssim
from semantic_transmission.evaluation.video_eval import evaluate_video


def rgb_to_y_channel(frame: np.ndarray) -> np.ndarray:
    """RGB uint8 帧转 Y 通道（亮度），返回单通道 uint8 ndarray。"""
    r, g, b = (
        frame[:, :, 0].astype(np.float32),
        frame[:, :, 1].astype(np.float32),
        frame[:, :, 2].astype(np.float32),
    )
    y = (0.299 * r + 0.587 * g + 0.114 * b).clip(0, 255).astype(np.uint8)
    return y


def compute_psnr_y(original: np.ndarray, reconstructed: np.ndarray) -> float:
    """计算 Y 通道 PSNR（与 DCVC-RT 论文口径一致）。"""
    y_orig = rgb_to_y_channel(original)
    y_recon = rgb_to_y_channel(reconstructed)
    return float(peak_signal_noise_ratio(y_orig, y_recon, data_range=255))


# ── 配置 ──────────────────────────────────────────────
FRAMES_DIR = Path("experiments/dcvc-rt/results/frames/original")
H265_OUT_DIR = Path("experiments/dcvc-rt/results/frames/h265")
H265_BIN = Path("experiments/dcvc-rt/results/h265_bin")
DCVC_METRICS = Path("experiments/dcvc-rt/results/dcvc_metrics.json")
RESULT_JSON = Path("experiments/dcvc-rt/results/h265_metrics.json")
COMPARISON_JSON = Path("experiments/dcvc-rt/results/comparison.json")
FPS = 6  # 帧率（与 prepared mp4 一致）
PRESETS = ["medium"]  # 可加 "slow" 作为质量上限参考
# ─────────────────────────────────────────────────────


def load_frames_as_ndarray(frames_dir: Path, count: int) -> list[np.ndarray]:
    """加载 PNG 帧为 ndarray 列表。"""
    frames = []
    for i in range(1, count + 1):
        path = frames_dir / f"im{i:05d}.png"
        if path.exists():
            frames.append(np.array(Image.open(path)))
    return frames


def encode_h265_abr(
    frames_dir: Path,
    output_bin: Path,
    target_bitrate_kbps: float,
    preset: str,
    num_frames: int,
    width: int,
    height: int,
) -> tuple[float, float, str]:
    """用 ffmpeg ABR 模式编码 PNG 帧序列为 H.265，返回 (编码耗时, 实际码率Mbps, 输出路径)。"""
    output_bin.mkdir(parents=True, exist_ok=True)

    ff = imageio_ffmpeg.get_ffmpeg_exe()

    # 输入：PNG 帧序列（image sequence pattern）
    input_pattern = str(frames_dir / "im%05d.png")
    output_path = str(output_bin / f"h265_{preset}_{int(target_bitrate_kbps)}k.mp4")

    cmd = [
        ff,
        "-y",
        "-framerate",
        str(FPS),
        "-i",
        input_pattern,
        "-c:v",
        "libx265",
        "-preset",
        preset,
        "-b:v",
        f"{int(target_bitrate_kbps)}k",
        "-maxrate",
        f"{int(target_bitrate_kbps * 1.2)}k",
        "-bufsize",
        f"{int(target_bitrate_kbps * 2)}k",
        "-x265-params",
        "keyint=9999:min-keyint=9999:scenecut=0",  # 超长 GOP 对齐 DCVC-RT
        "-pix_fmt",
        "yuv420p",
        "-frames:v",
        str(num_frames),
        output_path,
    ]

    print(f"  编码 H.265 preset={preset} target={int(target_bitrate_kbps)}kbps...")
    t_start = time.perf_counter()
    result = subprocess.run(cmd, capture_output=True, text=True)
    t_elapsed = time.perf_counter() - t_start

    if result.returncode != 0:
        print(f"  ffmpeg 编码失败:\n{result.stderr}")
        return 0.0, 0.0, output_path

    # 计算实际码率
    bin_path = Path(output_path)
    if bin_path.exists():
        size_bytes = bin_path.stat().st_size
        duration = num_frames / FPS
        actual_bitrate_mbps = (size_bytes * 8) / (duration * 1_000_000)
        print(f"  实际码率: {actual_bitrate_mbps:.4f} Mbps, 耗时: {t_elapsed:.2f}s")
    else:
        actual_bitrate_mbps = 0.0

    return t_elapsed, actual_bitrate_mbps, output_path


def decode_h265_to_frames(mp4_path: str, output_dir: Path, num_frames: int) -> float:
    """用 ffmpeg 解码 H.265 mp4 为 PNG 帧，返回解码耗时。"""
    output_dir.mkdir(parents=True, exist_ok=True)

    ff = imageio_ffmpeg.get_ffmpeg_exe()

    cmd = [
        ff,
        "-y",
        "-i",
        mp4_path,
        "-frames:v",
        str(num_frames),
        str(output_dir / "im%05d.png"),
    ]

    t_start = time.perf_counter()
    result = subprocess.run(cmd, capture_output=True, text=True)
    t_elapsed = time.perf_counter() - t_start

    if result.returncode != 0:
        print(f"  ffmpeg 解码失败:\n{result.stderr}")

    return t_elapsed


def main() -> None:
    # 读取 DCVC-RT 结果获取目标码率
    if not DCVC_METRICS.exists():
        print(f"错误: 找不到 {DCVC_METRICS}，请先运行 run_dcvc.py")
        sys.exit(1)

    with open(DCVC_METRICS) as f:
        dcvc_data = json.load(f)

    target_bitrate_mbps = dcvc_data["bitrate_mbps"]
    target_bitrate_kbps = target_bitrate_mbps * 1000
    num_frames = dcvc_data["frame_count"]
    width, height = dcvc_data["resolution"].split("x")
    width, height = int(width), int(height)
    duration = dcvc_data["duration_seconds"]

    print(f"DCVC-RT 参考码率: {target_bitrate_mbps:.4f} Mbps ({target_bitrate_kbps:.0f} kbps)")
    print(f"目标: {num_frames} 帧, {width}x{height}")

    # 加载原始帧
    orig_frames = load_frames_as_ndarray(FRAMES_DIR, num_frames)

    # 对每个 preset 编码 + 解码 + 评估
    results = []
    for preset in PRESETS:
        print(f"\n--- H.265 preset={preset} ---")

        # 编码
        encode_time, actual_bitrate, mp4_path = encode_h265_abr(
            FRAMES_DIR, H265_BIN, target_bitrate_kbps, preset, num_frames, width, height
        )

        # 解码
        decoded_dir = H265_OUT_DIR / preset
        decode_time = decode_h265_to_frames(mp4_path, decoded_dir, num_frames)

        # 加载还原帧
        h265_frames = load_frames_as_ndarray(decoded_dir, num_frames)
        if len(h265_frames) == 0:
            print("  警告: 未找到 H.265 还原帧，跳过")
            continue

        # 质量评估——SSIM 和 LPIPS 用 evaluate_video（RGB 域），PSNR-Y 单独算
        print("  运行质量评估...")
        eval_result = evaluate_video(
            orig_frames[: len(h265_frames)],
            h265_frames,
            with_lpips=True,
            with_clip=False,
            device="cuda",
        )

        # 补充 PSNR-Y（仅 Y 通道，与 DCVC-RT 对齐）
        psnr_y_values = [
            compute_psnr_y(o, h) for o, h in zip(orig_frames[: len(h265_frames)], h265_frames)
        ]
        psnr_y_mean = statistics.mean(psnr_y_values)
        psnr_y_std = statistics.pstdev(psnr_y_values) if len(psnr_y_values) > 1 else 0.0

        preset_result = {
            "preset": preset,
            "target_bitrate_mbps": round(target_bitrate_mbps, 4),
            "actual_bitrate_mbps": round(actual_bitrate, 4),
            "bitrate_deviation_pct": (
                round(abs(actual_bitrate - target_bitrate_mbps) / target_bitrate_mbps * 100, 2)
                if target_bitrate_mbps > 0
                else None
            ),
            "encode_time_seconds": round(encode_time, 3),
            "decode_time_seconds": round(decode_time, 3),
            "fps_encode": round(num_frames / encode_time, 2) if encode_time > 0 else None,
            "fps_decode": round(num_frames / decode_time, 2) if decode_time > 0 else None,
            "summary": {
                "psnr_y": {"mean": round(psnr_y_mean, 4), "std": round(psnr_y_std, 4)},
                "ssim": eval_result["summary"]["ssim"],
                "lpips": eval_result["summary"]["lpips"],
            },
        }
        results.append(preset_result)

        print(f"  PSNR-Y: {psnr_y_mean:.2f} dB")
        print(f"  SSIM: {eval_result['summary']['ssim']['mean']:.4f}")

    # 保存 H.265 结果
    h265_output = {
        "codec": "H.265/HEVC (libx265)",
        "source": dcvc_data["source"],
        "frame_count": num_frames,
        "resolution": f"{width}x{height}",
        "duration_seconds": duration,
        "results_by_preset": results,
    }

    RESULT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(RESULT_JSON, "w") as f:
        json.dump(h265_output, f, indent=2, ensure_ascii=False)

    print(f"\nH.265 结果已保存到 {RESULT_JSON}")

    # 生成对比表
    if results:
        comparison = {
            "dcvc_rt": {
                "bitrate_mbps": dcvc_data["bitrate_mbps"],
                "psnr_y_db": dcvc_data["summary"]["psnr_y"]["mean"],
                "ssim": dcvc_data["summary"]["ssim"]["mean"],
                "lpips": dcvc_data["summary"]["lpips"]["mean"],
                "fps_overall": dcvc_data["fps_overall"],
            },
            "h265": {},
        }
        for r in results:
            comparison["h265"][r["preset"]] = {
                "bitrate_mbps": r["actual_bitrate_mbps"],
                "bitrate_deviation_pct": r["bitrate_deviation_pct"],
                "psnr_y_db": r["summary"]["psnr_y"]["mean"],
                "ssim": r["summary"]["ssim"]["mean"],
                "lpips": r["summary"]["lpips"]["mean"],
                "fps_encode": r["fps_encode"],
                "fps_decode": r["fps_decode"],
            }

        with open(COMPARISON_JSON, "w") as f:
            json.dump(comparison, f, indent=2, ensure_ascii=False)

        print(f"\n对比表已保存到 {COMPARISON_JSON}")
        print("\n=== 对比汇总 ===")
        print(
            f"DCVC-RT: {comparison['dcvc_rt']['bitrate_mbps']:.4f} Mbps, "
            f"PSNR-Y={comparison['dcvc_rt']['psnr_y_db']:.2f}dB, "
            f"SSIM={comparison['dcvc_rt']['ssim']:.4f}"
        )
        for preset, h in comparison["h265"].items():
            print(
                f"H.265-{preset}: {h['bitrate_mbps']:.4f} Mbps "
                f"(偏差{h['bitrate_deviation_pct']:.1f}%), "
                f"PSNR-Y={h['psnr_y_db']:.2f}dB, "
                f"SSIM={h['ssim']:.4f}"
            )


if __name__ == "__main__":
    main()
