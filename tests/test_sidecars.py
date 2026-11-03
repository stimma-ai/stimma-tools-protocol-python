import asyncio
from fractions import Fraction

import pytest

from helpers import MemoryTransport
from stimma_tools_protocol.assets import FilesystemAssetManager
from stimma_tools_protocol.protocol import ExecuteRequest, JsonRpcRequest
from stimma_tools_protocol.provider import Provider, ProviderConfig
from stimma_tools_protocol.sidecars import map_interval
from stimma_tools_protocol.tool import Tool, ToolRegistry


@pytest.mark.parametrize("host_support", [False, True])
async def test_companions_survive_queue_and_negotiate_outputs(tmp_path, host_support):
    companion = {"asset_id": "opaque.bin", "format": "example.other_state", "format_version": 4,
                 "descriptor": {"arbitrary": [1, {"different": True}]}}
    inputs = {"clip.mp4": [companion]}
    transport = MemoryTransport()
    registry = ToolRegistry()

    async def execute(context, parameters):
        assert context.input_sidecars == inputs
        assert "input_sidecars" not in parameters
        return {"asset_id": "out.mp4", "sidecars": [companion]}

    registry.register(Tool("test", "Test", ["text-to-video"], execute))
    provider = Provider(ProviderConfig("test", "Test", media_sidecars=True), transport, registry)
    started = asyncio.create_task(provider.start(FilesystemAssetManager(str(tmp_path))))
    registration = await transport.host_receive(method="provider.register")
    assert registration["params"]["capabilities"]["media_sidecars"] is True
    await transport.host_respond(registration, {"session_id": "test", "capabilities": {"media_sidecars": host_support}})
    await started
    try:
        await transport.incoming.put(JsonRpcRequest("tools.execute", 1, {
            "request_id": "one", "tool_id": "test", "parameters": {}, "input_sidecars": inputs,
        }).to_json())
        result = await transport.host_receive(method="tools.result")
        assert result["params"]["success"] is True
        asset = result["params"]["output"]["assets"][0]
        assert asset.get("sidecars") == ([companion] if host_support else None)
    finally:
        await provider.stop()


def test_map_joined_tail_without_source_database_and_changed_audio():
    mapping = {"version": 1, "media_time_base": {"num": 1, "den": 24},
               "source_time_base": {"num": 1, "den": 24}, "source_extent": [0, 158],
               "spans": [{"media": [600, 719], "source": [39, 158], "preserved_streams": ["video"]}]}
    assert map_interval(mapping, Fraction(680, 24), Fraction(39, 24), ["video"]) == (Fraction(119, 24), Fraction(39, 24))
    assert map_interval(mapping, Fraction(680, 24), Fraction(39, 24), ["audio"]) is None
    assert map_interval(mapping, 24, 2, ["video"]) is None


def test_unavailable_entry_is_preserved():
    request = ExecuteRequest.from_dict({"request_id": "one", "tool_id": "test", "input_sidecars": {
        "clip.mp4": [{"format": "another.format", "format_version": 1,
                      "status": "unavailable", "unavailable_reason": "upload_failed"}]}})
    assert request.input_sidecars["clip.mp4"][0]["unavailable_reason"] == "upload_failed"
