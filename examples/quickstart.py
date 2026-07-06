"""Minimal end-to-end example: upload an image and read the result.

Run with:  KLAPPSTUHL_TOKEN=your-key python examples/quickstart.py path/to/image.png
"""

from __future__ import annotations

import asyncio
import os
import sys

import klappstuhl


async def main(path: str) -> None:
    token = os.environ["KLAPPSTUHL_TOKEN"]
    async with klappstuhl.Client(token) as client:
        result = await client.upload(path)
        if result.is_success:
            print("Uploaded:", result.links[0])
            print("Raw:", result.raw_links[0])
        else:
            print(f"Upload had problems: {result.errors} errors, {result.skipped} skipped")

        # Inspect the current rate-limit budget from the last response.
        if client.rate_limit:
            print(f"Remaining requests: {client.rate_limit.remaining}/{client.rate_limit.limit}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("usage: python examples/quickstart.py <image-path>")
    asyncio.run(main(sys.argv[1]))
