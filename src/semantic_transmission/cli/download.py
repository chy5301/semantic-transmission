"""semantic-tx download 子命令：下载所需模型文件。"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import click

# === 默认配置 ===
DEFAULT_COMFYUI_DIR = (
    Path(os.environ["COMFYUI_DIR"]) if os.environ.get("COMFYUI_DIR") else None
)
DEFAULT_PROXY = "http://127.0.0.1:7890"
HF_MIRROR_ENDPOINT = "https://hf-mirror.com"
DEFAULT_CACHE_DIR = (
    Path(os.environ["MODEL_CACHE_DIR"]) if os.environ.get("MODEL_CACHE_DIR") else None
)

# === 模型定义 ===
COMFYUI_MODELS = [
    ("huggingface", "Comfy-Org/z_image_turbo", "split_files/text_encoders/qwen_3_4b.safetensors", "text_encoders", "qwen_3_4b.safetensors"),
    ("huggingface", "Comfy-Org/z_image_turbo", "split_files/diffusion_models/z_image_turbo_bf16.safetensors", "diffusion_models", "z_image_turbo_bf16.safetensors"),
    ("huggingface", "Comfy-Org/z_image_turbo", "split_files/vae/ae.safetensors", "vae", "ae.safetensors"),
    ("modelscope", "PAI/Z-Image-Turbo-Fun-Controlnet-Union", "Z-Image-Turbo-Fun-Controlnet-Union.safetensors", "model_patches", "Z-Image-Turbo-Fun-Controlnet-Union.safetensors"),
]

HF_REPO_MODELS = [
    ("Qwen/Qwen2.5-VL-7B-Instruct",),
]


def _check_tool(name: str) -> bool:
    return shutil.which(name) is not None


def _is_hf_repo_complete(target_dir: Path) -> bool:
    index_file = target_dir / "model.safetensors.index.json"
    if not index_file.exists():
        return (target_dir / "model.safetensors").exists()
    index = json.loads(index_file.read_text(encoding="utf-8"))
    weight_files = set(index.get("weight_map", {}).values())
    for wf in weight_files:
        if not (target_dir / wf).exists():
            return False
    return True


def _download_modelscope(repo_id, file_path, target_dir, cache_dir):
    target_dir.mkdir(parents=True, exist_ok=True)
    cmd = ["modelscope", "download", "--model", repo_id, file_path, "--local_dir", str(target_dir), "--cache_dir", str(cache_dir / "modelscope")]
    env = os.environ.copy()
    for key in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"]:
        env.pop(key, None)
    print(f"  执行: {' '.join(cmd)}")
    subprocess.run(cmd, check=True, env=env)
    return target_dir / file_path


def _download_huggingface(repo_id, file_path, target_dir, proxy, hf_mirror, cache_dir):
    target_dir.mkdir(parents=True, exist_ok=True)
    cmd = ["hf", "download", repo_id, file_path, "--local-dir", str(target_dir), "--cache-dir", str(cache_dir / "huggingface")]
    env = os.environ.copy()
    if hf_mirror:
        env["HF_ENDPOINT"] = HF_MIRROR_ENDPOINT
        for key in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"]:
            env.pop(key, None)
        print(f"  使用镜像: {HF_MIRROR_ENDPOINT}")
    elif proxy:
        env["HTTP_PROXY"] = proxy
        env["HTTPS_PROXY"] = proxy
        env["http_proxy"] = proxy
        env["https_proxy"] = proxy
        print(f"  使用代理: {proxy}")
    print(f"  执行: {' '.join(cmd)}")
    subprocess.run(cmd, check=True, env=env)
    return target_dir / file_path


def _download_huggingface_repo(repo_id, target_dir, proxy, hf_mirror, cache_dir):
    target_dir.mkdir(parents=True, exist_ok=True)
    cmd = ["hf", "download", repo_id, "--local-dir", str(target_dir), "--cache-dir", str(cache_dir / "huggingface")]
    env = os.environ.copy()
    if hf_mirror:
        env["HF_ENDPOINT"] = HF_MIRROR_ENDPOINT
        for key in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"]:
            env.pop(key, None)
        print(f"  使用镜像: {HF_MIRROR_ENDPOINT}")
    elif proxy:
        env["HTTP_PROXY"] = proxy
        env["HTTPS_PROXY"] = proxy
        env["http_proxy"] = proxy
        env["https_proxy"] = proxy
        print(f"  使用代理: {proxy}")
    print(f"  执行: {' '.join(cmd)}")
    subprocess.run(cmd, check=True, env=env)
    return target_dir


@click.command()
@click.option("--comfyui-dir", default=DEFAULT_COMFYUI_DIR, type=click.Path(path_type=Path), help="ComfyUI 安装目录（默认从环境变量 COMFYUI_DIR 读取）")
@click.option("--proxy", default=None, type=str, help=f"HuggingFace 下载代理地址（默认: {DEFAULT_PROXY}，设为 'none' 禁用代理）")
@click.option("--no-mirror", is_flag=True, default=False, help=f"禁用 HuggingFace 国内镜像（默认使用 {HF_MIRROR_ENDPOINT}）")
@click.option("--cache-dir", default=DEFAULT_CACHE_DIR, type=click.Path(path_type=Path), help="下载缓存目录（默认从环境变量 MODEL_CACHE_DIR 读取）")
@click.option("--dry-run", is_flag=True, default=False, help="仅显示将要执行的操作，不实际下载")
def download(comfyui_dir, proxy, no_mirror, cache_dir, dry_run):
    """下载 ComfyUI 所需模型文件。"""
    if comfyui_dir is None:
        print("错误：未指定 ComfyUI 目录。请设置环境变量 COMFYUI_DIR 或使用 --comfyui-dir 参数")
        sys.exit(1)
    if cache_dir is None:
        print("错误：未指定缓存目录。请设置环境变量 MODEL_CACHE_DIR 或使用 --cache-dir 参数")
        sys.exit(1)

    hf_mirror = not no_mirror
    if hf_mirror:
        _proxy = None
    elif proxy is not None:
        _proxy = None if proxy.lower() == "none" else proxy
    else:
        _proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY") or DEFAULT_PROXY

    models_dir = comfyui_dir / "models"
    if not models_dir.exists():
        print(f"错误：ComfyUI models 目录不存在: {models_dir}")
        sys.exit(1)

    cache_dir.mkdir(parents=True, exist_ok=True)

    print(f"ComfyUI 目录: {comfyui_dir}")
    print(f"模型目录:     {models_dir}")
    print(f"缓存目录:     {cache_dir}")
    if hf_mirror:
        print(f"HF 访问方式:  镜像 ({HF_MIRROR_ENDPOINT})")
    elif _proxy:
        print(f"HF 代理:      {_proxy}")
    else:
        print("HF 代理:      无（直连）")
    print()

    # 检查 CLI 工具
    tool_cmd = {"modelscope": "modelscope", "huggingface": "hf"}
    for tool in {m[0] for m in COMFYUI_MODELS}:
        cmd = tool_cmd[tool]
        if not _check_tool(cmd):
            print(f"错误：{cmd} 未安装。请运行:")
            if tool == "modelscope":
                print("  uv tool install modelscope")
            else:
                print('  uv tool install "huggingface_hub[cli]"')
            sys.exit(1)

    if HF_REPO_MODELS and not _check_tool("hf"):
        print('错误：hf 未安装。请运行: uv tool install "huggingface_hub[cli]"')
        sys.exit(1)

    # === 下载 ComfyUI 单文件模型 ===
    print("=== ComfyUI 模型 ===\n")
    tmp_dir = comfyui_dir / "_model_downloads"

    for source, repo_id, file_path, sub_dir, target_name in COMFYUI_MODELS:
        target_path = models_dir / sub_dir / target_name
        print(f"[{source}] {target_name}")
        print(f"  仓库: {repo_id}")
        print(f"  目标: {target_path}")

        if target_path.exists():
            size_mb = target_path.stat().st_size / (1024 * 1024)
            print(f"  已存在 ({size_mb:.1f} MB)，跳过")
            print()
            continue

        if dry_run:
            print("  dry-run，跳过下载")
            print()
            continue

        try:
            dl_dir = tmp_dir / source / repo_id.replace("/", "_")
            if source == "modelscope":
                downloaded = _download_modelscope(repo_id, file_path, dl_dir, cache_dir)
            else:
                downloaded = _download_huggingface(repo_id, file_path, dl_dir, _proxy, hf_mirror, cache_dir)

            if not downloaded.exists():
                print(f"  下载文件未找到: {downloaded}")
                print()
                continue

            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(downloaded), str(target_path))
            size_mb = target_path.stat().st_size / (1024 * 1024)
            print(f"  下载完成 ({size_mb:.1f} MB)")
        except subprocess.CalledProcessError as e:
            print(f"  下载失败（命令返回码 {e.returncode}）")
        except Exception as e:
            print(f"  错误: {e}")
        print()

    if tmp_dir.exists() and not dry_run:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    # === 下载 HuggingFace 完整仓库模型 ===
    if HF_REPO_MODELS:
        print("=== HuggingFace 仓库模型 ===\n")

    for (repo_id,) in HF_REPO_MODELS:
        target_dir = cache_dir / repo_id
        print(f"[huggingface_repo] {repo_id}")
        print(f"  目标: {target_dir}")

        if _is_hf_repo_complete(target_dir):
            print("  已存在（权重文件完整），跳过")
            print()
            continue

        if dry_run:
            print("  dry-run，跳过下载")
            print()
            continue

        try:
            _download_huggingface_repo(repo_id, target_dir, _proxy, hf_mirror, cache_dir)
            print("  下载完成")
        except subprocess.CalledProcessError as e:
            print(f"  下载失败（命令返回码 {e.returncode}）")
        except Exception as e:
            print(f"  错误: {e}")
        print()

    # === 汇总 ===
    print("=== 模型文件状态 ===")
    all_ok = True
    for _, _, _, sub_dir, target_name in COMFYUI_MODELS:
        target_path = models_dir / sub_dir / target_name
        if target_path.exists():
            size_mb = target_path.stat().st_size / (1024 * 1024)
            print(f"  [ComfyUI] {sub_dir}/{target_name} ({size_mb:.1f} MB)")
        else:
            print(f"  [ComfyUI] {sub_dir}/{target_name} 缺失")
            all_ok = False

    for (repo_id,) in HF_REPO_MODELS:
        target_dir = cache_dir / repo_id
        if _is_hf_repo_complete(target_dir):
            print(f"  [HF Repo] {repo_id} ✓")
        else:
            print(f"  [HF Repo] {repo_id} 缺失或不完整")
            all_ok = False

    if all_ok:
        print("\n所有模型文件就绪！")
    else:
        print("\n部分模型文件缺失，请检查错误信息")
        sys.exit(1)
