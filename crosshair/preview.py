"""Pixel-exact preview widgets: background switch, integer nearest-neighbour zoom, optional pixel grid."""
from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QButtonGroup, QCheckBox, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

BACKGROUNDS = {"Checker": None, "Dark": "#202226", "Grey": "#7f858c", "Light": "#e9ecef"}


def paint_background(p, rect, name, cell=8):
    if BACKGROUNDS.get(name):
        p.fillRect(rect, QColor(BACKGROUNDS[name]))
        return
    p.fillRect(rect, QColor("#9a9a9a"))
    dark = QColor("#6e6e6e")
    for y in range(rect.top(), rect.bottom() + 1, cell):
        for x in range(rect.left() + (((y - rect.top()) // cell) % 2) * cell, rect.right() + 1, 2 * cell):
            p.fillRect(x, y, cell, cell, dark)


class PixelView(QWidget):
    """Shows source() -> (QImage, center_index) so pixel center_index sits on the widget's center pixel.
    Zoom is a whole number; if it doesn't fit it halves until it does (never stretched or cropped)."""

    def __init__(self, source, zoom=2, bg="Checker", grid=False, size=280):
        super().__init__()
        self.source, self.zoom, self.bg, self.grid = source, zoom, bg, grid
        self.shown_zoom = zoom
        self.setMinimumSize(size, size)

    def paintEvent(self, _):
        p = QPainter(self)
        paint_background(p, self.rect(), self.bg)
        got = self.source()
        if not got or got[0] is None or got[0].isNull():
            return
        img, c = got
        span = max(img.width(), img.height())
        z = self.zoom
        while z > 1 and span * z > min(self.width(), self.height()):
            z //= 2
        self.shown_zoom = z
        # Image pixel c lands on the widget's center pixel; integer offsets keep it sharp.
        x0 = self.width() // 2 - c * z
        y0 = self.height() // 2 - c * z
        p.setRenderHint(QPainter.SmoothPixmapTransform, False)
        p.drawImage(QRect(x0, y0, img.width() * z, img.height() * z), img)
        if self.grid and z >= 4:
            p.setPen(QColor(0, 0, 0, 60))
            for i in range(img.width() + 1):
                p.drawLine(x0 + i * z, y0, x0 + i * z, y0 + img.height() * z)
            for i in range(img.height() + 1):
                p.drawLine(x0, y0 + i * z, x0 + img.width() * z, y0 + i * z)
        p.setPen(QColor("#ffffff"))
        p.drawText(6, 16, f"{z}x" + ("" if z == self.zoom else f" ({self.zoom}x doesn't fit)"))


class PreviewPanel(QWidget):
    """PixelView + background / zoom / grid controls."""

    def __init__(self, source, tr=lambda s: s):
        super().__init__()
        self.view = PixelView(source)
        self.linked = []  # other views that follow this panel's zoom / background / grid (compare mode)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.view, 1)
        row = QHBoxLayout()
        self._buttons(row, list(BACKGROUNDS), "bg", "Checker", tr)
        lay.addLayout(row)
        row = QHBoxLayout()
        row.addWidget(QLabel(tr("Zoom")))
        self._buttons(row, [1, 2, 4, 8], "zoom", 2, tr)
        grid = QCheckBox(tr("Grid"))
        grid.toggled.connect(lambda v: self._set("grid", v))
        row.addWidget(grid)
        lay.addLayout(row)

    def _buttons(self, row, values, attr, current, tr):
        group = QButtonGroup(self)
        for v in values:
            b = QPushButton(f"{v}x" if attr == "zoom" else tr(v))
            b.setCheckable(True)
            b.setChecked(v == current)
            b.clicked.connect(lambda _=False, v=v: self._set(attr, v))
            group.addButton(b)
            row.addWidget(b)

    def _set(self, attr, value):
        for v in [self.view] + self.linked:
            setattr(v, attr, value)
            v.update()

    def link(self, view):
        for attr in ("zoom", "bg", "grid"):
            setattr(view, attr, getattr(self.view, attr))
        self.linked.append(view)

    def update(self):
        self.view.update()
        super().update()


def render_image(draw, c):
    """QImage of size 2c+1 drawn by draw(painter, c): the overlay, preview and thumbnails all go through this."""
    img = QImage(2 * c + 1, 2 * c + 1, QImage.Format_ARGB32_Premultiplied)
    img.fill(0)
    p = QPainter(img)
    draw(p, c)
    p.end()
    return img
