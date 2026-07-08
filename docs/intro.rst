Getting started
===============

Installation
------------

The package is distributed via **GitHub releases** (not on PyPI yet), so install it from the
repository and pin to a released tag:

.. code-block:: bash

   pip install "klappstuhl.py @ git+https://github.com/klappstuhlpy/klappstuhl.py@v0.4.0"
   # or
   poetry add "git+https://github.com/klappstuhlpy/klappstuhl.py#v0.4.0"

Optional C-accelerated ``aiohttp`` extras (the ``speed`` extra):

.. code-block:: bash

   pip install "klappstuhl.py[speed] @ git+https://github.com/klappstuhlpy/klappstuhl.py@v0.4.0"

The distribution installs as **klappstuhl.py**, but you import it as **klappstuhl**
(the same convention as discord.py). Requires Python 3.9+.

Authentication
--------------

Every endpoint except version discovery requires an API key. Generate one on your
`account page <https://klappstuhl.me/account>`_ and pass it to the client — it is sent in the
``Authorization`` header (a bare key, or ``Bearer <key>`` — both are accepted).

.. code-block:: python

   client = klappstuhl.Client("my-api-key")

Scopes
~~~~~~

API keys are **scoped**. A key with *no* scopes is treated as unrestricted (legacy). Otherwise each
endpoint requires a specific scope — calling without it raises
:class:`~klappstuhl.errors.Forbidden`. See :class:`~klappstuhl.enums.Scope` for the full list.
``me()`` and ``usage()`` work with any valid key.

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Scope
     - Grants
   * - ``images:read``
     - download, scan, metadata, manipulate, convert, palette, render (code / QR / chart), unfurl
   * - ``images:write``
     - upload, delete
   * - ``links:read``
     - list + read your short links
   * - ``links:write``
     - create + delete short links
   * - ``pastes:read``
     - list + read your pastes
   * - ``pastes:write``
     - create + delete pastes

Client options
--------------

.. code-block:: python

   klappstuhl.Client(
       token,                              # your API key (required)
       base_url="https://klappstuhl.me",   # override for a self-hosted instance
       session=None,                       # reuse an existing aiohttp.ClientSession
       timeout=30.0,                       # per-request timeout (seconds)
       max_retries=3,                      # retries for network errors, 5xx, and 429
       user_agent=None,                    # override the User-Agent
   )

Use it as an async context manager so the session is always closed, or call
``await client.close()`` yourself. After any call you can inspect:

- ``client.rate_limit`` → a :class:`~klappstuhl.models.RateLimit` snapshot from the last response.
- ``client.api_version`` → the ``X-API-Version`` the server reported.

Error handling
--------------

Every failure raises a subclass of :class:`~klappstuhl.errors.KlappstuhlError`::

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

Rate limits
-----------

The API allows **25 requests / 60 s** per IP. The client automatically waits out ``429`` s (up to
``max_retries``) using the ``x-ratelimit-reset-after`` header; only a persistent rate limit surfaces
as :class:`~klappstuhl.errors.RateLimited`. The latest budget is always on ``client.rate_limit``.
