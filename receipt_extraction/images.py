"""Decode actual image contents and remove metadata before upload."""
from io import BytesIO
import warnings
from PIL import Image, ImageOps
import pillow_heif
pillow_heif.register_heif_opener()
MAX_BYTES = 10 * 1024 * 1024

def normalize_image(data: bytes) -> bytes:
    if not data or len(data) > MAX_BYTES:
        raise ValueError("Choose an image smaller than 10 MB.")
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        with Image.open(BytesIO(data)) as image:
            if getattr(image, "n_frames", 1) != 1:
                raise ValueError("Use a single still image, not an animation or multi-page file.")
            if image.width * image.height > 20_000_000:
                raise ValueError("Image must be at most 20 megapixels.")
            image = ImageOps.exif_transpose(image).convert("RGB")
            output = BytesIO()
            image.save(output, format="PNG")
    result = output.getvalue()
    if len(result) > MAX_BYTES:
        raise ValueError("Decoded image is too large; crop it before uploading.")
    return result
