"""H1 对比产物组装：六联图、连续帧条、IoU 表。"""

import json
from pathlib import Path

import cv2
import numpy as np
from numpy.typing import NDArray


def _to_rgb(img: NDArray) -> NDArray[np.uint8]:
    if img.ndim == 2:
        return cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)
    return img.astype(np.uint8)


def _label(img: NDArray[np.uint8], text: str) -> NDArray[np.uint8]:
    out = img.copy()
    cv2.putText(
        out, text, (4, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1, cv2.LINE_AA
    )
    return out


def consecutive_strip(images: list[NDArray]) -> NDArray[np.uint8]:
    return np.concatenate([_to_rgb(im) for im in images], axis=1)


def comparison_grid(
    frame,
    input_canny,
    klein_img,
    klein_canny,
    qwen_img,
    qwen_canny,
    iou_klein,
    iou_qwen,
) -> NDArray[np.uint8]:
    panels = [
        _label(_to_rgb(frame), "input"),
        _label(_to_rgb(input_canny), "in-canny"),
        _label(_to_rgb(klein_img), f"klein {iou_klein:.2f}"),
        _label(_to_rgb(klein_canny), "klein-canny"),
        _label(_to_rgb(qwen_img), f"qwen {iou_qwen:.2f}"),
        _label(_to_rgb(qwen_canny), "qwen-canny"),
    ]
    h = min(p.shape[0] for p in panels)
    panels = [cv2.resize(p, (p.shape[1] * h // p.shape[0], h)) for p in panels]
    return np.concatenate(panels, axis=1)


def write_iou_table(klein_res: list[dict], qwen_res: list[dict], out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    k_mean = float(np.mean([r["iou"] for r in klein_res])) if klein_res else 0.0
    q_mean = float(np.mean([r["iou"] for r in qwen_res])) if qwen_res else 0.0
    summary = {
        "klein_mean": k_mean,
        "qwen_mean": q_mean,
        "klein": klein_res,
        "qwen": qwen_res,
    }
    (out_dir / "iou_table.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    lines = ["| frame | klein IoU | qwen IoU |", "|---|---|---|"]
    qmap = {r["index"]: r["iou"] for r in qwen_res}
    for r in klein_res:
        lines.append(
            f"| {r['index']} | {r['iou']:.3f} | {qmap.get(r['index'], float('nan')):.3f} |"
        )
    lines.append(f"| **均值** | **{k_mean:.3f}** | **{q_mean:.3f}** |")
    (out_dir / "iou_table.md").write_text("\n".join(lines), encoding="utf-8")
    return summary
