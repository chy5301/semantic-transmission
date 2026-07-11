"""DCVC-RT 编解码 + 质量/码率/延迟测量。

通过 subprocess 调用 DCVC-RT 的 test_video.py，解析输出 JSON，
再用项目 evaluation 模块计算 PSNR-Y/SSIM/LPIPS。
"""

from __future__ import annotations

import json
import shutil
import subprocess
import statistics
import time
from pathlib import Path

import numpy as np
from PIL import Image
from skimage.metrics import peak_signal_noise_ratio

from semantic_transmission.evaluation.video_eval import evaluate_video

# ── 配置 ──────────────────────────────────────────────
DCVC_DIR = Path("/home/ws-009/chy/Projects/DCVC")
DCVC_PYTHON = DCVC_DIR / ".venv" / "bin" / "python"
CKPT_I = DCVC_DIR / "checkpoints" / "cvpr2025_image.pth.tar"
CKPT_P = DCVC_DIR / "checkpoints" / "cvpr2025_video.pth.tar"
INPUT_MP4 = Path(
    "resources/test_videos/prepared/C104_20260115121711_10s_640x480_6fps.mp4"
)
FRAMES_DIR = Path("experiments/dcvc-rt/results/frames/original")
DCVC_OUT_DIR = Path("experiments/dcvc-rt/results/frames/dcvc")
STREAM_DIR = Path("experiments/dcvc-rt/results/dcvc_bin").resolve()
RESULT_JSON = Path("experiments/dcvc-rt/results/dcvc_metrics.json")
QP_I = 4  # I-frame QP（0=最高质量，值越大码率越低）
QP_P = 4  # P-frame QP
# ─────────────────────────────────────────────────────


def rgb_to_y_channel(frame: np.ndarray) -> np.ndarray:
    """RGB uint8 帧转 Y 通道（亮度），返回单通道 uint8 ndarray。"""
    # BT.601 公式: Y = 0.299R + 0.587G + 0.114B
    r = frame[:, :, 0].astype(np.float32)
    g = frame[:, :, 1].astype(np.float32)
    b = frame[:, :, 2].astype(np.float32)
    y = (0.299 * r + 0.587 * g + 0.114 * b).clip(0, 255).astype(np.uint8)
    return y


def compute_psnr_y(original: np.ndarray, reconstructed: np.ndarray) -> float:
    """计算 Y 通道 PSNR（与 DCVC-RT 论文口径一致）。"""
    y_orig = rgb_to_y_channel(original)
    y_recon = rgb_to_y_channel(reconstructed)
    return float(peak_signal_noise_ratio(y_orig, y_recon, data_range=255))


def build_dcvc_config(
    frames_dir: Path, width: int, height: int, num_frames: int
) -> Path:
    """生成 DCVC-RT 所需的 JSON 配置文件。

    DCVC-RT 的路径构造逻辑:
        dataset_path = root_path + base_path
        src_path = dataset_path + seq_name
    因此 root_path = frames_dir.parent, base_path = ".", seq_name = "original"
    使得 src_path = frames_dir.parent / "original" = frames_dir
    """
    config = {
        "root_path": str(frames_dir.parent.resolve()),
        "test_classes": {
            "experiment": {
                "base_path": ".",
                "src_type": "png",
                "test": 1,
                "sequences": {
                    "original": {
                        "height": height,
                        "width": width,
                        "frames": num_frames,
                        "intra_period": -1,
                    }
                },
            }
        },
    }
    config_path = frames_dir.parent / "dcvc_config.json"
    config_path.write_text(json.dumps(config, indent=2))
    return config_path


def run_dcvc_encode_decode(config_path: Path) -> dict:
    """subprocess 调用 DCVC-RT test_video.py，返回其输出 JSON 内容。

    注意: 必须使用 DCVC 自带 venv 的 Python（含 PyTorch + CUDA 扩展），
    不能用 sys.executable（那是本项目的 venv）。
    """
    output_json_path = (RESULT_JSON.parent / "dcvc_raw_output.json").resolve()
    cmd = [
        str(DCVC_PYTHON),
        str(DCVC_DIR / "test_video.py"),
        "--test_config",
        str(config_path.resolve()),
        "--model_path_i",
        str(CKPT_I),
        "--model_path_p",
        str(CKPT_P),
        "--cuda",
        "True",
        "--write_stream",
        "True",
        "--save_decoded_frame",
        "True",
        "--stream_path",
        str(STREAM_DIR),
        "--output_path",
        str(output_json_path),
        "--rate_num",
        "1",
        "--qp_i",
        str(QP_I),
        "--qp_p",
        str(QP_P),
        "--force_intra_period",
        "-1",
        "--verbose",
        "2",
    ]

    print(f"运行 DCVC-RT: {' '.join(cmd)}")
    t_start = time.perf_counter()
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(DCVC_DIR))
    t_elapsed = time.perf_counter() - t_start

    if result.returncode != 0:
        print(
            f"DCVC-RT 失败:\nstdout:\n{result.stdout[-2000:]}\nstderr:\n{result.stderr[-2000:]}"
        )
        raise RuntimeError("DCVC-RT 编解码失败")

    # 解析 DCVC-RT 输出 JSON
    with open(output_json_path) as f:
        dcvc_output = json.load(f)

    return {"dcvc_output": dcvc_output, "wall_clock_seconds": t_elapsed}


def compute_bitrate(stream_dir: Path, duration_seconds: float) -> float:
    """计算编码输出的实际码率（Mbps）。"""
    total_bytes = 0
    for bin_file in stream_dir.rglob("*.bin"):
        total_bytes += bin_file.stat().st_size
    if total_bytes == 0:
        return 0.0
    return (total_bytes * 8) / (duration_seconds * 1_000_000)


def load_frames_as_ndarray(frames_dir: Path, count: int) -> list[np.ndarray]:
    """加载 PNG 帧为 ndarray 列表（HWC uint8）。"""
    frames = []
    for i in range(1, count + 1):
        path = frames_dir / f"im{i:05d}.png"
        if path.exists():
            img = Image.open(path)
            frames.append(np.array(img))
    return frames


def collect_dcvc_frames(
    dcvc_bin_dir: Path, dcvc_out_dir: Path, num_frames: int
) -> None:
    """将 DCVC 输出的还原帧从 bin 目录复制到统一输出目录。

    DCVC-RT 的 PNGWriter 将还原帧写入 stream_path/ds_name/im*.png。
    """
    dcvc_out_dir.mkdir(parents=True, exist_ok=True)
    # DCVC 输出帧在 stream_path/experiment/im*.png
    src_dir = dcvc_bin_dir / "experiment"
    for i in range(1, num_frames + 1):
        src = src_dir / f"im{i:05d}.png"
        if src.exists():
            shutil.copy2(src, dcvc_out_dir / f"im{i:05d}.png")


def extract_dcvc_metrics(dcvc_output: dict) -> dict:
    """从 DCVC-RT 输出 JSON 中提取关键指标。"""
    for ds_name in dcvc_output:
        for seq in dcvc_output[ds_name]:
            for rate_key in dcvc_output[ds_name][seq]:
                entry = dcvc_output[ds_name][seq][rate_key]
                return {
                    "psnr_rgb_mean": entry.get("ave_all_frame_psnr"),
                    "bpp_mean": entry.get("ave_all_frame_bpp"),
                    "test_time_seconds": entry.get("test_time"),
                    "i_frame_num": entry.get("i_frame_num"),
                    "p_frame_num": entry.get("p_frame_num"),
                    "avg_encoding_time": entry.get("avg_frame_encoding_time"),
                    "avg_decoding_time": entry.get("avg_frame_decoding_time"),
                }
    return {}


def main() -> None:
    # 从 PNG 文件名推断帧数和分辨率
    frame_files = sorted(FRAMES_DIR.glob("im*.png"))
    num_frames = len(frame_files)
    if num_frames == 0:
        print(f"错误: 在 {FRAMES_DIR} 中未找到 PNG 帧")
        return

    # 从第一帧获取分辨率
    first_frame = Image.open(frame_files[0])
    width, height = first_frame.size
    duration = num_frames / 6.0  # 6fps 视频

    print(f"输入: {num_frames} 帧, {width}x{height}, 6fps, 时长={duration:.1f}s")

    # 生成 DCVC 配置
    config_path = build_dcvc_config(FRAMES_DIR, width, height, num_frames)
    print(f"DCVC 配置: {config_path}")

    # 运行 DCVC-RT 编解码
    dcvc_result = run_dcvc_encode_decode(config_path)
    wall_clock = dcvc_result["wall_clock_seconds"]
    dcvc_metrics = extract_dcvc_metrics(dcvc_result["dcvc_output"])

    # 计算码率
    bitrate_mbps = compute_bitrate(STREAM_DIR, duration)
    print(f"DCVC-RT 码率: {bitrate_mbps:.3f} Mbps, 墙钟: {wall_clock:.2f}s")

    # 将 DCVC 还原帧复制到统一输出目录
    collect_dcvc_frames(STREAM_DIR, DCVC_OUT_DIR, num_frames)

    # 加载原始帧和还原帧
    orig_frames = load_frames_as_ndarray(FRAMES_DIR, num_frames)
    dcvc_frames = load_frames_as_ndarray(DCVC_OUT_DIR, num_frames)

    if len(dcvc_frames) == 0:
        print("警告: 未找到 DCVC-RT 还原帧，跳过质量评估")
        return

    print(f"加载帧: 原始={len(orig_frames)}, DCVC={len(dcvc_frames)}")

    # 质量评估——SSIM 和 LPIPS 用 evaluate_video（RGB 域），PSNR-Y 单独算
    print("运行质量评估...")
    eval_result = evaluate_video(
        orig_frames[: len(dcvc_frames)],
        dcvc_frames,
        with_lpips=True,
        with_clip=False,
        device="cuda",
    )

    # 补充 PSNR-Y（仅 Y 通道，与论文口径一致）
    psnr_y_values = [
        compute_psnr_y(o, d)
        for o, d in zip(orig_frames[: len(dcvc_frames)], dcvc_frames)
    ]
    psnr_y_mean = statistics.mean(psnr_y_values)
    psnr_y_std = statistics.pstdev(psnr_y_values) if len(psnr_y_values) > 1 else 0.0

    # 汇总输出
    output = {
        "codec": "DCVC-RT",
        "source": str(INPUT_MP4),
        "frame_count": len(dcvc_frames),
        "resolution": f"{width}x{height}",
        "duration_seconds": duration,
        "qp_i": QP_I,
        "qp_p": QP_P,
        "bitrate_mbps": round(bitrate_mbps, 4),
        "wall_clock_seconds": round(wall_clock, 3),
        "fps_overall": round(len(dcvc_frames) / wall_clock, 2),
        "dcvc_internal": dcvc_metrics,
        "summary": {
            "psnr_y": {"mean": round(psnr_y_mean, 4), "std": round(psnr_y_std, 4)},
            "ssim": eval_result["summary"]["ssim"],
            "lpips": eval_result["summary"]["lpips"],
        },
    }

    RESULT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(RESULT_JSON, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\n结果已保存到 {RESULT_JSON}")
    print(f"PSNR-Y: {psnr_y_mean:.2f} dB")
    print(f"SSIM: {eval_result['summary']['ssim']['mean']:.4f}")
    if eval_result["summary"]["lpips"]["mean"] is not None:
        print(f"LPIPS: {eval_result['summary']['lpips']['mean']:.4f}")


if __name__ == "__main__":
    main()
