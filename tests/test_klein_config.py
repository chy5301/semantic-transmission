"""KleinReceiverConfig 单元测试。"""

from semantic_transmission.common.config import KleinReceiverConfig


def test_defaults():
    cfg = KleinReceiverConfig(model_dir="/x")  # 传 model_dir 跳过 load_config
    assert cfg.num_inference_steps == 4
    assert cfg.guidance_scale == 1.0
    assert cfg.torch_dtype == "bfloat16"
    assert cfg.max_side == 768
    assert cfg.enable_vae_tiling is False


def test_model_dir_resolves_from_cache(monkeypatch, tmp_path):
    monkeypatch.setenv("MODEL_CACHE_DIR", str(tmp_path))
    cfg = KleinReceiverConfig()
    assert cfg.model_dir.replace("\\", "/").endswith(
        "black-forest-labs/FLUX.2-klein-9B"
    )
    assert str(tmp_path).replace("\\", "/") in cfg.model_dir.replace("\\", "/")


def test_from_env_overrides(monkeypatch):
    monkeypatch.setenv("KLEIN_MAX_SIDE", "1024")
    monkeypatch.setenv("KLEIN_MODEL_DIR", "/custom/klein")
    monkeypatch.setenv("KLEIN_ENABLE_VAE_TILING", "true")
    cfg = KleinReceiverConfig.from_env()
    assert cfg.max_side == 1024
    assert cfg.model_dir == "/custom/klein"
    assert cfg.enable_vae_tiling is True
