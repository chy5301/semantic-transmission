"""批量处理公共模块：图片发现、结果统计、公共数据结构。"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal


# 支持的图片文件扩展名
SUPPORTED_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


@dataclass
class BatchDiscoveryResult:
    """目录图片扫描结果。"""

    images: list[Path]
    total_count: int
    formats_detected: dict[str, int] = field(default_factory=dict)

    def __bool__(self) -> bool:
        """返回是否找到图片。"""
        return self.total_count > 0


@dataclass
class SampleResult:
    """单张图片处理结果。"""

    name: str
    status: Literal["success", "failed", "skipped"]
    error: str | None = None
    timings: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """转换为字典用于 JSON 序列化。"""
        return {
            "name": self.name,
            "status": self.status,
            "error": self.error,
            "timings": self.timings,
            "total_time": sum(self.timings.values()),
        }


@dataclass
class BatchResult:
    """整个批量处理结果汇总。"""

    total: int
    success: int = 0
    failed: int = 0
    skipped: int = 0
    total_time: float = 0.0
    samples: list[SampleResult] = field(default_factory=list)

    def add_sample(self, result: SampleResult) -> None:
        """添加一张图片的处理结果。"""
        self.samples.append(result)
        if result.status == "success":
            self.success += 1
        elif result.status == "failed":
            self.failed += 1
        elif result.status == "skipped":
            self.skipped += 1

    def to_dict(self) -> dict:
        """转换为字典用于 JSON 序列化。"""
        return {
            "total": self.total,
            "success": self.success,
            "failed": self.failed,
            "skipped": self.skipped,
            "total_time": self.total_time,
            "success_rate": (self.success / self.total * 100) if self.total > 0 else 0,
            "samples": [s.to_dict() for s in self.samples],
        }


class BatchImageDiscoverer:
    """批量图片发现器：扫描目录找出所有支持的图片文件。"""

    def __init__(self, supported_exts: set[str] | None = None):
        self.supported_exts = supported_exts or SUPPORTED_IMAGE_EXTS

    def discover(
        self, input_dir: Path, recursive: bool = False
    ) -> BatchDiscoveryResult:
        """扫描目录，返回所有找到的图片。

        Args:
            input_dir: 输入目录
            recursive: 是否递归扫描子目录

        Returns:
            BatchDiscoveryResult 包含找到的图片列表
        """
        images: list[Path] = []
        formats: dict[str, int] = {}

        if recursive:
            # 递归扫描所有子目录
            for file in input_dir.rglob("*"):
                if self._is_image(file):
                    images.append(file)
                    ext = file.suffix.lower()
                    formats[ext] = formats.get(ext, 0) + 1
        else:
            # 只扫描当前目录
            for file in input_dir.iterdir():
                if file.is_file() and self._is_image(file):
                    images.append(file)
                    ext = file.suffix.lower()
                    formats[ext] = formats.get(ext, 0) + 1

        # 按文件名排序，保证处理顺序一致
        images.sort()

        return BatchDiscoveryResult(
            images=images,
            total_count=len(images),
            formats_detected=formats,
        )

    def _is_image(self, path: Path) -> bool:
        """判断是否为支持的图片文件。"""
        if not path.is_file():
            return False
        ext = path.suffix.lower()
        return ext in self.supported_exts


def make_sample_output_dir(output_root: Path, index: int, image_name: str) -> Path:
    """为单张图片创建输出子目录：NN-name。

    例如：01-cat-photo/

    Args:
        output_root: 批量输出根目录
        index: 图片索引（从 1 开始）
        image_name: 图片基本名称

    Returns:
        创建好的输出子目录路径
    """
    # 清理文件名，避免特殊字符问题
    clean_name = "".join(c if c.isalnum() or c in "._- " else "_" for c in image_name)
    clean_name = clean_name.strip().replace(" ", "_")
    # 两位索引前缀
    dir_name = f"{index:02d}-{clean_name}"
    output_dir = output_root / dir_name
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir
