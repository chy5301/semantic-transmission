"""klein 阶段 2 参考帧时间一致性补偿 harness（复用阶段 1 资产、单模型 klein）。

流水：读阶段 1 fixture_frames + 冻结 prompts → 多参考 smoke 探显存（有界回退）→
按 TemporalPolicyConfig 主跑（关键帧透传 / 中间帧带参考生成）→ 质量两栏评估 +
时序两读 + baseline 对照 → results.json + DONE sentinel + 目视网格。

健壮性：崩溃写 partial results + DONE.partial；smoke OOM 有界回退并同步重烘 baseline
分辨率；零交互输入。

用法（长 GPU 任务，须脱离跑；以模块方式运行以便 scripts.* 包导入）：
    uv run python -m scripts.poc.klein_ab.run_phase2 \
        --reference-mode prev --keyframe-interval 12 --label x_n12
    # smoke 验证接线（少量帧）：加 --limit 6
"""

from __future__ import annotations

import argparse
import json
import time
import traceback
from pathlib import Path

import numpy as np
from PIL import Image

from scripts.poc.klein_ab.phase2 import (
    TemporalPolicyConfig,
    build_reference_images,
    is_keyframe,
    split_summary,
)
from scripts.poc.klein_ab.run_ab import (
    _empty_cache,
    _is_oom,
    _peak_vram_gb,
    _reset_peak,
    log,
)
from semantic_transmission.common.config import KleinReceiverConfig, load_config
from semantic_transmission.common.image_io import load_as_rgb
from semantic_transmission.common.video_io import write_frames
from semantic_transmission.evaluation.temporal_consistency import temporal_report
from semantic_transmission.evaluation.video_eval import evaluate_video
from semantic_transmission.pipeline.video_pipeline import _fill_failed_frames
from semantic_transmission.receiver import create_receiver
from semantic_transmission.receiver.klein_receiver import fit_working_size
from semantic_transmission.sender.local_condition_extractor import LocalCannyExtractor

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_PHASE1_DIR = _PROJECT_ROOT / "output" / "poc" / "klein-ab-phase1"
_STATIC_WINDOW = (120, 128)  # 近静止段 [120,128)，重点看闪烁


def _load_pngs(frames_dir: Path, limit: int | None) -> list[Image.Image]:
    """按帧号顺序加载 PNG 为 RGB PIL 列表。"""
    paths = sorted(frames_dir.glob("frame_*.png"))
    if limit:
        paths = paths[:limit]
    return [load_as_rgb(p) for p in paths]


def _load_prompts(path: Path, limit: int | None) -> list[str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    ordered = sorted(data["frames"], key=lambda f: f["index"])
    prompts = [f.get("prompt", "") for f in ordered]
    return prompts[:limit] if limit else prompts


def _as_arrays(images: list[Image.Image]) -> list[np.ndarray]:
    return [np.asarray(im) for im in images]


def _fit_all(images: list[Image.Image], max_side: int) -> list[Image.Image]:
    """把整段帧统一降采样到工作分辨率 max_side（保宽高比、round 16）。

    smoke 若从原生分辨率回退到更小 R，fixture / baseline / 透传关键帧都要同步归一化到 R，
    否则透传帧(原生) 与生成帧(R) 尺寸混杂会让 write_frames/temporal_report 崩溃，并把
    X@R 与 baseline@原生 变成不公平的跨分辨率对照（落实 spec §5.4/§9 同步重烘 baseline）。
    """
    return [fit_working_size(im, max_side) for im in images]


def smoke_probe(fixture, canny, policy, candidates, seed):
    """前 3 帧跑真实策略，锁能扛的工作分辨率（多参考显存有界回退）。

    Returns: (max_side, vae_tiling, history)。全候选 OOM 抛 RuntimeError。
    """
    history: list[dict] = []
    test = fixture[: min(3, len(fixture))]
    for cand in candidates:
        for vae_tiling in (False, True):
            label = f"R={cand}, vae_tiling={vae_tiling}"
            log(
                f"smoke 尝试多参考 {label}（{len(test)} 帧, mode={policy.reference_mode}）"
            )
            rec = None
            try:
                cfg = KleinReceiverConfig(max_side=cand, enable_vae_tiling=vae_tiling)
                rec = create_receiver(config=cfg, backend="klein")
                _reset_peak()
                prev_out = None
                last_kf = None
                for i, frame in enumerate(test):
                    edge = canny.extract(np.asarray(frame))
                    if is_keyframe(i, policy) and policy.keyframe_passthrough:
                        prev_out = frame
                        last_kf = frame
                        continue
                    refs = build_reference_images(
                        policy.reference_mode, prev_out, last_kf
                    )
                    prev_out = rec.process(
                        load_as_rgb(edge),
                        "a dashcam road scene",
                        seed=seed,
                        reference_images=refs,
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
    raise RuntimeError(f"smoke 全部候选 OOM；history={history}")


def run_policy(fixture, prompts, canny, policy, max_side, vae_tiling, seed):
    """按策略主跑：关键帧透传、中间帧带参考生成。返回 (输出帧列表, 关键帧下标, 统计)。"""
    cfg = KleinReceiverConfig(max_side=max_side, enable_vae_tiling=vae_tiling)
    rec = create_receiver(config=cfg, backend="klein")
    outputs: list[Image.Image | None] = []
    keyframe_indices: list[int] = []
    prev_out = None
    last_kf = None
    _reset_peak()
    t0 = time.time()
    failed = 0
    try:
        for i, frame in enumerate(fixture):
            if is_keyframe(i, policy) and policy.keyframe_passthrough:
                outputs.append(frame)  # 透传原图，不生成
                keyframe_indices.append(i)
                prev_out = frame  # 链首复位到真关键帧
                last_kf = frame
                continue
            if is_keyframe(i, policy):
                last_kf = frame  # 关键帧但不透传（passthrough=False）时仍更新锚
            edge = canny.extract(np.asarray(frame))
            refs = build_reference_images(policy.reference_mode, prev_out, last_kf)
            try:
                img = rec.process(
                    load_as_rgb(edge), prompts[i], seed=seed, reference_images=refs
                )
            except Exception as e:  # noqa: BLE001
                log(f"[{i}] 生成失败：{type(e).__name__}: {str(e)[:160]}")
                img = None
                failed += 1
            outputs.append(img)
            prev_out = img if img is not None else prev_out
            if (i + 1) % 20 == 0:
                log(f"主跑 {i + 1}/{len(fixture)}")
    finally:
        try:
            rec.unload()
        except Exception:  # noqa: BLE001
            pass
        _empty_cache()
    elapsed = time.time() - t0
    generated = len(fixture) - len(keyframe_indices)
    stat = {
        "frames": len(fixture),
        "keyframe_count": len(keyframe_indices),
        "generated_frames": generated,
        "failed": failed,
        "total_time_s": round(elapsed, 1),
        "avg_s_per_generated": round(elapsed / max(1, generated), 2),
        "peak_vram_gb": _peak_vram_gb(),
    }
    log(
        f"主跑完成：{generated} 生成 + {len(keyframe_indices)} 透传，"
        f"失败 {failed}，均 {stat['avg_s_per_generated']}s/生成帧，峰值 {stat['peak_vram_gb']}GB"
    )
    return outputs, keyframe_indices, stat


def eval_quality(orig_arrays, restored_arrays, prompts, keyframe_indices, device):
    """逐帧质量评估 + 两栏拆分。"""
    report = evaluate_video(
        orig_arrays, restored_arrays, prompts=prompts, device=device
    )
    return split_summary(report["frames"], keyframe_indices)


def window_mae(arrays, lo, hi):
    """近静止窗口 [lo,hi) 的相邻帧 MAE 均值（纯闪烁读数）。"""
    from semantic_transmission.evaluation.temporal_consistency import frame_mae_series

    sub = arrays[lo:hi]
    series = frame_mae_series(sub)
    return float(np.mean(series)) if series else None


def _cell(img, size):
    return img if img is not None else Image.new("RGB", size, (40, 40, 40))


def make_grid(orig, canny, restored, baseline, out_dir, static_window=None, n=5):
    """抽 n 帧并排 orig｜canny｜drop-in｜X 网格；并对近静止窗口拼连续帧条带。

    baseline（阶段 1 drop-in，长度须等于 orig）作对照列；为空则退回 orig｜canny｜X。
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    total = len(orig)
    if total == 0:
        return
    has_base = len(baseline) == total
    n = min(n, total)
    idxs = [round(i * (total - 1) / (n - 1)) for i in range(n)] if n > 1 else [0]
    for idx in idxs:
        o = orig[idx]
        edge = load_as_rgb(canny.extract(np.asarray(o)))
        tiles = [o, edge]
        if has_base:
            tiles.append(_cell(baseline[idx], o.size))  # drop-in 对照列
        tiles.append(_cell(restored[idx], o.size))
        h = o.size[1]
        norm = [
            t if t.size[1] == h else t.resize((int(t.size[0] * h / t.size[1]), h))
            for t in tiles
        ]
        w = sum(t.size[0] for t in norm)
        grid = Image.new("RGB", (w, h), (0, 0, 0))
        x = 0
        for t in norm:
            grid.paste(t, (x, 0))
            x += t.size[0]
        grid.save(out_dir / f"grid_{idx:04d}.png")
    cols = "orig|canny|drop-in|X" if has_base else "orig|canny|X"
    log(f"目视网格完成：{len(idxs)} 张（{cols}）→ {out_dir}")
    if static_window is not None:
        _static_strip(orig, restored, baseline, static_window, out_dir)


def _static_strip(orig, restored, baseline, window, out_dir):
    """近静止窗口 [lo,hi) 连续帧横向拼条带，orig / drop-in / X 各一行纵向叠放，直观看闪烁。"""
    lo, hi = window
    hi = min(hi, len(orig))
    if hi - lo < 2:
        return
    rows = [("orig", orig)]
    if len(baseline) == len(orig):
        rows.append(("drop-in", baseline))
    rows.append(("X", restored))
    size = orig[lo].size
    cell_w, cell_h = size
    strips = []
    for _, seq in rows:
        row = Image.new("RGB", (cell_w * (hi - lo), cell_h), (0, 0, 0))
        for j, t in enumerate(range(lo, hi)):
            im = _cell(seq[t], size)
            if im.size != size:
                im = im.resize(size)
            row.paste(im, (j * cell_w, 0))
        strips.append(row)
    strip = Image.new("RGB", (cell_w * (hi - lo), cell_h * len(strips)), (0, 0, 0))
    for r, row in enumerate(strips):
        strip.paste(row, (0, r * cell_h))
    strip.save(out_dir / f"strip_static_{lo}-{hi - 1}.png")
    log(
        f"近静止条带完成：[{lo},{hi}) × {len(strips)} 行 → strip_static_{lo}-{hi - 1}.png"
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="klein 阶段 2 参考帧补偿 harness")
    parser.add_argument(
        "--reference-mode",
        default="prev",
        choices=["none", "prev", "keyframe", "prev_keyframe"],
    )
    parser.add_argument("--keyframe-interval", type=int, default=12)
    parser.add_argument(
        "--keyframe-passthrough", action=argparse.BooleanOptionalAction, default=True
    )
    parser.add_argument(
        "--label", default=None, help="输出子目录名，默认据策略自动生成"
    )
    parser.add_argument("--phase1-dir", type=Path, default=_PHASE1_DIR)
    parser.add_argument(
        "--out-root",
        type=Path,
        default=_PROJECT_ROOT / "output" / "poc" / "klein-phase2",
    )
    parser.add_argument("--candidates", default="896,768")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument(
        "--limit", type=int, default=None, help="仅前 N 帧（smoke 验证接线用）"
    )
    parser.add_argument("--grid", type=int, default=5)
    args = parser.parse_args(argv)

    policy = TemporalPolicyConfig(
        keyframe_interval=args.keyframe_interval,
        reference_mode=args.reference_mode,
        keyframe_passthrough=args.keyframe_passthrough,
    )
    label = args.label or f"{args.reference_mode}_n{args.keyframe_interval}"
    out_dir = args.out_root / label
    out_dir.mkdir(parents=True, exist_ok=True)
    for s in (out_dir / "DONE", out_dir / "DONE.partial"):
        if s.exists():
            s.unlink()

    candidates = [int(x) for x in args.candidates.split(",") if x.strip()]
    cfg = load_config()
    canny = LocalCannyExtractor(cfg.canny_low_threshold, cfg.canny_high_threshold)
    device = "cuda"
    results: dict = {
        "label": label,
        "policy": vars(policy),
        "seed": args.seed,
        "limit": args.limit,
    }
    t_start = time.time()
    ok = True
    try:
        import torch

        device = "cuda" if torch.cuda.is_available() else "cpu"

        fixture = _load_pngs(args.phase1_dir / "fixture" / "fixture_frames", args.limit)
        prompts = _load_prompts(args.phase1_dir / "prompts.json", args.limit)
        if len(fixture) != len(prompts):
            raise ValueError(
                f"fixture({len(fixture)}) 与 prompts({len(prompts)}) 帧数不符"
            )
        log(f"读阶段 1 资产：{len(fixture)} 帧 @ {fixture[0].size}")

        R, vae_tiling, smoke_hist = smoke_probe(
            fixture, canny, policy, candidates, args.seed
        )
        results["smoke"] = {
            "locked_R": R,
            "vae_tiling": vae_tiling,
            "history": smoke_hist,
        }

        # 缺陷 A 修复：smoke 锁定 R 后，把 fixture / baseline 统一归一化到 R，保证透传
        # 关键帧、生成帧、orig、baseline 全序列同尺寸（同步重烘 baseline，落实 §5.4/§9）。
        fixture = _fit_all(fixture, R)
        base_frames = _fit_all(
            _load_pngs(args.phase1_dir / "klein" / "frames", args.limit), R
        )
        results["work_size"] = list(fixture[0].size)
        log(f"工作分辨率归一化到 {fixture[0].size}（R={R}）")

        outputs, keyframe_indices, stat = run_policy(
            fixture, prompts, canny, policy, R, vae_tiling, args.seed
        )
        results["run"] = {**stat, "keyframe_indices": keyframe_indices}

        fdir = out_dir / "frames"
        fdir.mkdir(parents=True, exist_ok=True)
        for i, img in enumerate(outputs):
            if img is not None:
                img.save(fdir / f"frame_{i:04d}.png")
        filled = _fill_failed_frames(outputs)

        # 评估前断言全序列同尺寸，错配 fail-fast（而非静默产出崩溃/不公平数据）
        has_base = len(base_frames) == len(fixture)
        sizes = {im.size for im in filled} | {im.size for im in fixture}
        if has_base:
            sizes |= {im.size for im in base_frames}
        if len(sizes) != 1:
            raise RuntimeError(f"帧尺寸不一致，拒绝产出错配对照：{sorted(sizes)}")

        write_frames(out_dir / "out.mp4", filled, fps=25.0)

        orig_arrays = _as_arrays(fixture)
        rest_arrays = _as_arrays(filled)
        results["quality"] = eval_quality(
            orig_arrays, rest_arrays, prompts, keyframe_indices, device
        )
        results["temporal"] = temporal_report(
            rest_arrays, orig_arrays, keyframe_indices
        )
        results["temporal"]["static_window_mae"] = {
            "window": list(_STATIC_WINDOW),
            "restored": window_mae(rest_arrays, *_STATIC_WINDOW),
            "original": window_mae(orig_arrays, *_STATIC_WINDOW),
        }

        # baseline（阶段 1 drop-in，已归一化到 R）在相同下标上对照
        if has_base:
            base_arrays = _as_arrays(base_frames)
            results["baseline"] = {
                "quality": eval_quality(
                    orig_arrays, base_arrays, prompts, keyframe_indices, device
                ),
                "temporal": temporal_report(base_arrays, orig_arrays, keyframe_indices),
            }
            results["baseline"]["temporal"]["static_window_mae"] = {
                "restored": window_mae(base_arrays, *_STATIC_WINDOW),
            }
        else:
            base_frames = []
            log(f"baseline 帧数与 fixture({len(fixture)}) 不符，跳过对照")

        make_grid(
            fixture,
            canny,
            outputs,
            base_frames,
            out_dir / "compare",
            static_window=_STATIC_WINDOW,
            n=args.grid,
        )
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
    sentinel = out_dir / ("DONE" if ok else "DONE.partial")
    sentinel.write_text(time.strftime("%Y-%m-%d %H:%M:%S"), encoding="utf-8")
    log(
        f"{'=' * 50}\n结束（{'OK' if ok else 'PARTIAL'}），results.json + {sentinel.name} 已写。"
        f"墙钟 {results['total_wall_s']}s"
    )
    return 0 if ok else 1


if __name__ == "__main__":
    import sys

    sys.exit(main())
