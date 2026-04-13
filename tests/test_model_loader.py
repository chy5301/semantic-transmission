"""ModelLoader ABC + DiffusersModelLoader 单元测试。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from semantic_transmission.common.config import DiffusersLoaderConfig
from semantic_transmission.common.model_loader import DiffusersModelLoader, ModelLoader


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


def _make_mock_pipeline():
    """创建 mock pipeline。"""
    pipeline = MagicMock()
    pipeline.to.return_value = pipeline
    return pipeline


class TestDiffusersModelLoader:
    @pytest.fixture
    def config(self):
        return DiffusersLoaderConfig(device="cpu")

    @patch("diffusers.GGUFQuantizationConfig")
    @patch("diffusers.ZImageControlNetPipeline")
    @patch("diffusers.ZImageControlNetModel")
    @patch("diffusers.ZImageTransformer2DModel")
    def test_load_returns_pipeline(
        self, mock_xformer, mock_cnet, mock_pipe_cls, mock_quant, config
    ):
        mock_pipe = _make_mock_pipeline()
        mock_pipe_cls.from_pretrained.return_value = mock_pipe

        loader = DiffusersModelLoader(config)
        pipeline = loader.load()

        assert pipeline is mock_pipe
        assert loader.is_loaded
        mock_xformer.from_single_file.assert_called_once()
        mock_cnet.from_single_file.assert_called_once()
        mock_pipe_cls.from_pretrained.assert_called_once()
        # 验证 scheduler shift 设置
        mock_pipe.scheduler.set_shift.assert_called_once_with(config.scheduler_shift)

    @patch("diffusers.GGUFQuantizationConfig")
    @patch("diffusers.ZImageControlNetPipeline")
    @patch("diffusers.ZImageControlNetModel")
    @patch("diffusers.ZImageTransformer2DModel")
    def test_load_idempotent(
        self, mock_xformer, mock_cnet, mock_pipe_cls, mock_quant, config
    ):
        mock_pipe = _make_mock_pipeline()
        mock_pipe_cls.from_pretrained.return_value = mock_pipe

        loader = DiffusersModelLoader(config)
        p1 = loader.load()
        p2 = loader.load()

        assert p1 is p2
        mock_pipe_cls.from_pretrained.assert_called_once()

    def test_unload_releases_pipeline(self, config):
        loader = DiffusersModelLoader(config)
        loader._pipeline = MagicMock()
        assert loader.is_loaded

        loader.unload()
        assert not loader.is_loaded

    def test_unload_when_not_loaded(self, config):
        loader = DiffusersModelLoader(config)
        loader.unload()  # 空操作
        assert not loader.is_loaded

    @patch("diffusers.GGUFQuantizationConfig")
    @patch("diffusers.ZImageControlNetPipeline")
    @patch("diffusers.ZImageControlNetModel")
    @patch("diffusers.ZImageTransformer2DModel")
    def test_session_lifecycle(
        self, mock_xformer, mock_cnet, mock_pipe_cls, mock_quant, config
    ):
        mock_pipe = _make_mock_pipeline()
        mock_pipe_cls.from_pretrained.return_value = mock_pipe

        loader = DiffusersModelLoader(config)
        with loader.session() as pipeline:
            assert pipeline is mock_pipe
            assert loader.is_loaded
        assert not loader.is_loaded

    @patch("diffusers.GGUFQuantizationConfig")
    @patch("diffusers.ZImageControlNetPipeline")
    @patch("diffusers.ZImageControlNetModel")
    @patch("diffusers.ZImageTransformer2DModel")
    def test_custom_scheduler_shift(
        self, mock_xformer, mock_cnet, mock_pipe_cls, mock_quant
    ):
        mock_pipe = _make_mock_pipeline()
        mock_pipe_cls.from_pretrained.return_value = mock_pipe

        config = DiffusersLoaderConfig(device="cpu", scheduler_shift=5.0)
        loader = DiffusersModelLoader(config)
        loader.load()

        mock_pipe.scheduler.set_shift.assert_called_once_with(5.0)
