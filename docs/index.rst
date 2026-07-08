klappstuhl.py
=============

A fast, fully-typed **async** Python wrapper for the `klappstuhl.me <https://klappstuhl.me>`_ API.

Image hosting, media manipulation, format conversion, color-palette extraction, rendering
(code screenshots, QR codes, SVG charts, web-page screenshots, Markdown→PDF), malware scanning,
URL shortening, paste hosting, link unfurling, and account/usage introspection — all behind one
typed client.

- **Async**, built on :mod:`aiohttp` with connection reuse.
- **Reliable** — automatic retries with exponential backoff for network blips and ``5xx``, and
  transparent ``429`` rate-limit handling using the server's reset headers.
- **Typed** — every response is a dataclass, every error a specific exception; ships with ``py.typed``.
- **Complete** — covers every endpoint of the public API (``/api/v1``).

.. code-block:: python

   import asyncio
   import klappstuhl

   async def main():
       async with klappstuhl.Client("my-api-key") as client:
           result = await client.upload("cat.png")
           print("uploaded:", result.links[0])

           png = await client.blur("cat.png", amount=12)
           open("blurred.png", "wb").write(png)

   asyncio.run(main())

.. toctree::
   :maxdepth: 2
   :caption: Getting started

   intro

.. toctree::
   :maxdepth: 2
   :caption: API reference

   api/client
   api/models
   api/enums
   api/errors
   api/file

Indices
-------

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
