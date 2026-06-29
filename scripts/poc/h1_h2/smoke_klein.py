"""klein 加载 + 单图生成 smoke。通过 = 出一张非空 512² 图。"""

from pathlib import Path

import imageio.v3 as iio
import numpy as np
import torch

from scripts.poc.h1_h2.klein_loader import load_klein

OUT = Path("output/poc/h1-h2/smoke")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    pipe = load_klein()
    img = pipe(
        prompt="a desert road with a vehicle, clear daylight",
        guidance_scale=1.0,
        num_inference_steps=4,
        height=512,
        width=512,
        generator=torch.Generator("cpu").manual_seed(0),
    ).images[0]
    arr = np.asarray(img)
    assert arr.shape == (512, 512, 3), f"意外尺寸 {arr.shape}"
    assert arr.std() > 1.0, "输出近乎纯色，生成可能失败"
    iio.imwrite(OUT / "smoke_klein.png", arr)
    print(f"smoke OK -> {OUT / 'smoke_klein.png'}")


if __name__ == "__main__":
    main()
