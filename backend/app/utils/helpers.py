import os
import uuid
from PIL import Image
from werkzeug.utils import secure_filename

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
MAX_IMAGE_SIZE = (1024, 1024)  # resize large images to save space


def allowed_file(filename):
    """Check if uploaded file has an allowed extension."""
    return (
        "." in filename and
        filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
    )


def save_image(file, upload_folder):
    """
    Saves uploaded image to disk.
    - Generates a unique filename using UUID
    - Resizes if larger than MAX_IMAGE_SIZE
    - Returns the saved filename
    """
    # Generate unique filename to avoid conflicts
    ext = file.filename.rsplit(".", 1)[1].lower()
    unique_filename = f"{uuid.uuid4().hex}.{ext}"
    filepath = os.path.join(upload_folder, unique_filename)

    # Save original first
    file.save(filepath)

    # Resize if too large (keeps aspect ratio)
    with Image.open(filepath) as img:
        img.thumbnail(MAX_IMAGE_SIZE, Image.LANCZOS)
        img.save(filepath)

    return unique_filename


def get_image_dimensions(filepath):
    """Returns width and height of saved image."""
    with Image.open(filepath) as img:
        return img.size  # (width, height)
