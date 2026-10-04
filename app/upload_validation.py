import io
import warnings

from fastapi import HTTPException
from PIL import Image, UnidentifiedImageError

from app.core.config import settings


async def read_image_upload(upload):
    data = await read_upload(upload)

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as image:
                if image.format not in {"JPEG", "PNG", "WEBP"}:
                    raise ValueError("Unsupported image format")
                if image.width * image.height > 20000000:
                    raise ValueError("Image exceeds 20 megapixels")
                extension = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}[image.format]
                image.verify()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombWarning, Image.DecompressionBombError):
        raise HTTPException(status_code=400, detail="Upload a valid JPEG, PNG or WebP image of at most 20 megapixels. PDF is not supported.")
    return data, extension


async def read_upload(upload):
    data = await upload.read(settings.MAX_UPLOAD_SIZE + 1)
    if len(data) > settings.MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=413, detail="File exceeds the upload size limit.")
    return data
