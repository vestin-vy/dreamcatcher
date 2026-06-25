"""Serve product images straight from the database (DB-backed media).

Image bytes live in `ProductImage.data` / `.thumb_data` so they survive redeploys
on hosts with an ephemeral filesystem (e.g. Render's free tier), where the old
`static/uploads/` files would be wiped. If a row predates the DB-bytes migration and
has no bytes yet, we fall back to the on-disk file so local dev keeps working.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, Response
from sqlmodel import Session

from app.config import settings
from app.db import get_session
from app.models import ProductImage

router = APIRouter(prefix="/media")

# Each image id is immutable (re-uploads get a fresh id), so caching aggressively
# is safe and keeps the catalog snappy.
_CACHE_CONTROL = "public, max-age=31536000, immutable"


def _serve(img: ProductImage | None, *, thumb: bool) -> Response:
    if img is None:
        raise HTTPException(status_code=404)
    data = img.thumb_data if thumb else img.data
    media_type = img.content_type or "image/webp"
    if data:
        return Response(content=data, media_type=media_type,
                        headers={"Cache-Control": _CACHE_CONTROL})
    # Fallback for legacy rows without DB bytes: serve the on-disk file if present.
    rel = img.thumb if thumb else img.filename
    path: Path = settings.STATIC_DIR / rel
    if rel and path.is_file():
        return FileResponse(path, media_type=media_type,
                            headers={"Cache-Control": _CACHE_CONTROL})
    raise HTTPException(status_code=404)


@router.get("/{image_id}", name="media_full")
def media_full(image_id: int, session: Session = Depends(get_session)) -> Response:
    return _serve(session.get(ProductImage, image_id), thumb=False)


@router.get("/{image_id}/thumb", name="media_thumb")
def media_thumb(image_id: int, session: Session = Depends(get_session)) -> Response:
    return _serve(session.get(ProductImage, image_id), thumb=True)
