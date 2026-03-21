"""ComfyUISender 单元测试。"""

import io
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PIL import Image

from semantic_transmission.common.comfyui_client import (
    ComfyUIClient,
    ComfyUIConnectionError,
)
from semantic_transmission.sender.comfyui_sender import ComfyUISender, _LOAD_IMAGE_NODE


def _make_png_bytes() -> bytes:
    """生成最小有效 PNG 图像的 bytes。"""
    img = Image.new("RGB", (4, 4), color=(128, 128, 128))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def mock_client():
    client = MagicMock(spec=ComfyUIClient)
    client.upload_image.return_value = "uploaded_test.png"
    client.submit_workflow.return_value = "prompt_001"
    client.wait_for_completion.return_value = {
        "outputs": {
            "100": {
                "images": [
                    {
                        "filename": "canny_edge_00001_.png",
                        "subfolder": "",
                        "type": "output",
                    }
                ]
            }
        },
        "status": {"status_str": "success"},
    }
    client.get_result_images.return_value = [_make_png_bytes()]
    return client


@pytest.fixture
def sender_workflow_path():
    return (
        Path(__file__).resolve().parents[1]
        / "resources"
        / "comfyui"
        / "sender_workflow_api.json"
    )


@pytest.fixture
def sender(mock_client, sender_workflow_path):
    return ComfyUISender(mock_client, workflow_path=sender_workflow_path)


@pytest.fixture
def input_image(tmp_path) -> Path:
    """创建临时输入图像。"""
    img = Image.new("RGB", (64, 64), color=(255, 0, 0))
    path = tmp_path / "test_input.jpg"
    img.save(path, format="JPEG")
    return path


class TestProcessSuccess:
    def test_returns_pil_image(self, sender, input_image):
        result = sender.process(input_image)
        assert isinstance(result, Image.Image)

    def test_calls_client_methods_in_order(self, sender, input_image, mock_client):
        sender.process(input_image)

        mock_client.upload_image.assert_called_once()
        mock_client.submit_workflow.assert_called_once()
        mock_client.wait_for_completion.assert_called_once_with("prompt_001")
        mock_client.get_result_images.assert_called_once()


class TestWorkflowInjection:
    def test_injects_uploaded_filename(self, sender, input_image, mock_client):
        sender.process(input_image)

        submitted_workflow = mock_client.submit_workflow.call_args[0][0]
        assert (
            submitted_workflow[_LOAD_IMAGE_NODE]["inputs"]["image"]
            == "uploaded_test.png"
        )

    def test_does_not_mutate_original_workflow(self, sender, input_image, mock_client):
        original_image = sender._workflow[_LOAD_IMAGE_NODE]["inputs"]["image"]
        sender.process(input_image)
        assert sender._workflow[_LOAD_IMAGE_NODE]["inputs"]["image"] == original_image


class TestDefaultWorkflowPath:
    def test_default_path_exists(self):
        from semantic_transmission.sender.comfyui_sender import _DEFAULT_WORKFLOW

        assert _DEFAULT_WORKFLOW.exists(), f"默认工作流文件不存在: {_DEFAULT_WORKFLOW}"

    def test_default_path_loads(self, mock_client):
        sender = ComfyUISender(mock_client)
        assert _LOAD_IMAGE_NODE in sender._workflow


class TestCustomWorkflowPath:
    def test_custom_path(self, mock_client, tmp_path):
        workflow = {
            "58": {"class_type": "LoadImage", "inputs": {"image": "placeholder.jpg"}}
        }
        custom_path = tmp_path / "custom_workflow.json"
        custom_path.write_text(json.dumps(workflow), encoding="utf-8")

        sender = ComfyUISender(mock_client, workflow_path=custom_path)
        assert sender._workflow == workflow


class TestErrorHandling:
    def test_upload_error_propagation(self, sender, input_image, mock_client):
        mock_client.upload_image.side_effect = ComfyUIConnectionError("连接失败")
        with pytest.raises(ComfyUIConnectionError):
            sender.process(input_image)

    def test_no_result_images(self, sender, input_image, mock_client):
        mock_client.get_result_images.return_value = []
        with pytest.raises(ValueError, match="未返回输出图像"):
            sender.process(input_image)

    def test_file_not_found(self, sender):
        with pytest.raises(FileNotFoundError):
            sender.process("/nonexistent/image.jpg")
