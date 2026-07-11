import aiohttp
import pytest
from aiohttp import web

from stimma_tools_protocol.assets import FilesystemAssetManager, HttpAssetManager, LocalAssetServer


async def test_filesystem_assets_round_trip_and_sanitize_paths(tmp_path):
    manager = FilesystemAssetManager(str(tmp_path))
    asset_id = await manager.upload(b"pixels", ".png")

    assert await manager.exists(asset_id)
    assert await manager.download(asset_id) == b"pixels"
    assert await manager.delete(asset_id)
    assert not await manager.exists(asset_id)

    outside = tmp_path.parent / "outside.txt"
    outside.write_bytes(b"private")
    with pytest.raises(FileNotFoundError):
        await manager.download("../outside.txt")


async def test_http_and_local_asset_managers_conform(tmp_path):
    local = LocalAssetServer(str(tmp_path))
    app = web.Application()
    app.add_routes(local.get_aiohttp_routes("/assets"))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    remote = HttpAssetManager(f"http://127.0.0.1:{port}", "/assets")

    try:
        asset_id = await remote.upload(b"movie", ".mp4")
        assert await remote.exists(asset_id)
        assert await remote.download(asset_id) == b"movie"
        assert await remote.delete(asset_id)
        assert not await remote.exists(asset_id)

        async with aiohttp.ClientSession() as session:
            response = await session.put(
                f"http://127.0.0.1:{port}/assets/..%2Fescape.png", data=b"bad"
            )
            assert response.status == 400
    finally:
        await remote.close()
        await runner.cleanup()
