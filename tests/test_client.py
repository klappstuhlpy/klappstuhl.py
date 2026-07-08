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
    req = server.last_request()
    assert b"example.com" in req["body"]  # url field in multipart
    # A url-only source must still be sent as multipart/form-data (the endpoint
    # is multipart-only); a fields-only form must not degrade to urlencoded.
    assert req["headers"]["Content-Type"].startswith("multipart/form-data")


async def test_url_source_uses_multipart(client, server):
    # Regression: a fields-only form (the ``url`` alternative to a file) was
    # being sent as application/x-www-form-urlencoded, which the multipart-only
    # image endpoints reject with "Invalid boundary for multipart/form-data".
    server.add("POST", "/api/v1/image/blur", body=b"PNGRESULT", content_type="image/png")
    out = await client.blur(url="https://example.com/pic.png")
    assert out == b"PNGRESULT"
    ctype = server.last_request()["headers"]["Content-Type"]
    assert ctype.startswith("multipart/form-data")
    assert "boundary=" in ctype


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


async def test_raw_request_escape_hatch(client, server):
    # The raw ``request`` escape hatch reaches endpoints not on the typed
    # surface (e.g. the admin-only routes) and returns the unwrapped body.
    server.add("GET", "/api/v1/admin/updates", json=[
        {"service": "web", "image": "nginx:latest", "state": "up_to_date", "checked_at": 100}])
    data = await client.request("GET", "/admin/updates")
    assert data[0]["service"] == "web"
    # Callers parse it themselves with the public models if they wish.
    updates = [klappstuhl.ImageUpdate.from_dict(item) for item in data]
    assert updates[0].state is klappstuhl.UpdateState.UP_TO_DATE


async def test_raw_request_sends_auth_and_params(client, server):
    server.add("GET", "/api/v1/anything", json={"ok": True})
    await client.request("GET", "/anything", params={"a": 1, "b": None, "c": True})
    req = server.requests[-1]
    assert req["headers"]["Authorization"] == "test-token"
    assert req["query"]["a"] == "1"
    assert "b" not in req["query"]  # None dropped
    assert req["query"]["c"] == "true"  # bool coerced


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
    server.add("GET", "/api/v1/anything", json=[],
               headers={"x-ratelimit-limit": "25", "x-ratelimit-remaining": "24",
                        "x-ratelimit-reset-after": "0.5"},
               content_type="application/json")
    await client.request("GET", "/anything")
    assert client.rate_limit is not None
    assert client.rate_limit.limit == 25
    assert client.rate_limit.remaining == 24


async def test_me(client, server):
    server.add("GET", "/api/v1/me", json={
        "id": 7, "name": "ben", "admin": False, "totp_enabled": True,
        "discord_linked": True, "key_scopes": ["images:read", "links:write"]})
    me = await client.me()
    assert me.id == 7 and me.name == "ben"
    assert me.totp_enabled and me.discord_linked and not me.admin
    assert me.key_scopes == ["images:read", "links:write"]
    # Scope values in the response map onto the enum, including privilege info.
    scopes = [klappstuhl.Scope(s) for s in me.key_scopes]
    assert not any(s.is_privileged for s in scopes)


async def test_usage_series_is_chart_ready(client, server):
    server.add("GET", "/api/v1/me/usage", json={
        "images": {"count": 3, "bytes": 4096, "views": 12},
        "links": {"count": 2, "bytes": 0, "views": 40},
        "pastes": {"count": 1, "bytes": 0, "views": 5},
        "series": {"days": ["2026-07-07", "2026-07-08"], "uploads": [0, 3],
                   "upload_bytes": [0, 4096]}})
    usage = await client.usage()
    assert usage.images.count == 3 and usage.images.bytes == 4096
    assert usage.links.views == 40  # clicks surface as views
    # The series arrays line up so they can feed render_chart directly.
    assert len(usage.series.days) == len(usage.series.uploads) == len(usage.series.upload_bytes)


async def test_update_link(client, server):
    server.add("PATCH", "/api/v1/links/abc", json={
        "code": "abc", "short_url": "https://r.klappstuhl.me/abc",
        "target_url": "https://new.example.com/", "clicks": 5,
        "created_at": "2026-07-01T00:00:00Z"})
    link = await client.update_link("abc", "new.example.com")
    assert link.target_url == "https://new.example.com/"
    req = server.last_request()
    assert req["method"] == "PATCH"
    assert b"new.example.com" in req["body"]


async def test_render_chart_builds_spec(client, server):
    import json as _json

    server.add("POST", "/api/v1/render/chart", body=b"<svg>chart</svg>",
               content_type="image/svg+xml")
    out = await client.render_chart(
        klappstuhl.ChartKind.LINE,
        {"api": [1, 2, 3], "web": [(0, 4), (1, 5)]},
        labels=["a", "b", "c"],
        title="T",
        theme=klappstuhl.ChartTheme.DARK,
        width=700,
        y_label="req",
    )
    assert out.startswith(b"<svg")
    body = _json.loads(server.last_request()["body"])
    assert body["kind"] == "line" and body["theme"] == "dark"
    assert body["series"][0] == {"label": "api", "data": [1, 2, 3]}
    # (x, y) tuples serialize as [x, y] pairs.
    assert body["series"][1]["data"] == [[0, 4], [1, 5]]
    assert body["labels"] == ["a", "b", "c"]
    assert body["width"] == 700 and body["y_label"] == "req"
    assert "height" not in body  # unset optionals are omitted


async def test_render_chart_share(client, server):
    server.add("POST", "/api/v1/render/chart", json={
        "id": "c1", "url": "https://klappstuhl.me/m/c1", "content_type": "image/svg+xml"})
    out = await client.render_chart("pie", {"split": [3, 1]}, labels=["a", "b"], share=True)
    assert isinstance(out, klappstuhl.ShareResult)
    assert out.id == "c1"
    assert server.last_request()["query"]["share"] == "true"


async def test_color_palette(client, server):
    server.add("POST", "/api/v1/color/palette", json={
        "colors": [
            {"hex": "#d97757", "rgb": [217, 119, 87], "proportion": 0.6},
            {"hex": "#0e0e10", "rgb": [14, 14, 16], "proportion": 0.4},
        ],
        "pixels_sampled": 9216})
    palette = await client.color_palette(b"png-bytes", count=2)
    assert palette.pixels_sampled == 9216
    assert palette.colors[0].hex == "#d97757"
    assert palette.colors[0].rgb == (217, 119, 87)
    assert server.last_request()["query"]["count"] == "2"


async def test_color_palette_requires_one_source(client):
    with pytest.raises(ValueError):
        await client.color_palette()
