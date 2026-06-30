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


class TestCreateReceiverKlein:
    def test_returns_klein_receiver(self):
        from semantic_transmission.receiver.klein_receiver import KleinReceiver

        receiver = create_receiver(backend="klein")
        assert isinstance(receiver, KleinReceiver)
        assert isinstance(receiver, BaseReceiver)

    def test_klein_accepts_klein_config(self):
        from semantic_transmission.common.config import KleinReceiverConfig

        cfg = KleinReceiverConfig(model_dir="/x", max_side=1024)
        receiver = create_receiver(config=cfg, backend="klein")
        assert receiver.config.max_side == 1024

    def test_unknown_backend_raises(self):
        import pytest

        with pytest.raises(ValueError, match="backend"):
            create_receiver(backend="nope")
