"""semantic-tx download 子命令：下载所需模型文件。

模型清单从 ``ProjectConfig`` 派生：

- ``[models.diffusers]`` 的 ``transformer_path`` / ``controlnet_name`` 给出目标
  本地路径，本模块通过文件名匹配查表得到 HuggingFace/ModelScope 仓库来源；
- ``[models.vlm]`` 给出 VLM 完整仓库下载目标目录。

ComfyUI 路径在 Phase 2 已完全脱离，相关清单已移除。
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import click

from semantic_transmission.common.config import ProjectConfig, load_config

# === 默认配置 ===
DEFAULT_PROXY = "http://127.0.0.1:7890"
HF_MIRROR_ENDPOINT = "https://hf-mirror.com"
DEFAULT_CACHE_DIR = (
    Path(os.environ["MODEL_CACHE_DIR"]) if os.environ.get("MODEL_CACHE_DIR") else None
)


# === 单文件模型来源映射 ===
# 键: 目标文件名（取自 ProjectConfig 中 transformer_path / controlnet_name 的 basename）
# 值: (source, repo_id, repo_internal_path)
#   source: "huggingface" 或 "modelscope"
#   repo_id: 仓库 ID
#   repo_internal_path: 文件在仓库内的相对路径
_SINGLE_FILE_SOURCES: dict[str, tuple[str, str, str]] = {
    "z-image-turbo-Q8_0.gguf": (
        "huggingface",
        "city96/Z-Image-Turbo-gguf",
        "z-image-turbo-Q8_0.gguf",
    ),
    "Z-Image-Turbo-Fun-Controlnet-Union.safetensors": (
        "modelscope",
        "PAI/Z-Image-Turbo-Fun-Controlnet-Union",
        "Z-Image-Turbo-Fun-Controlnet-Union.safetensors",
    ),
}


@dataclass(frozen=True)
class _SingleFileTarget:
    """单文件下载条目。"""

    source: str
    repo_id: str
    repo_internal_path: str
    target_path: Path  # 落盘绝对路径

    @property
    def target_name(self) -> str:
        return self.target_path.name


@dataclass(frozen=True)
class _RepoTarget:
    """完整仓库下载条目（HuggingFace repo）。"""

    repo_id: str
    target_dir: Path


def _derive_single_file_targets(
    project_config: ProjectConfig,
) -> list[_SingleFileTarget]:
    """从 ProjectConfig 派生需要下载的单文件清单（GGUF transformer + ControlNet）。"""
    candidates = [
        project_config.diffusers_transformer_path,
        project_config.diffusers_controlnet_name,
    ]
    targets: list[_SingleFileTarget] = []
    for raw_path in candidates:
        if not raw_path:
            continue
        target_path = Path(raw_path)
        source_info = _SINGLE_FILE_SOURCES.get(target_path.name)
        if source_info is None:
            print(f"  [WARN] 未知的目标文件 {target_path.name}，无法派生下载来源，跳过")
            continue
        source, repo_id, repo_internal_path = source_info
        targets.append(
            _SingleFileTarget(
                source=source,
                repo_id=repo_id,
                repo_internal_path=repo_internal_path,
                target_path=target_path,
            )
        )
    return targets


def _derive_repo_targets(
    project_config: ProjectConfig, cache_dir: Path
) -> list[_RepoTarget]:
    """从 ProjectConfig 派生需要整库下载的 HuggingFace 仓库清单（VLM）。"""
    targets: list[_RepoTarget] = []
    vlm_repo = project_config.vlm_model_name
    if vlm_repo:
        vlm_path = project_config.vlm_model_path
        target_dir = Path(vlm_path) if vlm_path else cache_dir / vlm_repo
        targets.append(_RepoTarget(repo_id=vlm_repo, target_dir=target_dir))
    return targets


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
    cmd = [
        "modelscope",
        "download",
        "--model",
        repo_id,
        file_path,
        "--local_dir",
        str(target_dir),
        "--cache_dir",
        str(cache_dir / "modelscope"),
    ]
    env = os.environ.copy()
    for key in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"]:
        env.pop(key, None)
    print(f"  执行: {' '.join(cmd)}")
    subprocess.run(cmd, check=True, env=env)
    return target_dir / file_path


def _download_huggingface(repo_id, file_path, target_dir, proxy, hf_mirror, cache_dir):
    target_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        "hf",
        "download",
        repo_id,
        file_path,
        "--local-dir",
        str(target_dir),
        "--cache-dir",
        str(cache_dir / "huggingface"),
    ]
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
    cmd = [
        "hf",
        "download",
        repo_id,
        "--local-dir",
        str(target_dir),
        "--cache-dir",
        str(cache_dir / "huggingface"),
    ]
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
@click.option(
    "--proxy",
    default=None,
    type=str,
    help=f"HuggingFace 下载代理地址（默认: {DEFAULT_PROXY}，设为 'none' 禁用代理）",
)
@click.option(
    "--no-mirror",
    is_flag=True,
    default=False,
    help=f"禁用 HuggingFace 国内镜像（默认使用 {HF_MIRROR_ENDPOINT}）",
)
@click.option(
    "--cache-dir",
    default=DEFAULT_CACHE_DIR,
    type=click.Path(path_type=Path),
    help="下载缓存目录（默认从环境变量 MODEL_CACHE_DIR 读取）",
)
@click.option(
    "--dry-run", is_flag=True, default=False, help="仅显示将要执行的操作，不实际下载"
)
def download(proxy, no_mirror, cache_dir, dry_run):
    """下载项目所需模型文件（从 config.toml 派生清单）。"""
    project_config = load_config()

    if cache_dir is None:
        print(
            "错误：未指定缓存目录。请设置环境变量 MODEL_CACHE_DIR 或使用 --cache-dir 参数"
        )
        sys.exit(1)

    hf_mirror = not no_mirror
    if hf_mirror:
        _proxy = None
    elif proxy is not None:
        _proxy = None if proxy.lower() == "none" else proxy
    else:
        _proxy = (
            os.environ.get("HTTPS_PROXY")
            or os.environ.get("HTTP_PROXY")
            or DEFAULT_PROXY
        )

    cache_dir.mkdir(parents=True, exist_ok=True)

    single_file_targets = _derive_single_file_targets(project_config)
    repo_targets = _derive_repo_targets(project_config, cache_dir)

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
    for tool in {t.source for t in single_file_targets}:
        cmd = tool_cmd[tool]
        if not _check_tool(cmd):
            print(f"错误：{cmd} 未安装。请运行:")
            if tool == "modelscope":
                print("  uv tool install modelscope")
            else:
                print('  uv tool install "huggingface_hub[cli]"')
            sys.exit(1)

    if repo_targets and not _check_tool("hf"):
        print('错误：hf 未安装。请运行: uv tool install "huggingface_hub[cli]"')
        sys.exit(1)

    # === 下载 Diffusers 单文件模型 ===
    if single_file_targets:
        print("=== Diffusers 单文件模型 ===\n")
    tmp_dir = cache_dir / "_model_downloads"

    for t in single_file_targets:
        print(f"[{t.source}] {t.target_name}")
        print(f"  仓库: {t.repo_id}")
        print(f"  目标: {t.target_path}")

        if t.target_path.exists():
            size_mb = t.target_path.stat().st_size / (1024 * 1024)
            print(f"  已存在 ({size_mb:.1f} MB)，跳过")
            print()
            continue

        if dry_run:
            print("  dry-run，跳过下载")
            print()
            continue

        try:
            dl_dir = tmp_dir / t.source / t.repo_id.replace("/", "_")
            if t.source == "modelscope":
                downloaded = _download_modelscope(
                    t.repo_id, t.repo_internal_path, dl_dir, cache_dir
                )
            else:
                downloaded = _download_huggingface(
                    t.repo_id,
                    t.repo_internal_path,
                    dl_dir,
                    _proxy,
                    hf_mirror,
                    cache_dir,
                )

            if not downloaded.exists():
                print(f"  下载文件未找到: {downloaded}")
                print()
                continue

            t.target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(downloaded), str(t.target_path))
            size_mb = t.target_path.stat().st_size / (1024 * 1024)
            print(f"  下载完成 ({size_mb:.1f} MB)")
        except subprocess.CalledProcessError as e:
            print(f"  下载失败（命令返回码 {e.returncode}）")
        except Exception as e:
            print(f"  错误: {e}")
        print()

    if tmp_dir.exists() and not dry_run:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    # === 下载 HuggingFace 完整仓库模型（VLM） ===
    if repo_targets:
        print("=== HuggingFace 仓库模型 ===\n")

    for rt in repo_targets:
        print(f"[huggingface_repo] {rt.repo_id}")
        print(f"  目标: {rt.target_dir}")

        if _is_hf_repo_complete(rt.target_dir):
            print("  已存在（权重文件完整），跳过")
            print()
            continue

        if dry_run:
            print("  dry-run，跳过下载")
            print()
            continue

        try:
            _download_huggingface_repo(
                rt.repo_id, rt.target_dir, _proxy, hf_mirror, cache_dir
            )
            print("  下载完成")
        except subprocess.CalledProcessError as e:
            print(f"  下载失败（命令返回码 {e.returncode}）")
        except Exception as e:
            print(f"  错误: {e}")
        print()

    # === 汇总 ===
    print("=== 模型文件状态 ===")
    all_ok = True
    for t in single_file_targets:
        if t.target_path.exists():
            size_mb = t.target_path.stat().st_size / (1024 * 1024)
            print(f"  [Diffusers] {t.target_name} ({size_mb:.1f} MB)")
        else:
            print(f"  [Diffusers] {t.target_name} 缺失")
            all_ok = False

    for rt in repo_targets:
        if _is_hf_repo_complete(rt.target_dir):
            print(f"  [HF Repo] {rt.repo_id} ✓")
        else:
            print(f"  [HF Repo] {rt.repo_id} 缺失或不完整")
            all_ok = False

    if not single_file_targets and not repo_targets:
        print("  未派生出任何下载条目（请检查 config.toml [models.*] 配置）")
        all_ok = False

    if all_ok:
        print("\n所有模型文件就绪！")
    else:
        print("\n部分模型文件缺失，请检查错误信息")
        sys.exit(1)
