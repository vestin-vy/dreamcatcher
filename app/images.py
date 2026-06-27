"""Image processing with Pillow (SPEC §8): validate, resize, thumbnail, WebP."""
from __future__ import annotations

import uuid
from io import BytesIO

from PIL import Image, UnidentifiedImageError

from app.config import settings

ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP", "GIF", "BMP", "TIFF"}


class InvalidImageError(ValueError):
    """Raised when an upload is not a valid/allowed image."""


def _open_and_validate(data: bytes) -> Image.Image:
    # Reasons are lowercase phrases so callers can compose them into a sentence.
    if len(data) > settings.MAX_UPLOAD_BYTES:
        got = len(data) / (1024 * 1024)
        limit = settings.MAX_UPLOAD_BYTES / (1024 * 1024)
        raise InvalidImageError(f"file is {got:.1f} MB, over the {limit:.0f} MB limit")
    try:
        img = Image.open(BytesIO(data))
        img.verify()  # detect truncated/corrupt files
    except (UnidentifiedImageError, OSError) as exc:
        raise InvalidImageError("not a readable image (corrupt, or not an image file)") from exc
    # verify() leaves the image unusable; reopen for processing.
    img = Image.open(BytesIO(data))
    if img.format not in ALLOWED_FORMATS:
        allowed = ", ".join(sorted(ALLOWED_FORMATS))
        raise InvalidImageError(
            f"unsupported format {img.format or 'unknown'} — allowed: {allowed}"
        )
    return img


def _flatten(img: Image.Image) -> Image.Image:
    """Convert to RGB on a white background (drop alpha) for WebP saving."""
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img, mask=img.split()[-1])
        return bg
    return img.convert("RGB")


def save_image(data: bytes) -> dict:
    """Process an uploaded image; return its WebP bytes plus metadata.

    Returns a dict with:
      filename/thumb  — paths relative to `static/` (legacy on-disk copy / fallback)
      width/height    — full image dimensions
      data/thumb_data — the WebP bytes (stored in the DB and served via /media)
      content_type    — always 'image/webp'

    The bytes are the source of truth (DB-backed, survive ephemeral disks); the
    on-disk files are written too as a local-dev convenience. Raises
    InvalidImageError on bad input.
    """
    img = _open_and_validate(data)
    img = _flatten(img)

    name = uuid.uuid4().hex
    settings.ensure_dirs()

    # Full image (resized to max side). Encode once to bytes, then mirror to disk.
    full = img.copy()
    full.thumbnail((settings.IMAGE_MAX_SIDE, settings.IMAGE_MAX_SIDE), Image.LANCZOS)
    full_buf = BytesIO()
    full.save(full_buf, "WEBP", quality=85, method=6)
    full_bytes = full_buf.getvalue()
    width, height = full.size
    full_rel = f"uploads/{name}.webp"
    (settings.STATIC_DIR / full_rel).write_bytes(full_bytes)

    # Thumbnail.
    thumb = img.copy()
    thumb.thumbnail((settings.THUMB_MAX_SIDE, settings.THUMB_MAX_SIDE), Image.LANCZOS)
    thumb_buf = BytesIO()
    thumb.save(thumb_buf, "WEBP", quality=80, method=6)
    thumb_bytes = thumb_buf.getvalue()
    thumb_rel = f"uploads/thumbs/{name}.webp"
    (settings.STATIC_DIR / thumb_rel).write_bytes(thumb_bytes)

    return {
        "filename": full_rel, "thumb": thumb_rel, "width": width, "height": height,
        "data": full_bytes, "thumb_data": thumb_bytes, "content_type": "image/webp",
    }


def delete_image_files(filename: str, thumb: str) -> None:
    """Remove image files from disk (best-effort; ignores missing files)."""
    for rel in (filename, thumb):
        if not rel:
            continue
        path = settings.STATIC_DIR / rel
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
