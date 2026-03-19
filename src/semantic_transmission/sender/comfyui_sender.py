"""ComfyUI 发送端：通过 ComfyUI API 执行 Canny 边缘提取工作流。"""

import copy
import io
import json
from pathlib import Path

from PIL import Image

from semantic_transmission.common.comfyui_client import ComfyUIClient

_DEFAULT_WORKFLOW = (
    Path(__file__).resolve().parents[3]
    / "resources"
    / "comfyui"
    / "sender_workflow_api.json"
)

_LOAD_IMAGE_NODE = "58"


class ComfyUISender:
    """发送端：上传原始图像，执行 Canny 边缘提取，返回边缘图。"""

    def __init__(
        self,
        client: ComfyUIClient,
        workflow_path: str | Path | None = None,
    ) -> None:
        self.client = client
        self._workflow_path = Path(workflow_path) if workflow_path else _DEFAULT_WORKFLOW
        self._workflow: dict = json.loads(self._workflow_path.read_text(encoding="utf-8"))

    def process(self, image_path: str | Path) -> Image.Image:
        """执行发送端工作流：输入原始图像，输出 Canny 边缘图。

        Args:
            image_path: 原始图像文件路径。

        Returns:
            Canny 边缘图 PIL.Image。

        Raises:
            ComfyUIError: ComfyUI API 调用失败。
            FileNotFoundError: 图像文件不存在。
            ValueError: 工作流未返回输出图像。
        """
        image_path = Path(image_path)
        image_bytes = image_path.read_bytes()

        server_filename = self.client.upload_image(image_bytes, image_path.name)

        workflow = copy.deepcopy(self._workflow)
        workflow[_LOAD_IMAGE_NODE]["inputs"]["image"] = server_filename

        prompt_id = self.client.submit_workflow(workflow)
        entry = self.client.wait_for_completion(prompt_id)
        images = self.client.get_result_images(entry)

        if not images:
            raise ValueError(f"发送端工作流未返回输出图像: {prompt_id}")

        return Image.open(io.BytesIO(images[0]))
