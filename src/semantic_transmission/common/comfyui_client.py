"""ComfyUI REST API 客户端。"""

import time
import uuid

import requests

from semantic_transmission.common.config import ComfyUIConfig


class ComfyUIError(Exception):
    """ComfyUI API 通用异常基类。"""


class ComfyUIConnectionError(ComfyUIError):
    """ComfyUI 服务不可用或网络错误。"""


class ComfyUITimeoutError(ComfyUIError):
    """等待工作流完成超时。"""


class ComfyUIClient:
    """ComfyUI REST API 客户端，封装上传、提交、等待、下载流程。"""

    def __init__(self, config: ComfyUIConfig) -> None:
        self.config = config
        self._session = requests.Session()

    def _request(self, method: str, path: str, **kwargs) -> requests.Response:
        """统一 HTTP 请求封装，处理连接异常。"""
        kwargs.setdefault("timeout", self.config.timeout)
        try:
            resp = self._session.request(
                method, f"{self.config.base_url}{path}", **kwargs
            )
            resp.raise_for_status()
            return resp
        except requests.ConnectionError as e:
            raise ComfyUIConnectionError(
                f"ComfyUI 服务不可用: {self.config.base_url}"
            ) from e
        except requests.Timeout as e:
            raise ComfyUIConnectionError(
                f"请求超时: {self.config.base_url}{path}"
            ) from e
        except requests.HTTPError as e:
            raise ComfyUIError(
                f"HTTP {e.response.status_code}: {e.response.text}"
            ) from e

    def check_health(self) -> bool:
        """检查 ComfyUI 服务是否可用。"""
        try:
            self._request("GET", "/queue")
            return True
        except ComfyUIError:
            return False

    def upload_image(
        self,
        image_data: bytes,
        filename: str,
        *,
        overwrite: bool = True,
    ) -> str:
        """上传图像到 ComfyUI，返回服务端文件名。"""
        resp = self._request(
            "POST",
            "/upload/image",
            files={"image": (filename, image_data, "image/png")},
            data={"overwrite": str(overwrite).lower()},
        )
        return resp.json()["name"]

    def submit_workflow(self, workflow: dict) -> str:
        """提交工作流，返回 prompt_id。"""
        client_id = uuid.uuid4().hex
        resp = self._request(
            "POST",
            "/prompt",
            json={"prompt": workflow, "client_id": client_id},
        )
        result = resp.json()
        if "error" in result:
            raise ComfyUIError(f"工作流提交失败: {result['error']}")
        return result["prompt_id"]

    def wait_for_completion(
        self,
        prompt_id: str,
        *,
        timeout: float | None = None,
    ) -> dict:
        """轮询等待工作流完成，返回 history 条目。"""
        timeout = timeout if timeout is not None else self.config.timeout * 40
        deadline = time.monotonic() + timeout

        while True:
            resp = self._request("GET", f"/history/{prompt_id}")
            data = resp.json()

            if prompt_id in data:
                entry = data[prompt_id]
                status_str = entry.get("status", {}).get("status_str", "")
                if status_str == "error":
                    raise ComfyUIError(f"工作流执行出错: {prompt_id}")
                return entry

            if time.monotonic() > deadline:
                raise ComfyUITimeoutError(
                    f"等待工作流完成超时 ({timeout}s): {prompt_id}"
                )
            time.sleep(1.0)

    def get_result_images(self, history_entry: dict) -> list[bytes]:
        """从 history 条目中下载所有输出图像。"""
        images = []
        outputs = history_entry.get("outputs", {})

        for node_output in outputs.values():
            for img_info in node_output.get("images", []):
                params = {
                    "filename": img_info["filename"],
                    "subfolder": img_info.get("subfolder", ""),
                    "type": img_info.get("type", "output"),
                }
                resp = self._request("GET", "/view", params=params)
                images.append(resp.content)

        return images
