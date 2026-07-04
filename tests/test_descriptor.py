"""Tests for ToolDescriptor model_vendor / model fields."""

from stimma_tools_protocol.protocol import ToolDescriptor
from stimma_tools_protocol.tool import STANDARD_TASK_TYPES, Tool, ToolParameter


def test_standard_task_types_include_video_to_video():
    assert "image-to-image" in STANDARD_TASK_TYPES
    assert "video-to-video" in STANDARD_TASK_TYPES


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


def test_parameter_to_schema_emits_accept_media():
    param = ToolParameter(
        name="audio",
        type="string",
        accepted_media={
            "mime_types": ["audio/wav", "audio/mpeg"],
            "transcode_to": "audio/wav",
        },
    )
    schema = param.to_schema()
    assert schema["x-accept-media"] == {
        "mime_types": ["audio/wav", "audio/mpeg"],
        "transcode_to": "audio/wav",
    }


def test_parameter_to_schema_omits_accept_media_when_unset():
    param = ToolParameter(name="audio", type="string")
    assert "x-accept-media" not in param.to_schema()
