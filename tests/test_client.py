import pytest

import klappstuhl
from klappstuhl.errors import Forbidden, NotFound, RateLimited


async def test_versions(client, server):
    server.add("GET", "/api", json={"current": "v1", "versions": [
        {"version": "v1", "status": "stable", "base_path": "/api/v1"}]})
    res = await client.versions()
    assert res.current == "v1"
    assert res.versions[0].base_path == "/api/v1"


async def test_upload_sends_auth_and_ttl(client, server):
    server.add("POST", "/api/v1/images/upload", json={
        "total": 1, "errors": 0, "skipped": 0, "infected": 0,
        "links": ["https://klappstuhl.me/abc.png"], "raw_links": ["https://klappstuhl.me/r/abc.png"]})
    res = await client.upload(b"\x89PNG-bytes", expires_in=3600)
    assert res.is_success
    assert res.links[0].endswith("abc.png")

    req = server.last_request()
    assert req["headers"]["Authorization"] == "test-token"
    assert req["query"]["expires_in"] == "3600"
    assert b"PNG-bytes" in req["body"]  # multipart carried the file


async def test_upload_requires_file(client):
    with pytest.raises(ValueError):
        await client.upload()


async def test_delete_image_strips_extension(client, server):
    server.add("DELETE", "/api/v1/images/abc", json={"file": "abc", "failed": False})
    res = await client.delete_image("abc.png")
    assert res.file == "abc"
    assert not res.failed
    assert server.last_request()["path"] == "/api/v1/images/abc"


async def test_download_returns_bytes(client, server):
    server.add("POST", "/api/v1/images/download", body=b"PK\x03\x04zipdata",
               content_type="application/zip")
    data = await client.download(["abc", "def"])
    assert data.startswith(b"PK")


async def test_scan(client, server):
    server.add("POST", "/api/v1/scan", json={
        "sha256": "deadbeef", "file_size": 20, "verdict": "clean", "clamav_clean": True})
    report = await client.scan(b"harmless")
    assert report.is_clean
    assert report.clamav_clean is True


async def test_metadata_with_url(client, server):
    server.add("POST", "/api/v1/metadata", json={
        "width": 10, "height": 20, "format": "png", "color": "Rgb8", "file_size": 100})
    info = await client.metadata(url="https://example.com/pic.png")
    assert info.width == 10 and info.height == 20
    assert b"example.com" in server.last_request()["body"]  # url field in multipart


async def test_metadata_requires_exactly_one_source(client):
    with pytest.raises(ValueError):
        await client.metadata()
    with pytest.raises(ValueError):
        await client.metadata(b"x", url="https://e.com/a.png")


async def test_manipulate_returns_bytes(client, server):
    server.add("POST", "/api/v1/image/blur", body=b"PNGRESULT", content_type="image/png")
    out = await client.blur(b"src", amount=12)
    assert out == b"PNGRESULT"
    assert server.last_request()["query"]["amount"] == "12"


async def test_manipulate_share_returns_shareresult(client, server):
    server.add("POST", "/api/v1/image/deepfry", json={
        "id": "m1", "url": "https://klappstuhl.me/m/m1", "content_type": "image/png"})
    out = await client.deepfry(b"src", share=True)
    assert isinstance(out, klappstuhl.ShareResult)
    assert out.id == "m1"
    assert server.last_request()["query"]["share"] == "true"


async def test_convert(client, server):
    server.add("POST", "/api/v1/convert", body=b"WEBP", content_type="image/webp")
    out = await client.convert("webp", b"src")
    assert out == b"WEBP"
    assert server.last_request()["query"]["to"] == "webp"


async def test_render_code_bytes(client, server):
    server.add("POST", "/api/v1/render/code", body=b"<svg></svg>", content_type="image/svg+xml")
    out = await client.render_code("print('hi')", language="py")
    assert out.startswith(b"<svg")


async def test_screenshot_share(client, server):
    server.add("POST", "/api/v1/render/screenshot", json={
        "id": "s1", "url": "https://klappstuhl.me/m/s1", "content_type": "image/png"})
    out = await client.screenshot("https://example.com", full_page=True, share=True)
    assert out.url.endswith("/m/s1")


async def test_transcode(client, server):
    server.add("POST", "/api/v1/convert/transcode", body=b"mp4bytes", content_type="video/mp4")
    out = await client.transcode(b"movdata", to="mp4")
    assert out == b"mp4bytes"
    assert server.last_request()["query"]["to"] == "mp4"


async def test_guild_gallery_roundtrip(client, server):
    server.add("POST", "/api/v1/guilds/42/images/upload", json={
        "total": 1, "errors": 0, "skipped": 0, "infected": 0, "links": ["l"], "raw_links": ["r"]})
    server.add("GET", "/api/v1/guilds/42/images", json={
        "images": [{"id": "i", "ext": "png", "mimetype": "image/png", "size": 3,
                    "uploaded_at": "2026-07-06T00:00:00Z", "url": "u", "raw_url": "ru"}],
        "total": 1})
    server.add("DELETE", "/api/v1/guilds/42/images/i", json={"file": "i", "failed": False})

    up = await client.upload_guild_images(42, b"img")
    listed = await client.list_guild_images(42)
    deleted = await client.delete_guild_image(42, "i.png")

    assert up.total == 1
    assert listed.images[0].id == "i"
    assert deleted.file == "i"


async def test_admin_updates(client, server):
    server.add("GET", "/api/v1/admin/updates", json=[
        {"service": "web", "image": "nginx:latest", "state": "up_to_date", "checked_at": 100}])
    updates = await client.admin_updates()
    assert updates[0].service == "web"
    assert updates[0].state is klappstuhl.UpdateState.UP_TO_DATE


async def test_forbidden_error(client, server):
    server.add("POST", "/api/v1/images/upload", status=403, json={
        "error": "this API key is missing the `images:write` scope", "code": 4})
    with pytest.raises(Forbidden) as exc:
        await client.upload(b"x")
    assert "images:write" in exc.value.message


async def test_not_found_error(client, server):
    server.add("DELETE", "/api/v1/images/nope", status=404,
               json={"error": "Image not found", "code": 6})
    with pytest.raises(NotFound):
        await client.delete_image("nope")


async def test_rate_limit_is_retried_then_succeeds(client, server):
    server.add("POST", "/api/v1/scan", status=429,
               headers={"x-ratelimit-reset-after": "0"},
               json={"error": "rate limited", "code": 8})
    server.add("POST", "/api/v1/scan", json={"sha256": "d", "file_size": 1, "verdict": "clean"})
    report = await client.scan(b"x")
    assert report.is_clean
    assert len(server.requests) == 2  # retried once


async def test_rate_limit_exhausts_and_raises(server):
    async with klappstuhl.Client("t", base_url=server.base_url, max_retries=1) as c:
        server.add("POST", "/api/v1/scan", status=429,
                   headers={"x-ratelimit-reset-after": "0"},
                   json={"error": "rate limited", "code": 8})
        # Second queued response is also a 429 so the retry is exhausted.
        server.add("POST", "/api/v1/scan", status=429,
                   headers={"x-ratelimit-reset-after": "0"},
                   json={"error": "rate limited", "code": 8})
        with pytest.raises(RateLimited):
            await c.scan(b"x")


async def test_rate_limit_headers_exposed(client, server):
    server.add("GET", "/api/v1/admin/updates", json=[],
               headers={"x-ratelimit-limit": "25", "x-ratelimit-remaining": "24",
                        "x-ratelimit-reset-after": "0.5"},
               content_type="application/json")
    await client.admin_updates()
    assert client.rate_limit is not None
    assert client.rate_limit.limit == 25
    assert client.rate_limit.remaining == 24
