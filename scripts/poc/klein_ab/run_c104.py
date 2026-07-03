"""C104 三视频案例：各跑 X@N12 + C@N12（复用 run_ab 预处理 + run_phase2 生成）。

裸 .h265 码流无 fps 元数据、imageio 无法直接迭代，先用 ffmpeg 转成 25fps mp4；
再按 run_ab 的 load_window/bake_fixture/freeze_prompts 造 fixture+prompts（不跑 drop-in
baseline，用户只要 X/C 两方案 12 帧档），最后调 run_phase2.main 跑 X@N12 与 C@N12。

以模块方式运行（供 scripts.* 包导入）：
    uv run python -m scripts.poc.klein_ab.run_c104
"""

from __future__ import annotations

import subprocess
import time
import traceback
from pathlib import Path

import imageio_ffmpeg

from scripts.poc.klein_ab import run_phase2
from scripts.poc.klein_ab.run_ab import bake_fixture, freeze_prompts, load_window, log
from semantic_transmission.common.config import load_config

_MAIN = Path(r"D:\CONGHAOYANG\Projects\WorkProjects\semantic-transmission")
_VID_DIR = _MAIN / "resources" / "test_videos" / "C104"
_OUT = Path("output") / "poc" / "klein-c104"  # 相对 worktree cwd
_MAX_SIDE = (
    896  # 工作分辨率长边（1280x960 → 896x672）；run_phase2 内 smoke 会二次确认/回退
)

# (tag, start_s, dur_s)
_CASES = [
    ("20260115093008", 10, 10),  # 10-20s
    ("20260115093113", 0, 10),  # 0-10s
    ("20260115121711", 0, 10),  # 0-10s
]


def transcode(h265: Path, mp4: Path, fps: int = 25) -> None:
    """裸 h265 → 25fps mp4（libx264 视觉无损 crf16），补时间戳供 imageio 解码。"""
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    mp4.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            ff,
            "-y",
            "-r",
            str(fps),
            "-i",
            str(h265),
            "-c:v",
            "libx264",
            "-crf",
            "16",
            "-pix_fmt",
            "yuv420p",
            str(mp4),
        ],
        check=True,
        capture_output=True,
    )


def prep_case(tag: str, start: int, dur: int, cfg) -> Path | None:
    """转码 + 造 fixture/prompts，返回 prepdir（供 run_phase2 --phase1-dir）。"""
    case_dir = _OUT / tag
    prepdir = case_dir / "prep"
    if (prepdir / "prompts.json").is_file() and (
        prepdir / "fixture" / "fixture_frames"
    ).is_dir():
        log(f"[{tag}] prep 已存在，跳过预处理")
        return prepdir
    mp4 = case_dir / f"{tag}.mp4"
    log(f"[{tag}] 转码 h265→mp4")
    transcode(_VID_DIR / f"{tag}.h265", mp4)
    native, fps = load_window(mp4, start, dur)
    log(
        f"[{tag}] 窗口 [{start},{start + dur}]s：{len(native)} 帧 @ {native[0].shape[1]}x{native[0].shape[0]} {fps}fps"
    )
    _, small = bake_fixture(native, _MAX_SIDE, prepdir / "fixture", fps)
    del native
    freeze_prompts(small, cfg, prepdir)  # 写 prepdir/prompts.json（VLM 逐帧，较慢）
    return prepdir


def main() -> int:
    _OUT.mkdir(parents=True, exist_ok=True)
    done = _OUT / "ALL_C104_DONE"
    if done.exists():
        done.unlink()
    cfg = load_config()
    t0 = time.time()
    summary = []
    for tag, start, dur in _CASES:
        case_mark = _OUT / tag
        case_mark.mkdir(parents=True, exist_ok=True)
        try:
            prepdir = prep_case(tag, start, dur, cfg)
            for mode, label in (
                ("prev", f"{tag}_x_n12"),
                ("prev_keyframe", f"{tag}_c_n12"),
            ):
                if (_OUT / label / "DONE").is_file():
                    log(f"[{tag}] {label} 已 DONE，跳过（幂等恢复）")
                    summary.append(f"{label}: skip(DONE)")
                    continue
                log(f"[{tag}] 跑 {label}（{mode} N=12）")
                rc = run_phase2.main(
                    [
                        "--phase1-dir",
                        str(prepdir),
                        "--reference-mode",
                        mode,
                        "--keyframe-interval",
                        "12",
                        "--label",
                        label,
                        "--out-root",
                        str(_OUT),
                        "--candidates",
                        "896,768",
                    ]
                )
                summary.append(f"{label}: rc={rc}")
            (case_mark / "CASE_DONE").write_text(
                time.strftime("%Y-%m-%d %H:%M:%S"), encoding="utf-8"
            )
            log(f"[{tag}] 完成")
        except Exception as e:  # noqa: BLE001
            summary.append(f"{tag}: ERROR {type(e).__name__}: {str(e)[:200]}")
            (case_mark / "CASE_ERROR").write_text(
                traceback.format_exc(), encoding="utf-8"
            )
            log(f"[{tag}] 失败：{type(e).__name__}: {e}")
            traceback.print_exc()
    done.write_text(
        time.strftime("%Y-%m-%d %H:%M:%S") + "\n" + "\n".join(summary), encoding="utf-8"
    )
    log(
        f"{'=' * 50}\n全部 C104 案例结束，墙钟 {round((time.time() - t0) / 60, 1)}min\n"
        + "\n".join(summary)
    )
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
