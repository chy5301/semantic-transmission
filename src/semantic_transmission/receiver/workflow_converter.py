"""ComfyUI 工作流 JSON 格式转换器。

将 ComfyUI UI 导出格式转换为 API 提交格式（POST /prompt 接受的格式）。
"""

import json
from pathlib import Path
from typing import Any


class WorkflowConverter:
    """将 ComfyUI UI 导出的工作流 JSON 转换为 API 可提交格式。

    UI 导出格式包含 nodes、links、groups、definitions 等可视化元数据；
    API 提交格式是扁平的 {node_id_str: {class_type, inputs}} 字典。
    """

    SKIP_NODE_TYPES = {"PreviewImage", "MarkdownNote"}
    SEED_WIDGET_NAMES = {"seed", "noise_seed"}
    VIRTUAL_INPUT_ID = -10
    VIRTUAL_OUTPUT_ID = -20

    def __init__(self) -> None:
        self._raw: dict[str, Any] | None = None
        self._api_format: dict[str, Any] | None = None

    def load(self, json_path: str | Path) -> "WorkflowConverter":
        """加载 UI 格式的工作流 JSON 文件。"""
        with open(json_path, encoding="utf-8") as f:
            self._raw = json.load(f)
        self._api_format = None
        return self

    def to_api_format(self) -> dict[str, Any]:
        """将已加载的 UI 格式工作流转换为 API 提交格式。"""
        if self._raw is None:
            raise ValueError("请先调用 load() 加载工作流文件")

        if self._api_format is not None:
            return self._api_format

        result: dict[str, Any] = {}
        outer_link_lookup = self._build_outer_link_lookup()
        subgraph_defs = self._build_subgraph_defs()
        outer_nodes = self._raw["nodes"]

        # 先展开子图（会修改 outer_link_lookup 中的输出重定向）
        for node in outer_nodes:
            if node["type"] in subgraph_defs:
                expanded = self._expand_subgraph(
                    node, subgraph_defs[node["type"]], outer_link_lookup
                )
                result.update(expanded)

        # 再转换普通节点（使用已更新的 outer_link_lookup）
        for node in outer_nodes:
            node_type = node["type"]
            if node_type in self.SKIP_NODE_TYPES or node_type in subgraph_defs:
                continue
            node_id_str, node_data = self._convert_node(node, outer_link_lookup)
            result[node_id_str] = node_data

        self._api_format = result
        return result

    def set_prompt(self, text: str) -> "WorkflowConverter":
        """注入文本描述到 CLIPTextEncode 节点。"""
        api = self.to_api_format()
        for node_data in api.values():
            if node_data["class_type"] == "CLIPTextEncode":
                node_data["inputs"]["text"] = text
                break
        return self

    def set_condition_image(self, image_name: str) -> "WorkflowConverter":
        """注入条件图像文件名到 LoadImage 节点。"""
        api = self.to_api_format()
        for node_data in api.values():
            if node_data["class_type"] == "LoadImage":
                node_data["inputs"]["image"] = image_name
                break
        return self

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _build_outer_link_lookup(self) -> dict[int, tuple[int, int]]:
        """构建外层连接查找表: link_id → (from_node_id, from_slot)。"""
        lookup: dict[int, tuple[int, int]] = {}
        for link in self._raw.get("links", []):
            # 格式: [link_id, from_node, from_slot, to_node, to_slot, type]
            lookup[link[0]] = (link[1], link[2])
        return lookup

    def _build_subgraph_defs(self) -> dict[str, dict]:
        """构建子图定义查找表: subgraph_uuid → subgraph_definition。"""
        defs: dict[str, dict] = {}
        for sg in self._raw.get("definitions", {}).get("subgraphs", []):
            defs[sg["id"]] = sg
        return defs

    def _convert_node(
        self, node: dict, link_lookup: dict[int, tuple[int, int]]
    ) -> tuple[str, dict[str, Any]]:
        """将单个节点转换为 API 格式。"""
        inputs = self._map_widgets(node)

        # 用连接覆盖 widget 值
        for inp in node.get("inputs", []):
            link_id = inp.get("link")
            if link_id is not None and link_id in link_lookup:
                from_node, from_slot = link_lookup[link_id]
                inputs[inp["name"]] = [str(from_node), from_slot]

        return str(node["id"]), {"class_type": node["type"], "inputs": inputs}

    def _map_widgets(self, node: dict) -> dict[str, Any]:
        """将节点的 widgets_values 映射到对应的 widget input 名称。"""
        result: dict[str, Any] = {}
        widgets_values = node.get("widgets_values", [])
        if not widgets_values:
            return result

        widget_inputs = [inp for inp in node.get("inputs", []) if "widget" in inp]

        vi = 0  # widgets_values 游标
        for wi_inp in widget_inputs:
            if vi >= len(widgets_values):
                break
            widget_name = wi_inp["widget"]["name"]
            result[widget_name] = widgets_values[vi]
            vi += 1

            # seed / noise_seed 后面可能跟着隐藏的 control_after_generate
            if (
                widget_name in self.SEED_WIDGET_NAMES
                and vi < len(widgets_values)
                and len(widgets_values) > len(widget_inputs)
            ):
                vi += 1  # 跳过 control_after_generate

        return result

    def _expand_subgraph(
        self,
        sg_ref_node: dict,
        sg_def: dict,
        outer_link_lookup: dict[int, tuple[int, int]],
    ) -> dict[str, Any]:
        """展开子图引用节点，返回扁平化的内部节点字典。"""
        result: dict[str, Any] = {}
        sg_ref_id = sg_ref_node["id"]
        internal_links = sg_def["links"]

        # 子图内部 link 查找表: link_id → (from_node_id, from_slot)
        internal_link_lookup: dict[int, tuple[int, int]] = {}
        for link in internal_links:
            internal_link_lookup[link["id"]] = (
                link["origin_id"],
                link["origin_slot"],
            )

        # 解析虚拟输入节点的连接
        virtual_input_overrides = self._resolve_virtual_inputs(
            sg_ref_node, sg_def, outer_link_lookup, internal_links
        )

        # 重定向虚拟输出节点：修改 outer_link_lookup 使外层节点
        # 直接引用子图内部的源节点
        self._redirect_virtual_outputs(
            sg_ref_id, sg_def, internal_links, outer_link_lookup
        )

        # 转换所有内部节点
        for node in sg_def["nodes"]:
            node_id = node["id"]
            inputs = self._map_widgets(node)

            for slot_idx, inp in enumerate(node.get("inputs", [])):
                link_id = inp.get("link")
                if link_id is None or link_id not in internal_link_lookup:
                    continue

                from_node_id, _ = internal_link_lookup[link_id]

                override_key = (node_id, slot_idx)
                if override_key in virtual_input_overrides:
                    inputs[inp["name"]] = virtual_input_overrides[override_key]
                elif from_node_id != self.VIRTUAL_INPUT_ID:
                    inputs[inp["name"]] = [
                        str(from_node_id),
                        internal_link_lookup[link_id][1],
                    ]

            result[str(node_id)] = {
                "class_type": node["type"],
                "inputs": inputs,
            }

        return result

    def _resolve_virtual_inputs(
        self,
        sg_ref_node: dict,
        sg_def: dict,
        outer_link_lookup: dict[int, tuple[int, int]],
        internal_links: list[dict],
    ) -> dict[tuple[int, int], Any]:
        """解析子图虚拟输入节点 (-10) 的连接，返回覆盖值映射。

        返回: {(target_node_id, target_slot) → 实际值或 [node_id_str, slot] 连接}
        """
        overrides: dict[tuple[int, int], Any] = {}
        sg_inputs = sg_def.get("inputs", [])
        sg_ref_inputs = sg_ref_node.get("inputs", [])
        sg_ref_widget_values = self._map_widgets(sg_ref_node)

        for slot_idx, sg_input in enumerate(sg_inputs):
            # 收集从 -10 的 slot_idx 出发的内部连接目标
            targets = [
                (link["target_id"], link["target_slot"])
                for link in internal_links
                if link["origin_id"] == self.VIRTUAL_INPUT_ID
                and link["origin_slot"] == slot_idx
            ]

            # 确定值来源：外部连接 or widget 值
            external_source = None
            if slot_idx < len(sg_ref_inputs):
                link_id = sg_ref_inputs[slot_idx].get("link")
                if link_id is not None and link_id in outer_link_lookup:
                    external_source = outer_link_lookup[link_id]

            for target_node_id, target_slot in targets:
                if external_source is not None:
                    from_node, from_slot = external_source
                    overrides[(target_node_id, target_slot)] = [
                        str(from_node),
                        from_slot,
                    ]
                elif sg_input["name"] in sg_ref_widget_values:
                    overrides[(target_node_id, target_slot)] = sg_ref_widget_values[
                        sg_input["name"]
                    ]

        return overrides

    def _redirect_virtual_outputs(
        self,
        sg_ref_id: int,
        sg_def: dict,
        internal_links: list[dict],
        outer_link_lookup: dict[int, tuple[int, int]],
    ) -> None:
        """将外层中指向子图引用节点输出的连接重定向到内部源节点。"""
        # 找到连接到 -20 的内部源节点: output_slot → (internal_node_id, slot)
        virtual_output_sources: dict[int, tuple[int, int]] = {}
        for link in internal_links:
            if link["target_id"] == self.VIRTUAL_OUTPUT_ID:
                virtual_output_sources[link["target_slot"]] = (
                    link["origin_id"],
                    link["origin_slot"],
                )

        # 修改 outer_link_lookup 中源节点为 sg_ref_id 的条目
        for link in self._raw.get("links", []):
            link_id, from_node, from_slot = link[0], link[1], link[2]
            if from_node == sg_ref_id and from_slot in virtual_output_sources:
                outer_link_lookup[link_id] = virtual_output_sources[from_slot]
