"""H1 复测：用 Qwen-VL 逐帧生成的 prompt 重跑 klein 臂。

动机：实际管道里 prompt 是主信息源，固定通用 prompt 会低估 klein。本脚本按真实
管道错峰——VLM 逐帧描述 → 卸载 VLM → 加载 klein 生成，排除"通用 prompt"混淆变量。
输出独立目录 output/poc/h1-h2/h1_vlm/，保留原固定-prompt 结果（h1/）供对比。
"""

import json
from pathlib import Path

import imageio.v3 as iio

from semantic_transmission.common.config import load_config
from semantic_transmission.common.model_loader import QwenVLModelLoader
from semantic_transmission.sender.qwen_vl_sender import QwenVLSender

from scripts.poc.h1_h2.frames import extract_frames, resize_frame
from scripts.poc.h1_h2.klein_loader import load_klein
from scripts.poc.h1_h2.klein_runner import run_klein_h1
from scripts.poc.h1_h2.report import comparison_grid, consecutive_strip, write_iou_table

_VID = "resources/test_videos/prepared/"
_PRIMARY = _VID + "C1X_20250721112728_10s_640x480_6fps.mp4"
_DIVERSITY = _VID + "C104_20260115093008_10s_640x480_6fps.mp4"
_SIZE = 512
_OUT = Path("output/poc/h1-h2/h1_vlm")


def _gather_frames():
    primary = [
        resize_frame(f, _SIZE) for f in extract_frames(_PRIMARY, list(range(26, 34)))
    ]
    diversity = [resize_frame(f, _SIZE) for f in extract_frames(_DIVERSITY, [25, 35])]
    return primary + diversity


def main() -> None:
    import torch

    _OUT.mkdir(parents=True, exist_ok=True)
    frames = _gather_frames()

    # 阶段一：VLM 逐帧生成 prompt（真实管道的主信息源）
    cfg = load_config()
    sender = QwenVLSender(loader=QwenVLModelLoader(cfg.to_vlm_loader_config()))
    prompts: list[str] = []
    for i, frame in enumerate(frames):
        text = sender.describe(frame).text
        prompts.append(text)
        print(f"[vlm] frame {i}: {text[:80]}...")
    sender.unload()
    torch.cuda.empty_cache()
    (_OUT / "prompts.json").write_text(
        json.dumps(prompts, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # 阶段二：klein 用 VLM prompt 逐帧生成
    klein_pipe = load_klein()
    klein_res = run_klein_h1(klein_pipe, frames, prompts, _SIZE, _OUT / "klein")
    summary = write_iou_table(klein_res, [], _OUT)
    print(f"[VLM-prompt] klein 均值 IoU={summary['klein_mean']:.4f}")

    # 对比网格（qwen 留空）+ 连续帧条
    for i, kr in enumerate(klein_res):
        frame = iio.imread(_OUT / "klein" / f"frame{i:02d}_input.png")
        in_canny = iio.imread(kr["input_canny_path"])
        k_img = iio.imread(kr["output_path"])
        k_canny = iio.imread(kr["output_canny_path"])
        grid = comparison_grid(
            frame,
            in_canny,
            k_img,
            k_canny,
            frame * 0,
            in_canny * 0,
            kr["iou"],
            float("nan"),
        )
        iio.imwrite(_OUT / f"grid_frame{i:02d}.png", grid)
    iio.imwrite(
        _OUT / "strip_klein.png",
        consecutive_strip([iio.imread(r["output_path"]) for r in klein_res[:8]]),
    )
    print(f"产物落盘 -> {_OUT}")


if __name__ == "__main__":
    main()
