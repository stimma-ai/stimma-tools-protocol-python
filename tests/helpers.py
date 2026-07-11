import asyncio
from collections.abc import AsyncIterator

from stimma_tools_protocol.protocol import JsonRpcResponse, parse_message
from stimma_tools_protocol.transport import Transport


class MemoryTransport(Transport):
    """Bidirectional transport controlled by a test host."""

    def __init__(self) -> None:
        self.incoming: asyncio.Queue[str | None] = asyncio.Queue()
        self.outgoing: asyncio.Queue[str] = asyncio.Queue()
        self._running = False

    async def start(self) -> None:
        self._running = True

    async def stop(self) -> None:
        self._running = False
        await self.incoming.put(None)

    async def send(self, message: str) -> None:
        await self.outgoing.put(message)

    async def receive(self) -> AsyncIterator[str]:
        while self._running:
            message = await self.incoming.get()
            if message is None:
                break
            yield message

    @property
    def is_running(self) -> bool:
        return self._running

    async def host_receive(self, *, method: str | None = None) -> dict:
        while True:
            message = parse_message(await asyncio.wait_for(self.outgoing.get(), 1))
            data = message.to_dict()
            if method is None or data.get("method") == method:
                return data

    async def host_respond(self, request: dict, result: dict) -> None:
        response = JsonRpcResponse.success(request["id"], result)
        await self.incoming.put(response.to_json())
