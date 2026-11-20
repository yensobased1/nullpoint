"""Saved crosshairs in %APPDATA%\\Nullpoint\\library.json: [{"name", "crosshair", "image"}]."""
import hashlib
import json
import os
import re

from config import CONFIG_DIR, clean_crosshair

LIBRARY_PATH = os.path.join(CONFIG_DIR, "library.json")
CUSTOM_DIR = os.path.join(CONFIG_DIR, "custom")


def load():
    try:
        with open(LIBRARY_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return []
    return clean(data)


def clean(data):
    """Validate untrusted entries (file on disk or an import): bad items dropped, missing fields defaulted."""
    if not isinstance(data, list):
        return []
    return [{"name": str(e.get("name", "Crosshair"))[:60], "crosshair": clean_crosshair(e.get("crosshair")),
             "image": str(e.get("image", "")),
             "tags": [str(t)[:24] for t in e.get("tags", []) if str(t).strip()][:12] if isinstance(e.get("tags"), list) else [],
             "fav": e.get("fav") is True} for e in data if isinstance(e, dict)]


def save(entries):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    tmp = LIBRARY_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2)
    os.replace(tmp, LIBRARY_PATH)


def fingerprint(cross, image=""):
    """Same fingerprint = the same crosshair. Opacities are compared to 0.1, so near-identical copies match too;
    image crosshairs compare the image file's bytes."""
    from share_code import export_code
    code = re.sub(r"\d+\.\d+", lambda m: f"{float(m.group()):.1f}", export_code(cross))
    digest = ""
    if cross["mode"] == "png" and image:
        try:
            if os.path.getsize(image) <= 20 * 1024 * 1024:
                with open(image, "rb") as f:
                    digest = hashlib.sha256(f.read()).hexdigest()
        except OSError:
            digest = image
    return code, digest


def find_duplicate(entries, cross, image=""):
    """Index of an entry that looks the same, or None."""
    fp = fingerprint(cross, image)
    return next((i for i, e in enumerate(entries) if fingerprint(e["crosshair"], e["image"]) == fp), None)


def add(name, crosshair, image="", tags=None):
    entries = load()
    entries.append({"name": name, "crosshair": crosshair, "image": image, "tags": tags or [], "fav": False})
    save(entries)
