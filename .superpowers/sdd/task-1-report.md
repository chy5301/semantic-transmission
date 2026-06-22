# Task 1 Report: video_io 帧序列读写模块

## 实现内容

新增 `src/semantic_transmission/common/video_io.py`，基于 `imageio[ffmpeg]` 封装：

- `VideoMeta(fps, width, height, frame_count)` — 视频元数据 dataclass
- `read_frames(path) -> tuple[list[NDArray[uint8]], VideoMeta]` — 解码视频为 RGB ndarray 帧列表
- `write_frames(path, frames, fps)` — 将 PIL Image 列表编码为视频（mp4）

底层使用 imageio ffmpeg 插件，自带静态二进制，无需系统安装 ffmpeg。

## 改动文件

| 文件 | 变更类型 |
|------|----------|
| `src/semantic_transmission/common/video_io.py` | 新建 |
| `tests/test_video_io.py` | 新建 |
| `pyproject.toml` | 添加依赖 `imageio[ffmpeg]>=2.37.3` |
| `uv.lock` | 同步更新（新增 imageio-ffmpeg==0.6.0） |

## TDD 证据

### RED（Step 3）

命令：`uv run pytest tests/test_video_io.py -v`

输出：
```
ERROR collecting tests/test_video_io.py
ImportError while importing test module ...
E   ModuleNotFoundError: No module named 'semantic_transmission.common.video_io'
1 error in 0.73s
```

为何预期失败：`video_io.py` 尚未创建，导入必然失败，测试无法收集。

### GREEN（Step 5）

命令：`uv run pytest tests/test_video_io.py -v`

输出：
```
tests/test_video_io.py::test_write_then_read_roundtrip PASSED  [ 50%]
tests/test_video_io.py::test_write_empty_frames_raises PASSED  [100%]
2 passed in 1.21s
```

往返测试的 3 帧断言严格通过，无帧数不一致问题。

## 测试结果

- `test_write_then_read_roundtrip`：PASS — 写 3 帧（64×48 RGB），读回断言 `len(read)==3`、`meta.width==64`、`meta.height==48`、`meta.frame_count==3`、dtype 和 shape 全部通过
- `test_write_empty_frames_raises`：PASS — 空帧列表抛出 `ValueError`

## Lint

```
uv run ruff check .     → All checks passed!
uv run ruff format --check .  → 60 files already formatted
```

## 提交

```
f46c3c5 feat(common): 新增 video_io 帧序列读写模块
```

## 自检发现

- brief 提到"mp4 极短视频解码帧数可能与写入不一致"的风险点，实际运行中 3 帧 64×48 视频严格通过，无此问题。
- `imageio.v2.get_writer(path, fps=fps)` 对 `.mp4` 自动选用 ffmpeg/libx264 编码，imageio-ffmpeg 捆绑二进制确保无系统依赖。
- `get_meta_data()` 的 `fps` 字段在读回时可能略有浮点偏差（如 10.0 → 10.0），但本测试未断言 fps 精确值，故无影响。

## 遗留疑虑

无。往返测试严格通过，lint 干净，帧数匹配正常。

---

## Review 修复补丁（2026-06-22）

### 问题

设计 spec §5 要求「空/损坏视频都抛 ValueError（清晰报错）」。损坏/非视频文件会让 imageio 的原始异常直接逸出（`OSError`、`RuntimeError` 等），违反契约，且无测试覆盖。

### 修改文件

| 文件 | 变更内容 |
|------|----------|
| `src/semantic_transmission/common/video_io.py` | `read_frames` 中将 `get_reader` 及逐帧解码包进 `try/except`，统一 `raise ValueError` |
| `tests/test_video_io.py` | 新增 `test_read_corrupt_file_raises` |

### 修复逻辑

```python
try:
    reader = imageio.get_reader(path)
    try:
        meta = reader.get_meta_data()
        frames = [np.asarray(frame, dtype=np.uint8) for frame in reader]
    finally:
        reader.close()
except ValueError:
    raise           # 放过我们自己的 ValueError（零帧等），不重包
except Exception as e:
    raise ValueError(f"无法解码视频: {path}") from e
```

零帧检查在外层 `try` 之后，不会被 `except` 捕获；对 imageio/ffmpeg 抛出的其他异常统一包装为 `ValueError`。

### 运行命令与完整输出

```
uv run ruff check .
→ All checks passed!

uv run ruff format --check .
→ 60 files already formatted

uv run pytest tests/test_video_io.py -v
```

```
platform win32 -- Python 3.12.11, pytest-9.0.2, pluggy-1.6.0
collected 3 items

tests/test_video_io.py::test_write_then_read_roundtrip PASSED  [ 33%]
tests/test_video_io.py::test_write_empty_frames_raises PASSED  [ 66%]
tests/test_video_io.py::test_read_corrupt_file_raises  PASSED  [100%]

3 passed in 0.48s
```

test_read_corrupt_file_raises 通过，原有两个测试无回归。
