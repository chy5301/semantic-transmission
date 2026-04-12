"""模型加载器：抽象基类 + Diffusers 具体实现。"""

from __future__ import annotations

import contextlib
import gc
from abc import ABC, abstractmethod
from collections.abc import Generator
from typing import TYPE_CHECKING, Generic, TypeVar

import torch

if TYPE_CHECKING:
    from semantic_transmission.common.config import DiffusersLoaderConfig

TModel = TypeVar("TModel")

TORCH_DTYPE_MAP: dict[str, torch.dtype] = {
    "float16": torch.float16,
    "bfloat16": torch.bfloat16,
    "float32": torch.float32,
}


class ModelLoader(ABC, Generic[TModel]):
    """模型加载器抽象基类。

    子类需实现 ``load()``、``unload()``、``is_loaded``。
    ``session()`` 提供 context manager 自动管理生命周期。
    """

    @abstractmethod
    def load(self) -> TModel:
        """加载模型并返回模型实例。幂等：已加载时直接返回。"""

    @abstractmethod
    def unload(self) -> None:
        """卸载模型，释放资源。未加载时应为空操作。"""

    @property
    @abstractmethod
    def is_loaded(self) -> bool:
        """模型是否已加载。"""

    @contextlib.contextmanager
    def session(self) -> Generator[TModel, None, None]:
        """Context manager：进入时 load，退出时 unload。

        Usage::

            with loader.session() as model:
                result = model(inputs)
        """
        model = self.load()
        try:
            yield model
        finally:
            self.unload()


class DiffusersModelLoader(ModelLoader):
    """Diffusers pipeline 加载器：GGUF transformer + ControlNet + base pipeline。"""

    def __init__(self, config: DiffusersLoaderConfig) -> None:
        self._config = config
        self._pipeline = None

    def load(self):
        """加载 Diffusers pipeline。幂等：已加载时直接返回。"""
        if self._pipeline is not None:
            return self._pipeline

        from diffusers import (
            GGUFQuantizationConfig,
            ZImageControlNetModel,
            ZImageControlNetPipeline,
            ZImageTransformer2DModel,
        )

        dtype = TORCH_DTYPE_MAP.get(self._config.torch_dtype, torch.bfloat16)

        transformer = ZImageTransformer2DModel.from_single_file(
            self._config.transformer_path,
            quantization_config=GGUFQuantizationConfig(compute_dtype=dtype),
            torch_dtype=dtype,
        )
        controlnet = ZImageControlNetModel.from_single_file(
            self._config.controlnet_name,
            torch_dtype=dtype,
        )
        self._pipeline = ZImageControlNetPipeline.from_pretrained(
            self._config.model_name,
            transformer=transformer,
            controlnet=controlnet,
            torch_dtype=dtype,
        ).to(self._config.device)

        return self._pipeline

    def unload(self) -> None:
        """卸载 pipeline，释放 GPU 显存。"""
        if self._pipeline is None:
            return
        self._pipeline = None
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        gc.collect()

    @property
    def is_loaded(self) -> bool:
        """Pipeline 是否已加载。"""
        return self._pipeline is not None
