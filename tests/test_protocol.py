import asyncio

import pytest

from stimma_tools_protocol.protocol import (
    JsonRpcErrorCode,
    JsonRpcNotification,
    JsonRpcRequest,
    JsonRpcResponse,
    parse_message,
)
from stimma_tools_protocol.transport import MessageHandler

from helpers import MemoryTransport


def test_parse_message_distinguishes_requests_notifications_and_responses():
    assert isinstance(parse_message(JsonRpcRequest("tools.list", 1).to_json()), JsonRpcRequest)
    assert isinstance(parse_message(JsonRpcNotification("host.ready").to_json()), JsonRpcNotification)
    assert isinstance(parse_message(JsonRpcResponse.success(1, {}).to_json()), JsonRpcResponse)


@pytest.mark.parametrize("message", ["not json", "[]", '{"jsonrpc":"1.0","method":"x"}'])
def test_parse_message_rejects_invalid_json_rpc(message):
    with pytest.raises(ValueError):
        parse_message(message)


async def test_message_handler_routes_requests_and_parse_errors():
    transport = MemoryTransport()
    await transport.start()
    handler = MessageHandler(
        transport,
        on_request=lambda request: asyncio.sleep(
            0, result=JsonRpcResponse.success(request.id, {"method": request.method})
        ),
    )

    await handler.handle_message(JsonRpcRequest("tools.list", 7).to_json())
    response = parse_message(await transport.outgoing.get())
    assert response.to_dict() == {"jsonrpc": "2.0", "id": 7, "result": {"method": "tools.list"}}

    await handler.handle_message("{")
    error = parse_message(await transport.outgoing.get())
    assert error.error.code == JsonRpcErrorCode.PARSE_ERROR.value
    assert error.id is None


async def test_message_handler_resolves_and_cancels_pending_requests():
    transport = MemoryTransport()
    await transport.start()
    handler = MessageHandler(transport)

    pending = asyncio.create_task(handler.send_request("provider.register"))
    request = parse_message(await transport.outgoing.get()).to_dict()
    await handler.handle_message(JsonRpcResponse.success(request["id"], {"session_id": "s"}).to_json())
    assert (await pending).result == {"session_id": "s"}

    abandoned = asyncio.create_task(handler.send_request("provider.register"))
    await transport.outgoing.get()
    handler.close()
    with pytest.raises(asyncio.CancelledError):
        await abandoned
