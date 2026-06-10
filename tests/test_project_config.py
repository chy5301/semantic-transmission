"""ProjectConfig 与 load_config() 单元测试。"""

from pathlib import Path

import pytest

from semantic_transmission.common.config import ProjectConfig, load_config


class TestProjectConfigDefaults:
    def test_frozen(self):
        cfg = ProjectConfig()
        with pytest.raises(AttributeError):
            cfg.num_inference_steps = 99  # type: ignore[misc]

    def test_default_values(self):
        cfg = ProjectConfig()
        assert cfg.diffusers_model_name == "Tongyi-MAI/Z-Image-Turbo"
        assert cfg.vlm_model_name == "Qwen/Qwen2.5-VL-7B-Instruct"
        assert cfg.num_inference_steps == 9
        assert cfg.guidance_scale == 1.0
        assert cfg.canny_low_threshold == 100
        assert cfg.canny_high_threshold == 200
        assert cfg.diffusers_device == "cuda"


class TestLoadConfigFromToml:
    def test_loads_from_toml(self, tmp_path: Path):
        toml = tmp_path / "config.toml"
        toml.write_text(
            "[inference]\nnum_inference_steps = 20\nguidance_scale = 3.5\n",
            encoding="utf-8",
        )
        cfg = load_config(toml)
        assert cfg.num_inference_steps == 20
        assert cfg.guidance_scale == 3.5
        # 未指定字段保留代码默认
        assert cfg.diffusers_model_name == "Tongyi-MAI/Z-Image-Turbo"

    def test_nested_toml_keys(self, tmp_path: Path):
        toml = tmp_path / "config.toml"
        toml.write_text(
            '[models.diffusers]\nmodel_name = "custom/model"\ndevice = "cpu"\n',
            encoding="utf-8",
        )
        cfg = load_config(toml)
        assert cfg.diffusers_model_name == "custom/model"
        assert cfg.diffusers_device == "cpu"

    def test_missing_toml_uses_defaults(self, tmp_path: Path, monkeypatch):
        monkeypatch.delenv("MODEL_CACHE_DIR", raising=False)
        cfg = load_config(tmp_path / "nonexistent.toml")
        assert cfg == ProjectConfig()


class TestLocalOverride:
    def test_local_overrides_base(self, tmp_path: Path):
        base = tmp_path / "config.toml"
        base.write_text(
            "[inference]\nnum_inference_steps = 20\nguidance_scale = 3.5\n",
            encoding="utf-8",
        )
        local = tmp_path / "config.local.toml"
        local.write_text(
            "[inference]\nnum_inference_steps = 30\n",
            encoding="utf-8",
        )
        cfg = load_config(base)
        assert cfg.num_inference_steps == 30
        # base 的 guidance_scale 保留
        assert cfg.guidance_scale == 3.5


class TestEnvVarExpansion:
    def test_expand_model_cache_dir_in_toml(self, tmp_path: Path, monkeypatch):
        monkeypatch.setenv("MODEL_CACHE_DIR", "/models")
        toml = tmp_path / "config.toml"
        toml.write_text(
            "[models.diffusers]\n"
            'transformer_path = "${MODEL_CACHE_DIR}/Z-Image-Turbo/model.gguf"\n',
            encoding="utf-8",
        )
        cfg = load_config(toml)
        assert cfg.diffusers_transformer_path == "/models/Z-Image-Turbo/model.gguf"

    def test_unset_env_var_kept_as_literal(self, tmp_path: Path, monkeypatch):
        monkeypatch.delenv("MODEL_CACHE_DIR", raising=False)
        toml = tmp_path / "config.toml"
        toml.write_text(
            '[models.diffusers]\ntransformer_path = "${MODEL_CACHE_DIR}/model.gguf"\n',
            encoding="utf-8",
        )
        cfg = load_config(toml)
        assert cfg.diffusers_transformer_path == "${MODEL_CACHE_DIR}/model.gguf"

    def test_env_override_model_cache_dir(self, tmp_path: Path, monkeypatch):
        monkeypatch.setenv("MODEL_CACHE_DIR", "/env/models")
        toml = tmp_path / "config.toml"
        toml.write_text(
            '[paths]\nmodel_cache_dir = "/toml/models"\n',
            encoding="utf-8",
        )
        cfg = load_config(toml)
        # 环境变量优先级高于 toml
        assert cfg.model_cache_dir == "/env/models"

    def test_no_env_uses_toml_value(self, tmp_path: Path, monkeypatch):
        monkeypatch.delenv("MODEL_CACHE_DIR", raising=False)
        toml = tmp_path / "config.toml"
        toml.write_text(
            '[paths]\nmodel_cache_dir = "/toml/models"\n',
            encoding="utf-8",
        )
        cfg = load_config(toml)
        assert cfg.model_cache_dir == "/toml/models"
