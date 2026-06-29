"""qwen+InstantX 全驻方案：预编码 prompt → 释放文本编码器 → transformer+controlnet+vae 驻 cuda。

绕开三条 offload 死路（model_cpu_offload 的 RoPE 设备不匹配 / sequential_cpu_offload 与
GGUF 不兼容 / 全量 .to(cuda) OOM）：文本编码器(Qwen2.5-VL ~16GB)是唯一装不下的大头，
编完即释放，剩下 GGUF transformer(13GB)+controlnet(3.5GB)+vae 全驻 ~17GB，24GB 够。
"""

import os
import sys
import time
from pathlib import Path

import cv2
import imageio.v3 as iio
import numpy as np
import torch
from diffusers import GGUFQuantizationConfig, QwenImageTransformer2DModel
from PIL import Image

from scripts.poc.h1_h2.iou import recanny_iou

_CACHE = Path(os.environ.get("MODEL_CACHE_DIR", "D:/Downloads/Models"))
QWEN_BASE = _CACHE / "Qwen" / "Qwen-Image"
INSTANTX_DIR = _CACHE / "InstantX" / "Qwen-Image-ControlNet-Union"
GGUF_PATH = _CACHE / "QuantStack" / "Qwen-Image-GGUF" / "Qwen_Image-Q4_K_M.gguf"
sys.path.insert(0, str(INSTANTX_DIR))

_LOW, _HIGH, _DIL = 100, 200, 3


def _manual_encode(pipe, prompt, device, dtype):
    """复刻 pipeline._get_qwen_prompt_embeds，但显式用传入 device（绕开 self.device）。"""
    template = pipe.prompt_template_encode
    drop_idx = pipe.prompt_template_encode_start_idx
    txt = [template.format(prompt)]
    toks = pipe.tokenizer(
        txt,
        max_length=pipe.tokenizer_max_length + drop_idx,
        padding=True,
        truncation=True,
        return_tensors="pt",
    ).to(device)
    ehs = pipe.text_encoder(
        input_ids=toks.input_ids,
        attention_mask=toks.attention_mask,
        output_hidden_states=True,
    )
    hidden = ehs.hidden_states[-1]
    bool_mask = toks.attention_mask.bool()
    valid = bool_mask.sum(dim=1)
    selected = hidden[bool_mask]
    split = torch.split(selected, valid.tolist(), dim=0)
    split = [e[drop_idx:] for e in split]
    attn = [torch.ones(e.size(0), dtype=torch.long, device=e.device) for e in split]
    msl = max(e.size(0) for e in split)
    pe = torch.stack(
        [torch.cat([u, u.new_zeros(msl - u.size(0), u.size(1))]) for u in split]
    )
    pm = torch.stack([torch.cat([u, u.new_zeros(msl - u.size(0))]) for u in attn])
    return pe.to(dtype=dtype, device=device), pm.to(device)


def run_qwen_resident(frames, prompts, cannies, size, out_dir: Path) -> list[dict]:
    from controlnet_qwenimage import QwenImageControlNetModel  # type: ignore
    from pipeline_qwenimage_controlnet import QwenImageControlNetPipeline  # type: ignore

    out_dir.mkdir(parents=True, exist_ok=True)
    controlnet = QwenImageControlNetModel.from_pretrained(
        str(INSTANTX_DIR), torch_dtype=torch.bfloat16
    )
    transformer = QwenImageTransformer2DModel.from_single_file(
        str(GGUF_PATH),
        quantization_config=GGUFQuantizationConfig(compute_dtype=torch.bfloat16),
        torch_dtype=torch.bfloat16,
        config=str(QWEN_BASE / "transformer"),
    )
    pipe = QwenImageControlNetPipeline.from_pretrained(
        str(QWEN_BASE),
        controlnet=controlnet,
        transformer=transformer,
        torch_dtype=torch.bfloat16,
        local_files_only=True,
    )

    # 阶段一：仅文本编码器驻 cuda，预编码所有 prompt + 负向 " "
    dev = torch.device("cuda")
    pipe.text_encoder.to(dev)
    with torch.inference_mode():
        embeds = [_manual_encode(pipe, p, dev, torch.bfloat16) for p in prompts]
        neg_pe, neg_pm = _manual_encode(pipe, " ", dev, torch.bfloat16)
    embeds = [(pe.cpu(), pm.cpu()) for pe, pm in embeds]
    neg_pe, neg_pm = neg_pe.cpu(), neg_pm.cpu()
    pipe.text_encoder.to("cpu")
    del pipe.text_encoder
    pipe.text_encoder = None
    torch.cuda.empty_cache()

    # 阶段二：transformer+controlnet+vae 驻 cuda，逐帧用预编码 embeds 生成
    pipe.transformer.to(dev)
    pipe.controlnet.to(dev)
    pipe.vae.to(dev)

    results: list[dict] = []
    for i, (edges, (pe, pm)) in enumerate(zip(cannies, embeds)):
        cond = Image.fromarray(cv2.cvtColor(edges, cv2.COLOR_GRAY2RGB))
        t0 = time.perf_counter()
        with torch.inference_mode():
            img = pipe(
                prompt_embeds=pe.to(dev),
                prompt_embeds_mask=pm.to(dev),
                negative_prompt_embeds=neg_pe.to(dev),
                negative_prompt_embeds_mask=neg_pm.to(dev),
                control_image=cond,
                controlnet_conditioning_scale=1.0,
                width=size,
                height=size,
                num_inference_steps=30,
                true_cfg_scale=4.0,
                generator=torch.Generator(device="cuda").manual_seed(0),
            ).images[0]
        dt = time.perf_counter() - t0
        arr = np.asarray(img.convert("RGB"), dtype=np.uint8)
        if arr.shape[:2] != (size, size):
            arr = cv2.resize(arr, (size, size))
        iou = recanny_iou(arr, edges, _LOW, _HIGH, _DIL)
        iio.imwrite(out_dir / f"frame{i:02d}_qwen.png", arr)
        results.append(
            {
                "index": i,
                "iou": iou,
                "s": dt,
                "output_path": str(out_dir / f"frame{i:02d}_qwen.png"),
            }
        )
        print(f"[qwen] frame {i}: IoU={iou:.3f} {dt:.1f}s")
    return results
