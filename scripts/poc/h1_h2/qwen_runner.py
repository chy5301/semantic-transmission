"""Qwen+InstantX H1：Canny 走 ControlNet，逐帧生成并算 IoU。"""

from pathlib import Path

import cv2
import imageio.v3 as iio
import numpy as np
import torch
from PIL import Image

from scripts.poc.h1_h2.iou import recanny_iou

_CANNY_LOW, _CANNY_HIGH, _IOU_DILATION = 100, 200, 3
_CN_SCALE = 1.0


def run_qwen_h1(pipe, frames, prompts, size, out_dir: Path) -> list[dict]:
    out_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict] = []
    for i, (frame, prompt) in enumerate(zip(frames, prompts, strict=True)):
        gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        edges = cv2.Canny(gray, _CANNY_LOW, _CANNY_HIGH)
        cond = Image.fromarray(cv2.cvtColor(edges, cv2.COLOR_GRAY2RGB))
        gen = pipe(
            prompt=prompt + ", TEXT",  # 官方建议 Canny prompt 含 'TEXT'
            negative_prompt=" ",
            control_image=cond,
            controlnet_conditioning_scale=_CN_SCALE,
            width=size,
            height=size,
            num_inference_steps=30,
            true_cfg_scale=4.0,
            generator=torch.Generator(device="cuda").manual_seed(42),
        ).images[0]
        gen_arr = np.asarray(gen, dtype=np.uint8)
        iou = recanny_iou(gen_arr, edges, _CANNY_LOW, _CANNY_HIGH, _IOU_DILATION)
        op = out_dir / f"frame{i:02d}_qwen.png"
        ocp = out_dir / f"frame{i:02d}_qwen_canny.png"
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
                "output_path": str(op),
                "output_canny_path": str(ocp),
            }
        )
        print(f"[qwen] frame {i}: IoU={iou:.3f}")
    return results
