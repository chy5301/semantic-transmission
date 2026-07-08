"""relay 时序输出 vs 单机 klein 基线的逐帧 parity 对比。

用途：阶段 3（二）验收——同 seed / prompt / policy 下，双机 relay 时序输出应与
单机 ``video --backend klein`` 基线逐帧近乎一致，以证明"把 _run_temporal 切一刀
放到网络两侧"没切错。关键帧（透传）MAE 应≈0（PNG 无损、整帧往返精确）；生成帧
因同 seed/prompt/参考帧链应逐帧一致、平均 MAE 接近 0。

用法：
    uv run python scripts/poc/relay_parity_compare.py <relay_out.mp4> <baseline.mp4>
"""

import sys

import numpy as np

from semantic_transmission.common.video_io import read_frames


def main(a_path: str, b_path: str) -> None:
    a, _ = read_frames(a_path)
    b, _ = read_frames(b_path)
    if len(a) != len(b):
        raise SystemExit(f"帧数不一致: {len(a)} vs {len(b)}")

    diffs: list[float] = []
    for i, (x, y) in enumerate(zip(a, b)):
        if x.shape != y.shape:
            raise SystemExit(f"帧 {i} 尺寸不一致: {x.shape} vs {y.shape}")
        diffs.append(float(np.mean(np.abs(x.astype("int16") - y.astype("int16")))))

    print(f"帧数={len(a)} 平均MAE={np.mean(diffs):.3f} 最大MAE={np.max(diffs):.3f}")
    print("逐帧 MAE:", [round(d, 2) for d in diffs])


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(
            "用法: uv run python scripts/poc/relay_parity_compare.py "
            "<relay_out.mp4> <baseline.mp4>"
        )
    main(sys.argv[1], sys.argv[2])
