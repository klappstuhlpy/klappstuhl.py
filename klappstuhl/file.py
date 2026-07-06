"""Helpers for turning user-supplied file inputs into multipart fields."""

from __future__ import annotations

import io
import mimetypes
import os
from pathlib import Path
from typing import IO, Union

__all__ = ("File", "FileInput")

#: Anything the client accepts wherever an uploaded file is expected: a
#: filesystem path, raw ``bytes``, an open binary file object, or an explicit
#: :class:`File`.
FileInput = Union[str, "os.PathLike[str]", bytes, bytearray, IO[bytes], "File"]


class File:
    """A single file to upload.

    You rarely need to construct this directly — every ``file=`` parameter also
    accepts a path, ``bytes``, or an open binary stream and wraps it for you.
    Reach for :class:`File` when you need to control the ``filename`` (which the
    server may store and echo back) or the ``content_type``.

    Parameters
    ----------
    content:
        The file payload: ``bytes``, a :class:`bytearray`, or a binary
        file-like object (read fully on construction).
    filename:
        The name sent in the multipart part. Defaults to ``"upload"`` (or the
        stream's name when available).
    content_type:
        The MIME type. Guessed from ``filename`` when omitted, falling back to
        ``application/octet-stream``.
    """

    __slots__ = ("content", "content_type", "filename")

    def __init__(
        self,
        content: bytes | bytearray | IO[bytes],
        *,
        filename: str | None = None,
        content_type: str | None = None,
    ) -> None:
        if isinstance(content, (bytes, bytearray)):
            data = bytes(content)
        elif hasattr(content, "read"):
            data = content.read()
            if isinstance(data, str):  # opened in text mode
                raise TypeError("file object must be opened in binary mode ('rb')")
            if filename is None:
                name = getattr(content, "name", None)
                if isinstance(name, str):
                    filename = os.path.basename(name)
        else:  # pragma: no cover - defensive
            raise TypeError(f"unsupported file content: {type(content)!r}")

        self.content: bytes = data
        self.filename: str = filename or "upload"
        self.content_type: str = (
            content_type or mimetypes.guess_type(self.filename)[0] or "application/octet-stream"
        )

    @classmethod
    def from_path(
        cls,
        path: str | os.PathLike[str],
        *,
        filename: str | None = None,
        content_type: str | None = None,
    ) -> File:
        """Build a :class:`File` by reading ``path`` from disk."""

        p = Path(path)
        return cls(
            p.read_bytes(),
            filename=filename or p.name,
            content_type=content_type,
        )

    def __repr__(self) -> str:
        return (
            f"<File filename={self.filename!r} "
            f"content_type={self.content_type!r} size={len(self.content)}>"
        )


def resolve_file(value: FileInput) -> File:
    """Coerce any :data:`FileInput` into a concrete :class:`File`."""

    if isinstance(value, File):
        return value
    if isinstance(value, (bytes, bytearray)):
        return File(value)
    if isinstance(value, (str, os.PathLike)):
        return File.from_path(value)
    if isinstance(value, io.IOBase) or hasattr(value, "read"):
        return File(value)
    raise TypeError(f"cannot use {type(value)!r} as a file input")
