<div align="center">

# klappstuhl.py

A fast, fully-typed **async** Python wrapper for the [klappstuhl.me](https://klappstuhl.me) API.

[![Python](https://img.shields.io/badge/python-3.9%2B-blue?logo=python&logoColor=white)](https://www.python.org/downloads/)
[![Typed](https://img.shields.io/badge/typed-py.typed-3776AB?logo=python&logoColor=white)](https://peps.python.org/pep-0561/)
[![API docs](https://img.shields.io/badge/API-Scalar%20reference-3178C6?logo=openapiinitiative&logoColor=white)](https://klappstuhl.me/api/docs)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

</div>

Image hosting, media manipulation, format conversion, color-palette extraction, rendering (code
screenshots, QR codes, SVG charts, web-page screenshots, Markdown→PDF), malware scanning, URL
shortening, paste hosting, link unfurling, and account/usage introspection, all behind one typed client.

- **Async**, built on `aiohttp` with connection reuse.
- **Reliable** — automatic retries with exponential backoff for network blips and `5xx`, and transparent `429`
  rate-limit handling using the server's reset headers.
- **Typed** — every response is a dataclass, every error a specific exception, ships with `py.typed`.
- **Complete** — covers every endpoint of the public API (`/api/v1`).

> New to it? The [examples](examples) directory has a quick start.

---

## Table of Contents

- [Installation](#installation)
- [Authentication](#authentication)
- [Client options](#client-options)
- [API reference](#api-reference)
- [Error handling](#error-handling)
- [Rate limits](#rate-limits)
- [License](#license)

---

## Installation

The package is distributed via **GitHub releases** (not on PyPI yet), so install it from the
repository and pin to a released tag:

```bash
pip install "klappstuhl.py @ git+https://github.com/klappstuhlpy/klappstuhl.py@v0.4.0"
# or
poetry add "git+https://github.com/klappstuhlpy/klappstuhl.py#v0.4.0"
```

Optional C-accelerated `aiohttp` extras (the `speed` extra):

```bash
pip install "klappstuhl.py[speed] @ git+https://github.com/klappstuhlpy/klappstuhl.py@v0.4.0"
```

Or, declaring it as a project dependency:

```toml
# PEP 621 — pyproject.toml [project.dependencies]
dependencies = ["klappstuhl.py @ git+https://github.com/klappstuhlpy/klappstuhl.py@v0.4.0"]

# Poetry — [tool.poetry.dependencies]
klappstuhl-py = { git = "https://github.com/klappstuhlpy/klappstuhl.py", tag = "v0.4.0" }
```

The distribution installs as **`klappstuhl.py`**, but you import it as **`klappstuhl`**
(same convention as discord.py). Requires Python 3.9+.

## Authentication

Every endpoint except version discovery requires an API key. Generate one on your
[account page](https://klappstuhl.me/account) and pass it to the client — it is sent in the
`Authorization` header (a bare key, or `Bearer <key>` — both are accepted).

```python
client = klappstuhl.Client("my-api-key")
```

### Scopes

API keys are **scoped**. A key with *no* scopes is treated as unrestricted (legacy). Otherwise each
endpoint requires a specific scope — calling without it raises `Forbidden`. All the scopes below are
**user-grantable** on your [account page](https://klappstuhl.me/account). `me()` and `usage()` work
with any valid key, no specific scope needed:

| Scope          | Grants                                                                                     |
|----------------|--------------------------------------------------------------------------------------------|
| `images:read`  | download, scan, metadata, manipulate, convert, palette, render (code / QR / chart), unfurl |
| `images:write` | upload, delete                                                                             |
| `links:read`   | list + read your short links                                                               |
| `links:write`  | create + delete short links                                                                |
| `pastes:read`  | list + read your pastes                                                                    |
| `pastes:write` | create + delete pastes                                                                     |

## Client options

```python
klappstuhl.Client(
    token,  # your API key (required)
    base_url="https://klappstuhl.me",  # override for a self-hosted instance
    session=None,  # reuse an existing aiohttp.ClientSession
    timeout=30.0,  # per-request timeout (seconds)
    max_retries=3,  # retries for network errors, 5xx, and 429
    user_agent=None,  # override the User-Agent
)
```

Use it as an async context manager so the session is always closed, or call `await client.close()` yourself.

After any call you can inspect:

- `client.rate_limit` → a `RateLimit(limit, remaining, reset, reset_after)` snapshot from the last response.
- `client.api_version` → the `X-API-Version` the server reported.

---

## API reference

All methods are coroutines on `Client`; each returns a typed model from `klappstuhl.models` (or raw
`bytes` for binary results). Binary render endpoints accept `share=True` to instead store the result
server-side and return a `ShareResult(id, url, content_type)` with a short `/m/<id>` link. Full
signatures live in the docstrings and the [interactive API docs](https://klappstuhl.me/api/docs).

| Area                | Methods                                                                                                         |
|---------------------|-----------------------------------------------------------------------------------------------------------------|
| **Discovery**       | `versions()` — the unauthenticated `GET /api` version document                                                  |
| **Images**          | `upload()`, `delete_image()`, `download()`                                                                      |
| **Account**         | `me()` — identity + key scopes, `usage()` — totals + a chart-ready 30-day series                                |
| **Short links**     | `shorten()`, `list_links()`, `get_link()`, `update_link()`, `delete_link()`                                     |
| **Pastes**          | `create_paste()`, `list_pastes()`, `get_paste()`, `delete_paste()`                                              |
| **Media**           | `metadata()`, `manipulate()` (`blur`/`pixelate`/`deepfry`/`invert`/`grayscale`), `convert()`, `color_palette()` |
| **Render**          | `render_code()`, `render_qr()`, `render_chart()`, `screenshot()`, `markdown_pdf()`, `transcode()`               |
| **Web**             | `unfurl()` — Open Graph / link-preview metadata                                                                 |
| **Scan**            | `scan()` — ClamAV + VirusTotal                                                                                  |
| **Escape hatch**    | `request()` — hand-craft any request (e.g. admin-only routes)                                                   |

List endpoints (`list_links`, `list_pastes`) take Discord-style cursor pagination: `limit`,
`before`, `after`.

---

## Error handling

Every failure raises a subclass of `klappstuhl.KlappstuhlError`:

```
KlappstuhlError
├── TransportError          # network failure after all retries
└── HTTPError               # any non-2xx response (.status, .message, .code)
    ├── BadRequest          # 400 (incl. validation errors)
    ├── Unauthorized        # 401
    ├── Forbidden           # 403 / missing scope
    ├── NotFound            # 404
    ├── EntryAlreadyExists  # 409
    ├── RateLimited         # 429 (.retry_after)
    └── ServerError         # 5xx / feature tool unavailable
```

Error bodies follow Discord's shape (`{ message, code, errors }`); `HTTPError.message` and `.code`
carry those through, and validation failures surface as `BadRequest`.

## Rate limits

The API allows **25 requests / 60 s** per IP. The client automatically waits out `429`s (up to
`max_retries`) using the `x-ratelimit-reset-after` header; only a persistent rate limit surfaces as
`RateLimited`. The latest budget is always on `client.rate_limit`.

## License

MIT — see [LICENSE](LICENSE).