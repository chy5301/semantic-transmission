"""语义级质量评估指标：CLIP Score。"""

from __future__ import annotations

import torch
from PIL import Image
from transformers import CLIPModel, CLIPProcessor

from .utils import ImageInput, to_numpy


def compute_clip_score(
    image: ImageInput,
    text: str,
    *,
    model_name: str = "openai/clip-vit-base-patch32",
    device: str | None = None,
) -> float:
    """计算 CLIP Score（图文语义匹配度）。

    使用 CLIP 模型分别编码图像和文本，计算余弦相似度。
    标准公式：max(100 × cosine_similarity, 0)

    Args:
        image: 输入图像（通常是还原图像）
        text: 文本描述（通常是发送端生成的 prompt）
        model_name: CLIP 模型名称
        device: 计算设备，None 时使用 CPU

    Returns:
        CLIP Score，范围 [0, 100]，越高表示图文匹配度越好。
    """
    # 转为 PIL Image（CLIPProcessor 需要 PIL 输入）
    arr = to_numpy(image)
    pil_image = Image.fromarray(arr)

    processor = CLIPProcessor.from_pretrained(model_name)
    model = CLIPModel.from_pretrained(model_name)
    model.eval()

    if device:
        model = model.to(device)

    inputs = processor(
        text=[text], images=[pil_image], return_tensors="pt", padding=True
    )
    if device:
        inputs = {k: v.to(device) for k, v in inputs.items()}

    with torch.no_grad():
        image_features = model.get_image_features(pixel_values=inputs["pixel_values"])
        text_features = model.get_text_features(
            input_ids=inputs["input_ids"],
            attention_mask=inputs["attention_mask"],
        )

    # L2 归一化
    image_features = image_features / image_features.norm(dim=-1, keepdim=True)
    text_features = text_features / text_features.norm(dim=-1, keepdim=True)

    # 余弦相似度 → CLIP Score
    cosine_sim = (image_features * text_features).sum(dim=-1)
    score = max(100.0 * cosine_sim.item(), 0.0)

    return score
