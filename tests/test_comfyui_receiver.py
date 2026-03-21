"""ComfyUIReceiver 单元测试。"""

import io
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PIL import Image

from semantic_transmission.common.comfyui_client import (
    ComfyUIClient,
    ComfyUIConnectionError,
)
from semantic_transmission.receiver.comfyui_receiver import (
    ComfyUIReceiver,
    _CLIP_TEXT_NODE,
    _KSAMPLER_NODE,
    _LOAD_IMAGE_NODE,
)


def _make_png_bytes() -> bytes:
    img = Image.new("RGB", (4, 4), color=(128, 128, 128))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def mock_client():
    client = MagicMock(spec=ComfyUIClient)
    client.upload_image.return_value = "uploaded_edge.png"
    client.submit_workflow.return_value = "prompt_002"
    client.wait_for_completion.return_value = {
        "outputs": {
            "9": {
                "images": [
                    {
                        "filename": "z-image-turbo_00001_.png",
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
def receiver_workflow_path():
    return (
        Path(__file__).resolve().parents[1]
        / "resources"
        / "comfyui"
        / "receiver_workflow_api.json"
    )


@pytest.fixture
def receiver(mock_client, receiver_workflow_path):
    return ComfyUIReceiver(mock_client, workflow_path=receiver_workflow_path)


@pytest.fixture
def edge_image_path(tmp_path) -> Path:
    img = Image.new("L", (64, 64), color=255)
    path = tmp_path / "canny_edge.png"
    img.save(path, format="PNG")
    return path


PROMPT_TEXT = "A desert road with mountains in the background."


class TestProcessSuccess:
    def test_returns_pil_image(self, receiver, edge_image_path):
        result = receiver.process(edge_image_path, PROMPT_TEXT)
        assert isinstance(result, Image.Image)

    def test_calls_client_methods_in_order(
        self, receiver, edge_image_path, mock_client
    ):
        receiver.process(edge_image_path, PROMPT_TEXT)
        mock_client.upload_image.assert_called_once()
        mock_client.submit_workflow.assert_called_once()
        mock_client.wait_for_completion.assert_called_once_with("prompt_002")
        mock_client.get_result_images.assert_called_once()


class TestWorkflowInjection:
    def test_injects_all_params(self, receiver, edge_image_path, mock_client):
        receiver.process(edge_image_path, PROMPT_TEXT, seed=42)
        submitted = mock_client.submit_workflow.call_args[0][0]
        assert submitted[_LOAD_IMAGE_NODE]["inputs"]["image"] == "uploaded_edge.png"
        assert submitted[_CLIP_TEXT_NODE]["inputs"]["text"] == PROMPT_TEXT
        assert submitted[_KSAMPLER_NODE]["inputs"]["seed"] == 42

    def test_seed_optional_uses_default(self, receiver, edge_image_path, mock_client):
        default_seed = receiver._workflow[_KSAMPLER_NODE]["inputs"]["seed"]
        receiver.process(edge_image_path, PROMPT_TEXT)
        submitted = mock_client.submit_workflow.call_args[0][0]
        assert submitted[_KSAMPLER_NODE]["inputs"]["seed"] == default_seed

    def test_does_not_mutate_original_workflow(
        self, receiver, edge_image_path, mock_client
    ):
        original_text = receiver._workflow[_CLIP_TEXT_NODE]["inputs"]["text"]
        receiver.process(edge_image_path, "new prompt", seed=999)
        assert receiver._workflow[_CLIP_TEXT_NODE]["inputs"]["text"] == original_text
        assert receiver._workflow[_KSAMPLER_NODE]["inputs"]["seed"] != 999


class TestDefaultWorkflowPath:
    def test_default_path_exists(self):
        from semantic_transmission.receiver.comfyui_receiver import _DEFAULT_WORKFLOW

        assert _DEFAULT_WORKFLOW.exists(), f"默认工作流文件不存在: {_DEFAULT_WORKFLOW}"

    def test_default_path_loads(self, mock_client):
        receiver = ComfyUIReceiver(mock_client)
        assert _LOAD_IMAGE_NODE in receiver._workflow
        assert _CLIP_TEXT_NODE in receiver._workflow
        assert _KSAMPLER_NODE in receiver._workflow


class TestEdgeImageInput:
    def test_accepts_bytes(self, receiver, mock_client):
        edge_bytes = _make_png_bytes()
        result = receiver.process(edge_bytes, PROMPT_TEXT)
        assert isinstance(result, Image.Image)
        mock_client.upload_image.assert_called_once_with(edge_bytes, "edge_input.png")

    def test_accepts_path(self, receiver, edge_image_path, mock_client):
        receiver.process(edge_image_path, PROMPT_TEXT)
        call_args = mock_client.upload_image.call_args
        assert call_args[0][1] == "canny_edge.png"


class TestErrorHandling:
    def test_upload_error_propagation(self, receiver, edge_image_path, mock_client):
        mock_client.upload_image.side_effect = ComfyUIConnectionError("连接失败")
        with pytest.raises(ComfyUIConnectionError):
            receiver.process(edge_image_path, PROMPT_TEXT)

    def test_no_result_images(self, receiver, edge_image_path, mock_client):
        mock_client.get_result_images.return_value = []
        with pytest.raises(ValueError, match="未返回输出图像"):
            receiver.process(edge_image_path, PROMPT_TEXT)
