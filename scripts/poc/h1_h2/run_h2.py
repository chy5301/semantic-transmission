"""H2：klein 速度三档（512/768/1024）+ 显存峰值。

注：因 fp8 单文件加载受阻（见 klein_loader docstring），本测为 bf16 4 步速度，
官方「<1s」的 fp8 前提未验，结论须据此标注。
"""

import json
import time
from pathlib import Path

import torch

from scripts.poc.h1_h2.klein_loader import load_klein

_RESOLUTIONS = [512, 768, 1024]
_WARMUP, _RUNS = 1, 5
_OUT = Path("output/poc/h1-h2/h2")


def main() -> None:
    _OUT.mkdir(parents=True, exist_ok=True)
    pipe = load_klein()
    rows = []
    for size in _RESOLUTIONS:
        torch.cuda.reset_peak_memory_stats()
        times = []
        for r in range(_WARMUP + _RUNS):
            t0 = time.perf_counter()
            pipe(
                prompt="a desert road with vehicles",
                guidance_scale=1.0,
                num_inference_steps=4,
                height=size,
                width=size,
                generator=torch.Generator("cpu").manual_seed(r),
            )
            torch.cuda.synchronize()
            dt = time.perf_counter() - t0
            if r >= _WARMUP:  # 排冷加载
                times.append(dt)
        times.sort()
        median = times[len(times) // 2]
        peak_gb = torch.cuda.max_memory_allocated() / 1e9
        rows.append({"resolution": size, "median_s": median, "peak_vram_gb": peak_gb})
        print(f"[H2] {size}^2: 中位 {median:.2f}s/帧, 峰值显存 {peak_gb:.1f}GB")

    (_OUT / "speed.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    lines = ["| 分辨率 | 中位 s/帧 | 峰值显存 GB |", "|---|---|---|"]
    lines += [
        f"| {r['resolution']}^2 | {r['median_s']:.2f} | {r['peak_vram_gb']:.1f} |"
        for r in rows
    ]
    (_OUT / "speed.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"产物 -> {_OUT}")


if __name__ == "__main__":
    main()
