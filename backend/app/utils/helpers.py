import os
import uuid
from PIL import Image, ImageOps
from werkzeug.utils import secure_filename

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
FORMAT_TO_EXT = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}


class InvalidImageError(ValueError):
    """The uploaded bytes are not a real JPG / PNG / WEBP image."""
MAX_IMAGE_SIZE = (1024, 1024)  # resize large images to save space


def allowed_file(filename):
    """Check if uploaded file has an allowed extension."""
    return (
        "." in filename and
        filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
    )


def save_image(file, upload_folder):
    """
    Saves an uploaded image to disk.
    - the file CONTENT is decoded and checked (the filename extension is never trusted)
    - the stored name is a random UUID plus the extension of the detected format
    - large images are shrunk to MAX_IMAGE_SIZE (aspect ratio kept)
    Raises InvalidImageError (and stores nothing) if the bytes are not a supported image.
    """
    tmp_path = os.path.join(upload_folder, f"tmp_{uuid.uuid4().hex}")
    file.save(tmp_path)
    try:
        with Image.open(tmp_path) as probe:
            fmt = probe.format
            probe.verify()
        if fmt not in FORMAT_TO_EXT:
            raise InvalidImageError("Only JPG, PNG and WEBP images are supported.")
        unique_filename = f"{uuid.uuid4().hex}.{FORMAT_TO_EXT[fmt]}"
        filepath = os.path.join(upload_folder, unique_filename)
        with Image.open(tmp_path) as img:
            img.load()
            # re-encoding drops EXIF, so bake the camera rotation into the pixels first
            img = ImageOps.exif_transpose(img)
            img.thumbnail(MAX_IMAGE_SIZE, Image.LANCZOS)
            img.save(filepath)
        return unique_filename
    except InvalidImageError:
        raise
    except Exception as exc:                       # decoding failure, truncated / hostile file
        raise InvalidImageError("That file is not a valid image.") from exc
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def get_image_dimensions(filepath):
    """Returns width and height of saved image."""
    with Image.open(filepath) as img:
        return img.size  # (width, height)
