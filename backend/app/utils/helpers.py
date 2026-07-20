import os
import uuid

def generate_unique_filename(original_filename):
    ext = os.path.splitext(original_filename)[1]
    return f"{uuid.uuid4().hex}{ext}"
