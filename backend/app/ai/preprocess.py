"""Image preparation shared by training and by the running app, so both see a garment the same way."""
from PIL import Image, ImageOps

PAD_COLOUR = (114, 114, 114)
CROP_MARGIN = 0.10


def load_rgb(path):
    """Open a photo upright (EXIF rotation applied) as RGB."""
    with Image.open(path) as im:
        return ImageOps.exif_transpose(im).convert("RGB")


def crop_box(image, box_xyxy, margin=CROP_MARGIN):
    """Crop to a box widened by `margin` on every side (clamped to the image). `None` box = the whole image."""
    if not box_xyxy:
        return image
    x1, y1, x2, y2 = [float(v) for v in box_xyxy]
    mx, my = margin * (x2 - x1), margin * (y2 - y1)
    box = (max(0, int(x1 - mx)), max(0, int(y1 - my)), min(image.width, int(x2 + mx)), min(image.height, int(y2 + my)))
    if box[2] - box[0] < 2 or box[3] - box[1] < 2:
        return image
    return image.crop(box)


def square_pad(image, size=None):
    """
    Pad to a square with a neutral border (nothing is cut off or stretched), optionally resized to size x size.
    A classifier's centre crop would otherwise cut the top of a tall garment crop - where the neckline is.
    """
    side = max(image.width, image.height)
    canvas = Image.new("RGB", (side, side), PAD_COLOUR)
    canvas.paste(image, ((side - image.width) // 2, (side - image.height) // 2))
    if size:
        canvas = canvas.resize((size, size), Image.Resampling.BILINEAR)
    return canvas
