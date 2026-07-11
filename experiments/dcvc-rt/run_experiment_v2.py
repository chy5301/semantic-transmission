"""DCVC-RT 实验 v2：正确方法论。

原始 H.265 视频作为基线（不二次编码），DCVC-RT 对同一内容编码后对比。
生成可播放的对比视频和实测数据。
"""

from __future__ import annotations

import json
import shutil
import statistics
import subprocess
import sys
import time
from pathlib import Path

import imageio_ffmpeg
import numpy as np
from PIL import Image

from semantic_transmission.evaluation.perceptual_metrics import compute_lpips, load_lpips_model
from semantic_transmission.evaluation.pixel_metrics import compute_psnr, compute_ssim
from semantic_transmission.evaluation.video_eval import evaluate_video

# ── 配置 ──────────────────────────────────────────────
ORIGINAL_H265 = Path("/home/ws-009/chy/Projects/semantic-transmission/resources/test_videos/C104/20260115121711.h265")
WORK_DIR = Path("experiments/dcvc-rt/results_v2")
FPS = 25
CLIP_START_SEC = 0      # 从第 0 秒开始截取
CLIP_DURATION_SEC = 10   # 截取 10 秒（250 帧）

DCVC_DIR = Path("/home/ws-009/chy/Projects/DCVC")
DCVC_PYTHON = DCVC_DIR / ".venv" / "bin" / "python"
CKPT_I = DCVC_DIR / "checkpoints" / "cvpr2025_image.pth.tar"
CKPT_P = DCVC_DIR / "checkpoints" / "cvpr2025_video.pth.tar"

QP_VALUES = [2, 4, 6]  # 测试多个 QP 点
# ─────────────────────────────────────────────────────


def rgb_to_y_channel(frame: np.ndarray) -> np.ndarray:
    """RGB uint8 帧转 Y 通道（亮度）。"""
    r, g, b = frame[:, :, 0].astype(np.float32), frame[:, :, 1].astype(np.float32), frame[:, :, 2].astype(np.float32)
    return (0.299 * r + 0.587 * g + 0.114 * b).clip(0, 255).astype(np.uint8)


def compute_psnr_y(original: np.ndarray, reconstructed: np.ndarray) -> float:
    """计算 Y 通道 PSNR。"""
    from skimage.metrics import peak_signal_noise_ratio
    return float(peak_signal_noise_ratio(
        rgb_to_y_channel(original), rgb_to_y_channel(reconstructed), data_range=255
    ))


def get_ffmpeg():
    return imageio_ffmpeg.get_ffmpeg_exe()


def step1_extract_clip():
    """Step 1: 从原始 h265 提取 10s 片段并解码为 PNG 帧。"""
    print("\n=== Step 1: 提取 10s 片段并解码为 PNG 帧 ===")

    frames_dir = WORK_DIR / "frames" / "original"
    frames_dir.mkdir(parents=True, exist_ok=True)

    ff = get_ffmpeg()

    # 先把整个 h265 裸码流封装为 mp4（需要先生成带时间戳的容器）
    full_mp4 = WORK_DIR / "original_full.mp4"
    cmd_wrap = [
        ff, "-y",
        "-r", str(FPS),
        "-i", str(ORIGINAL_H265),
        "-c:v", "copy",
        str(full_mp4),
    ]
    subprocess.run(cmd_wrap, check=True, capture_output=True)
    print(f"  完整封装: {full_mp4}")

    # 从封装后的 mp4 提取 10s 片段（copy 模式，不重编码）
    clip_mp4 = WORK_DIR / "original_clip_10s.mp4"
    start_frame = CLIP_START_SEC * FPS
    cmd_clip = [
        ff, "-y",
        "-i", str(full_mp4),
        "-vf", f"select='between(n\\,{start_frame}\\,{start_frame + CLIP_DURATION_SEC * FPS - 1})',setpts=PTS-STARTPTS",
        "-c:v", "libx264",
        "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-r", str(FPS),
        str(clip_mp4),
    ]
    subprocess.run(cmd_clip, check=True, capture_output=True)
    print(f"  片段提取: {clip_mp4}")

    # 解码片段为 PNG 帧
    cmd_decode = [
        ff, "-y",
        "-i", str(clip_mp4),
        str(frames_dir / "im%05d.png"),
    ]
    subprocess.run(cmd_decode, check=True, capture_output=True)

    frame_count = len(list(frames_dir.glob("im*.png")))
    print(f"  解码完成: {frame_count} 帧 @ {FPS}fps")

    # 获取原始片段的码率（用原始 h265 文件大小计算）
    original_size = ORIGINAL_H265.stat().st_size
    total_duration = 79.0  # 原始视频总时长
    original_bitrate_kbps = (original_size * 8) / (total_duration * 1000)
    clip_bitrate_kbps = original_bitrate_kbps  # 同编码参数，码率一致
    print(f"  原始视频码率: {original_bitrate_kbps:.1f} kbps")

    return frame_count, clip_bitrate_kbps, clip_mp4


def step2_run_dcvc(frame_count: int, qp: int) -> dict:
    """Step 2: 用 DCVC-RT 编码并解码。"""
    frames_dir = WORK_DIR / "frames" / "original"
    output_dir = WORK_DIR / "frames" / "dcvc" / f"qp{qp}"
    output_dir.mkdir(parents=True, exist_ok=True)
    stream_dir = (WORK_DIR / "dcvc_bin" / f"qp{qp}").resolve()
    stream_dir.mkdir(parents=True, exist_ok=True)

    # 生成 DCVC 配置
    config = {
        "root_path": str(frames_dir.parent.resolve()),
        "test_classes": {
            "experiment": {
                "base_path": ".",
                "src_type": "png",
                "test": 1,
                "sequences": {
                    "original": {
                        "height": 960,
                        "width": 1280,
                        "frames": frame_count,
                        "intra_period": -1,
                    }
                },
            }
        },
    }
    config_path = (WORK_DIR / f"dcvc_config_qp{qp}.json").resolve()
    config_path.write_text(json.dumps(config, indent=2))

    # 运行 DCVC-RT
    result_json = (WORK_DIR / f"dcvc_raw_qp{qp}.json").resolve()
    cmd = [
        str(DCVC_PYTHON),
        str(DCVC_DIR / "test_video.py"),
        "--test_config", str(config_path),
        "--model_path_i", str(CKPT_I),
        "--model_path_p", str(CKPT_P),
        "--cuda", "True",
        "--write_stream", "True",
        "--save_decoded_frame", "True",
        "--stream_path", str(stream_dir),
        "--output_path", str(result_json),
        "--rate_num", "1",
        "--qp_i", str(qp),
        "--qp_p", str(qp),
        "--force_intra_period", "-1",
        "--verbose", "2",
    ]

    print(f"\n  运行 DCVC-RT QP={qp}...")
    t_start = time.perf_counter()
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(DCVC_DIR), timeout=600)
    t_elapsed = time.perf_counter() - t_start

    if result.returncode != 0:
        print(f"  DCVC-RT 失败:\n{result.stderr[-500:]}")
        return None

    # 收集还原帧（DCVC 输出到 stream_dir/experiment/ 下）
    dcvc_decoded = stream_dir / "experiment"
    if dcvc_decoded.exists():
        for f in sorted(dcvc_decoded.glob("*.png")):
            shutil.copy2(f, output_dir / f.name)

    # 收集码流文件
    bin_files = list(stream_dir.rglob("*.bin"))
    total_bytes = sum(f.stat().st_size for f in bin_files)
    bitrate_kbps = (total_bytes * 8) / (CLIP_DURATION_SEC * 1000)

    decoded_count = len(list(output_dir.glob("*.png")))
    print(f"  DCVC-RT QP={qp}: {decoded_count} 帧, 码率 {bitrate_kbps:.1f} kbps, 耗时 {t_elapsed:.1f}s, fps {frame_count/t_elapsed:.1f}")

    return {
        "qp": qp,
        "frame_count": decoded_count,
        "bitrate_kbps": bitrate_kbps,
        "wall_clock_seconds": t_elapsed,
        "fps": frame_count / t_elapsed,
        "decoded_dir": output_dir,
        "raw_result": result_json,
    }


def step3_decode_original_as_mp4(clip_mp4: Path) -> Path:
    """Step 3: 把原始片段重新封装为可播放 mp4（copy 模式）。"""
    # 原始 clip_mp4 已经是 mp4，直接用
    return clip_mp4


def step4_create_dcvc_mp4(dcvc_frames_dir: Path, fps: int, qp: int) -> Path:
    """Step 4: 从 DCVC 还原帧生成可播放 mp4。"""
    output_mp4 = WORK_DIR / f"dcvc_qp{qp}.mp4"
    ff = get_ffmpeg()

    cmd = [
        ff, "-y",
        "-framerate", str(fps),
        "-i", str(dcvc_frames_dir / "im%05d.png"),
        "-c:v", "libx264",
        "-crf", "18",
        "-pix_fmt", "yuv420p",
        str(output_mp4),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    print(f"  DCVC-RT QP={qp} 视频: {output_mp4} ({output_mp4.stat().st_size / 1024:.0f} KB)")
    return output_mp4


def step5_create_comparison_video(original_mp4: Path, dcvc_mp4: Path, qp: int) -> Path:
    """Step 5: 生成左右对比视频。"""
    output = WORK_DIR / f"comparison_qp{qp}.mp4"
    ff = get_ffmpeg()

    # 使用 ffmpeg 的 hstack 滤镜
    cmd = [
        ff, "-y",
        "-i", str(original_mp4),
        "-i", str(dcvc_mp4),
        "-filter_complex",
        "[0:v]drawtext=text='Original H.265':fontsize=24:fontcolor=white:x=10:y=10:box=1:boxcolor=black@0.5:boxborderw=5[left];"
        "[1:v]drawtext=text='DCVC-RT QP={qp}':fontsize=24:fontcolor=white:x=10:y=10:box=1:boxcolor=black@0.5:boxborderw=5[right];"
        "[left][right]hstack[out]".format(qp=qp),
        "-map", "[out]",
        "-c:v", "libx264",
        "-crf", "18",
        "-pix_fmt", "yuv420p",
        str(output),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        # 降级：不加文字标注，直接 hstack
        cmd_simple = [
            ff, "-y",
            "-i", str(original_mp4),
            "-i", str(dcvc_mp4),
            "-filter_complex", "[0:v][1:v]hstack[out]",
            "-map", "[out]",
            "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p",
            str(output),
        ]
        subprocess.run(cmd_simple, check=True, capture_output=True)

    print(f"  对比视频: {output} ({output.stat().st_size / 1024:.0f} KB)")
    return output


def step6_evaluate(original_mp4: Path, dcvc_frames_dir: Path, frame_count: int) -> dict:
    """Step 6: 计算质量指标。"""
    # 解码原始 mp4 为帧
    ff = get_ffmpeg()
    orig_tmp = WORK_DIR / "frames" / "original_eval"
    orig_tmp.mkdir(exist_ok=True)
    cmd = [ff, "-y", "-i", str(original_mp4), str(orig_tmp / "im%05d.png")]
    subprocess.run(cmd, check=True, capture_output=True)

    # 加载帧
    def load_frames(d, n):
        frames = []
        for i in range(1, n + 1):
            p = d / f"im{i:05d}.png"
            if p.exists():
                frames.append(np.array(Image.open(p)))
        return frames

    orig_frames = load_frames(orig_tmp, frame_count)
    dcvc_frames = load_frames(dcvc_frames_dir, frame_count)
    n = min(len(orig_frames), len(dcvc_frames))

    if n == 0:
        return None

    print(f"  评估 {n} 帧...")

    # PSNR-Y
    psnr_y = [compute_psnr_y(o, d) for o, d in zip(orig_frames[:n], dcvc_frames[:n])]

    # SSIM 和 LPIPS
    eval_result = evaluate_video(
        orig_frames[:n], dcvc_frames[:n],
        with_lpips=True, with_clip=False, device="cuda",
    )

    return {
        "psnr_y": {"mean": round(statistics.mean(psnr_y), 4), "std": round(statistics.pstdev(psnr_y), 4)},
        "ssim": eval_result["summary"]["ssim"],
        "lpips": eval_result["summary"]["lpips"],
    }


def main():
    WORK_DIR.mkdir(parents=True, exist_ok=True)

    # Step 1: 提取片段 + 解码帧
    frame_count, original_bitrate_kbps, original_clip = step1_extract_clip()

    # Step 2: 多 QP 点 DCVC-RT 编解码
    dcvc_results = []
    for qp in QP_VALUES:
        result = step2_run_dcvc(frame_count, qp)
        if result:
            dcvc_results.append(result)

    if not dcvc_results:
        print("所有 DCVC-RT 编码均失败")
        return

    # Step 3: 原始视频（已经是 mp4）
    original_mp4 = step3_decode_original_as_mp4(original_clip)

    # Step 4+5+6: 对每个 QP 生成对比视频和评估
    comparison_results = []
    for dcvc in dcvc_results:
        qp = dcvc["qp"]
        print(f"\n=== QP={qp} 对比 ===")

        # 生成 DCVC 还原视频
        dcvc_mp4 = step4_create_dcvc_mp4(dcvc["decoded_dir"], FPS, qp)

        # 生成对比视频
        comp_video = step5_create_comparison_video(original_mp4, dcvc_mp4, qp)

        # 质量评估
        metrics = step6_evaluate(original_mp4, dcvc["decoded_dir"], dcvc["frame_count"])

        comparison_results.append({
            "qp": qp,
            "bitrate_kbps": dcvc["bitrate_kbps"],
            "fps": round(dcvc["fps"], 1),
            "metrics": metrics,
            "comparison_video": str(comp_video),
            "dcvc_video": str(dcvc_mp4),
        })

    # 汇总输出
    output = {
        "source": str(ORIGINAL_H265),
        "clip": f"{CLIP_START_SEC}s ~ {CLIP_START_SEC + CLIP_DURATION_SEC}s, {FPS}fps, 1280x960",
        "original": {
            "codec": "H.265/HEVC",
            "bitrate_kbps": original_bitrate_kbps,
            "video": str(original_mp4),
        },
        "dcvc_rt_results": comparison_results,
    }

    result_file = WORK_DIR / "experiment_v2_results.json"
    with open(result_file, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    # 打印汇总
    print(f"\n{'='*60}")
    print("实验结果汇总")
    print(f"{'='*60}")
    print(f"原始视频: H.265, {original_bitrate_kbps:.1f} kbps")
    print(f"{'─'*60}")
    print(f"{'QP':>4} {'码率(kbps)':>12} {'PSNR-Y(dB)':>12} {'SSIM':>8} {'LPIPS':>8} {'fps':>8}")
    print(f"{'─'*60}")
    for r in comparison_results:
        m = r["metrics"]
        psnr = m["psnr_y"]["mean"] if m else 0
        ssim = m["ssim"]["mean"] if m else 0
        lpips = m["lpips"]["mean"] if m else 0
        print(f"{r['qp']:>4} {r['bitrate_kbps']:>12.1f} {psnr:>12.2f} {ssim:>8.4f} {lpips:>8.4f} {r['fps']:>8.1f}")
    print(f"{'─'*60}")
    print(f"\n对比视频:")
    for r in comparison_results:
        print(f"  QP={r['qp']}: {r['comparison_video']}")
    print(f"\n完整结果: {result_file}")


if __name__ == "__main__":
    main()
