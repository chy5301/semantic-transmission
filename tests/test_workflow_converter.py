"""WorkflowConverter 单元测试。"""

from pathlib import Path

import pytest

from semantic_transmission.receiver.workflow_converter import WorkflowConverter

WORKFLOW_PATH = (
    Path(__file__).parent.parent
    / "resources"
    / "comfyui"
    / "image_z_image_turbo_fun_union_controlnet.json"
)


@pytest.fixture
def converter() -> WorkflowConverter:
    return WorkflowConverter().load(WORKFLOW_PATH)


@pytest.fixture
def api(converter: WorkflowConverter) -> dict:
    return converter.to_api_format()


# ------------------------------------------------------------------
# 基础结构测试
# ------------------------------------------------------------------


class TestLoadAndStructure:
    def test_load_workflow(self, converter: WorkflowConverter):
        assert converter._raw is not None

    def test_api_format_node_count(self, api: dict):
        assert len(api) == 16

    def test_all_nodes_have_class_type_and_inputs(self, api: dict):
        for node_id, node_data in api.items():
            assert "class_type" in node_data, f"节点 {node_id} 缺少 class_type"
            assert "inputs" in node_data, f"节点 {node_id} 缺少 inputs"

    def test_no_skipped_types(self, api: dict):
        for node_data in api.values():
            assert node_data["class_type"] not in {"PreviewImage", "MarkdownNote"}

    def test_no_subgraph_uuid_types(self, api: dict):
        for node_data in api.values():
            # 子图 UUID 包含连字符
            assert "-" not in node_data["class_type"]


# ------------------------------------------------------------------
# 连接有效性测试
# ------------------------------------------------------------------


class TestConnections:
    def test_connections_reference_valid_nodes(self, api: dict):
        for node_id, node_data in api.items():
            for input_name, value in node_data["inputs"].items():
                if isinstance(value, list) and len(value) == 2:
                    ref_id, slot = value
                    assert ref_id in api, (
                        f"节点 {node_id} 的 {input_name} 引用了"
                        f"不存在的节点 {ref_id}"
                    )

    def test_subgraph_boundary_connections(self, api: dict):
        """Canny(#57) output 0 → QwenImageDiffsynthControlnet(#60) image input。"""
        node_60 = api["60"]
        assert node_60["inputs"]["image"] == ["57", 0]

    def test_subgraph_output_connection(self, api: dict):
        """SaveImage(#9) images ← VAEDecode(#43) output 0。"""
        node_9 = api["9"]
        assert node_9["inputs"]["images"] == ["43", 0]

    def test_canny_to_get_image_size(self, api: dict):
        """Canny(#57) output 0 → GetImageSize(#69) image input。"""
        node_69 = api["69"]
        assert node_69["inputs"]["image"] == ["57", 0]


# ------------------------------------------------------------------
# 具体节点内容测试
# ------------------------------------------------------------------


class TestNodeContent:
    def test_load_image_inputs(self, api: dict):
        node = api["58"]
        assert node["class_type"] == "LoadImage"
        assert "image" in node["inputs"]

    def test_ksampler_inputs(self, api: dict):
        node = api["44"]
        assert node["class_type"] == "KSampler"
        assert "seed" in node["inputs"]
        assert "steps" in node["inputs"]
        assert "cfg" in node["inputs"]
        assert "sampler_name" in node["inputs"]
        assert "scheduler" in node["inputs"]
        assert "denoise" in node["inputs"]
        # 隐藏 widget 不应出现
        assert "control_after_generate" not in node["inputs"]

    def test_ksampler_values(self, api: dict):
        inputs = api["44"]["inputs"]
        assert inputs["steps"] == 9
        assert inputs["cfg"] == 1
        assert inputs["sampler_name"] == "res_multistep"
        assert inputs["scheduler"] == "simple"
        assert inputs["denoise"] == 1

    def test_clip_text_encode_has_text(self, api: dict):
        node = api["45"]
        assert node["class_type"] == "CLIPTextEncode"
        assert "text" in node["inputs"]
        assert isinstance(node["inputs"]["text"], str)
        assert len(node["inputs"]["text"]) > 0

    def test_clip_loader_inputs(self, api: dict):
        node = api["39"]
        assert node["class_type"] == "CLIPLoader"
        assert node["inputs"]["clip_name"] == "qwen_3_4b.safetensors"
        assert node["inputs"]["type"] == "lumina2"

    def test_canny_inputs(self, api: dict):
        node = api["57"]
        assert node["class_type"] == "Canny"
        assert node["inputs"]["low_threshold"] == 0.15
        assert node["inputs"]["high_threshold"] == 0.35

    def test_controlnet_strength(self, api: dict):
        node = api["60"]
        assert node["class_type"] == "QwenImageDiffsynthControlnet"
        assert node["inputs"]["strength"] == 1


# ------------------------------------------------------------------
# 参数注入测试
# ------------------------------------------------------------------


class TestParameterInjection:
    def test_set_prompt(self, converter: WorkflowConverter):
        converter.to_api_format()
        converter.set_prompt("a cat sitting on a table")
        assert api_node_by_type(converter, "CLIPTextEncode")["inputs"]["text"] == (
            "a cat sitting on a table"
        )

    def test_set_condition_image(self, converter: WorkflowConverter):
        converter.to_api_format()
        converter.set_condition_image("test_image.png")
        assert api_node_by_type(converter, "LoadImage")["inputs"]["image"] == (
            "test_image.png"
        )

    def test_set_prompt_chaining(self, converter: WorkflowConverter):
        result = converter.set_prompt("test").set_condition_image("img.png")
        assert result is converter

    def test_to_api_format_caching(self, converter: WorkflowConverter):
        api1 = converter.to_api_format()
        api2 = converter.to_api_format()
        assert api1 is api2


# ------------------------------------------------------------------
# 辅助函数
# ------------------------------------------------------------------


def api_node_by_type(converter: WorkflowConverter, class_type: str) -> dict:
    for node_data in converter.to_api_format().values():
        if node_data["class_type"] == class_type:
            return node_data
    raise ValueError(f"未找到 class_type={class_type} 的节点")
