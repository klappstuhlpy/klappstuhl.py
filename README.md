# klappstuhl.py

A fast, fully-typed **async** Python wrapper for the [klappstuhl.me](https://klappstuhl.me) API — image hosting, media manipulation, format conversion, rendering (code screenshots, web-page screenshots, Markdown→PDF), malware scanning, and Discord-guild galleries.

- **Async**, built on `aiohttp` with connection reuse.
- **Reliable** — automatic retries with exponential backoff for network blips and `5xx`, and transparent `429` rate-limit handling using the server's reset headers.
- **Typed** — every response is a dataclass, every error a specific exception, ships with `py.typed`.
- **Complete** — covers every endpoint of the public API (`/api/v1`).

> If you're curious on how to use this package, look at the [examples](examples) for a quick start.

---

## Installation

The package is distributed via **GitHub releases** (it is not on PyPI yet), so
install it from the repository and pin to a released tag:

```bash
pip install "klappstuhl @ git+https://github.com/klappstuhlpy/klappstuhl.py@v0.2.0"
# or
poetry add "git+https://github.com/klappstuhlpy/klappstuhl.py#v0.2.0"
```

Optional C-accelerated `aiohttp` extras (the `speed` extra):

```bash
pip install "klappstuhl[speed] @ git+https://github.com/klappstuhlpy/klappstuhl.py@v0.2.0"
```

Or, declaring it as a project dependency:

```toml
# PEP 621 — pyproject.toml [project.dependencies]
dependencies = ["klappstuhl @ git+https://github.com/klappstuhlpy/klappstuhl.py@v0.2.0"]

# Poetry — [tool.poetry.dependencies]
klappstuhl = { git = "https://github.com/klappstuhlpy/klappstuhl.py", tag = "v0.2.0" }
```

Requires Python 3.9+.

## Authentication

Every endpoint except version discovery requires an API key. Generate one on your [account page](https://klappstuhl.me/account) and pass it to the client — it is sent verbatim in the `Authorization` header.

```python
client = klappstuhl.Client("my-api-key")
```

### Scopes

API keys are scoped. A key with **no** scopes is treated as unrestricted (legacy). Otherwise each endpoint requires a specific scope — calling without it raises `Forbidden`.

**User-grantable** — generate a key with these on your [account page](https://klappstuhl.me/account):

| Scope          | Grants                                                                            |
|----------------|-----------------------------------------------------------------------------------|
| `images:read`  | download, scan, metadata, manipulate, convert, and all render/transcode endpoints |
| `images:write` | upload, delete                                                                    |

**Privileged** — reserved for the operator's own services and **not grantable to a personal key** (the account page hides them, and the server drops them from a normal key's generation request):

| Scope                        | Grants                                                                                                                                     |
|------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------|
| `images:guild`               | guild-gallery upload / list / delete — these keys are **minted per Discord guild by the service** (e.g. Percy's bot), not created by users |
| `admin:read` / `admin:write` | operator / homelab admin routes — **no typed methods** on this client                                                                      |

The `klappstuhl.Scope` enum lists all five. The guild-gallery methods below and the `admin:*` routes only work with a key that already holds the matching privileged scope — a key you generate yourself will not have them. For admin routes, use the [raw `request` escape hatch](#raw-requests).

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

---

## API reference

All methods are coroutines on `Client`. Binary endpoints return `bytes`; pass `share=True` to instead store the result server-side and get back a `ShareResult(id, url, content_type)` with a short `/m/<id>` link.

For further details, please visit the [official API docs](https://klappstuhl.me/docs/api).

### Discovery

#### `versions() -> ApiVersions`
The unauthenticated `GET /api` version-discovery document.

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

## Rate limits

The API allows **25 requests / 60 s** per IP. The client automatically waits out `429`s (up to `max_retries`) using the `x-ratelimit-reset-after` header; only a persistent rate limit surfaces as `RateLimited`. The latest budget is always on `client.rate_limit`.

## License

MIT — see [LICENSE](LICENSE).