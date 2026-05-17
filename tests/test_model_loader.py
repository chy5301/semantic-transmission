"""ModelLoader ABC + DiffusersModelLoader + QwenVLModelLoader 单元测试。"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

from semantic_transmission.common.config import (
    DiffusersLoaderConfig,
    VLMLoaderConfig,
)
from semantic_transmission.common.model_loader import (
    DiffusersModelLoader,
    ModelLoader,
    QwenVLBundle,
    QwenVLModelLoader,
)


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


# ---------------------------------------------------------------------------
# QwenVLModelLoader
# ---------------------------------------------------------------------------


@pytest.fixture
def vlm_config():
    return VLMLoaderConfig(model_name="Qwen/Qwen2.5-VL-7B-Instruct")


def _patch_transformers(monkeypatch, processor=None, model=None):
    """构造 transformers 子模块的 patcher，让 import 命中 mock。"""
    fake_module = MagicMock()
    fake_model_cls = MagicMock()
    fake_model_cls.from_pretrained.return_value = model or MagicMock()
    fake_processor_cls = MagicMock()
    fake_processor_cls.from_pretrained.return_value = processor or MagicMock()
    fake_module.Qwen2_5_VLForConditionalGeneration = fake_model_cls
    fake_module.AutoProcessor = fake_processor_cls
    # 保留 BitsAndBytesConfig 占位（cascade 测试用）
    fake_module.BitsAndBytesConfig = MagicMock()
    monkeypatch.setitem(sys.modules, "transformers", fake_module)
    return fake_module, fake_model_cls, fake_processor_cls


def _patch_torchao_unavailable(monkeypatch):
    """让 ``from torchao.quantization import TorchAoConfig`` 真正抛 ImportError。

    在 ``sys.modules`` 中将目标模块设为 ``None``，Python 在 import 时遇到
    ``None`` 占位会主动抛 ``ImportError``。比 ``MagicMock(spec=[])``（抛
    ``AttributeError``）更贴近"包未装"的真实场景，因此能被收紧后的
    ``except ImportError`` 子句正确捕获。
    """
    monkeypatch.setitem(sys.modules, "torchao", None)
    monkeypatch.setitem(sys.modules, "torchao.quantization", None)


class TestQwenVLModelLoader:
    def test_load_returns_bundle(self, vlm_config, monkeypatch):
        fake_model = MagicMock()
        fake_processor = MagicMock()
        _, _, _ = _patch_transformers(
            monkeypatch, processor=fake_processor, model=fake_model
        )

        loader = QwenVLModelLoader(vlm_config)
        bundle = loader.load()

        assert isinstance(bundle, QwenVLBundle)
        assert bundle.model is fake_model
        assert bundle.processor is fake_processor
        assert loader.is_loaded

    def test_load_idempotent(self, vlm_config, monkeypatch):
        _, fake_model_cls, _ = _patch_transformers(monkeypatch)

        loader = QwenVLModelLoader(vlm_config)
        b1 = loader.load()
        b2 = loader.load()

        assert b1 is b2
        fake_model_cls.from_pretrained.assert_called_once()

    def test_unload_releases_bundle(self, vlm_config):
        loader = QwenVLModelLoader(vlm_config)
        loader._bundle = QwenVLBundle(
            model=MagicMock(), processor=MagicMock(), actual_quantization="int4"
        )
        assert loader.is_loaded

        loader.unload()
        assert not loader.is_loaded

    def test_unload_when_not_loaded(self, vlm_config):
        loader = QwenVLModelLoader(vlm_config)
        loader.unload()  # 空操作
        assert not loader.is_loaded

    def test_session_lifecycle(self, vlm_config, monkeypatch):
        _patch_transformers(monkeypatch)

        loader = QwenVLModelLoader(vlm_config)
        with loader.session() as bundle:
            assert isinstance(bundle, QwenVLBundle)
            assert loader.is_loaded
        assert not loader.is_loaded

    def test_quantization_cascade_falls_back_to_bnb(self, vlm_config, monkeypatch):
        """torchao 不可用时应回退到 bitsandbytes 4-bit。"""
        _patch_torchao_unavailable(monkeypatch)
        fake_module, _, _ = _patch_transformers(monkeypatch)

        loader = QwenVLModelLoader(vlm_config)
        bundle = loader.load()

        # bnb 配置被构造说明走到了第二级
        fake_module.BitsAndBytesConfig.assert_called_once()
        assert bundle.actual_quantization == "bitsandbytes-4bit"

    def test_quantization_cascade_falls_back_to_float16(self, vlm_config, monkeypatch):
        """torchao + bitsandbytes 都不可用时应回退到 float16。"""
        _patch_torchao_unavailable(monkeypatch)

        # 构造 transformers 但让 BitsAndBytesConfig 抛错
        fake_module, fake_model_cls, fake_processor_cls = _patch_transformers(
            monkeypatch
        )
        fake_module.BitsAndBytesConfig = MagicMock(
            side_effect=ImportError("bnb not available")
        )

        loader = QwenVLModelLoader(vlm_config)
        bundle = loader.load()

        assert bundle.actual_quantization == "float16"

    def test_non_int4_quantization_skips_cascade(self, monkeypatch):
        """quantization 非 int4 时不应进入 cascade，直接走 float16。"""
        fake_module, fake_model_cls, _ = _patch_transformers(monkeypatch)
        # 即使 BitsAndBytesConfig 存在也不应该被调用
        bnb_call_tracker = MagicMock()
        fake_module.BitsAndBytesConfig = bnb_call_tracker

        config = VLMLoaderConfig(quantization="float16")
        loader = QwenVLModelLoader(config)
        bundle = loader.load()

        bnb_call_tracker.assert_not_called()
        assert bundle.actual_quantization == "float16"
        # quantization_config 应为 None
        kwargs = fake_model_cls.from_pretrained.call_args.kwargs
        assert kwargs["quantization_config"] is None

    def test_model_path_takes_priority_over_model_name(self, monkeypatch):
        """model_path 非空时应作为 model_id 传给 from_pretrained。"""
        fake_module, fake_model_cls, fake_processor_cls = _patch_transformers(
            monkeypatch
        )
        config = VLMLoaderConfig(model_name="ignored/name", model_path="/local/qwen-vl")
        loader = QwenVLModelLoader(config)
        loader.load()

        args, _ = fake_model_cls.from_pretrained.call_args
        assert args[0] == "/local/qwen-vl"
        args2, _ = fake_processor_cls.from_pretrained.call_args
        assert args2[0] == "/local/qwen-vl"


class TestProjectConfigToVLMLoader:
    """ProjectConfig.to_vlm_loader_config() 派生测试。"""

    def test_derives_from_defaults(self):
        from semantic_transmission.common.config import ProjectConfig

        cfg = ProjectConfig()
        vlm_cfg = cfg.to_vlm_loader_config()
        assert vlm_cfg.model_name == "Qwen/Qwen2.5-VL-7B-Instruct"
        assert vlm_cfg.model_path == ""
        assert vlm_cfg.quantization == "int4"
        assert vlm_cfg.max_new_tokens == 512

    def test_derives_from_custom(self):
        from semantic_transmission.common.config import ProjectConfig

        cfg = ProjectConfig(
            vlm_model_name="custom/model",
            vlm_model_path="/custom/path",
            vlm_quantization="float16",
            vlm_max_new_tokens=1024,
        )
        vlm_cfg = cfg.to_vlm_loader_config()
        assert vlm_cfg.model_name == "custom/model"
        assert vlm_cfg.model_path == "/custom/path"
        assert vlm_cfg.quantization == "float16"
        assert vlm_cfg.max_new_tokens == 1024
