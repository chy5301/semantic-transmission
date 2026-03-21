"""下载 ComfyUI 所需模型文件到指定目录。

使用 hf CLI 从 HuggingFace 下载主模型（ComfyUI 格式单文件），
使用 modelscope CLI 从魔搭下载 ControlNet Union 补丁（国内直连更快）。

工具安装：
    uv tool install modelscope
    uv tool install "huggingface_hub[cli]"

用法示例：
    # 查看将要下载的文件（不实际下载）
    uv run python scripts/download_models.py --dry-run

    # 正式下载（使用默认代理和路径）
    uv run python scripts/download_models.py

    # 指定代理和 ComfyUI 路径
    uv run python scripts/download_models.py --proxy http://127.0.0.1:7890 --comfyui-dir D:\\path\\to\\ComfyUI

    # 使用 HuggingFace 国内镜像替代代理
    uv run python scripts/download_models.py --hf-mirror
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

# === 默认配置 ===

# ComfyUI 安装路径
DEFAULT_COMFYUI_DIR = Path(
    r"D:\CONGHAOYANG\工具\ComfyUI\ComfyUI-aki\ComfyUI-aki-v3\ComfyUI"
)

# 默认代理地址（用于 HuggingFace 下载）
DEFAULT_PROXY = "http://127.0.0.1:7890"

# HuggingFace 国内镜像（--hf-mirror 启用时替代代理）
HF_MIRROR_ENDPOINT = "https://hf-mirror.com"

# 模型下载缓存目录（避免占用 C 盘默认缓存）
DEFAULT_CACHE_DIR = Path(r"D:\Downloads\Models")

# === 模型定义 ===
# (源, 仓库ID, 仓库内文件路径, ComfyUI models/ 下的子目录, 目标文件名)
MODELS = [
    # HuggingFace: Comfy-Org/z_image_turbo（ComfyUI 格式单文件）
    # 注：魔搭 Tongyi-MAI/Z-Image-Turbo 存的是分片模型（DiffSynth 格式），不兼容 ComfyUI
    (
        "huggingface",
        "Comfy-Org/z_image_turbo",
        "split_files/text_encoders/qwen_3_4b.safetensors",
        "text_encoders",
        "qwen_3_4b.safetensors",
    ),
    (
        "huggingface",
        "Comfy-Org/z_image_turbo",
        "split_files/diffusion_models/z_image_turbo_bf16.safetensors",
        "diffusion_models",
        "z_image_turbo_bf16.safetensors",
    ),
    (
        "huggingface",
        "Comfy-Org/z_image_turbo",
        "split_files/vae/ae.safetensors",
        "vae",
        "ae.safetensors",
    ),
    # 魔搭: PAI/Z-Image-Turbo-Fun-Controlnet-Union（国内直连，无需代理）
    (
        "modelscope",
        "PAI/Z-Image-Turbo-Fun-Controlnet-Union",
        "Z-Image-Turbo-Fun-Controlnet-Union.safetensors",
        "model_patches",
        "Z-Image-Turbo-Fun-Controlnet-Union.safetensors",
    ),
]


def check_tool(name: str) -> bool:
    return shutil.which(name) is not None


def download_modelscope(
    repo_id: str, file_path: str, target_dir: Path, cache_dir: Path
) -> Path:
    """使用 modelscope CLI 下载单个文件（国内直连，不需要代理）。"""
    target_dir.mkdir(parents=True, exist_ok=True)
    cmd = ["modelscope", "download", "--model", repo_id, file_path,
           "--local_dir", str(target_dir),
           "--cache_dir", str(cache_dir / "modelscope")]

    # modelscope 走国内直连，清除代理环境变量避免干扰
    env = os.environ.copy()
    for key in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"]:
        env.pop(key, None)

    print(f"  执行: {' '.join(cmd)}")
    subprocess.run(cmd, check=True, env=env)
    return target_dir / file_path


def download_huggingface(
    repo_id: str,
    file_path: str,
    target_dir: Path,
    proxy: str | None,
    hf_mirror: bool,
    cache_dir: Path,
) -> Path:
    """使用 hf CLI 下载单个文件（需要代理或镜像）。"""
    target_dir.mkdir(parents=True, exist_ok=True)
    cmd = ["hf", "download", repo_id, file_path,
           "--local-dir", str(target_dir),
           "--cache-dir", str(cache_dir / "huggingface")]

    env = os.environ.copy()

    # 配置访问方式：镜像优先于代理
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


def main():
    parser = argparse.ArgumentParser(
        description="下载 ComfyUI 所需模型文件",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--comfyui-dir", type=Path, default=DEFAULT_COMFYUI_DIR,
        help=f"ComfyUI 安装目录 (默认: {DEFAULT_COMFYUI_DIR})",
    )
    parser.add_argument(
        "--proxy", type=str, default=None,
        help=f"HuggingFace 下载代理地址 (默认: {DEFAULT_PROXY}，"
             f"设为 'none' 禁用代理)",
    )
    parser.add_argument(
        "--hf-mirror", action="store_true",
        help=f"使用 HuggingFace 国内镜像 ({HF_MIRROR_ENDPOINT}) 替代代理",
    )
    parser.add_argument(
        "--cache-dir", type=Path, default=DEFAULT_CACHE_DIR,
        help=f"下载缓存目录 (默认: {DEFAULT_CACHE_DIR})",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="仅显示将要执行的操作，不实际下载",
    )
    args = parser.parse_args()

    # 确定 HuggingFace 代理配置
    if args.hf_mirror:
        proxy = None
    elif args.proxy is not None:
        proxy = None if args.proxy.lower() == "none" else args.proxy
    else:
        proxy = (
            os.environ.get("HTTPS_PROXY")
            or os.environ.get("HTTP_PROXY")
            or DEFAULT_PROXY
        )

    models_dir = args.comfyui_dir / "models"
    if not models_dir.exists():
        print(f"错误：ComfyUI models 目录不存在: {models_dir}")
        sys.exit(1)

    # 确保缓存目录存在
    args.cache_dir.mkdir(parents=True, exist_ok=True)

    print(f"ComfyUI 目录: {args.comfyui_dir}")
    print(f"模型目录:     {models_dir}")
    print(f"缓存目录:     {args.cache_dir}")
    if args.hf_mirror:
        print(f"HF 访问方式:  镜像 ({HF_MIRROR_ENDPOINT})")
    elif proxy:
        print(f"HF 代理:      {proxy}")
    else:
        print("HF 代理:      无（直连）")
    print()

    # 检查 CLI 工具
    tool_cmd = {"modelscope": "modelscope", "huggingface": "hf"}
    for tool in {m[0] for m in MODELS}:
        cmd = tool_cmd[tool]
        if not check_tool(cmd):
            print(f"错误：{cmd} 未安装。请运行:")
            if tool == "modelscope":
                print("  uv tool install modelscope")
            else:
                print('  uv tool install "huggingface_hub[cli]"')
            sys.exit(1)

    # 临时下载目录
    tmp_dir = args.comfyui_dir / "_model_downloads"

    for source, repo_id, file_path, sub_dir, target_name in MODELS:
        target_path = models_dir / sub_dir / target_name
        print(f"[{source}] {target_name}")
        print(f"  仓库: {repo_id}")
        print(f"  目标: {target_path}")

        if target_path.exists():
            size_mb = target_path.stat().st_size / (1024 * 1024)
            print(f"  已存在 ({size_mb:.1f} MB)，跳过")
            print()
            continue

        if args.dry_run:
            print("  dry-run，跳过下载")
            print()
            continue

        try:
            dl_dir = tmp_dir / source / repo_id.replace("/", "_")
            if source == "modelscope":
                downloaded = download_modelscope(
                    repo_id, file_path, dl_dir, args.cache_dir
                )
            else:
                downloaded = download_huggingface(
                    repo_id, file_path, dl_dir,
                    proxy=proxy, hf_mirror=args.hf_mirror,
                    cache_dir=args.cache_dir,
                )

            if not downloaded.exists():
                print(f"  下载文件未找到: {downloaded}")
                print()
                continue

            # 移动到目标位置
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(downloaded), str(target_path))
            size_mb = target_path.stat().st_size / (1024 * 1024)
            print(f"  下载完成 ({size_mb:.1f} MB)")
        except subprocess.CalledProcessError as e:
            print(f"  下载失败（命令返回码 {e.returncode}）")
        except Exception as e:
            print(f"  错误: {e}")
        print()

    # 清理临时目录
    if tmp_dir.exists() and not args.dry_run:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        print("已清理临时下载目录")

    # 汇总
    print("\n=== 模型文件状态 ===")
    all_ok = True
    for _, _, _, sub_dir, target_name in MODELS:
        target_path = models_dir / sub_dir / target_name
        if target_path.exists():
            size_mb = target_path.stat().st_size / (1024 * 1024)
            print(f"  {sub_dir}/{target_name} ({size_mb:.1f} MB)")
        else:
            print(f"  {sub_dir}/{target_name} 缺失")
            all_ok = False

    if all_ok:
        print("\n所有模型文件就绪！")
    else:
        print("\n部分模型文件缺失，请检查错误信息")
        sys.exit(1)


if __name__ == "__main__":
    main()
