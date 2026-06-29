"""H1 端到端：抽帧 → klein → qwen → 组装对比产物。

抽帧方案见 spec §4.1：主测 C1X_112728 连续 8 帧 + C104_093008 多样性 2 帧。
"""

from pathlib import Path

import imageio.v3 as iio

from scripts.poc.h1_h2.frames import extract_frames, resize_frame
from scripts.poc.h1_h2.klein_loader import load_klein
from scripts.poc.h1_h2.klein_runner import run_klein_h1
from scripts.poc.h1_h2.qwen_loader import load_qwen_controlnet
from scripts.poc.h1_h2.qwen_runner import run_qwen_h1
from scripts.poc.h1_h2.report import (
    comparison_grid,
    consecutive_strip,
    write_iou_table,
)

_VID_DIR = Path("resources/test_videos/prepared")
_PRIMARY = _VID_DIR / "C1X_20250721112728_10s_640x480_6fps.mp4"
_DIVERSITY = _VID_DIR / "C104_20260115093008_10s_640x480_6fps.mp4"
_SIZE = 512
_OUT = Path("output/poc/h1-h2/h1")


def _gather_frames():
    primary = [
        resize_frame(f, _SIZE) for f in extract_frames(_PRIMARY, list(range(26, 34)))
    ]
    diversity = [resize_frame(f, _SIZE) for f in extract_frames(_DIVERSITY, [25, 35])]
    return primary + diversity


def main() -> None:
    frames = _gather_frames()
    prompts = ["a real driving scene, road and vehicles, daylight"] * len(frames)

    # klein 臂（跑完卸载再上 qwen，单卡串行）
    klein_pipe = load_klein()
    klein_res = run_klein_h1(klein_pipe, frames, prompts, _SIZE, _OUT / "klein")
    del klein_pipe
    import torch

    torch.cuda.empty_cache()

    # qwen 臂（加载失败则记空，报告标注对照缺失）
    try:
        qwen_pipe = load_qwen_controlnet()
        qwen_res = run_qwen_h1(qwen_pipe, frames, prompts, _SIZE, _OUT / "qwen")
    except Exception as e:  # noqa: BLE001 —— spike，记录失败结论而非中断
        print(f"[qwen] 加载/运行失败，H1 以 klein 单臂交付：{e}")
        qwen_res = []

    summary = write_iou_table(klein_res, qwen_res, _OUT)
    print(
        f"klein 均值 IoU={summary['klein_mean']:.3f} / "
        f"qwen 均值 IoU={summary['qwen_mean']:.3f}"
    )

    # 对比网格 + 连续帧条
    for i, kr in enumerate(klein_res):
        qr = (
            qwen_res[i]
            if i < len(qwen_res)
            else {"iou": float("nan"), "output_path": None, "output_canny_path": None}
        )
        frame = iio.imread(_OUT / "klein" / f"frame{i:02d}_input.png")
        in_canny = iio.imread(kr["input_canny_path"])
        k_img = iio.imread(kr["output_path"])
        k_canny = iio.imread(kr["output_canny_path"])
        q_img = iio.imread(qr["output_path"]) if qr["output_path"] else frame * 0
        q_canny = (
            iio.imread(qr["output_canny_path"])
            if qr["output_canny_path"]
            else in_canny * 0
        )
        grid = comparison_grid(
            frame, in_canny, k_img, k_canny, q_img, q_canny, kr["iou"], qr["iou"]
        )
        iio.imwrite(_OUT / f"grid_frame{i:02d}.png", grid)

    # 主测连续 8 帧的 klein vs qwen 对比条
    iio.imwrite(
        _OUT / "strip_klein.png",
        consecutive_strip([iio.imread(r["output_path"]) for r in klein_res[:8]]),
    )
    if qwen_res:
        iio.imwrite(
            _OUT / "strip_qwen.png",
            consecutive_strip([iio.imread(r["output_path"]) for r in qwen_res[:8]]),
        )
    print(f"产物落盘 -> {_OUT}")


if __name__ == "__main__":
    main()
