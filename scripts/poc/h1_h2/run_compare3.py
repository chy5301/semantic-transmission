"""三方综合对比：klein vs 现役 Z-Image+ControlNet vs qwen+InstantX ControlNet。

同一组帧 + 同一份 VLM prompt + 同一张 Canny，唯一变量 = 模型/结构条件机制。
单卡串行错峰：klein（4步,image=参考图）→ Z-Image（9步,原生ControlNet）→ qwen（30步,全驻）。
输出质量(IoU)+速度(s/帧)综合表 + 五联对比图（input|in-canny|klein|zimage|qwen）。
"""

import json
import time
from pathlib import Path

import cv2
import imageio.v3 as iio
import numpy as np
import torch
from PIL import Image

from semantic_transmission.receiver.diffusers_receiver import DiffusersReceiver

from scripts.poc.h1_h2.frames import extract_frames, resize_frame
from scripts.poc.h1_h2.iou import recanny_iou
from scripts.poc.h1_h2.klein_loader import load_klein
from scripts.poc.h1_h2.qwen_resident import run_qwen_resident

_VID = "resources/test_videos/prepared/"
_PRIMARY = _VID + "C1X_20250721112728_10s_640x480_6fps.mp4"
_DIVERSITY = _VID + "C104_20260115093008_10s_640x480_6fps.mp4"
_SIZE = 512
_LOW, _HIGH, _DIL = 100, 200, 3
_OUT = Path("output/poc/h1-h2/compare3")
_PROMPTS = Path("output/poc/h1-h2/h1_vlm/prompts.json")


def _gather():
    primary = [
        resize_frame(f, _SIZE) for f in extract_frames(_PRIMARY, list(range(26, 34)))
    ]
    diversity = [resize_frame(f, _SIZE) for f in extract_frames(_DIVERSITY, [25, 35])]
    return primary + diversity


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
    frames = _gather()
    prompts = json.loads(_PROMPTS.read_text(encoding="utf-8"))
    cannies = [
        cv2.Canny(cv2.cvtColor(f, cv2.COLOR_RGB2GRAY), _LOW, _HIGH) for f in frames
    ]
    rows = [{"index": i} for i in range(len(frames))]

    # 臂 1：klein（4 步，Canny 当参考图）
    kp = load_klein()
    klein_imgs = []
    for i, (frame, prompt, edges) in enumerate(zip(frames, prompts, cannies)):
        cond = Image.fromarray(cv2.cvtColor(edges, cv2.COLOR_GRAY2RGB))
        t0 = time.perf_counter()
        img = kp(
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
        iio.imwrite(_OUT / f"frame{i:02d}_klein.png", arr)
        rows[i]["klein_iou"] = recanny_iou(arr, edges, _LOW, _HIGH, _DIL)
        rows[i]["klein_s"] = dt
        print(f"[klein] {i}: IoU={rows[i]['klein_iou']:.3f} {dt:.1f}s")
    del kp
    torch.cuda.empty_cache()

    # 臂 2：Z-Image + ControlNet（现役，9 步，原生 Canny ControlNet）
    rec = DiffusersReceiver()
    rec.load()
    zimg_imgs = []
    for i, (prompt, edges) in enumerate(zip(prompts, cannies)):
        cond = Image.fromarray(cv2.cvtColor(edges, cv2.COLOR_GRAY2RGB))
        t0 = time.perf_counter()
        img = rec.process(cond, prompt, seed=0)
        dt = time.perf_counter() - t0
        arr = np.asarray(img.convert("RGB"), dtype=np.uint8)
        if arr.shape[:2] != (_SIZE, _SIZE):
            arr = cv2.resize(arr, (_SIZE, _SIZE))
        zimg_imgs.append(arr)
        iio.imwrite(_OUT / f"frame{i:02d}_zimage.png", arr)
        rows[i]["zimage_iou"] = recanny_iou(arr, edges, _LOW, _HIGH, _DIL)
        rows[i]["zimage_s"] = dt
        print(f"[zimage] {i}: IoU={rows[i]['zimage_iou']:.3f} {dt:.1f}s")
    rec.unload()
    torch.cuda.empty_cache()

    # 臂 3：qwen + InstantX（30 步，全驻预编码）
    qrows = run_qwen_resident(frames, prompts, cannies, _SIZE, _OUT / "qwen")
    qwen_imgs = [iio.imread(r["output_path"]) for r in qrows]
    for i, qr in enumerate(qrows):
        rows[i]["qwen_iou"] = qr["iou"]
        rows[i]["qwen_s"] = qr["s"]

    # 五联对比图
    for i, (frame, edges) in enumerate(zip(frames, cannies)):
        panels = [
            _label(frame, "input"),
            _label(edges, "in-canny"),
            _label(
                klein_imgs[i],
                f"klein {rows[i]['klein_iou']:.2f}/{rows[i]['klein_s']:.0f}s",
            ),
            _label(
                zimg_imgs[i],
                f"zimage {rows[i]['zimage_iou']:.2f}/{rows[i]['zimage_s']:.0f}s",
            ),
            _label(
                qwen_imgs[i], f"qwen {rows[i]['qwen_iou']:.2f}/{rows[i]['qwen_s']:.0f}s"
            ),
        ]
        iio.imwrite(_OUT / f"grid_frame{i:02d}.png", np.concatenate(panels, axis=1))

    # 综合表
    def mean(k):
        return float(np.mean([r[k] for r in rows]))

    summary = {"rows": rows}
    for k in ("klein_iou", "zimage_iou", "qwen_iou", "klein_s", "zimage_s", "qwen_s"):
        summary[k + "_mean"] = mean(k)
    (_OUT / "compare3.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    lines = [
        "| frame | klein IoU | zimage IoU | qwen IoU | klein s | zimage s | qwen s |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r['index']} | {r['klein_iou']:.3f} | {r['zimage_iou']:.3f} | {r['qwen_iou']:.3f} "
            f"| {r['klein_s']:.1f} | {r['zimage_s']:.1f} | {r['qwen_s']:.1f} |"
        )
    lines.append(
        f"| **均值** | **{mean('klein_iou'):.3f}** | **{mean('zimage_iou'):.3f}** | **{mean('qwen_iou'):.3f}** "
        f"| **{mean('klein_s'):.1f}** | **{mean('zimage_s'):.1f}** | **{mean('qwen_s'):.1f}** |"
    )
    lines.append("")
    lines.append(
        "> klein=bf16+offload 4步(image=Canny参考图)；zimage=Z-Image-Turbo GGUF Q8+ControlNet 9步常驻；"
        "qwen=Qwen-Image GGUF Q4+InstantX ControlNet 30步全驻(预编码)。"
    )
    (_OUT / "compare3.md").write_text("\n".join(lines), encoding="utf-8")
    print(
        f"COMPARE3_DONE klein_iou={mean('klein_iou'):.4f} zimage_iou={mean('zimage_iou'):.4f} "
        f"qwen_iou={mean('qwen_iou'):.4f} | klein_s={mean('klein_s'):.1f} zimage_s={mean('zimage_s'):.1f} qwen_s={mean('qwen_s'):.1f}"
    )
    print(f"产物 -> {_OUT}")


if __name__ == "__main__":
    main()
