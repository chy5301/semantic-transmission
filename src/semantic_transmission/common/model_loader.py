"""模型加载器抽象基类：统一模型加载/卸载/生命周期管理。"""

from __future__ import annotations

import contextlib
from abc import ABC, abstractmethod
from collections.abc import Generator
from typing import Generic, TypeVar

TModel = TypeVar("TModel")


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
