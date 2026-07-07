# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.1] - 2026-07-07

### Fixed

- `resolve_file` is now asynchronous to handle cases where the `.read()` function 
  of a file-like object is a coroutine. 
  This ensures compatibility with asynchronous file-like objects like e.g. discord.File.
- `_image_source` is also now asynchronous to follow the change of `resolve_file`.

## [0.3.0] - 2026-07-07

### Added
- Short links: `shorten`, `list_links`, `get_link`, `delete_link` (scopes
  `links:read` / `links:write`).
- Pastes: `create_paste`, `list_pastes`, `get_paste`, `delete_paste` (scopes
  `pastes:read` / `pastes:write`).
- `render_qr` — render text/URLs to a QR code (SVG or PNG).
- `unfurl` — fetch a URL's Open Graph / link-preview metadata.
- New response models `ShortLink`, `Paste`, `Unfurl`; new `Scope` members
  (`links:*`, `pastes:*`) and `ApiErrorCode` values (`VALIDATION`,
  `PAYLOAD_TOO_LARGE`, `UNSUPPORTED_MEDIA`).
- Cursor pagination (`limit` / `before` / `after`) on `list_links` and
  `list_pastes`.

## [0.2.0] - 2026-07-07

### Added
- `Client.request(...)` — a low-level escape hatch for hand-crafting requests
  to endpoints without a typed method (e.g. the admin-only `/admin/*` routes) or
  to anything added server-side after this release. Runs through the same auth,
  retry, and rate-limit machinery and returns the unwrapped body.

### Removed
- `Client.admin_updates()`. The `admin:*` routes are reserved for privileged
  operators and are no longer on the public client surface. Call them through
  `Client.request(...)` instead; `ImageUpdate` / `UpdateState` remain exported so
  you can still parse the response.

## [0.1.0] - 2026-07-06

Initial release.

### Added
- Async `Client` covering the full `/api/v1` surface:
  - Images: `upload`, `delete_image`, `download`.
  - Guild galleries: `upload_guild_images`, `list_guild_images`, `delete_guild_image`.
  - Media: `metadata`, `manipulate` (+ `blur`/`pixelate`/`deepfry`/`invert`/`grayscale`), `convert`.
  - Render: `render_code`, `screenshot`, `markdown_pdf`, `transcode`.
  - Scan: `scan`.
  - Admin: `admin_updates`.
  - Discovery: `versions`.
- Typed response models and a full exception hierarchy.
- Automatic retries for network errors / `5xx` and transparent `429` handling.
- Flexible file inputs (path, bytes, stream, or `File`) and `share=True` support.
- `py.typed` marker for downstream type-checking.

[0.3.1]: https://github.com/klappstuhlpy/klappstuhl.py/releases/tag/v0.3.1
[0.3.0]: https://github.com/klappstuhlpy/klappstuhl.py/releases/tag/v0.3.0
[0.2.0]: https://github.com/klappstuhlpy/klappstuhl.py/releases/tag/v0.2.0
[0.1.0]: https://github.com/klappstuhlpy/klappstuhl.py/releases/tag/v0.1.0
