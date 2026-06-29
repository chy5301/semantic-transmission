"""klein H1：Canny 当参考图，逐帧生成并算 IoU。"""

from pathlib import Path

import cv2
import imageio.v3 as iio
import numpy as np
import torch
from numpy.typing import NDArray
from PIL import Image

from scripts.poc.h1_h2.iou import recanny_iou

_CANNY_LOW, _CANNY_HIGH = 100, 200
_IOU_DILATION = 3


def _canny_rgb(
    frame: NDArray[np.uint8],
) -> tuple[NDArray[np.uint8], NDArray[np.uint8]]:
    gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
    edges = cv2.Canny(gray, _CANNY_LOW, _CANNY_HIGH)
    rgb = cv2.cvtColor(edges, cv2.COLOR_GRAY2RGB)
    return edges, rgb


def run_klein_h1(pipe, frames, prompts, size, out_dir: Path) -> list[dict]:
    out_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict] = []
    for i, (frame, prompt) in enumerate(zip(frames, prompts, strict=True)):
        edges, edges_rgb = _canny_rgb(frame)
        cond = Image.fromarray(edges_rgb)
        gen = pipe(
            prompt=prompt,
            image=[cond],
            guidance_scale=1.0,
            num_inference_steps=4,
            height=size,
            width=size,
            generator=torch.Generator("cpu").manual_seed(0),
        ).images[0]
        gen_arr = np.asarray(gen, dtype=np.uint8)
        iou = recanny_iou(gen_arr, edges, _CANNY_LOW, _CANNY_HIGH, _IOU_DILATION)

        ip = out_dir / f"frame{i:02d}_input.png"
        cp = out_dir / f"frame{i:02d}_input_canny.png"
        op = out_dir / f"frame{i:02d}_klein.png"
        ocp = out_dir / f"frame{i:02d}_klein_canny.png"
        iio.imwrite(ip, frame)
        iio.imwrite(cp, edges)
        iio.imwrite(op, gen_arr)
        iio.imwrite(
            ocp,
            cv2.Canny(
                cv2.cvtColor(gen_arr, cv2.COLOR_RGB2GRAY), _CANNY_LOW, _CANNY_HIGH
            ),
        )
        results.append(
            {
                "index": i,
                "iou": iou,
                "input_canny_path": str(cp),
                "output_path": str(op),
                "output_canny_path": str(ocp),
            }
        )
        print(f"[klein] frame {i}: IoU={iou:.3f}")
    return results
