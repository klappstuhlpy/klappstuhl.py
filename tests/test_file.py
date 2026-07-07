import io

import pytest

from klappstuhl.file import File, resolve_file


def test_file_from_bytes_guesses_default_content_type():
    f = File(b"hello")
    assert f.content == b"hello"
    assert f.filename == "upload"
    assert f.content_type == "application/octet-stream"


def test_file_content_type_from_filename():
    f = File(b"\x89PNG", filename="cat.png")
    assert f.content_type == "image/png"


def test_file_from_stream_picks_up_name(tmp_path):
    p = tmp_path / "pic.jpg"
    p.write_bytes(b"jpegdata")
    with open(p, "rb") as fp:
        f = File(fp)
    assert f.filename == "pic.jpg"
    assert f.content == b"jpegdata"
    assert f.content_type == "image/jpeg"


def test_file_rejects_text_mode(tmp_path):
    p = tmp_path / "a.txt"
    p.write_text("hi")
    with open(p) as fp:  # text mode
        with pytest.raises(TypeError):
            File(fp)


def test_file_from_path(tmp_path):
    p = tmp_path / "x.gif"
    p.write_bytes(b"GIF89a")
    f = File.from_path(p)
    assert f.filename == "x.gif"
    assert f.content_type == "image/gif"


async def test_resolve_file_variants(tmp_path):
    p = tmp_path / "y.png"
    p.write_bytes(b"data")

    assert (await resolve_file(b"raw")).content == b"raw"
    assert (await resolve_file(str(p))).filename == "y.png"
    assert (await resolve_file(p)).filename == "y.png"
    assert (await resolve_file(io.BytesIO(b"stream"))).content == b"stream"

    existing = File(b"z")
    assert await resolve_file(existing) is existing


async def test_resolve_file_rejects_unknown():
    with pytest.raises(TypeError):
        await resolve_file(12345)  # type: ignore[arg-type]
