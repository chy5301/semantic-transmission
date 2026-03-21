"""ComfyUIConfig 和 SemanticTransmissionConfig 单元测试。"""

from semantic_transmission.common.config import (
    ComfyUIConfig,
    SemanticTransmissionConfig,
)


class TestComfyUIConfigDefaults:
    def test_default_values(self):
        config = ComfyUIConfig()
        assert config.host == "127.0.0.1"
        assert config.port == 8188
        assert config.timeout == 30

    def test_base_url(self):
        config = ComfyUIConfig(host="10.0.0.1", port=9000)
        assert config.base_url == "http://10.0.0.1:9000"

    def test_ws_url(self):
        config = ComfyUIConfig(host="10.0.0.1", port=9000)
        assert config.ws_url == "ws://10.0.0.1:9000/ws"


class TestComfyUIConfigFromEnv:
    def test_no_prefix_reads_base_env(self, monkeypatch):
        monkeypatch.setenv("COMFYUI_HOST", "192.168.1.100")
        monkeypatch.setenv("COMFYUI_PORT", "7777")
        monkeypatch.setenv("COMFYUI_TIMEOUT", "60")
        config = ComfyUIConfig.from_env()
        assert config.host == "192.168.1.100"
        assert config.port == 7777
        assert config.timeout == 60

    def test_no_prefix_uses_defaults_when_unset(self, monkeypatch):
        monkeypatch.delenv("COMFYUI_HOST", raising=False)
        monkeypatch.delenv("COMFYUI_PORT", raising=False)
        monkeypatch.delenv("COMFYUI_TIMEOUT", raising=False)
        config = ComfyUIConfig.from_env()
        assert config.host == "127.0.0.1"
        assert config.port == 8188
        assert config.timeout == 30

    def test_prefix_reads_prefixed_env(self, monkeypatch):
        monkeypatch.setenv("COMFYUI_SENDER_HOST", "10.0.0.1")
        monkeypatch.setenv("COMFYUI_SENDER_PORT", "9001")
        monkeypatch.setenv("COMFYUI_SENDER_TIMEOUT", "15")
        config = ComfyUIConfig.from_env(prefix="SENDER")
        assert config.host == "10.0.0.1"
        assert config.port == 9001
        assert config.timeout == 15

    def test_prefix_falls_back_to_base_env(self, monkeypatch):
        monkeypatch.delenv("COMFYUI_SENDER_HOST", raising=False)
        monkeypatch.delenv("COMFYUI_SENDER_PORT", raising=False)
        monkeypatch.delenv("COMFYUI_SENDER_TIMEOUT", raising=False)
        monkeypatch.setenv("COMFYUI_HOST", "192.168.1.100")
        monkeypatch.setenv("COMFYUI_PORT", "7777")
        monkeypatch.setenv("COMFYUI_TIMEOUT", "60")
        config = ComfyUIConfig.from_env(prefix="SENDER")
        assert config.host == "192.168.1.100"
        assert config.port == 7777
        assert config.timeout == 60

    def test_prefix_falls_back_to_defaults(self, monkeypatch):
        monkeypatch.delenv("COMFYUI_SENDER_HOST", raising=False)
        monkeypatch.delenv("COMFYUI_HOST", raising=False)
        monkeypatch.delenv("COMFYUI_SENDER_PORT", raising=False)
        monkeypatch.delenv("COMFYUI_PORT", raising=False)
        monkeypatch.delenv("COMFYUI_SENDER_TIMEOUT", raising=False)
        monkeypatch.delenv("COMFYUI_TIMEOUT", raising=False)
        config = ComfyUIConfig.from_env(prefix="SENDER")
        assert config.host == "127.0.0.1"
        assert config.port == 8188
        assert config.timeout == 30

    def test_prefix_partial_override(self, monkeypatch):
        """前缀只覆盖部分变量，其余回退到基础环境变量。"""
        monkeypatch.setenv("COMFYUI_SENDER_HOST", "10.0.0.1")
        monkeypatch.delenv("COMFYUI_SENDER_PORT", raising=False)
        monkeypatch.setenv("COMFYUI_PORT", "7777")
        monkeypatch.delenv("COMFYUI_SENDER_TIMEOUT", raising=False)
        monkeypatch.delenv("COMFYUI_TIMEOUT", raising=False)
        config = ComfyUIConfig.from_env(prefix="SENDER")
        assert config.host == "10.0.0.1"
        assert config.port == 7777
        assert config.timeout == 30


class TestSemanticTransmissionConfig:
    def test_single_machine_mode(self, monkeypatch):
        """单机模式：未设置 SENDER/RECEIVER 前缀，两端使用相同地址。"""
        monkeypatch.setenv("COMFYUI_HOST", "192.168.1.100")
        monkeypatch.setenv("COMFYUI_PORT", "8188")
        for prefix in ("SENDER", "RECEIVER"):
            for key in ("HOST", "PORT", "TIMEOUT"):
                monkeypatch.delenv(f"COMFYUI_{prefix}_{key}", raising=False)
        config = SemanticTransmissionConfig.from_env()
        assert config.sender.host == config.receiver.host == "192.168.1.100"
        assert config.sender.port == config.receiver.port == 8188

    def test_dual_machine_mode(self, monkeypatch):
        """双机模式：SENDER 和 RECEIVER 指向不同地址。"""
        monkeypatch.setenv("COMFYUI_SENDER_HOST", "10.0.0.1")
        monkeypatch.setenv("COMFYUI_SENDER_PORT", "8188")
        monkeypatch.setenv("COMFYUI_RECEIVER_HOST", "10.0.0.2")
        monkeypatch.setenv("COMFYUI_RECEIVER_PORT", "8189")
        config = SemanticTransmissionConfig.from_env()
        assert config.sender.host == "10.0.0.1"
        assert config.sender.port == 8188
        assert config.receiver.host == "10.0.0.2"
        assert config.receiver.port == 8189

    def test_manual_construction(self):
        config = SemanticTransmissionConfig(
            sender=ComfyUIConfig(host="10.0.0.1", port=8188),
            receiver=ComfyUIConfig(host="10.0.0.2", port=8189),
        )
        assert config.sender.base_url == "http://10.0.0.1:8188"
        assert config.receiver.base_url == "http://10.0.0.2:8189"
