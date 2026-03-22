"""QwenVLSender 单元测试（mock 模式，不需要 GPU 或真实模型）。"""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from semantic_transmission.common.types import SenderOutput
from semantic_transmission.sender.qwen_vl_sender import (
    QwenVLSender,
    _DEFAULT_SYSTEM_PROMPT,
)


@pytest.fixture
def sample_image():
    """创建测试用 numpy RGB 图像。"""
    return np.zeros((64, 64, 3), dtype=np.uint8)


@pytest.fixture
def mock_vlm_sender():
    """创建已 mock 模型加载的 QwenVLSender。"""
    sender = QwenVLSender()

    mock_model = MagicMock()
    mock_model.device = "cpu"
    mock_model.generate.return_value = [[1, 2, 3, 100, 200, 300]]

    mock_processor = MagicMock()
    mock_processor.apply_chat_template.return_value = "formatted text"
    mock_processor.return_value = MagicMock(
        input_ids=[[1, 2, 3]],
        to=MagicMock(return_value=MagicMock(input_ids=[[1, 2, 3]])),
    )
    mock_processor.batch_decode.return_value = [
        "A detailed description of a dark scene with black pixels."
    ]

    sender._model = mock_model
    sender._processor = mock_processor
    sender._actual_quantization = "int4"

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
        assert sender._model is None
        assert sender._processor is None


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
        mock_vlm_sender._model.generate.assert_called_once()

    def test_calls_processor_apply_chat_template(self, mock_vlm_sender, sample_image):
        mock_vlm_sender.describe(sample_image)
        mock_vlm_sender._processor.apply_chat_template.assert_called_once()


class TestModelLoading:
    """测试模型加载逻辑。"""

    def test_loads_model_on_first_describe(self, sample_image):
        sender = QwenVLSender()
        assert sender._model is None

        with patch.object(sender, "_load_model") as mock_load:
            # _load_model 被 mock 了，所以不会真正加载
            # 但需要设置 _model 不为 None，否则每次都会调用 _load_model
            def set_model():
                sender._model = MagicMock()
                sender._model.device = "cpu"
                sender._model.generate.return_value = [[1, 2, 3, 100]]
                sender._processor = MagicMock()
                sender._processor.apply_chat_template.return_value = "text"
                sender._processor.return_value = MagicMock(
                    input_ids=[[1, 2, 3]],
                    to=MagicMock(return_value=MagicMock(input_ids=[[1, 2, 3]])),
                )
                sender._processor.batch_decode.return_value = ["desc"]
                sender._actual_quantization = "int4"

            mock_load.side_effect = set_model
            sender.describe(sample_image)
            mock_load.assert_called_once()

    def test_does_not_reload_on_second_describe(self, mock_vlm_sender, sample_image):
        with patch.object(mock_vlm_sender, "_load_model") as mock_load:
            mock_vlm_sender.describe(sample_image)
            mock_vlm_sender.describe(sample_image)
            mock_load.assert_not_called()


class TestSystemPrompt:
    """测试系统提示词。"""

    def test_default_system_prompt_used(self, mock_vlm_sender, sample_image):
        mock_vlm_sender.describe(sample_image)
        call_args = mock_vlm_sender._processor.apply_chat_template.call_args
        messages = call_args[0][0]
        system_msg = messages[0]
        assert system_msg["role"] == "system"
        assert _DEFAULT_SYSTEM_PROMPT in system_msg["content"][0]["text"]

    def test_custom_system_prompt(self, sample_image):
        sender = QwenVLSender(system_prompt="Custom system prompt")

        mock_model = MagicMock()
        mock_model.device = "cpu"
        mock_model.generate.return_value = [[1, 2, 3, 100]]

        mock_processor = MagicMock()
        mock_processor.apply_chat_template.return_value = "text"
        mock_processor.return_value = MagicMock(
            input_ids=[[1, 2, 3]],
            to=MagicMock(return_value=MagicMock(input_ids=[[1, 2, 3]])),
        )
        mock_processor.batch_decode.return_value = ["output"]

        sender._model = mock_model
        sender._processor = mock_processor
        sender._actual_quantization = "int4"

        sender.describe(sample_image)
        call_args = mock_processor.apply_chat_template.call_args
        messages = call_args[0][0]
        assert messages[0]["content"][0]["text"] == "Custom system prompt"
