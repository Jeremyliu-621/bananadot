"""Zip a folder into bytes for HTTP streaming back to the client."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path


def zip_folder(folder: Path) -> bytes:
    """Return a zip archive of `folder` as bytes, preserving relative paths."""
    if not folder.is_dir():
        raise FileNotFoundError(f"Not a folder: {folder}")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in folder.rglob("*"):
            if path.is_file():
                zf.write(path, arcname=path.relative_to(folder))
    return buf.getvalue()
