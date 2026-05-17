"""模型加载器：抽象基类 + Diffusers / Qwen-VL 具体实现。"""

from __future__ import annotations

import contextlib
import gc
from abc import ABC, abstractmethod
from collections.abc import Generator
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Generic, TypeVar

import torch

if TYPE_CHECKING:
    from semantic_transmission.common.config import (
        DiffusersLoaderConfig,
        VLMLoaderConfig,
    )

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

        self._pipeline.scheduler.set_shift(self._config.scheduler_shift)

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


@dataclass
class QwenVLBundle:
    """Qwen-VL 加载结果：model + processor + 实际生效的量化策略。"""

    model: Any
    processor: Any
    actual_quantization: str


class QwenVLModelLoader(ModelLoader[QwenVLBundle]):
    """Qwen2.5-VL 加载器：含 torchao → bitsandbytes → float16 量化 cascade。"""

    def __init__(self, config: VLMLoaderConfig) -> None:
        self._config = config
        self._bundle: QwenVLBundle | None = None

    @property
    def config(self) -> VLMLoaderConfig:
        """暴露只读 loader 配置，供调用方读取派生字段（model_name 等）。"""
        return self._config

    def load(self) -> QwenVLBundle:
        """加载 Qwen-VL 模型与处理器。幂等：已加载时直接返回。"""
        if self._bundle is not None:
            return self._bundle

        from transformers import AutoProcessor, Qwen2_5_VLForConditionalGeneration

        quantization_config = None
        actual_quantization = self._config.quantization
        used_torchao = False

        if self._config.quantization == "int4":
            # 优先尝试 torchao INT4（仅 Linux 推荐）
            try:
                from torchao.quantization import TorchAoConfig

                quantization_config = TorchAoConfig("int4_weight_only", group_size=128)
                used_torchao = True
            except ImportError as e:
                print(f"  提示：torchao INT4 不可用（{e}），尝试 bitsandbytes 4-bit...")
                # 回退到 bitsandbytes 4-bit（Windows 友好）
                try:
                    from transformers import BitsAndBytesConfig

                    quantization_config = BitsAndBytesConfig(
                        load_in_4bit=True,
                        bnb_4bit_use_double_quant=True,
                        bnb_4bit_quant_type="nf4",
                        bnb_4bit_compute_dtype=torch.float16,
                    )
                    actual_quantization = "bitsandbytes-4bit"
                except ImportError as e2:
                    print(
                        f"  警告：bitsandbytes 4-bit 也不可用（{e2}），回退到 float16"
                    )
                    actual_quantization = "float16"

        dtype = torch.bfloat16 if used_torchao else torch.float16

        # 优先使用本地路径，其次使用 HuggingFace Hub ID
        model_id = self._config.model_path or self._config.model_name

        model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
            model_id,
            torch_dtype=dtype,
            device_map="auto",
            quantization_config=quantization_config,
        )
        processor = AutoProcessor.from_pretrained(model_id)

        self._bundle = QwenVLBundle(
            model=model,
            processor=processor,
            actual_quantization=actual_quantization,
        )
        return self._bundle

    def unload(self) -> None:
        """卸载模型，释放 GPU 显存。"""
        if self._bundle is None:
            return
        self._bundle = None
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    @property
    def is_loaded(self) -> bool:
        """模型是否已加载。"""
        return self._bundle is not None
