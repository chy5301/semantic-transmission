"""ComfyUIClient 单元测试。"""

import time
from dataclasses import dataclass

import pytest
import requests

from semantic_transmission.common.comfyui_client import (
    ComfyUIClient,
    ComfyUIConnectionError,
    ComfyUIError,
    ComfyUITimeoutError,
)
from semantic_transmission.common.config import ComfyUIConfig


@dataclass
class MockResponse:
    status_code: int = 200
    content: bytes = b""
    text: str = ""
    _json: dict | None = None

    def json(self):
        return self._json if self._json is not None else {}

    def raise_for_status(self):
        if self.status_code >= 400:
            resp = requests.models.Response()
            resp.status_code = self.status_code
            resp._content = self.text.encode()
            raise requests.HTTPError(response=resp)


@pytest.fixture
def config():
    return ComfyUIConfig()


@pytest.fixture
def client(config):
    return ComfyUIClient(config)


# ── upload_image ──


class TestUploadImage:
    def test_upload_success(self, client, monkeypatch):
        def mock_request(*args, **kwargs):
            return MockResponse(_json={"name": "uploaded.png", "subfolder": "", "type": "input"})

        monkeypatch.setattr(client._session, "request", mock_request)
        result = client.upload_image(b"\x89PNG", "test.png")
        assert result == "uploaded.png"

    def test_upload_connection_error(self, client, monkeypatch):
        def mock_request(*args, **kwargs):
            raise requests.ConnectionError("refused")

        monkeypatch.setattr(client._session, "request", mock_request)
        with pytest.raises(ComfyUIConnectionError):
            client.upload_image(b"\x89PNG", "test.png")

    def test_upload_http_error(self, client, monkeypatch):
        def mock_request(*args, **kwargs):
            return MockResponse(status_code=400, text="Bad Request")

        monkeypatch.setattr(client._session, "request", mock_request)
        with pytest.raises(ComfyUIError):
            client.upload_image(b"\x89PNG", "test.png")


# ── submit_workflow ──


class TestSubmitWorkflow:
    def test_submit_success(self, client, monkeypatch):
        def mock_request(*args, **kwargs):
            return MockResponse(_json={"prompt_id": "abc123"})

        monkeypatch.setattr(client._session, "request", mock_request)
        result = client.submit_workflow({"1": {"class_type": "LoadImage", "inputs": {}}})
        assert result == "abc123"

    def test_submit_workflow_error(self, client, monkeypatch):
        def mock_request(*args, **kwargs):
            return MockResponse(_json={"error": "invalid workflow", "prompt_id": "x"})

        monkeypatch.setattr(client._session, "request", mock_request)
        with pytest.raises(ComfyUIError, match="工作流提交失败"):
            client.submit_workflow({"bad": "workflow"})

    def test_submit_connection_error(self, client, monkeypatch):
        def mock_request(*args, **kwargs):
            raise requests.ConnectionError("refused")

        monkeypatch.setattr(client._session, "request", mock_request)
        with pytest.raises(ComfyUIConnectionError):
            client.submit_workflow({})


# ── wait_for_completion ──


class TestWaitForCompletion:
    def test_wait_immediate_completion(self, client, monkeypatch):
        entry = {"outputs": {"9": {"images": []}}, "status": {"status_str": "success"}}

        def mock_request(*args, **kwargs):
            return MockResponse(_json={"prompt123": entry})

        monkeypatch.setattr(client._session, "request", mock_request)
        monkeypatch.setattr(time, "sleep", lambda _: None)
        result = client.wait_for_completion("prompt123")
        assert result == entry

    def test_wait_delayed_completion(self, client, monkeypatch):
        entry = {"outputs": {}, "status": {"status_str": "success"}}
        call_count = 0

        def mock_request(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                return MockResponse(_json={})
            return MockResponse(_json={"prompt456": entry})

        monkeypatch.setattr(client._session, "request", mock_request)
        monkeypatch.setattr(time, "sleep", lambda _: None)
        result = client.wait_for_completion("prompt456")
        assert result == entry
        assert call_count == 3

    def test_wait_timeout(self, client, monkeypatch):
        def mock_request(*args, **kwargs):
            return MockResponse(_json={})

        monkeypatch.setattr(client._session, "request", mock_request)
        monkeypatch.setattr(time, "sleep", lambda _: None)
        # monotonic 递增模拟超时
        times = iter([0.0, 0.5, 1.5, 2.5])
        monkeypatch.setattr(time, "monotonic", lambda: next(times))

        with pytest.raises(ComfyUITimeoutError):
            client.wait_for_completion("prompt789", timeout=2.0)

    def test_wait_execution_error(self, client, monkeypatch):
        entry = {"outputs": {}, "status": {"status_str": "error"}}

        def mock_request(*args, **kwargs):
            return MockResponse(_json={"prompt_err": entry})

        monkeypatch.setattr(client._session, "request", mock_request)
        monkeypatch.setattr(time, "sleep", lambda _: None)
        with pytest.raises(ComfyUIError, match="工作流执行出错"):
            client.wait_for_completion("prompt_err")


# ── get_result_images ──


class TestGetResultImages:
    def test_get_single_image(self, client, monkeypatch):
        history_entry = {
            "outputs": {
                "9": {
                    "images": [
                        {"filename": "output_00001_.png", "subfolder": "", "type": "output"}
                    ]
                }
            }
        }

        def mock_request(*args, **kwargs):
            return MockResponse(content=b"\x89PNG_FAKE_IMAGE")

        monkeypatch.setattr(client._session, "request", mock_request)
        result = client.get_result_images(history_entry)
        assert len(result) == 1
        assert result[0] == b"\x89PNG_FAKE_IMAGE"

    def test_get_multiple_images(self, client, monkeypatch):
        history_entry = {
            "outputs": {
                "9": {
                    "images": [
                        {"filename": "img1.png", "subfolder": "", "type": "output"},
                        {"filename": "img2.png", "subfolder": "", "type": "output"},
                    ]
                }
            }
        }
        call_count = 0

        def mock_request(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return MockResponse(content=f"image_{call_count}".encode())

        monkeypatch.setattr(client._session, "request", mock_request)
        result = client.get_result_images(history_entry)
        assert len(result) == 2

    def test_get_no_images(self, client, monkeypatch):
        history_entry = {"outputs": {}}
        result = client.get_result_images(history_entry)
        assert result == []


# ── check_health ──


class TestCheckHealth:
    def test_health_ok(self, client, monkeypatch):
        def mock_request(*args, **kwargs):
            return MockResponse(_json={"queue_running": [], "queue_pending": []})

        monkeypatch.setattr(client._session, "request", mock_request)
        assert client.check_health() is True

    def test_health_fail(self, client, monkeypatch):
        def mock_request(*args, **kwargs):
            raise requests.ConnectionError("refused")

        monkeypatch.setattr(client._session, "request", mock_request)
        assert client.check_health() is False


# ── 集成流程 ──


class TestIntegration:
    def test_full_flow(self, client, monkeypatch):
        """串联 upload → submit → wait → get_result_images 完整流程。"""
        call_log = []

        def mock_request(method, url, **kwargs):
            call_log.append((method, url))

            if "/upload/image" in url:
                return MockResponse(_json={"name": "uploaded.png", "subfolder": "", "type": "input"})
            elif "/prompt" in url and method == "POST":
                return MockResponse(_json={"prompt_id": "flow_001"})
            elif "/history/flow_001" in url:
                return MockResponse(_json={
                    "flow_001": {
                        "outputs": {
                            "9": {
                                "images": [{"filename": "result.png", "subfolder": "", "type": "output"}]
                            }
                        },
                        "status": {"status_str": "success"},
                    }
                })
            elif "/view" in url:
                return MockResponse(content=b"RESULT_IMAGE_BYTES")
            return MockResponse()

        monkeypatch.setattr(client._session, "request", mock_request)
        monkeypatch.setattr(time, "sleep", lambda _: None)

        # 1. 上传
        server_name = client.upload_image(b"img_data", "input.png")
        assert server_name == "uploaded.png"

        # 2. 提交
        workflow = {"1": {"class_type": "LoadImage", "inputs": {"image": server_name}}}
        prompt_id = client.submit_workflow(workflow)
        assert prompt_id == "flow_001"

        # 3. 等待
        entry = client.wait_for_completion(prompt_id)
        assert "outputs" in entry

        # 4. 下载
        images = client.get_result_images(entry)
        assert len(images) == 1
        assert images[0] == b"RESULT_IMAGE_BYTES"

        # 验证调用顺序
        methods = [m for m, _ in call_log]
        assert methods == ["POST", "POST", "GET", "GET"]
