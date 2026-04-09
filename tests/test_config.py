"""common.config 模块单元测试。"""

import os

from semantic_transmission.common.config import (
    DiffusersReceiverConfig,
    get_default_vlm_path,
    get_default_z_image_path,
)


class TestGetDefaultVlmPath:
    def test_returns_none_when_env_unset(self, monkeypatch):
        monkeypatch.delenv("MODEL_CACHE_DIR", raising=False)
        assert get_default_vlm_path() is None

    def test_returns_joined_path_when_env_set(self, monkeypatch):
        monkeypatch.setenv("MODEL_CACHE_DIR", os.path.join("D:", "Models"))
        result = get_default_vlm_path()
        assert result is not None
        assert result.endswith(os.path.join("Qwen", "Qwen2.5-VL-7B-Instruct"))


class TestGetDefaultZImagePath:
    def test_returns_filename_when_env_unset(self, monkeypatch):
        monkeypatch.delenv("MODEL_CACHE_DIR", raising=False)
        assert get_default_z_image_path("foo.gguf") == "foo.gguf"

    def test_returns_joined_path_when_env_set(self, monkeypatch):
        monkeypatch.setenv("MODEL_CACHE_DIR", os.path.join("D:", "Models"))
        result = get_default_z_image_path("foo.gguf")
        assert result.endswith(os.path.join("Z-Image-Turbo", "foo.gguf"))


class TestDiffusersReceiverConfigDefaults:
    def test_default_fields(self):
        config = DiffusersReceiverConfig()
        assert config.model_name == "Tongyi-MAI/Z-Image-Turbo"
        assert config.device == "cuda"
        assert config.num_inference_steps == 9
        assert config.guidance_scale == 1.0
        assert config.torch_dtype == "bfloat16"

    def test_post_init_fills_transformer_path(self, monkeypatch):
        monkeypatch.delenv("MODEL_CACHE_DIR", raising=False)
        config = DiffusersReceiverConfig()
        assert config.transformer_path.endswith("z-image-turbo-Q8_0.gguf")

    def test_post_init_fills_controlnet_name(self, monkeypatch):
        monkeypatch.delenv("MODEL_CACHE_DIR", raising=False)
        config = DiffusersReceiverConfig()
        assert config.controlnet_name.endswith(
            "Z-Image-Turbo-Fun-Controlnet-Union.safetensors"
        )

    def test_explicit_values_not_overridden(self):
        config = DiffusersReceiverConfig(
            transformer_path="/tmp/custom.gguf",
            controlnet_name="/tmp/custom_cnet.safetensors",
        )
        assert config.transformer_path == "/tmp/custom.gguf"
        assert config.controlnet_name == "/tmp/custom_cnet.safetensors"


class TestDiffusersReceiverConfigFromEnv:
    def test_reads_env_overrides(self, monkeypatch):
        monkeypatch.setenv("DIFFUSERS_MODEL_NAME", "custom/model")
        monkeypatch.setenv("DIFFUSERS_NUM_INFERENCE_STEPS", "20")
        monkeypatch.setenv("DIFFUSERS_GUIDANCE_SCALE", "2.5")
        monkeypatch.setenv("DIFFUSERS_DEVICE", "cpu")
        config = DiffusersReceiverConfig.from_env()
        assert config.model_name == "custom/model"
        assert config.num_inference_steps == 20
        assert config.guidance_scale == 2.5
        assert config.device == "cpu"

    def test_invalid_int_raises_value_error(self, monkeypatch):
        monkeypatch.setenv("DIFFUSERS_NUM_INFERENCE_STEPS", "not-a-number")
        import pytest

        with pytest.raises(ValueError, match="DIFFUSERS_NUM_INFERENCE_STEPS"):
            DiffusersReceiverConfig.from_env()
