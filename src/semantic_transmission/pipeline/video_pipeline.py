"""视频流编排：video→video 保底骨架。

VideoPipeline 复用现有逐帧管道（LocalCannyExtractor + receiver.process_batch），
串接 video_io 解码/编码，并在收帧后做失败帧填充 + 序列级 frame_postprocess。
VLM 不在本模块——prompt 由调用方通过 prompt_fn 注入，保证可在无 GPU 下单测。
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Callable

from PIL import Image

from semantic_transmission.common.image_io import load_as_rgb
from semantic_transmission.common.video_io import read_frames, write_frames
from semantic_transmission.pipeline.batch_processor import BatchResult, SampleResult
from semantic_transmission.pipeline.temporal_policy import (
    TemporalPolicyConfig,
    build_reference_images,
    is_keyframe,
)
from semantic_transmission.receiver.base import BaseReceiver, FrameInput
from semantic_transmission.sender.local_condition_extractor import LocalCannyExtractor

FramePostprocessor = Callable[[list[Image.Image]], list[Image.Image]]
"""序列级帧后处理钩子：list[Image] -> list[Image]。

D1 恒等透传。D5 插帧（返回更长帧列表）/ D6 超分（逐帧映射）替换此实现。
"""


def identity_postprocess(frames: list[Image.Image]) -> list[Image.Image]:
    """D1 默认钩子：原样返回。"""
    return frames


PromptFn = Callable[[int, Any], str]
"""逐帧 prompt 提供器：(frame_index, frame_rgb_ndarray) -> prompt_text。"""


def _fill_failed_frames(images: list[Image.Image | None]) -> list[Image.Image]:
    """用上一成功帧填充失败帧（None），保证输出帧数 = 输入帧数。

    前导 None 用第一帧成功帧回填；中间 None 用上一成功帧填充。

    Raises:
        ValueError: 全部帧失败（无可用帧）。
    """
    valid = [img for img in images if img is not None]
    if not valid:
        raise ValueError("所有帧生成失败，无可用帧")

    filled: list[Image.Image] = []
    last: Image.Image = valid[0]  # 前导 None 用第一帧成功帧
    for img in images:
        if img is not None:
            last = img
        filled.append(last)
    return filled


def _save_artifacts(artifacts_dir, frame_inputs: list[FrameInput], meta) -> None:
    """保存语义传输的中间产物：逐帧 prompt（语义码流）+ Canny 边缘图。

    产出：
        ``prompts.json`` —— 逐帧描述文本 + 字符/字节数 + 整段语义码率统计；
        ``edges/frame_XXXX.png`` —— 每帧条件信息（Canny 边缘图）。

    VLM 描述是语义传输的"压缩码流"，保存它用于复现、质量核查与码率
    （压缩率）统计。须在 VLM 释放前调用（此时 frame_inputs 已含全部 prompt）。
    """
    artifacts_dir = Path(artifacts_dir)
    edges_dir = artifacts_dir / "edges"
    edges_dir.mkdir(parents=True, exist_ok=True)

    frames_meta: list[dict[str, Any]] = []
    total_bytes = 0
    for fi in frame_inputs:
        index = fi.metadata["index"]
        prompt = fi.prompt_text
        byte_count = len(prompt.encode("utf-8"))
        total_bytes += byte_count
        frames_meta.append(
            {
                "index": index,
                "prompt": prompt,
                "char_count": len(prompt),
                "byte_count": byte_count,
            }
        )
        fi.edge_image.save(edges_dir / f"frame_{index:04d}.png")

    n = len(frame_inputs)
    avg_bytes = total_bytes / n if n else 0.0
    payload = {
        "total_frames": n,
        "fps": meta.fps,
        "semantic_bitrate": {
            "total_bytes": total_bytes,
            "avg_bytes_per_frame": round(avg_bytes, 2),
            "avg_bytes_per_second": round(avg_bytes * meta.fps, 2),
        },
        "frames": frames_meta,
    }
    (artifacts_dir / "prompts.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def _save_temporal_artifacts(
    artifacts_dir,
    generated_inputs: list[FrameInput],
    passthrough_indices,
    total_frames: int,
    meta,
) -> None:
    """时序路径的语义中间产物保存：透传关键帧无描述、码率仅计生成帧。

    与无状态 ``_save_artifacts`` 并存。透传关键帧发整帧、不发 prompt（§5 VLM 跳过），
    故其在 ``prompts.json`` 中仅留 ``{"index": i, "passthrough": true}``、不产 edge；
    语义码率（压缩率账本）只累加生成帧的 prompt 字节。
    """
    artifacts_dir = Path(artifacts_dir)
    edges_dir = artifacts_dir / "edges"
    edges_dir.mkdir(parents=True, exist_ok=True)

    passthrough = set(passthrough_indices or [])
    by_index = {fi.metadata["index"]: fi for fi in generated_inputs}

    frames_meta: list[dict[str, Any]] = []
    total_bytes = 0
    for i in range(total_frames):
        if i in passthrough:
            frames_meta.append({"index": i, "passthrough": True})
            continue
        fi = by_index[i]
        prompt = fi.prompt_text
        byte_count = len(prompt.encode("utf-8"))
        total_bytes += byte_count
        frames_meta.append(
            {
                "index": i,
                "prompt": prompt,
                "char_count": len(prompt),
                "byte_count": byte_count,
            }
        )
        fi.edge_image.save(edges_dir / f"frame_{i:04d}.png")

    generated = total_frames - len(passthrough)
    avg_bytes = total_bytes / generated if generated else 0.0
    payload = {
        "total_frames": total_frames,
        "generated_frames": generated,
        "keyframe_indices": sorted(passthrough),
        "fps": meta.fps,
        "semantic_bitrate": {
            "total_bytes": total_bytes,
            "avg_bytes_per_generated_frame": round(avg_bytes, 2),
            "avg_bytes_per_second": round(avg_bytes * meta.fps, 2),
        },
        "frames": frames_meta,
    }
    (artifacts_dir / "prompts.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )


class VideoPipeline:
    """video→video 编排：解码→逐帧 Canny+构造 FrameInput→process_batch→
    失败帧填充→frame_postprocess→编码。"""

    def __init__(
        self,
        receiver: BaseReceiver,
        extractor: LocalCannyExtractor,
        frame_postprocess: FramePostprocessor = identity_postprocess,
    ):
        self.receiver = receiver
        self.extractor = extractor
        self.frame_postprocess = frame_postprocess

    def run(
        self,
        input_path,
        output_path,
        prompt_fn: PromptFn,
        seed: int | None = None,
        fps: float | None = None,
        on_prompts_ready: Callable[[], None] | None = None,
        save_artifacts_to: Path | None = None,
        temporal_policy: TemporalPolicyConfig | None = None,
    ) -> BatchResult:
        """跑通一段视频的 video→video 闭环，返回逐帧/整段统计。

        Args:
            input_path: 输入视频路径。
            output_path: 输出视频路径。
            prompt_fn: ``(frame_index, frame_rgb_ndarray) -> prompt_text``。
            seed: 透传给每帧的随机种子。
            fps: 输出帧率，None 时沿用输入 fps。
            on_prompts_ready: 全部帧 prompt 生成完毕、接收端 ``process_batch``
                （加载生成模型）之前调用的钩子。auto-prompt 时由调用方传入
                ``vlm_sender.unload``，在生成模型上显存前先释放 VLM，避免
                VLM 与 Diffusers 同驻 24GB 触发 OOM / device_map=auto 的 CPU offload。
            save_artifacts_to: 若提供，将语义中间产物（``prompts.json`` 逐帧描述
                + 码率统计、``edges/`` 边缘图）保存到该目录。None 时不保存。
            temporal_policy: 若提供，走有状态串行时序路径 ``_run_temporal``
                （关键帧透传 + 参考帧补偿）；None 时走现有无状态路径（逐字节
                向后兼容）。

        Returns:
            BatchResult 逐帧计时 + 成功率统计。
        """
        # temporal_policy 非空 → 走有状态串行时序路径（klein 关键帧主线）；
        # 为空 → 现有无状态 process_batch 路径，逐字节向后兼容。
        if temporal_policy is not None:
            return self._run_temporal(
                input_path,
                output_path,
                prompt_fn,
                temporal_policy,
                seed=seed,
                fps=fps,
                on_prompts_ready=on_prompts_ready,
                save_artifacts_to=save_artifacts_to,
            )

        frames, meta = read_frames(input_path)

        frame_inputs: list[FrameInput] = []
        for i, frame in enumerate(frames):
            edge_np = self.extractor.extract(frame)
            edge_img = load_as_rgb(edge_np)
            try:
                prompt_text = prompt_fn(i, frame)
            except Exception:
                prompt_text = ""
            frame_inputs.append(
                FrameInput(
                    edge_image=edge_img,
                    prompt_text=prompt_text,
                    seed=seed,
                    metadata={"name": f"frame_{i:04d}", "index": i},
                )
            )

        # 保存语义中间产物（prompt 码流 + 边缘图）须在 on_prompts_ready 释放
        # VLM 前完成——此时 frame_inputs 已含全部 prompt 文本。
        if save_artifacts_to is not None:
            _save_artifacts(save_artifacts_to, frame_inputs, meta)

        # VLM 描述阶段已结束：在接收端加载生成模型前释放 VLM 显存，确保两模型
        # 不同时驻留 GPU（见 on_prompts_ready 说明）。
        if on_prompts_ready is not None:
            on_prompts_ready()

        output = self.receiver.process_batch(frame_inputs)
        filled = _fill_failed_frames(output.images)
        processed = self.frame_postprocess(filled)
        write_frames(output_path, processed, fps=fps if fps is not None else meta.fps)
        return output.stats

    def _run_temporal(
        self,
        input_path,
        output_path,
        prompt_fn: PromptFn,
        policy: TemporalPolicyConfig,
        seed: int | None = None,
        fps: float | None = None,
        on_prompts_ready: Callable[[], None] | None = None,
        save_artifacts_to: Path | None = None,
    ) -> BatchResult:
        """有状态串行时序路径：关键帧透传 + 中间帧带参考帧生成。

        与 run() 无状态路径的差别集中在两处：透传关键帧跳过 prompt_fn 与 process
        （§5），生成阶段持 prev/keyframe 状态构造参考帧（§4）。透传帧缩到与生成帧
        相同的工作分辨率以保尺寸一致；生成失败帧记 None、不污染 prev 链。
        """
        # 惰性导入：fit_working_size 依赖 klein_receiver（间接 import torch），
        # 只在时序路径需要，避免无状态路径被动引入重依赖。
        from semantic_transmission.receiver.klein_receiver import fit_working_size

        # 能力门控：串行路径要求 receiver.process 接受 reference_images（§3.3/§8）。
        import inspect

        params = inspect.signature(self.receiver.process).parameters
        if "reference_images" not in params:
            raise TypeError(
                "时序补偿要求 receiver.process 接受 reference_images 参数，"
                f"当前接收端 {type(self.receiver).__name__} 不支持——请用 --backend klein"
            )

        max_side = self.receiver.config.max_side
        frames, meta = read_frames(input_path)
        n = len(frames)
        kf_set = {i for i in range(n) if is_keyframe(i, policy)}
        passthrough = policy.keyframe_passthrough
        # 透传关键帧下标集合：仅 passthrough 开启时透传帧才跳过 prompt/生成。
        passthrough_set = kf_set if passthrough else set()

        # 前半段：仅对非透传帧提 Canny + prompt（透传帧不需要，§5 VLM 跳过）。
        generated_inputs: list[FrameInput] = []
        for i, frame in enumerate(frames):
            if i in passthrough_set:
                continue
            edge_img = load_as_rgb(self.extractor.extract(frame))
            try:
                prompt_text = prompt_fn(i, frame)
            except Exception:
                prompt_text = ""
            generated_inputs.append(
                FrameInput(
                    edge_image=edge_img,
                    prompt_text=prompt_text,
                    seed=seed,
                    metadata={"name": f"frame_{i:04d}", "index": i},
                )
            )

        # 语义产物须在 VLM 释放前保存（此时 prompt 已全部就绪）。
        if save_artifacts_to is not None:
            _save_temporal_artifacts(
                save_artifacts_to,
                generated_inputs,
                sorted(passthrough_set),
                n,
                meta,
            )
        if on_prompts_ready is not None:
            on_prompts_ready()

        # 生成阶段：串行、持状态。
        inputs_by_index = {fi.metadata["index"]: fi for fi in generated_inputs}
        outputs: list[Image.Image | None] = [None] * n
        keyframe_indices: list[int] = []
        prev_out: Image.Image | None = None
        last_kf: Image.Image | None = None
        batch = BatchResult(total=n)

        for i in range(n):
            if i in passthrough_set:
                kf = fit_working_size(load_as_rgb(frames[i]), max_side)
                outputs[i] = kf
                keyframe_indices.append(i)
                prev_out = kf  # 链首复位到真关键帧
                last_kf = kf
                batch.add_sample(
                    SampleResult(
                        name=f"frame_{i:04d}",
                        status="success",
                        timings={"process": 0.0},
                    )
                )
                continue
            if i in kf_set:
                # 关键帧但 passthrough=False：仍更新锚，正常生成。
                last_kf = fit_working_size(load_as_rgb(frames[i]), max_side)

            fi = inputs_by_index[i]
            refs = build_reference_images(policy.reference_mode, prev_out, last_kf)
            sample = SampleResult(name=fi.metadata["name"], status="success")
            t0 = time.time()
            try:
                img = self.receiver.process(
                    fi.edge_image,
                    fi.prompt_text,
                    seed=seed,
                    reference_images=refs,
                )
            except Exception as e:
                sample.status = "failed"
                sample.error = str(e)
                img = None
            sample.timings["process"] = time.time() - t0
            batch.add_sample(sample)
            outputs[i] = img
            prev_out = img if img is not None else prev_out  # 失败帧不污染 prev 链

        batch.total_time = sum(s.timings.get("process", 0) for s in batch.samples)
        # keyframe_indices 记录“透传关键帧”下标（沿用 spec §7 / PoC run_policy 口径）。
        # --no-keyframe-passthrough 时无透传帧 → keyframe_count=0、全部帧计入
        # generated_frames，始终保持 keyframe_count + generated_frames == total 不变量。
        batch.keyframe_count = len(keyframe_indices)
        batch.generated_frames = n - len(keyframe_indices)
        batch.keyframe_indices = keyframe_indices

        filled = _fill_failed_frames(outputs)
        processed = self.frame_postprocess(filled)
        write_frames(output_path, processed, fps=fps if fps is not None else meta.fps)
        return batch


__all__ = [
    "FramePostprocessor",
    "identity_postprocess",
    "PromptFn",
    "VideoPipeline",
]
