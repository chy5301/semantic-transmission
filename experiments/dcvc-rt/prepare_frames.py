"""从 prepared mp4 提取 PNG 帧序列，供 DCVC-RT 和 H.265 两条管线共用。"""

from __future__ import annotations

import shutil
from pathlib import Path

from semantic_transmission.common.video_io import read_frames

# ── 配置 ──────────────────────────────────────────────
INPUT_MP4 = Path("resources/test_videos/prepared/C104_20260115121711_10s_640x480_6fps.mp4")
OUTPUT_DIR = Path("experiments/dcvc-rt/results/frames/original")
# ─────────────────────────────────────────────────────


def main() -> None:
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True)

    frames, meta = read_frames(str(INPUT_MP4))
    print(f"读取 {len(frames)} 帧，分辨率 {meta.width}x{meta.height}，fps={meta.fps}")

    for i, frame in enumerate(frames, start=1):
        # DCVC-RT PNG 模式要求 im{i}.png 或 im{i:05d}.png 命名
        out_path = OUTPUT_DIR / f"im{i:05d}.png"

        from PIL import Image
        Image.fromarray(frame).save(out_path)

    print(f"已保存 {len(frames)} 帧到 {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
