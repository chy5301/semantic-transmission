"""ComfyUI 接收端：通过 ComfyUI API 执行图像还原工作流。"""

import copy
import io
import json
import random
from pathlib import Path

from PIL import Image

from semantic_transmission.common.comfyui_client import ComfyUIClient

_DEFAULT_WORKFLOW = (
    Path(__file__).resolve().parents[3]
    / "resources"
    / "comfyui"
    / "receiver_workflow_api.json"
)

_LOAD_IMAGE_NODE = "101"
_CLIP_TEXT_NODE = "45"
_KSAMPLER_NODE = "44"


class ComfyUIReceiver:
    """接收端：上传边缘图，注入 prompt，执行还原工作流，返回生成图像。"""

    def __init__(
        self,
        client: ComfyUIClient,
        workflow_path: str | Path | None = None,
    ) -> None:
        self.client = client
        self._workflow_path = (
            Path(workflow_path) if workflow_path else _DEFAULT_WORKFLOW
        )
        self._workflow: dict = json.loads(
            self._workflow_path.read_text(encoding="utf-8")
        )

    def process(
        self,
        edge_image: bytes | str | Path,
        prompt_text: str,
        seed: int | None = None,
    ) -> Image.Image:
        """执行接收端工作流：输入边缘图 + prompt，输出还原图像。

        Args:
            edge_image: 边缘图，bytes 数据或文件路径。
            prompt_text: 图像描述文本。
            seed: KSampler 随机种子，None 时使用工作流默认值。

        Returns:
            还原图像 PIL.Image。

        Raises:
            ComfyUIError: ComfyUI API 调用失败。
            ValueError: 工作流未返回输出图像。
        """
        if isinstance(edge_image, (str, Path)):
            edge_path = Path(edge_image)
            edge_bytes = edge_path.read_bytes()
            filename = edge_path.name
        else:
            edge_bytes = edge_image
            filename = "edge_input.png"

        server_filename = self.client.upload_image(edge_bytes, filename)

        workflow = copy.deepcopy(self._workflow)
        workflow[_LOAD_IMAGE_NODE]["inputs"]["image"] = server_filename
        workflow[_CLIP_TEXT_NODE]["inputs"]["text"] = prompt_text
        if seed is None:
            seed = random.randint(0, 2**32 - 1)
        workflow[_KSAMPLER_NODE]["inputs"]["seed"] = seed

        prompt_id = self.client.submit_workflow(workflow)
        entry = self.client.wait_for_completion(prompt_id)
        images = self.client.get_result_images(entry)

        if not images:
            raise ValueError(f"接收端工作流未返回输出图像: {prompt_id}")

        return Image.open(io.BytesIO(images[0]))
