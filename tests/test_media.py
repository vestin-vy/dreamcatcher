"""DB-backed image tests (images in Postgres/SQLite). Pure logic — no TestClient/sockets."""
from io import BytesIO

import pytest

try:
    from PIL import Image
    from fastapi import HTTPException

    from app.images import save_image
    from app.models import ProductImage
    from app.routes import media
    _IMPORT_ERROR = None
except Exception as exc:  # pragma: no cover
    _IMPORT_ERROR = exc


def _skip_if_no_app():
    if _IMPORT_ERROR is not None:
        pytest.skip(f"app not importable: {_IMPORT_ERROR}")


def _png_bytes() -> bytes:
    buf = BytesIO()
    Image.new("RGB", (40, 50), (10, 20, 30)).save(buf, "PNG")
    return buf.getvalue()


def test_save_image_returns_webp_bytes():
    _skip_if_no_app()
    meta = save_image(_png_bytes())
    assert meta["content_type"] == "image/webp"
    assert meta["data"][:4] == b"RIFF" and meta["data"][8:12] == b"WEBP"
    assert meta["thumb_data"][:4] == b"RIFF"
    assert meta["width"] > 0 and meta["height"] > 0
    assert meta["filename"].startswith("uploads/") and meta["thumb"].startswith("uploads/")


def test_media_serves_db_bytes_and_404s():
    _skip_if_no_app()
    meta = save_image(_png_bytes())
    img = ProductImage(
        product_id=1, filename=meta["filename"], thumb=meta["thumb"],
        width=meta["width"], height=meta["height"],
        data=meta["data"], thumb_data=meta["thumb_data"], content_type=meta["content_type"],
    )
    full = media._serve(img, thumb=False)
    thumb = media._serve(img, thumb=True)
    assert full.media_type == "image/webp" and full.body == meta["data"]
    assert thumb.body == meta["thumb_data"]
    assert "immutable" in full.headers.get("cache-control", "")

    # Missing image -> 404.
    with pytest.raises(HTTPException) as ei:
        media._serve(None, thumb=False)
    assert ei.value.status_code == 404

    # Legacy row without DB bytes but with an on-disk file -> served from disk.
    legacy = ProductImage(
        product_id=1, filename=meta["filename"], thumb=meta["thumb"],
        width=meta["width"], height=meta["height"], data=None, thumb_data=None,
    )
    assert media._serve(legacy, thumb=False) is not None
