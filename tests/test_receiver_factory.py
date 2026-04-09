"""create_receiver 工厂函数单元测试。"""

from semantic_transmission.common.config import DiffusersReceiverConfig
from semantic_transmission.receiver import create_receiver
from semantic_transmission.receiver.base import BaseReceiver


class TestCreateReceiverDiffusers:
    def test_returns_diffusers_receiver(self):
        from semantic_transmission.receiver.diffusers_receiver import DiffusersReceiver

        receiver = create_receiver()
        assert isinstance(receiver, DiffusersReceiver)
        assert isinstance(receiver, BaseReceiver)

    def test_uses_default_config(self):
        receiver = create_receiver()
        assert receiver.config.model_name == "Tongyi-MAI/Z-Image-Turbo"

    def test_accepts_custom_config(self):
        config = DiffusersReceiverConfig(num_inference_steps=4)
        receiver = create_receiver(config=config)
        assert receiver.config.num_inference_steps == 4

    def test_default_transformer_path(self):
        receiver = create_receiver()
        assert receiver.config.transformer_path.endswith("z-image-turbo-Q8_0.gguf")
