"""Resize uploaded product photos to three widths with Pillow. Reject bad types and huge files."""

import uuid
from pathlib import Path
from typing import List

from fastapi import UploadFile
from PIL import Image

from app.core.config import get_settings
from app.core.errors import AppError

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_BYTES = 5 * 1024 * 1024
SIZES = [("full", 1600), ("md", 800), ("thumb", 200)]


def save_product_image(product_id: int, upload: UploadFile) -> str:
    """
    Save the original plus resized copies. Return the public URL of the medium size.

    Callers store that URL on product_images.
    """
    content_type = upload.content_type or ""
    if content_type not in ALLOWED_TYPES:
        raise AppError("invalid_file", "Use a JPEG, PNG or WebP image.", 400)

    raw = upload.file.read()
    size = len(raw)
    if size > MAX_BYTES:
        raise AppError("file_too_large", "Image must be 5 MB or smaller.", 400)
    if size == 0:
        raise AppError("invalid_file", "The upload was empty.", 400)

    settings = get_settings()
    folder = Path(settings.upload_dir) / "products" / str(product_id)
    folder.mkdir(parents=True, exist_ok=True)
    stem = uuid.uuid4().hex

    from io import BytesIO

    image = Image.open(BytesIO(raw))
    if image.mode != "RGB":
        image = image.convert("RGB")

    medium_url = ""
    for label, width in SIZES:
        copy = image.copy()
        # Keep aspect ratio. Do not enlarge a small photo.
        if copy.width > width:
            new_height = (copy.height * width) // copy.width
            if new_height < 1:
                new_height = 1
            copy = copy.resize((width, new_height))
        path = folder / (stem + "-" + label + ".jpg")
        copy.save(path, format="JPEG", quality=85, optimize=True)
        if label == "md":
            medium_url = "/uploads/products/" + str(product_id) + "/" + path.name

    if medium_url == "":
        raise AppError("invalid_file", "Could not save the image.", 500)
    return medium_url


def list_saved_paths(product_id: int) -> List[str]:
    settings = get_settings()
    folder = Path(settings.upload_dir) / "products" / str(product_id)
    if folder.exists() is False:
        return []
    names: List[str] = []
    for path in folder.iterdir():
        names.append(str(path))
    return names
