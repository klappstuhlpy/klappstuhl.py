"""Media manipulation, conversion, and rendering examples.

Shows the two output styles: raw ``bytes`` (write them yourself) and, with
``share=True``, a short hosted ``/m/<id>`` link via a ``ShareResult``.

Run with:  KLAPPSTUHL_TOKEN=your-key python examples/media_and_render.py
"""

from __future__ import annotations

import asyncio
import os

import klappstuhl


async def main() -> None:
    token = os.environ["KLAPPSTUHL_TOKEN"]
    async with klappstuhl.Client(token) as client:
        # 1. Apply an effect from a public URL, saving the raw PNG bytes.
        png = await client.blur(url="https://http.cat/404.jpg", amount=10)
        with open("blurred.png", "wb") as fh:
            fh.write(png)
        print("wrote blurred.png")

        # 2. Convert a local image to WebP and get a shareable link back.
        share = await client.convert("webp", "photo.png", share=True)
        print("converted, shareable at:", share.url)

        # 3. Inspect an image without storing it.
        info = await client.metadata(url="https://http.cat/200.jpg")
        print(f"{info.width}x{info.height} {info.format} ({info.file_size} bytes)")

        # 4. Render a code screenshot (SVG bytes).
        svg = await client.render_code(
            "fn main() { println!(\"hi\"); }", language="rust", theme="base16-ocean.dark"
        )
        with open("code.svg", "wb") as fh:
            fh.write(svg)
        print("wrote code.svg")

        # 5. Screenshot a web page (needs Chromium on the server).
        try:
            shot = await client.screenshot("https://example.com", full_page=True, share=True)
            print("screenshot:", shot.url)
        except klappstuhl.ServerError as e:
            print("screenshot unavailable:", e.message)

        # 6. Extract an image's dominant colors (e.g. for embed accents).
        palette = await client.color_palette(url="https://http.cat/200.jpg", count=4)
        print("palette:", ", ".join(c.hex for c in palette.colors))

        # 7. Render a chart server-side — no plotting library needed. Here:
        #    your own 30-day upload activity, straight from `usage()`.
        usage = await client.usage()
        chart = await client.render_chart(
            klappstuhl.ChartKind.LINE,
            {"uploads": usage.series.uploads},
            labels=usage.series.days,
            title="Uploads, last 30 days",
            share=True,
        )
        print("chart:", chart.url)


if __name__ == "__main__":
    asyncio.run(main())
