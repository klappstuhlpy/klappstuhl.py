# klappstuhl.py

A fast, fully-typed **async** Python wrapper for the [klappstuhl.me](https://klappstuhl.me) API — image hosting, media manipulation, format conversion, rendering (code screenshots, web-page screenshots, Markdown→PDF), malware scanning, and Discord-guild galleries.

- ⚡ **Async-first**, built on `aiohttp` with connection reuse.
- 🧯 **Reliable** — automatic retries with exponential backoff for network blips and `5xx`, and transparent `429` rate-limit handling using the server's reset headers.
- 🧩 **Typed** — every response is a dataclass, every error a specific exception, ships with `py.typed`.
- 📦 **Complete** — covers every endpoint of the public API (`/api/v1`).

```python
import asyncio
import klappstuhl

async def main():
    async with klappstuhl.Client("my-api-key") as client:
        result = await client.upload("cat.png")
        print(result.links[0])

asyncio.run(main())
```

---

## Installation

With **pip**:

```bash
pip install klappstuhl
```

Or with **Poetry**:

```bash
poetry add klappstuhl
```

Optional C-accelerated `aiohttp` extras (the `speed` extra):

```bash
pip install "klappstuhl[speed]"
# or
poetry add "klappstuhl[speed]"
```

Requires Python 3.9+.

## Authentication

Every endpoint except version discovery requires an API key. Generate one on your [account page](https://klappstuhl.me/account) and pass it to the client — it is sent verbatim in the `Authorization` header.

```python
client = klappstuhl.Client("my-api-key")
```

### Scopes

API keys are scoped. A key with **no** scopes is treated as unrestricted (legacy). Otherwise the following are enforced (calling without the scope raises `Forbidden`):

| Scope          | Grants                                                                            |
|----------------|-----------------------------------------------------------------------------------|
| `images:read`  | download, scan, metadata, manipulate, convert, and all render/transcode endpoints |
| `images:write` | upload, delete                                                                    |
| `images:guild` | guild-gallery upload / list / delete                                              |

The `klappstuhl.Scope` enum lists them. The `admin:*` scopes exist server-side but are reserved for privileged operators — they have **no typed methods** on this client. If you hold such a key, reach those routes with the [raw `request` escape hatch](#raw-requests).

## Client options

```python
klappstuhl.Client(
    token,                 # your API key (required)
    base_url="https://klappstuhl.me",  # override for a self-hosted instance
    session=None,          # reuse an existing aiohttp.ClientSession
    timeout=30.0,          # per-request timeout (seconds)
    max_retries=3,         # retries for network errors, 5xx, and 429
    user_agent=None,       # override the User-Agent
)
```

Use it as an async context manager so the session is always closed, or call `await client.close()` yourself.

After any call you can inspect:

- `client.rate_limit` → a `RateLimit(limit, remaining, reset, reset_after)` snapshot from the last response.
- `client.api_version` → the `X-API-Version` the server reported.

## File inputs

Anywhere a `file` is expected you may pass a **path**, **`bytes`**, an **open binary stream**, or an explicit `klappstuhl.File` (to control the filename/content-type):

```python
await client.upload("photo.png")                       # path
await client.upload(open("photo.png", "rb"))           # stream
await client.upload(b"...raw bytes...")                # bytes
await client.upload(klappstuhl.File(data, filename="x.png", content_type="image/png"))
await client.upload("a.png", "b.png", "c.png")         # many at once
```

---

## API reference

All methods are coroutines on `Client`. Binary endpoints return `bytes`; pass `share=True` to instead store the result server-side and get back a `ShareResult(id, url, content_type)` with a short `/m/<id>` link.

### Images

#### `upload(*files, expires_in=None) -> UploadResult` · *`images:write`*
Upload one or more images (`.apng`, `.png`, `.jpg`, `.jpeg`, `.gif`, `.avif`). `expires_in` sets a TTL in seconds (max 365 days) for an auto-deleting upload.

```python
res = await client.upload("a.png", "b.png", expires_in=86400)
res.links        # canonical URLs
res.raw_links    # direct-bytes URLs
res.successful   # number that uploaded cleanly
res.is_success   # bool
```

#### `delete_image(image_id) -> DeleteResult` · *`images:write`*
Delete one of your images. Accepts `abc123` or `abc123.png`.

#### `download(files=None) -> bytes` · *`images:read`*
Bundle images into a ZIP (returned as bytes). Pass `None`/`[]` to download **all** your images. Unknown IDs are skipped; if none resolve you get `NotFound`.

```python
zip_bytes = await client.download(["abc", "def"])
open("images.zip", "wb").write(zip_bytes)
```

### Media

#### `metadata(file=None, *, url=None) -> ImageInfo` · *`images:read`*
Inspect an image's `width`, `height`, `format`, `color`, and `file_size` without storing it. Supply exactly one of `file` or a public `url`.

#### `manipulate(op, file=None, *, url=None, amount=None, share=False)` · *`images:read`*
Apply a visual effect, returning a PNG. `op` is one of `blur`, `pixelate`, `deepfry`, `invert`, `grayscale` (or the `klappstuhl.Effect` enum). `amount` tunes the effect (blur sigma / pixelate block size / deepfry intensity). Convenience methods exist for each:

```python
png   = await client.blur("in.png", amount=12)
png   = await client.pixelate(url="https://…/x.jpg", amount=24)
png   = await client.deepfry("meme.png", amount=80)
png   = await client.invert("in.png")
share = await client.grayscale("in.png", share=True)   # -> ShareResult
```

#### `convert(to, file=None, *, url=None, quality=None, share=False)` · *`images:read`*
Transcode between raster formats. `to` is `png`, `jpeg`/`jpg`, `webp`, `gif`, `bmp`, `tiff` (or the `klappstuhl.ImageFormat` enum). `quality` (1–100, default 85) applies to JPEG.

```python
webp = await client.convert("webp", "photo.png")
```

### Render

#### `render_code(code, *, language=None, theme=None, share=False)` · *`images:read`*
Render a syntax-highlighted code screenshot to **SVG** (bytes). Source capped at 100 KB. `language` is a token/extension (`rust`, `py`, `js`); `theme` is a syntect theme (`base16-ocean.dark`, `InspiredGitHub`, `Solarized (dark)`).

#### `screenshot(url, *, width=None, height=None, dark_mode=False, mobile=False, full_page=False, share=False)` · *`images:read`*
Render a web page to a PNG via headless Chromium. Raises `ServerError` if the server has no Chromium binary. Private/reserved URLs are refused.

#### `markdown_pdf(markdown, *, share=False)` · *`images:read`*
Render Markdown to a PDF via headless Chromium. Raises `ServerError` if Chromium is absent.

#### `transcode(file, *, to, share=False)` · *`images:read`*
ffmpeg-backed conversion: `to="mp4"` (e.g. MOV→MP4) or `to="jpg"` (e.g. HEIC→JPG). Raises `ServerError` if ffmpeg is absent.

### Scan

#### `scan(file) -> ScanReport` · *`images:read`*
Scan a file for malware (ClamAV + VirusTotal). Any file type is accepted; nothing is persisted, and only the SHA-256 (never the bytes) is sent to VirusTotal.

```python
report = await client.scan("suspect.bin")
report.verdict        # "clean" | "infected" | "unknown"
report.is_infected    # bool
report.vt_positives   # engines that flagged it (or None)
```

### Discord guild galleries · *`images:guild`*

Shared per-guild image galleries (used e.g. for Discord poll banners).

```python
await client.upload_guild_images(guild_id, "banner.png", expires_in=3600)
gallery = await client.list_guild_images(guild_id)   # GuildImagesResult
await client.delete_guild_image(guild_id, "abc123")
```

### Discovery

#### `versions() -> ApiVersions`
The unauthenticated `GET /api` version-discovery document.

---

### Raw requests

<a name="raw-requests"></a>

Every endpoint meant for general use has a typed method above. For anything else — the `admin:*` routes (which only privileged keys may call), or an endpoint added server-side after this release — use the low-level escape hatch:

#### `request(method, path, *, params=None, json=None, files=None, fields=None, expect="json", versioned=True) -> Any`

It runs through the same auth, retry, and rate-limit machinery as every typed call, but returns the **unwrapped** response for you to parse yourself. `path` is below the version prefix (`/api/v1` is added unless `versioned=False`).

```python
# An admin-only route, with a key that holds the admin scope:
data = await client.request("GET", "/admin/updates")
updates = [klappstuhl.ImageUpdate.from_dict(u) for u in data]
```

---

## Error handling

Every failure raises a subclass of `klappstuhl.KlappstuhlError`:

```
KlappstuhlError
├── TransportError          # network failure after all retries
└── HTTPError               # any non-2xx response (.status, .message, .code)
    ├── BadRequest          # 400
    ├── Unauthorized        # 401
    ├── Forbidden           # 403 / missing scope
    ├── NotFound            # 404
    ├── EntryAlreadyExists  # 409
    ├── RateLimited         # 429 (.retry_after)
    └── ServerError         # 5xx / feature tool unavailable
```

```python
try:
    await client.upload("cat.png")
except klappstuhl.Forbidden as e:
    print("missing scope:", e.message)
except klappstuhl.RateLimited as e:
    print("slow down, retry after", e.retry_after)
except klappstuhl.HTTPError as e:
    print(e.status, e.code, e.message)
```

## Rate limits

The API allows **25 requests / 60 s** per IP. The client automatically waits out `429`s (up to `max_retries`) using the `x-ratelimit-reset-after` header; only a persistent rate limit surfaces as `RateLimited`. The latest budget is always on `client.rate_limit`.

## Development

The project uses a PEP 621 `pyproject.toml`, so you can manage the dev environment with either tool.

With **pip**:

```bash
pip install -e ".[dev]"
pytest
ruff check .
mypy klappstuhl
```

With **Poetry** (2.0+, which reads the standard `[project]` table directly):

```bash
poetry install --extras dev
poetry run pytest
poetry run ruff check .
poetry run mypy klappstuhl
```

## License

MIT — see [LICENSE](LICENSE).