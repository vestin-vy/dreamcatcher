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
    if len(data) > settings.MAX_UPLOAD_BYTES:
        raise InvalidImageError("File too large")
    try:
        img = Image.open(BytesIO(data))
        img.verify()  # detect truncated/corrupt files
    except (UnidentifiedImageError, OSError) as exc:
        raise InvalidImageError("Not a valid image") from exc
    # verify() leaves the image unusable; reopen for processing.
    img = Image.open(BytesIO(data))
    if img.format not in ALLOWED_FORMATS:
        raise InvalidImageError(f"Unsupported format: {img.format}")
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
    """Process an uploaded image; return dict with filename/thumb/width/height.

    Paths are relative to the `static/` directory (e.g. 'uploads/<uuid>.webp').
    Raises InvalidImageError on bad input.
    """
    img = _open_and_validate(data)
    img = _flatten(img)

    name = uuid.uuid4().hex
    settings.ensure_dirs()

    # Full image (resized to max side).
    full = img.copy()
    full.thumbnail((settings.IMAGE_MAX_SIDE, settings.IMAGE_MAX_SIDE), Image.LANCZOS)
    full_rel = f"uploads/{name}.webp"
    full.save(settings.STATIC_DIR / full_rel, "WEBP", quality=85, method=6)
    width, height = full.size

    # Thumbnail.
    thumb = img.copy()
    thumb.thumbnail((settings.THUMB_MAX_SIDE, settings.THUMB_MAX_SIDE), Image.LANCZOS)
    thumb_rel = f"uploads/thumbs/{name}.webp"
    thumb.save(settings.STATIC_DIR / thumb_rel, "WEBP", quality=80, method=6)

    return {"filename": full_rel, "thumb": thumb_rel, "width": width, "height": height}


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
