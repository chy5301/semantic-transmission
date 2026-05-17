"""common.config 模块单元测试。

涵盖 ``DiffusersReceiverConfig`` 的默认值/``__post_init__`` 回退到 ``ProjectConfig``
的等价行为，以及 ``DiffusersReceiverConfig.from_env()`` 环境变量解析。

``ProjectConfig`` / ``load_config`` 本身的加载层级与 TOML 解析在
``tests/test_project_config.py`` 覆盖；本文件聚焦消费侧的派生与回退。
"""

import pytest

from semantic_transmission.common.config import DiffusersReceiverConfig


class TestDiffusersReceiverConfigDefaults:
    def test_default_fields(self):
        config = DiffusersReceiverConfig()
        assert config.model_name == "Tongyi-MAI/Z-Image-Turbo"
        assert config.device == "cuda"
        assert config.num_inference_steps == 9
        assert config.guidance_scale == 1.0
        assert config.torch_dtype == "bfloat16"

    def test_post_init_fills_transformer_path_from_project_config(self):
        """空 transformer_path 时回退到 ProjectConfig.diffusers_transformer_path。

        config.toml 默认 ``${MODEL_CACHE_DIR}/Z-Image-Turbo/z-image-turbo-Q8_0.gguf``，
        无论 MODEL_CACHE_DIR 是否设置，结果都应以 ``z-image-turbo-Q8_0.gguf`` 结尾。
        """
        config = DiffusersReceiverConfig()
        assert config.transformer_path.endswith("z-image-turbo-Q8_0.gguf")

    def test_post_init_fills_controlnet_name_from_project_config(self):
        """空 controlnet_name 时回退到 ProjectConfig.diffusers_controlnet_name。"""
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

        with pytest.raises(ValueError, match="DIFFUSERS_NUM_INFERENCE_STEPS"):
            DiffusersReceiverConfig.from_env()
