"""Feature icons from assets/icons/ui/*.svg, tinted with the theme's text color (they use currentColor)."""
import os
import sys

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QIcon, QImage, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from ui import theme

ICON_DIR = os.path.join(getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))), "assets", "icons", "ui")
_cache = {}


def icon(name, size=18):
    """QIcon for assets/icons/ui/<name>.svg in the current theme color; empty icon if the file is missing."""
    color = theme.tokens["text"]
    key = (name, color, size)
    if key not in _cache:
        path = os.path.join(ICON_DIR, name + ".svg")
        try:
            with open(path, encoding="utf-8") as f:
                svg = f.read().replace("currentColor", color)
        except OSError:
            _cache[key] = QIcon()
            return _cache[key]
        r = QSvgRenderer(QByteArray(svg.encode("utf-8")))
        img = QImage(size * 2, size * 2, QImage.Format_ARGB32_Premultiplied)  # 2x for crisp HiDPI
        img.fill(Qt.transparent)
        p = QPainter(img)
        r.render(p)
        p.end()
        _cache[key] = QIcon(QPixmap.fromImage(img))
    return _cache[key]
