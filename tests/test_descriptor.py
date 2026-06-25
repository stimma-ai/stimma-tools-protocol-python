"""Tests for ToolDescriptor model_vendor / model fields."""

from stimma_tools_protocol.protocol import ToolDescriptor
from stimma_tools_protocol.tool import Tool


def test_descriptor_to_dict_includes_model_fields():
    desc = ToolDescriptor(
        id="flux-dev:text-to-image",
        name="Flux Dev",
        task_types=["text-to-image"],
        model_vendor="black-forest-labs",
        model="flux2-klein-9b",
    )
    d = desc.to_dict()
    assert d["model_vendor"] == "black-forest-labs"
    assert d["model"] == "flux2-klein-9b"


def test_descriptor_to_dict_omits_model_fields_when_unset():
    desc = ToolDescriptor(
        id="t",
        name="T",
        task_types=["text-to-image"],
    )
    d = desc.to_dict()
    assert "model_vendor" not in d
    assert "model" not in d


def test_tool_to_descriptor_propagates_model_fields():
    async def _run(context, **kwargs):
        return {"assets": []}

    tool = Tool(
        slug="qwen:text-to-image",
        display_name="Qwen Image",
        task_types=["text-to-image"],
        function=_run,
        model_vendor="alibaba",
        model="qwen-image-2512",
    )
    desc = tool.to_descriptor()
    assert desc.model_vendor == "alibaba"
    assert desc.model == "qwen-image-2512"

    d = desc.to_dict()
    assert d["model_vendor"] == "alibaba"
    assert d["model"] == "qwen-image-2512"
