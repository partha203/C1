import os
import uuid
from werkzeug.utils import secure_filename


def save_upload(file_storage, subfolder, allowed_ext, upload_root, max_bytes=15 * 1024 * 1024):
    """Validate and save an uploaded file. Returns relative path or None."""
    if not file_storage or file_storage.filename == "":
        return None
    filename = secure_filename(file_storage.filename)
    if "." not in filename:
        return None
    ext = filename.rsplit(".", 1)[1].lower()
    if ext not in allowed_ext:
        return None

    file_storage.seek(0, os.SEEK_END)
    size = file_storage.tell()
    file_storage.seek(0)
    if size > max_bytes:
        return None

    unique_name = f"{uuid.uuid4().hex}_{filename}"
    folder = os.path.join(upload_root, subfolder)
    os.makedirs(folder, exist_ok=True)
    full_path = os.path.join(folder, unique_name)
    file_storage.save(full_path)
    return f"{subfolder}/{unique_name}"
