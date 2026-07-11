# DCVC-RT 神经编解码实验

> 对应设计文档: `docs/superpowers/specs/2026-07-11-dcvc-rt-experiment-design.md`

## 使用步骤

1. 确认 DCVC 仓库已 clone 并编译（见 Task 1）
2. 准备帧序列: `uv run python experiments/dcvc-rt/prepare_frames.py`
3. 跑 DCVC-RT: `uv run python experiments/dcvc-rt/run_dcvc.py`
4. 跑 H.265 对照: `uv run python experiments/dcvc-rt/compare_h265.py`
5. 查看结果: `cat experiments/dcvc-rt/results/comparison.json`

## 结论

（待填写）
