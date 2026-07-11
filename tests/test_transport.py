import asyncio

import aiohttp

from stimma_tools_protocol.transport import WebSocketTransport


async def _wait_for_port(transport: WebSocketTransport) -> int:
    for _ in range(100):
        if transport.port:
            return transport.port
        await asyncio.sleep(0.01)
    raise AssertionError("transport did not bind")


async def test_websocket_transport_auth_send_receive_and_shutdown():
    transport = WebSocketTransport(port=0, auth_token="secret")
    start = asyncio.create_task(transport.start())
    port = await _wait_for_port(transport)

    async with aiohttp.ClientSession() as session:
        unauthorized = await session.get(f"http://127.0.0.1:{port}/missing")
        assert unauthorized.status == 401

        ws = await session.ws_connect(
            f"http://127.0.0.1:{port}/stp-v1",
            headers={"Authorization": "Bearer secret"},
        )
        await asyncio.wait_for(start, 1)
        assert transport.is_running

        await ws.send_str("host-to-provider")
        receiver = transport.receive()
        assert await asyncio.wait_for(anext(receiver), 1) == "host-to-provider"

        await transport.send("provider-to-host")
        assert (await asyncio.wait_for(ws.receive(), 1)).data == "provider-to-host"

        await transport.stop()
        await receiver.aclose()
        assert not transport.is_running
