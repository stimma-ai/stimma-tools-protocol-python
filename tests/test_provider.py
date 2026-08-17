import asyncio

from stimma_tools_protocol.assets import FilesystemAssetManager
from stimma_tools_protocol.protocol import JsonRpcRequest
from stimma_tools_protocol.provider import Provider, ProviderConfig
from stimma_tools_protocol.tool import Tool, ToolRegistry

from helpers import MemoryTransport


async def _start_provider(provider, transport, assets):
    started = asyncio.create_task(provider.start(assets))
    registration = await transport.host_receive(method="provider.register")
    assert registration["params"]["stp_version"] == "1.0"
    assert registration["params"]["capabilities"] == {"cancel": True}
    await transport.host_respond(registration, {"session_id": "session-1", "stp_version": "1.0"})
    await started


async def _request(transport, method, request_id, params=None):
    await transport.incoming.put(JsonRpcRequest(method, request_id, params).to_json())
    while True:
        message = await transport.host_receive()
        if message.get("id") == request_id:
            return message


async def test_provider_executes_reports_progress_and_normalizes_assets(tmp_path):
    transport = MemoryTransport()
    registry = ToolRegistry()

    async def execute(context, parameters):
        assert parameters["steps"] == 4
        assert parameters["_provided_keys"] == {"prompt"}
        await context.report_progress(0.5)
        asset_id = await context.assets.upload(b"image", ".png")
        return {"asset_id": asset_id, "seed": 12}

    from stimma_tools_protocol.tool import ToolParameter
    registry.register(Tool("image", "Image", ["text-to-image"], execute, parameters=[
        ToolParameter("prompt", "string", required=True),
        ToolParameter("steps", "integer", default=4),
    ]))
    provider = Provider(ProviderConfig("test", "Test", max_concurrent=1), transport, registry)
    await _start_provider(provider, transport, FilesystemAssetManager(str(tmp_path)))

    listed = await _request(transport, "tools.list", 1)
    assert listed["result"]["tools"][0]["id"] == "image"

    accepted = await _request(transport, "tools.execute", 2, {
        "request_id": "job-1", "tool_id": "image", "parameters": {"prompt": "hi"}
    })
    assert accepted["result"] == {"accepted": True}

    notifications = []
    while not any(m.get("method") == "tools.result" for m in notifications):
        notifications.append(await transport.host_receive())
    assert any(m.get("method") == "tools.progress" and m["params"]["progress"] == 0.5 for m in notifications)
    result = next(m for m in notifications if m.get("method") == "tools.result")["params"]
    assert result["success"] is True
    assert result["output"]["seed"] == 12
    assert result["output"]["assets"][0]["type"] == "image"

    await provider.stop()
    disconnect = await transport.host_receive(method="provider.disconnect")
    assert disconnect["params"] == {"reason": "shutdown"}


async def test_provider_state_includes_update_attention(tmp_path):
    transport = MemoryTransport()
    provider = Provider(
        ProviderConfig("test", "Test", provider_state=True),
        transport,
        ToolRegistry(),
    )
    started = asyncio.create_task(
        provider.start(FilesystemAssetManager(str(tmp_path)))
    )
    registration = await transport.host_receive(method="provider.register")
    await transport.host_respond(
        registration,
        {"session_id": "session-1", "stp_version": "1.0"},
    )
    await started

    await provider.send_state("ready", attention="update_available")

    notification = await transport.host_receive(method="provider.state")
    assert notification["params"] == {
        "state": "ready",
        "attention": "update_available",
    }
    await provider.stop()
    await transport.host_receive(method="provider.disconnect")


async def test_queueing_cancellation_and_shutdown_cleanup(tmp_path):
    transport = MemoryTransport()
    registry = ToolRegistry()
    started = asyncio.Event()
    release = asyncio.Event()

    async def execute(context, parameters):
        started.set()
        await release.wait()
        return {"assets": []}

    registry.register(Tool("slow", "Slow", ["text-to-image"], execute))
    provider = Provider(ProviderConfig("test", "Test", max_concurrent=1), transport, registry)
    await _start_provider(provider, transport, FilesystemAssetManager(str(tmp_path)))

    await _request(transport, "tools.execute", 1, {"request_id": "running", "tool_id": "slow"})
    await asyncio.wait_for(started.wait(), 1)
    await _request(transport, "tools.execute", 2, {"request_id": "queued", "tool_id": "slow"})

    cancelled = await _request(transport, "tools.cancel", 3, {"request_id": "queued"})
    assert cancelled["result"] == {"cancelled": True}
    cancelled = await _request(transport, "tools.cancel", 4, {"request_id": "running"})
    assert cancelled["result"] == {"cancelled": True}

    result = await transport.host_receive(method="tools.result")
    assert result["params"]["request_id"] == "running"
    assert result["params"]["error"]["code"] == "CANCELLED"

    await asyncio.wait_for(provider.stop(), 1)
    assert not transport.is_running
