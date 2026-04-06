"""create_receiver 工厂函数单元测试。"""

from unittest.mock import MagicMock, patch

import pytest

from semantic_transmission.common.config import DiffusersReceiverConfig
from semantic_transmission.receiver import create_receiver
from semantic_transmission.receiver.base import BaseReceiver


class TestCreateReceiverDiffusers:
    def test_returns_diffusers_receiver(self):
        from semantic_transmission.receiver.diffusers_receiver import DiffusersReceiver

        receiver = create_receiver("diffusers")
        assert isinstance(receiver, DiffusersReceiver)
        assert isinstance(receiver, BaseReceiver)

    def test_uses_default_config(self):
        receiver = create_receiver("diffusers")
        assert receiver.config.model_name == "Tongyi-MAI/Z-Image-Turbo"

    def test_accepts_custom_config(self):
        config = DiffusersReceiverConfig(num_inference_steps=4)
        receiver = create_receiver("diffusers", config=config)
        assert receiver.config.num_inference_steps == 4


class TestCreateReceiverComfyUI:
    @patch("semantic_transmission.receiver.comfyui_receiver.ComfyUIReceiver")
    @patch("semantic_transmission.common.comfyui_client.ComfyUIClient")
    def test_returns_comfyui_receiver(self, mock_client_cls, mock_receiver_cls):
        mock_receiver = MagicMock()
        mock_receiver_cls.return_value = mock_receiver
        mock_client_cls.return_value = MagicMock()

        # 直接测试能否调用而不抛异常（不 mock 整个链路，只验证分支走通）
        receiver = create_receiver("comfyui")
        assert receiver is not None


class TestCreateReceiverInvalid:
    def test_invalid_backend_raises_value_error(self):
        with pytest.raises(ValueError, match="不支持的接收端后端"):
            create_receiver("invalid_backend")
