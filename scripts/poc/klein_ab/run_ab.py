"""klein vs Z-Image video→video 阶段 1 A/B harness（完全托管单脚本）。

流水：trim 源片 → smoke 锁工作分辨率 → 烘焙 fixture → 冻结 VLM prompt →
klein/Z-Image 主跑 → evaluate_video → results.json + DONE sentinel。

健壮性（无人值守）：
- 每阶段 try/except，崩溃也写 partial results.json + 写 ``DONE.partial``。
- smoke OOM 有界回退（候选分辨率 × 是否 vae_tiling），不无限重试。
- 每 backend 独立 try/except，一个崩不影响另一个。
- VLM 失败回退固定 prompt，A/B 仍可跑。
- 零交互输入。

设计见 docs/test-reports/2026-06-30-klein-video-ab-phase1-plan.md。
用法：uv run python scripts/poc/klein_ab/run_ab.py
"""

from __future__ import annotations

import argparse
import gc
import json
import subprocess
import sys
import time
import traceback
from pathlib import Path

import imageio.v2 as imageio
import numpy as np
import torch
from PIL import Image

from semantic_transmission.common.config import KleinReceiverConfig, load_config
from semantic_transmission.common.image_io import load_as_rgb
from semantic_transmission.common.video_io import write_frames
from semantic_transmission.pipeline.video_pipeline import _fill_failed_frames
from semantic_transmission.receiver import create_receiver
from semantic_transmission.receiver.base import FrameInput
from semantic_transmission.receiver.klein_receiver import fit_working_size
from semantic_transmission.sender.local_condition_extractor import LocalCannyExtractor

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_SOURCE = (
    Path(r"D:\CONGHAOYANG\Projects\WorkProjects\semantic-transmission")
    / "resources"
    / "test_videos"
    / "视频记录"
    / "20251109134829.mp4"
)
_BACKEND_DIRNAME = {"klein": "klein", "diffusers": "zimage"}


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def _empty_cache() -> None:
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


def _reset_peak() -> None:
    if torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats()


def _peak_vram_gb() -> float | None:
    if torch.cuda.is_available():
        return round(torch.cuda.max_memory_reserved() / 1024**3, 2)
    return None


def _is_oom(e: Exception) -> bool:
    if isinstance(e, torch.cuda.OutOfMemoryError):
        return True
    return "out of memory" in str(e).lower()


def load_window(src: Path, start: float, dur: float):
    """流式读源片，只保留 [start, start+dur) 秒窗口的帧。

    不走 ffmpeg 时间裁剪——源 mp4 容器时间戳常损坏（Duration N/A），基于时间的
    -ss/-to 会取不到帧。imageio 逐帧迭代不依赖时间戳，且只在内存保留窗口内帧。

    Returns:
        ``(frames, fps)``，frames 为 (H,W,3) uint8 RGB 列表。
    """
    reader = imageio.get_reader(src)
    meta = reader.get_meta_data()
    fps = float(meta.get("fps", 0.0) or 0.0)
    if fps <= 0:
        fps = 25.0
    s_idx = int(start * fps)
    e_idx = int((start + dur) * fps)
    frames = []
    try:
        for i, fr in enumerate(reader):
            if i < s_idx:
                continue
            if i >= e_idx:
                break
            frames.append(np.asarray(fr, dtype=np.uint8))
    finally:
        reader.close()
    if not frames:
        raise ValueError(f"窗口 [{s_idx},{e_idx}) 无帧（源可能不足 {start + dur}s）")
    return frames, fps


def smoke_lock_resolution(native_frames, candidates, canny, seed, smoke_frames):
    """前若干帧上跑 klein，锁定能扛的工作分辨率。

    Returns:
        ``(R, vae_tiling, history)``。全候选 OOM 则抛 RuntimeError。
    """
    history: list[dict] = []
    test = native_frames[: max(1, smoke_frames)]
    for cand in candidates:
        for vae_tiling in (False, True):
            label = f"R={cand}, vae_tiling={vae_tiling}"
            log(f"smoke 尝试 {label}（{len(test)} 帧）")
            rec = None
            try:
                cfg = KleinReceiverConfig(max_side=cand, enable_vae_tiling=vae_tiling)
                rec = create_receiver(config=cfg, backend="klein")
                _reset_peak()
                for f in test:
                    small = fit_working_size(load_as_rgb(f), cand)
                    edge = canny.extract(np.asarray(small))
                    rec.process(
                        load_as_rgb(edge), "a dashcam photo of a road scene", seed=seed
                    )
                peak = _peak_vram_gb()
                history.append(
                    {
                        "candidate": cand,
                        "vae_tiling": vae_tiling,
                        "result": "ok",
                        "peak_vram_gb": peak,
                    }
                )
                log(f"smoke 通过 {label}，峰值显存={peak}GB")
                return cand, vae_tiling, history
            except Exception as e:  # noqa: BLE001
                oom = _is_oom(e)
                history.append(
                    {
                        "candidate": cand,
                        "vae_tiling": vae_tiling,
                        "result": "oom" if oom else "error",
                        "error": str(e)[:300],
                    }
                )
                log(
                    f"smoke 失败 {label}: {'OOM' if oom else type(e).__name__}: {str(e)[:160]}"
                )
                if not oom:
                    raise
            finally:
                if rec is not None:
                    try:
                        rec.unload()
                    except Exception:  # noqa: BLE001
                        pass
                _empty_cache()
    raise RuntimeError(f"smoke 全部候选 OOM，无可用工作分辨率；history={history}")


def bake_fixture(native_frames, R, fixture_dir, fps):
    """把原生帧降采样到工作分辨率 R，落盘 fixture.mp4 + 逐帧 PNG。"""
    frames_dir = fixture_dir / "fixture_frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    small_frames = []
    for i, f in enumerate(native_frames):
        s = fit_working_size(load_as_rgb(f), R)
        small_frames.append(s)
        s.save(frames_dir / f"frame_{i:04d}.png")
    fx = fixture_dir / "fixture.mp4"
    write_frames(fx, small_frames, fps=fps)
    log(
        f"fixture 烘焙完成：{len(small_frames)} 帧 @ {small_frames[0].size} → {fx.name}"
    )
    return fx, small_frames


def freeze_prompts(small_frames, cfg, out_dir):
    """VLM 逐帧描述一次并存盘；失败回退固定 prompt。返回 prompts 列表。"""
    prompts: list[str] = []
    mode = "vlm"
    try:
        from semantic_transmission.sender.qwen_vl_sender import QwenVLSender

        vlm = QwenVLSender(
            model_name=cfg.vlm_model_name,
            model_path=cfg.vlm_model_path or None,
            max_new_tokens=cfg.vlm_max_new_tokens,
        )
        try:
            for i, f in enumerate(small_frames):
                prompts.append(vlm.describe(np.asarray(f)).text)
                if i % 20 == 0:
                    log(f"VLM describe {i + 1}/{len(small_frames)}")
        finally:
            vlm.unload()
            _empty_cache()
    except Exception as e:  # noqa: BLE001
        log(f"VLM 冻结失败，回退固定 prompt：{type(e).__name__}: {str(e)[:160]}")
        mode = "fixed-fallback"
        prompts = [
            "a dashcam photo of a road scene with vehicles, road markings and sky"
        ] * len(small_frames)

    total_bytes = sum(len(p.encode("utf-8")) for p in prompts)
    payload = {
        "mode": mode,
        "frames": [{"index": i, "prompt": p} for i, p in enumerate(prompts)],
        "failed_indices": [],
        "semantic_bitrate": {
            "total_bytes": total_bytes,
            "avg_bytes_per_frame": round(total_bytes / max(1, len(prompts)), 2),
        },
    }
    (out_dir / "prompts.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    log(
        f"prompt 冻结完成（{mode}）：{len(prompts)} 条，均 {payload['semantic_bitrate']['avg_bytes_per_frame']} B/帧"
    )
    return prompts


def run_backend(
    backend, small_frames, prompts, canny, R, vae_tiling, seed, out_dir, fps
):
    """对单个 backend 跑 process_batch，落盘帧/视频/summary，返回统计。"""
    bdir = out_dir / _BACKEND_DIRNAME[backend]
    fdir = bdir / "frames"
    fdir.mkdir(parents=True, exist_ok=True)

    if backend == "klein":
        cfg = KleinReceiverConfig(max_side=R, enable_vae_tiling=vae_tiling)
        rec = create_receiver(config=cfg, backend="klein")
    else:
        rec = create_receiver(backend="diffusers")

    frame_inputs = []
    for i, f in enumerate(small_frames):
        edge = canny.extract(np.asarray(f))
        frame_inputs.append(
            FrameInput(
                edge_image=load_as_rgb(edge),
                prompt_text=prompts[i],
                seed=seed,
                metadata={"name": f"frame_{i:04d}", "index": i},
            )
        )

    log(f"[{backend}] 开始主跑 {len(frame_inputs)} 帧 @ {small_frames[0].size}")
    _reset_peak()
    t0 = time.time()
    try:
        out = rec.process_batch(frame_inputs)
    finally:
        try:
            rec.unload()
        except Exception:  # noqa: BLE001
            pass
        _empty_cache()
    elapsed = time.time() - t0
    peak = _peak_vram_gb()

    images = out.images
    for i, img in enumerate(images):
        if img is not None:
            img.save(fdir / f"frame_{i:04d}.png")
    filled = _fill_failed_frames(images)
    write_frames(bdir / "out.mp4", filled, fps=fps)
    (bdir / "summary.json").write_text(
        json.dumps(out.stats.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    failed = [i for i, img in enumerate(images) if img is None]
    stat = {
        "backend": backend,
        "frames": len(images),
        "failed_indices": failed,
        "total_time_s": round(elapsed, 1),
        "avg_s_per_frame": round(elapsed / max(1, len(images)), 2),
        "peak_vram_gb": peak,
        "out_video": str(bdir / "out.mp4"),
    }
    log(
        f"[{backend}] 完成：{len(images) - len(failed)}/{len(images)} 帧，"
        f"总耗时 {stat['total_time_s']}s，均 {stat['avg_s_per_frame']}s/帧，峰值显存 {peak}GB"
    )
    return stat


def run_eval(backend, fixture_mp4, restored_mp4, prompts_json, eval_dir):
    """子进程调用 evaluate_video.py，返回 CLIP/PSNR/SSIM/LPIPS 均值。"""
    eval_dir.mkdir(parents=True, exist_ok=True)
    name = _BACKEND_DIRNAME[backend]
    out_json = eval_dir / f"{name}_eval.json"
    cmd = [
        sys.executable,
        "scripts/evaluate_video.py",
        "--original",
        str(fixture_mp4),
        "--restored",
        str(restored_mp4),
        "--prompts",
        str(prompts_json),
        "--output",
        str(out_json),
    ]
    log(f"[{backend}] 评估中…")
    r = subprocess.run(
        cmd,
        cwd=str(_PROJECT_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if r.returncode != 0 or not out_json.is_file():
        return {"error": f"eval rc={r.returncode}: {(r.stderr or '')[-300:]}"}
    data = json.loads(out_json.read_text(encoding="utf-8"))
    s = data["summary"]
    res = {k: s[k]["mean"] for k in ("clip_score", "psnr", "ssim", "lpips")}
    res["json"] = str(out_json)
    log(f"[{backend}] 评估完成：CLIP={res['clip_score']}")
    return res


def make_grid(small_frames, canny, out_dir, klein_dir, zimage_dir, n=5):
    """抽 n 帧并排 orig｜canny｜klein｜zimage 存网格。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    total = len(small_frames)
    if total == 0:
        return
    n = min(n, total)
    idxs = [round(i * (total - 1) / (n - 1)) for i in range(n)] if n > 1 else [0]

    def _load(d, idx):
        p = d / "frames" / f"frame_{idx:04d}.png"
        return Image.open(p).convert("RGB") if p.is_file() else None

    for idx in idxs:
        orig = small_frames[idx]
        edge = load_as_rgb(canny.extract(np.asarray(orig)))
        tiles = [orig, edge, _load(klein_dir, idx), _load(zimage_dir, idx)]
        h = orig.size[1]
        norm = []
        for t in tiles:
            if t is None:
                t = Image.new("RGB", orig.size, (40, 40, 40))
            if t.size[1] != h:
                t = t.resize((int(t.size[0] * h / t.size[1]), h))
            norm.append(t)
        w = sum(t.size[0] for t in norm)
        grid = Image.new("RGB", (w, h), (0, 0, 0))
        x = 0
        for t in norm:
            grid.paste(t, (x, 0))
            x += t.size[0]
        grid.save(out_dir / f"grid_{idx:04d}.png")
    log(f"目视网格完成：{len(idxs)} 张 → {out_dir}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="klein vs Z-Image video→video A/B")
    parser.add_argument("--source", type=Path, default=_DEFAULT_SOURCE)
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=_PROJECT_ROOT / "output" / "poc" / "klein-ab-phase1",
    )
    parser.add_argument("--start", type=float, default=20.0)
    parser.add_argument("--dur", type=float, default=10.0)
    parser.add_argument("--candidates", type=str, default="768,640")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--smoke-frames", type=int, default=3)
    parser.add_argument("--grid", type=int, default=5)
    args = parser.parse_args(argv)

    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    sentinel_ok = out_dir / "DONE"
    sentinel_partial = out_dir / "DONE.partial"
    for s in (sentinel_ok, sentinel_partial):
        if s.exists():
            s.unlink()

    candidates = [int(x) for x in args.candidates.split(",") if x.strip()]
    cfg = load_config()
    canny = LocalCannyExtractor(cfg.canny_low_threshold, cfg.canny_high_threshold)
    results: dict = {
        "source": str(args.source),
        "window_s": [args.start, args.start + args.dur],
        "seed": args.seed,
        "candidates": candidates,
        "backends": {},
        "eval": {},
        "phases": {},
    }
    t_start = time.time()
    ok = True

    try:
        if not args.source.is_file():
            raise FileNotFoundError(f"源片不存在: {args.source}")

        # ① 读窗口（流式，绕开坏时间戳）
        fixture_dir = out_dir / "fixture"
        native_frames, fps = load_window(args.source, args.start, args.dur)
        h0, w0 = native_frames[0].shape[:2]
        results["native"] = {"frames": len(native_frames), "fps": fps, "size": [w0, h0]}
        log(f"读窗口完成：{len(native_frames)} 帧 @ {w0}x{h0} {fps}fps")

        # ② smoke 锁分辨率
        try:
            R, vae_tiling, smoke_hist = smoke_lock_resolution(
                native_frames, candidates, canny, args.seed, args.smoke_frames
            )
            klein_ok = True
        except Exception as e:  # noqa: BLE001
            log(
                f"smoke 全失败：klein 跳过，fixture 用最小候选 R={min(candidates)} 供 Z-Image baseline"
            )
            R, vae_tiling, klein_ok = min(candidates), True, False
            smoke_hist = [{"result": "all-failed", "error": str(e)[:300]}]
        results["phases"]["smoke"] = {
            "locked_R": R,
            "vae_tiling": vae_tiling,
            "klein_ok": klein_ok,
            "history": smoke_hist,
        }

        # ③ 烘焙 fixture
        fixture_mp4, small_frames = bake_fixture(native_frames, R, fixture_dir, fps)
        results["fixture"] = {
            "R": R,
            "size": list(small_frames[0].size),
            "frames": len(small_frames),
            "mp4": str(fixture_mp4),
        }
        del native_frames
        _empty_cache()

        # ④ 冻结 prompt
        prompts = freeze_prompts(small_frames, cfg, out_dir)
        prompts_json = out_dir / "prompts.json"

        # ⑤ A/B 主跑（每 backend 独立保护）
        backends = (["klein"] if klein_ok else []) + ["diffusers"]
        for backend in backends:
            try:
                results["backends"][backend] = run_backend(
                    backend,
                    small_frames,
                    prompts,
                    canny,
                    R,
                    vae_tiling,
                    args.seed,
                    out_dir,
                    fps,
                )
            except Exception as e:  # noqa: BLE001
                ok = False
                log(f"[{backend}] 主跑失败：{type(e).__name__}: {str(e)[:200]}")
                results["backends"][backend] = {
                    "backend": backend,
                    "error": f"{type(e).__name__}: {str(e)[:300]}",
                    "oom": _is_oom(e),
                }
                _empty_cache()

        # ⑥ 评估（每 backend 独立保护）
        for backend in backends:
            bstat = results["backends"].get(backend, {})
            if "out_video" not in bstat:
                continue
            try:
                results["eval"][backend] = run_eval(
                    backend,
                    fixture_mp4,
                    Path(bstat["out_video"]),
                    prompts_json,
                    out_dir / "eval",
                )
            except Exception as e:  # noqa: BLE001
                log(f"[{backend}] 评估失败：{type(e).__name__}: {str(e)[:160]}")
                results["eval"][backend] = {
                    "error": f"{type(e).__name__}: {str(e)[:200]}"
                }

        # ⑦ 目视网格
        try:
            make_grid(
                small_frames,
                canny,
                out_dir / "compare",
                out_dir / "klein",
                out_dir / "zimage",
                n=args.grid,
            )
        except Exception as e:  # noqa: BLE001
            log(f"网格失败：{type(e).__name__}: {str(e)[:160]}")

    except Exception as e:  # noqa: BLE001
        ok = False
        results["fatal_error"] = f"{type(e).__name__}: {e}"
        results["traceback"] = traceback.format_exc()
        log(f"致命错误：{type(e).__name__}: {e}")
        traceback.print_exc()

    results["total_wall_s"] = round(time.time() - t_start, 1)
    (out_dir / "results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    sentinel = sentinel_ok if ok else sentinel_partial
    sentinel.write_text(time.strftime("%Y-%m-%d %H:%M:%S"), encoding="utf-8")
    log(
        f"{'=' * 50}\n全部结束（{'OK' if ok else 'PARTIAL'}），results.json + {sentinel.name} 已写。总墙钟 {results['total_wall_s']}s"
    )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
