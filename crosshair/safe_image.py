"""Load outside images with limits, so a hostile file can't eat memory or hang the app.

Every image that comes from a file, the clipboard, a drop or a pack goes through here (Qt decoder for
PNG/JPG/BMP/GIF, QtSvg for SVG). Pillow is used only for writing animated GIFs; its bomb guard is set anyway.
"""
import os
import re

from PySide6.QtCore import QByteArray, QSize
from PySide6.QtGui import QImage, QImageReader, QPainter
from PySide6.QtSvg import QSvgRenderer

MAX_SIDE = 4096  # px per side
MAX_BYTES = 20 * 1024 * 1024  # file size
MAX_FRAMES = 300  # GIF frames

try:
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = MAX_SIDE * MAX_SIDE  # bigger = DecompressionBombError
except ImportError:  # only needed for GIF export
    Image = None


class ImageError(ValueError):
    pass


def check_file(path):
    try:
        size = os.path.getsize(path)
    except OSError:
        raise ImageError("Can't open that file.") from None
    if size > MAX_BYTES:
        raise ImageError("That image file is too big (max 20 MB).")


def read_qimage(reader):
    size = reader.size()
    if not size.isValid() or size.width() > MAX_SIDE or size.height() > MAX_SIDE:
        raise ImageError("That image is too large (max 4096 x 4096 px) or not an image.")
    if reader.supportsAnimation() and reader.imageCount() > MAX_FRAMES:
        raise ImageError("That GIF has too many frames (max 300).")
    img = reader.read()
    if img.isNull():
        raise ImageError("That file isn't a readable image.")
    return img


# SVG: no scripts, no external files or links, no huge canvases. QtSvg ignores scripts, but we refuse them anyway.
SVG_BAD = re.compile(rb"<script|<foreignObject|<!ENTITY|xlink:href\s*=\s*[\"'](?!#)|\shref\s*=\s*[\"'](?!#|data:image/)",
                     re.IGNORECASE)


def svg_ok(data):
    if SVG_BAD.search(data):
        raise ImageError("That SVG uses scripts or external files, which aren't allowed.")
    r = QSvgRenderer(QByteArray(data))
    if not r.isValid():
        raise ImageError("That SVG can't be read.")
    box = r.viewBoxF()
    if box.width() > MAX_SIDE or box.height() > MAX_SIDE or r.defaultSize().width() > MAX_SIDE \
            or r.defaultSize().height() > MAX_SIDE:
        raise ImageError("That SVG is too large (max 4096 x 4096).")
    return r


def load(path):
    """File -> QImage (first frame for GIFs). Raises ImageError with a readable message."""
    check_file(path)
    if path.lower().endswith(".svg"):
        with open(path, "rb") as f:
            r = svg_ok(f.read())
        size = r.defaultSize()
        img = QImage(max(1, size.width()), max(1, size.height()), QImage.Format_ARGB32_Premultiplied)
        img.fill(0)
        p = QPainter(img)
        r.render(p)
        p.end()
        return img
    reader = QImageReader(path)
    reader.setDecideFormatFromContent(True)
    return read_qimage(reader)


def load_bytes(data):
    """Bytes (clipboard / pack / drop) -> QImage."""
    if len(data) > MAX_BYTES:
        raise ImageError("That image file is too big (max 20 MB).")
    if data.lstrip()[:5].lower() in (b"<?xml", b"<svg ") or b"<svg" in data[:512].lower():
        r = svg_ok(data)
        img = QImage(QSize(max(1, r.defaultSize().width()), max(1, r.defaultSize().height())),
                     QImage.Format_ARGB32_Premultiplied)
        img.fill(0)
        p = QPainter(img)
        r.render(p)
        p.end()
        return img
    from PySide6.QtCore import QBuffer, QIODevice
    buf = QBuffer()
    buf.setData(QByteArray(data))
    buf.open(QIODevice.ReadOnly)
    reader = QImageReader(buf)
    return read_qimage(reader)


def checked(img):
    """An already-decoded QImage (e.g. clipboard) within the size limit."""
    if img.isNull() or img.width() > MAX_SIDE or img.height() > MAX_SIDE:
        raise ImageError("That image is too large (max 4096 x 4096 px) or not an image.")
    return img
