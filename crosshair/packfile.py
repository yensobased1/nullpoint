""".nullpoint files: one crosshair (name + share code + its image, if any) in a small JSON file.

{"format": "nullpoint-crosshair", "version": 1, "name": "...", "code": "XH4;...", "image": "<base64>", "ext": "png"}
Everything read from a file is untrusted: size, schema, code and image are all checked before use.
"""
import base64
import binascii
import json
import os
import uuid

import safe_image
from share_code import ShareCodeError, export_code, import_code

FORMAT = "nullpoint-crosshair"
MAX_FILE = 5 * 1024 * 1024
IMAGE_EXTS = ("png", "gif", "svg")


class PackError(ValueError):
    pass


def dump(name, cross, image_path=""):
    data = {"format": FORMAT, "version": 1, "name": str(name)[:60], "code": export_code(cross)}
    if cross["mode"] == "png" and image_path and os.path.isfile(image_path):
        ext = os.path.splitext(image_path)[1].lower().lstrip(".")
        if ext in IMAGE_EXTS:
            safe_image.check_file(image_path)
            with open(image_path, "rb") as f:
                data.update(image=base64.b64encode(f.read()).decode("ascii"), ext=ext)
    return json.dumps(data, indent=1).encode("utf-8")


def load(raw):
    """bytes -> (name, crosshair, image bytes or None, ext). Raises PackError."""
    if len(raw) > MAX_FILE:
        raise PackError("That .nullpoint file is too big (max 5 MB).")
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise PackError("That isn't a .nullpoint file.") from None
    if not isinstance(data, dict) or data.get("format") != FORMAT or not isinstance(data.get("code"), str):
        raise PackError("That isn't a .nullpoint file.")
    try:
        cross = import_code(data["code"])
    except ShareCodeError as e:
        raise PackError(str(e)) from None
    name = data.get("name") if isinstance(data.get("name"), str) else "Crosshair"
    img, ext = None, ""
    if data.get("image") is not None:
        ext = data.get("ext") if data.get("ext") in IMAGE_EXTS else ""
        if not ext or not isinstance(data["image"], str):
            raise PackError("The image in that file is damaged.")
        try:
            img = base64.b64decode(data["image"], validate=True)
        except (binascii.Error, ValueError):
            raise PackError("The image in that file is damaged.") from None
        safe_image.load_bytes(img)  # raises ImageError for bombs, huge sizes, unsafe SVGs
    return name.strip()[:60] or "Crosshair", cross, img, ext


def store_image(img, ext, folder):
    """Save imported image bytes into our own folder under a fresh name (never a name from the file)."""
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, f"imported_{uuid.uuid4().hex[:12]}.{ext}")
    with open(path, "wb") as f:
        f.write(img)
    return path
