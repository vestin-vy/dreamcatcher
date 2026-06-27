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
from app.models import Category, ProductImage

router = APIRouter(prefix="/media")

# Each image id is immutable (re-uploads get a fresh id), so caching aggressively
# is safe and keeps the catalog snappy.
_CACHE_CONTROL = "public, max-age=31536000, immutable"


def _serve_bytes(data: bytes | None, content_type: str | None, fallback_rel: str | None) -> Response:
    media_type = content_type or "image/webp"
    if data:
        return Response(content=data, media_type=media_type,
                        headers={"Cache-Control": _CACHE_CONTROL})
    # Fallback for legacy rows without DB bytes: serve the on-disk file if present.
    if fallback_rel:
        path: Path = settings.STATIC_DIR / fallback_rel
        if path.is_file():
            return FileResponse(path, media_type=media_type,
                                headers={"Cache-Control": _CACHE_CONTROL})
    raise HTTPException(status_code=404)


def _serve(img: ProductImage | None, *, thumb: bool) -> Response:
    """Serve a ProductImage (DB bytes, falling back to its on-disk file)."""
    if img is None:
        raise HTTPException(status_code=404)
    data = img.thumb_data if thumb else img.data
    rel = img.thumb if thumb else img.filename
    return _serve_bytes(data, img.content_type, rel)


# --- Category images (declared before /{image_id} so "category" never reaches it) ---
@router.get("/category/{category_id}", name="media_category")
def media_category(category_id: int, session: Session = Depends(get_session)) -> Response:
    cat = session.get(Category, category_id)
    if cat is None:
        raise HTTPException(status_code=404)
    return _serve_bytes(cat.image_data, cat.image_content_type, cat.image)


@router.get("/category/{category_id}/thumb", name="media_category_thumb")
def media_category_thumb(category_id: int, session: Session = Depends(get_session)) -> Response:
    cat = session.get(Category, category_id)
    if cat is None:
        raise HTTPException(status_code=404)
    return _serve_bytes(cat.thumb_data, cat.image_content_type, cat.thumb)


# --- Product images ---
@router.get("/{image_id}", name="media_full")
def media_full(image_id: int, session: Session = Depends(get_session)) -> Response:
    return _serve(session.get(ProductImage, image_id), thumb=False)


@router.get("/{image_id}/thumb", name="media_thumb")
def media_thumb(image_id: int, session: Session = Depends(get_session)) -> Response:
    return _serve(session.get(ProductImage, image_id), thumb=True)
