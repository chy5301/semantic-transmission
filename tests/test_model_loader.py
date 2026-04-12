"""ModelLoader ABC 单元测试。"""

from __future__ import annotations

import pytest

from semantic_transmission.common.model_loader import ModelLoader


class _FakeLoader(ModelLoader[str]):
    """测试用的具体实现。"""

    def __init__(self) -> None:
        self._model: str | None = None

    def load(self) -> str:
        if self._model is None:
            self._model = "fake-model"
        return self._model

    def unload(self) -> None:
        self._model = None

    @property
    def is_loaded(self) -> bool:
        return self._model is not None


class TestModelLoaderABC:
    def test_load_returns_model(self):
        loader = _FakeLoader()
        model = loader.load()
        assert model == "fake-model"
        assert loader.is_loaded

    def test_load_idempotent(self):
        loader = _FakeLoader()
        m1 = loader.load()
        m2 = loader.load()
        assert m1 is m2

    def test_unload_releases_model(self):
        loader = _FakeLoader()
        loader.load()
        loader.unload()
        assert not loader.is_loaded

    def test_unload_when_not_loaded(self):
        loader = _FakeLoader()
        loader.unload()  # 空操作，不报错
        assert not loader.is_loaded


class TestSession:
    def test_session_yields_model(self):
        loader = _FakeLoader()
        with loader.session() as model:
            assert model == "fake-model"
            assert loader.is_loaded
        assert not loader.is_loaded

    def test_session_unloads_on_exception(self):
        loader = _FakeLoader()
        with pytest.raises(RuntimeError, match="boom"):
            with loader.session() as model:
                assert model == "fake-model"
                raise RuntimeError("boom")
        assert not loader.is_loaded

    def test_session_unloads_on_normal_exit(self):
        loader = _FakeLoader()
        with loader.session():
            pass
        assert not loader.is_loaded
