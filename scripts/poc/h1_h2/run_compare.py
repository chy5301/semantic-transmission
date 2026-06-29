"""klein vs 现役 Z-Image+ControlNet 综合对比（质量 IoU + 速度）。

流程（按真实管道错峰，单卡串行）：
1. 复用 h1_vlm/prompts.json 的 VLM 逐帧 prompt（无则用 Qwen-VL 现生成）；
2. 全部帧过 klein（image=[Canny] 参考图，4 步，计时）；卸载；
3. 全部帧过 DiffusersReceiver = Z-Image-Turbo + ControlNet Union（原生 Canny ControlNet，9 步，计时）；卸载；
4. 出六联对比图（input | in-canny | klein | klein-canny | zimage | zimage-canny）+ 质量/速度综合表。

同一组帧 + 同一份 VLM prompt + 同一张 Canny，唯一变量 = 模型/结构条件机制。
"""

import json
import time
from pathlib import Path

import cv2
import imageio.v3 as iio
import numpy as np
import torch
from PIL import Image

from semantic_transmission.common.config import load_config
from semantic_transmission.common.model_loader import QwenVLModelLoader
from semantic_transmission.receiver.diffusers_receiver import DiffusersReceiver
from semantic_transmission.sender.qwen_vl_sender import QwenVLSender

from scripts.poc.h1_h2.frames import extract_frames, resize_frame
from scripts.poc.h1_h2.iou import recanny_iou
from scripts.poc.h1_h2.klein_loader import load_klein

_VID = "resources/test_videos/prepared/"
_PRIMARY = _VID + "C1X_20250721112728_10s_640x480_6fps.mp4"
_DIVERSITY = _VID + "C104_20260115093008_10s_640x480_6fps.mp4"
_SIZE = 512
_LOW, _HIGH, _DIL = 100, 200, 3
_OUT = Path("output/poc/h1-h2/compare")
_PROMPTS_CACHE = Path("output/poc/h1-h2/h1_vlm/prompts.json")


def _gather_frames():
    primary = [
        resize_frame(f, _SIZE) for f in extract_frames(_PRIMARY, list(range(26, 34)))
    ]
    diversity = [resize_frame(f, _SIZE) for f in extract_frames(_DIVERSITY, [25, 35])]
    return primary + diversity


def _canny(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
    edges = cv2.Canny(gray, _LOW, _HIGH)
    return edges


def _get_prompts(frames):
    if _PROMPTS_CACHE.is_file():
        prompts = json.loads(_PROMPTS_CACHE.read_text(encoding="utf-8"))
        if len(prompts) == len(frames):
            print(f"[prompt] 复用缓存 {_PROMPTS_CACHE}")
            return prompts
    print("[prompt] 现用 Qwen-VL 逐帧生成")
    cfg = load_config()
    sender = QwenVLSender(loader=QwenVLModelLoader(cfg.to_vlm_loader_config()))
    prompts = [sender.describe(f).text for f in frames]
    sender.unload()
    torch.cuda.empty_cache()
    return prompts


def _label(img, text):
    if img.ndim == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)
    out = img.copy()
    cv2.putText(
        out, text, (4, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1, cv2.LINE_AA
    )
    return out


def main() -> None:
    _OUT.mkdir(parents=True, exist_ok=True)
    frames = _gather_frames()
    prompts = _get_prompts(frames)
    cannies = [_canny(f) for f in frames]

    # 阶段 klein（4 步，bf16+offload，image=[Canny]）
    rows = []
    klein_pipe = load_klein()
    klein_imgs = []
    for i, (frame, prompt, edges) in enumerate(zip(frames, prompts, cannies)):
        cond = Image.fromarray(cv2.cvtColor(edges, cv2.COLOR_GRAY2RGB))
        t0 = time.perf_counter()
        img = klein_pipe(
            prompt=prompt,
            image=[cond],
            guidance_scale=1.0,
            num_inference_steps=4,
            height=_SIZE,
            width=_SIZE,
            generator=torch.Generator("cpu").manual_seed(0),
        ).images[0]
        dt = time.perf_counter() - t0
        arr = np.asarray(img, dtype=np.uint8)
        klein_imgs.append(arr)
        rows.append(
            {
                "index": i,
                "klein_iou": recanny_iou(arr, edges, _LOW, _HIGH, _DIL),
                "klein_s": dt,
            }
        )
        print(f"[klein] frame {i}: IoU={rows[i]['klein_iou']:.3f} {dt:.1f}s")
    del klein_pipe
    torch.cuda.empty_cache()

    # 阶段 Z-Image + ControlNet（现役接收端，9 步，原生 Canny ControlNet）
    receiver = DiffusersReceiver()
    receiver.load()
    zimg_imgs = []
    for i, (prompt, edges) in enumerate(zip(prompts, cannies)):
        cond = Image.fromarray(cv2.cvtColor(edges, cv2.COLOR_GRAY2RGB))
        t0 = time.perf_counter()
        img = receiver.process(cond, prompt, seed=0)
        dt = time.perf_counter() - t0
        arr = np.asarray(img.convert("RGB"), dtype=np.uint8)
        if arr.shape[:2] != (_SIZE, _SIZE):
            arr = cv2.resize(arr, (_SIZE, _SIZE))
        zimg_imgs.append(arr)
        rows[i]["zimage_iou"] = recanny_iou(arr, edges, _LOW, _HIGH, _DIL)
        rows[i]["zimage_s"] = dt
        print(f"[zimage] frame {i}: IoU={rows[i]['zimage_iou']:.3f} {dt:.1f}s")
    receiver.unload()

    # 六联对比图
    for i, (frame, edges) in enumerate(zip(frames, cannies)):
        k_canny = cv2.Canny(
            cv2.cvtColor(klein_imgs[i], cv2.COLOR_RGB2GRAY), _LOW, _HIGH
        )
        z_canny = cv2.Canny(cv2.cvtColor(zimg_imgs[i], cv2.COLOR_RGB2GRAY), _LOW, _HIGH)
        panels = [
            _label(frame, "input"),
            _label(edges, "in-canny"),
            _label(
                klein_imgs[i],
                f"klein {rows[i]['klein_iou']:.2f}/{rows[i]['klein_s']:.0f}s",
            ),
            _label(k_canny, "klein-canny"),
            _label(
                zimg_imgs[i],
                f"zimage {rows[i]['zimage_iou']:.2f}/{rows[i]['zimage_s']:.0f}s",
            ),
            _label(z_canny, "zimage-canny"),
        ]
        iio.imwrite(_OUT / f"grid_frame{i:02d}.png", np.concatenate(panels, axis=1))

    # 综合表
    ki = np.mean([r["klein_iou"] for r in rows])
    zi = np.mean([r["zimage_iou"] for r in rows])
    ks = np.mean([r["klein_s"] for r in rows])
    zs = np.mean([r["zimage_s"] for r in rows])
    summary = {
        "rows": rows,
        "klein_iou_mean": float(ki),
        "zimage_iou_mean": float(zi),
        "klein_s_mean": float(ks),
        "zimage_s_mean": float(zs),
    }
    (_OUT / "compare.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    lines = [
        "| frame | klein IoU | klein s | zimage IoU | zimage s |",
        "|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r['index']} | {r['klein_iou']:.3f} | {r['klein_s']:.1f} | {r['zimage_iou']:.3f} | {r['zimage_s']:.1f} |"
        )
    lines.append(
        f"| **均值** | **{ki:.3f}** | **{ks:.1f}** | **{zi:.3f}** | **{zs:.1f}** |"
    )
    lines.append("")
    lines.append(
        "> klein=bf16+offload 4步（fp8 加载受阻）；zimage=Z-Image-Turbo GGUF Q8 + ControlNet Union 9步常驻。"
    )
    (_OUT / "compare.md").write_text("\n".join(lines), encoding="utf-8")
    print(
        f"COMPARE_DONE klein_iou={ki:.4f} zimage_iou={zi:.4f} klein_s={ks:.1f} zimage_s={zs:.1f}"
    )
    print(f"产物 -> {_OUT}")


if __name__ == "__main__":
    main()
