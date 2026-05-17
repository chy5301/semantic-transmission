"""``semantic_transmission.common.image_io`` 单元测试。

覆盖 :func:`load_as_rgb` 与 :func:`image_to_numpy` 对 5 种输入类型
（str/Path/bytes/ndarray/PIL）以及异常分支的处理。
"""

from __future__ import annotations

import io
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from semantic_transmission.common.image_io import image_to_numpy, load_as_rgb


# ----------------------------------------------------------------------
# load_as_rgb
# ----------------------------------------------------------------------


class TestLoadAsRgbFromPath:
    """str / Path 输入分支。"""

    def test_str_path(self, tmp_path: Path) -> None:
        path = tmp_path / "rgb.png"
        Image.new("RGB", (8, 8), (10, 20, 30)).save(path)
        img = load_as_rgb(str(path))
        assert isinstance(img, Image.Image)
        assert img.mode == "RGB"
        assert img.size == (8, 8)
        assert np.asarray(img)[0, 0].tolist() == [10, 20, 30]

    def test_pathlib_path(self, tmp_path: Path) -> None:
        path = tmp_path / "rgb.png"
        Image.new("RGB", (4, 6), (1, 2, 3)).save(path)
        img = load_as_rgb(path)
        assert img.mode == "RGB"
        assert img.size == (4, 6)

    def test_rgba_file_converted_to_rgb(self, tmp_path: Path) -> None:
        path = tmp_path / "rgba.png"
        Image.new("RGBA", (4, 4), (200, 100, 50, 128)).save(path)
        img = load_as_rgb(path)
        assert img.mode == "RGB"
        assert np.asarray(img)[0, 0].tolist() == [200, 100, 50]


class TestLoadAsRgbFromBytes:
    """bytes 输入分支。"""

    def test_png_bytes(self) -> None:
        buf = io.BytesIO()
        Image.new("RGB", (5, 5), (255, 0, 0)).save(buf, format="PNG")
        img = load_as_rgb(buf.getvalue())
        assert img.mode == "RGB"
        assert img.size == (5, 5)
        assert np.asarray(img)[0, 0].tolist() == [255, 0, 0]


class TestLoadAsRgbFromNdarray:
    """numpy.ndarray 输入分支。"""

    def test_rgb_array(self) -> None:
        arr = np.zeros((6, 8, 3), dtype=np.uint8)
        arr[:, :, 1] = 200
        img = load_as_rgb(arr)
        assert img.mode == "RGB"
        assert img.size == (8, 6)
        assert np.asarray(img)[0, 0].tolist() == [0, 200, 0]

    def test_grayscale_array(self) -> None:
        arr = np.full((4, 4), 77, dtype=np.uint8)
        img = load_as_rgb(arr)
        assert img.mode == "RGB"
        assert img.size == (4, 4)
        assert np.asarray(img)[0, 0].tolist() == [77, 77, 77]

    def test_rgba_array(self) -> None:
        arr = np.zeros((3, 3, 4), dtype=np.uint8)
        arr[:, :, 0] = 11
        arr[:, :, 3] = 200  # alpha 应被丢弃
        img = load_as_rgb(arr)
        assert img.mode == "RGB"
        assert np.asarray(img)[0, 0].tolist() == [11, 0, 0]

    def test_invalid_shape_raises(self) -> None:
        with pytest.raises(ValueError, match="不支持的数组形状"):
            load_as_rgb(np.zeros((3, 3, 5), dtype=np.uint8))


class TestLoadAsRgbFromPil:
    """PIL.Image 输入分支。"""

    def test_pil_rgb_passthrough(self) -> None:
        pil = Image.new("RGB", (2, 2), (5, 5, 5))
        img = load_as_rgb(pil)
        assert img.mode == "RGB"
        assert img.size == (2, 2)

    def test_pil_l_converted(self) -> None:
        pil = Image.new("L", (3, 3), 128)
        img = load_as_rgb(pil)
        assert img.mode == "RGB"
        assert np.asarray(img)[0, 0].tolist() == [128, 128, 128]

    def test_pil_rgba_converted(self) -> None:
        pil = Image.new("RGBA", (2, 2), (10, 20, 30, 40))
        img = load_as_rgb(pil)
        assert img.mode == "RGB"
        assert np.asarray(img)[0, 0].tolist() == [10, 20, 30]


class TestLoadAsRgbTypeErrors:
    """非支持类型应抛 TypeError。"""

    def test_int_raises(self) -> None:
        with pytest.raises(TypeError, match="不支持的输入类型"):
            load_as_rgb(123)  # type: ignore[arg-type]

    def test_none_raises(self) -> None:
        with pytest.raises(TypeError):
            load_as_rgb(None)  # type: ignore[arg-type]

    def test_dict_raises(self) -> None:
        with pytest.raises(TypeError):
            load_as_rgb({"foo": "bar"})  # type: ignore[arg-type]


# ----------------------------------------------------------------------
# image_to_numpy
# ----------------------------------------------------------------------


class TestImageToNumpy:
    """image_to_numpy 复合 helper。"""

    def test_from_path(self, tmp_path: Path) -> None:
        path = tmp_path / "x.png"
        Image.new("RGB", (3, 3), (9, 9, 9)).save(path)
        arr = image_to_numpy(path)
        assert arr.dtype == np.uint8
        assert arr.shape == (3, 3, 3)
        assert arr[0, 0].tolist() == [9, 9, 9]

    def test_from_pil(self) -> None:
        arr = image_to_numpy(Image.new("RGB", (2, 4), (1, 2, 3)))
        assert arr.shape == (4, 2, 3)  # PIL size 是 (w,h)，ndarray 是 (h,w,c)
        assert arr.dtype == np.uint8

    def test_from_ndarray_roundtrip(self) -> None:
        src = np.random.randint(0, 256, size=(5, 7, 3), dtype=np.uint8)
        arr = image_to_numpy(src)
        assert arr.shape == src.shape
        assert np.array_equal(arr, src)
