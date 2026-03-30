"""语义级质量评估指标：CLIP Score。"""

from __future__ import annotations

import torch
from PIL import Image
from transformers import CLIPModel, CLIPProcessor

from .utils import ImageInput, to_numpy


def load_clip_model(
    model_name: str = "openai/clip-vit-base-patch32",
    device: str | None = None,
):
    """加载 CLIP 模型和 processor（可复用以避免重复加载）。

    Args:
        model_name: CLIP 模型名称
        device: 计算设备，None 时使用 CPU

    Returns:
        (model, processor) 元组。
    """
    processor = CLIPProcessor.from_pretrained(model_name)
    model = CLIPModel.from_pretrained(model_name)
    model.eval()
    if device:
        model = model.to(device)
    return model, processor


def compute_clip_score(
    image: ImageInput,
    text: str,
    *,
    model_name: str = "openai/clip-vit-base-patch32",
    device: str | None = None,
    model=None,
    processor=None,
) -> float:
    """计算 CLIP Score（图文语义匹配度）。

    使用 CLIP 模型分别编码图像和文本，计算余弦相似度。
    标准公式：max(100 × cosine_similarity, 0)

    Args:
        image: 输入图像（通常是还原图像）
        text: 文本描述（通常是发送端生成的 prompt）
        model_name: CLIP 模型名称
        device: 计算设备，None 时使用 CPU
        model: 预加载的 CLIPModel（通过 load_clip_model 创建），
               传入时复用该模型，否则每次调用重新加载
        processor: 预加载的 CLIPProcessor，需与 model 配对使用

    Returns:
        CLIP Score，范围 [0, 100]，越高表示图文匹配度越好。
    """
    arr = to_numpy(image)
    pil_image = Image.fromarray(arr)

    if model is None or processor is None:
        model, processor = load_clip_model(model_name=model_name, device=device)

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

    image_features = image_features / image_features.norm(dim=-1, keepdim=True)
    text_features = text_features / text_features.norm(dim=-1, keepdim=True)

    cosine_sim = (image_features * text_features).sum(dim=-1)
    return max(100.0 * cosine_sim.item(), 0.0)
