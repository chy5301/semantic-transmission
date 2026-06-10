"""QwenVLSender 单元测试（mock 模式，不需要 GPU 或真实模型）。"""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from semantic_transmission.common.model_loader import QwenVLBundle, QwenVLModelLoader
from semantic_transmission.common.types import SenderOutput
from semantic_transmission.sender.qwen_vl_sender import (
    QwenVLSender,
    _DEFAULT_SYSTEM_PROMPT,
)


def _build_mock_bundle(decode_text: str = "decoded text"):
    """构造一个可直接装进 loader 的 mock bundle。"""
    mock_model = MagicMock()
    mock_model.device = "cpu"
    mock_model.generate.return_value = [[1, 2, 3, 100, 200, 300]]

    mock_processor = MagicMock()
    mock_processor.apply_chat_template.return_value = "formatted text"
    mock_processor.return_value = MagicMock(
        input_ids=[[1, 2, 3]],
        to=MagicMock(return_value=MagicMock(input_ids=[[1, 2, 3]])),
    )
    mock_processor.batch_decode.return_value = [decode_text]

    return QwenVLBundle(
        model=mock_model,
        processor=mock_processor,
        actual_quantization="int4",
    )


def _inject_mock_bundle(sender: QwenVLSender, bundle: QwenVLBundle) -> None:
    """直接将 bundle 注入 sender 的 loader，跳过真实加载。"""
    sender._loader._bundle = bundle


@pytest.fixture
def sample_image():
    """创建测试用 numpy RGB 图像。"""
    return np.zeros((64, 64, 3), dtype=np.uint8)


@pytest.fixture
def mock_vlm_sender():
    """创建已 mock 模型加载的 QwenVLSender。"""
    sender = QwenVLSender()
    bundle = _build_mock_bundle(
        decode_text="A detailed description of a dark scene with black pixels."
    )
    _inject_mock_bundle(sender, bundle)
    return sender


class TestQwenVLSenderInit:
    """测试构造函数参数。"""

    def test_default_params(self):
        sender = QwenVLSender()
        assert sender._model_name == "Qwen/Qwen2.5-VL-7B-Instruct"
        assert sender._quantization == "int4"
        assert sender._max_new_tokens == 512
        assert sender._system_prompt == _DEFAULT_SYSTEM_PROMPT

    def test_custom_params(self):
        sender = QwenVLSender(
            model_name="custom/model",
            quantization="float16",
            max_new_tokens=256,
            system_prompt="Custom prompt",
        )
        assert sender._model_name == "custom/model"
        assert sender._quantization == "float16"
        assert sender._max_new_tokens == 256
        assert sender._system_prompt == "Custom prompt"

    def test_lazy_load_model_not_loaded_on_init(self):
        sender = QwenVLSender()
        assert not sender.is_loaded

    def test_accepts_loader_directly(self):
        from semantic_transmission.common.config import VLMLoaderConfig

        loader = QwenVLModelLoader(
            VLMLoaderConfig(model_name="custom/loader-model", max_new_tokens=128)
        )
        sender = QwenVLSender(loader=loader)
        assert sender._loader is loader
        assert sender._model_name == "custom/loader-model"
        assert sender._max_new_tokens == 128


class TestDescribe:
    """测试 describe() 方法。"""

    def test_returns_sender_output(self, mock_vlm_sender, sample_image):
        result = mock_vlm_sender.describe(sample_image)
        assert isinstance(result, SenderOutput)

    def test_output_text_not_empty(self, mock_vlm_sender, sample_image):
        result = mock_vlm_sender.describe(sample_image)
        assert len(result.text) > 0

    def test_output_text_matches_decode(self, mock_vlm_sender, sample_image):
        result = mock_vlm_sender.describe(sample_image)
        assert (
            result.text == "A detailed description of a dark scene with black pixels."
        )

    def test_metadata_contains_model_info(self, mock_vlm_sender, sample_image):
        result = mock_vlm_sender.describe(sample_image)
        assert "model" in result.metadata
        assert result.metadata["model"] == "Qwen/Qwen2.5-VL-7B-Instruct"
        assert "quantization" in result.metadata

    def test_calls_model_generate(self, mock_vlm_sender, sample_image):
        mock_vlm_sender.describe(sample_image)
        mock_vlm_sender._loader._bundle.model.generate.assert_called_once()

    def test_calls_processor_apply_chat_template(self, mock_vlm_sender, sample_image):
        mock_vlm_sender.describe(sample_image)
        mock_vlm_sender._loader._bundle.processor.apply_chat_template.assert_called_once()


class TestModelLoading:
    """测试模型加载逻辑（通过 loader 委托）。"""

    def test_loads_model_on_first_describe(self, sample_image):
        sender = QwenVLSender()
        assert not sender.is_loaded

        bundle = _build_mock_bundle(decode_text="desc")

        with patch.object(sender._loader, "load", return_value=bundle) as mock_load:
            sender.describe(sample_image)
            mock_load.assert_called_once()

    def test_does_not_reload_on_second_describe(self, mock_vlm_sender, sample_image):
        # loader.load() 在 bundle 已存在时直接返回，应只触发一次真实加载逻辑
        with patch.object(
            QwenVLModelLoader, "load", wraps=mock_vlm_sender._loader.load
        ) as spy:
            mock_vlm_sender.describe(sample_image)
            mock_vlm_sender.describe(sample_image)
            # 每次 describe 都会调一次 loader.load()，但底层 bundle 已 cache
            assert spy.call_count == 2
            assert mock_vlm_sender.is_loaded


class TestSystemPrompt:
    """测试系统提示词。"""

    def test_default_system_prompt_used(self, mock_vlm_sender, sample_image):
        mock_vlm_sender.describe(sample_image)
        processor = mock_vlm_sender._loader._bundle.processor
        call_args = processor.apply_chat_template.call_args
        messages = call_args[0][0]
        system_msg = messages[0]
        assert system_msg["role"] == "system"
        assert _DEFAULT_SYSTEM_PROMPT in system_msg["content"][0]["text"]

    def test_custom_system_prompt(self, sample_image):
        sender = QwenVLSender(system_prompt="Custom system prompt")
        bundle = _build_mock_bundle(decode_text="output")
        _inject_mock_bundle(sender, bundle)

        sender.describe(sample_image)
        call_args = bundle.processor.apply_chat_template.call_args
        messages = call_args[0][0]
        assert messages[0]["content"][0]["text"] == "Custom system prompt"


class TestUnload:
    """测试 unload() 方法。"""

    def test_unload_clears_model(self, mock_vlm_sender):
        assert mock_vlm_sender.is_loaded
        mock_vlm_sender.unload()
        assert not mock_vlm_sender.is_loaded

    def test_unload_idempotent(self):
        sender = QwenVLSender()
        assert not sender.is_loaded
        sender.unload()  # 未加载状态调用不应报错
        sender.unload()  # 连续调用不应报错
        assert not sender.is_loaded

    def test_describe_after_unload_reloads(self, mock_vlm_sender, sample_image):
        mock_vlm_sender.unload()
        assert not mock_vlm_sender.is_loaded

        reloaded_bundle = _build_mock_bundle(decode_text="reloaded")

        with patch.object(
            mock_vlm_sender._loader, "load", return_value=reloaded_bundle
        ) as mock_load:
            result = mock_vlm_sender.describe(sample_image)
            mock_load.assert_called_once()
            assert result.text == "reloaded"
