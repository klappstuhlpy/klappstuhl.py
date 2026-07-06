# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project adheres
to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

[0.1.0]: https://github.com/klappstuhlpy/klappstuhl.py/releases/tag/v0.1.0
