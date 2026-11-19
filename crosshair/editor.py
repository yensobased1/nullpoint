"""Pixel crosshair editor tab. Saves exact-pixel transparent PNGs."""
import copy
import os
import time
from collections import deque

from PySide6.QtCore import QRect, Qt, Signal
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import (QButtonGroup, QColorDialog, QComboBox, QFileDialog, QGridLayout, QHBoxLayout,
                               QInputDialog, QLabel, QMessageBox, QPushButton, QSlider, QSpinBox, QVBoxLayout,
                               QWidget)

import library
from config import DEFAULT_CROSSHAIR
from preview import PixelView, paint_background

SIZES = [16, 32, 64]
TOOLS = ["Pencil", "Eraser", "Line", "Rectangle", "Fill", "Eyedropper"]
CLEAR = QColor(0, 0, 0, 0)
MAX_UNDO = 50


def line_points(x0, y0, x1, y1):
    """Bresenham: every cell between two points, so fast strokes have no gaps."""
    dx, dy = abs(x1 - x0), -abs(y1 - y0)
    sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
    err = dx + dy
    while True:
        yield x0, y0
        if x0 == x1 and y0 == y1:
            return
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy


def rect_points(x0, y0, x1, y1):
    for a, b in ((x0, x1), (x1, x0)):
        yield from line_points(a, y0, b, y0)
        yield from line_points(a, y1, b, y1)
    yield from line_points(x0, y0, x0, y1)
    yield from line_points(x1, y0, x1, y1)


class Canvas(QWidget):
    changed = Signal()
    picked = Signal(QColor)

    def __init__(self, editor):
        super().__init__()
        self.ed = editor
        self.img = self.blank(32)
        self.undo, self.redo = [], []
        self.last = self.start = self.base = self.before = None
        self.erasing = False
        self.setMinimumSize(384, 384)
        self.setMouseTracking(False)

    @staticmethod
    def blank(n):
        img = QImage(n, n, QImage.Format_ARGB32)
        img.fill(0)
        return img

    @property
    def n(self):
        return self.img.width()

    def geom(self):
        cell = max(1, min(self.width(), self.height()) // self.n)
        return cell, (self.width() - cell * self.n) // 2, (self.height() - cell * self.n) // 2

    def cell_at(self, pos, clamp=False):
        cell, ox, oy = self.geom()
        x, y = (pos.x() - ox) // cell, (pos.y() - oy) // cell
        if clamp:
            return min(max(x, 0), self.n - 1), min(max(y, 0), self.n - 1)
        return (x, y) if 0 <= x < self.n and 0 <= y < self.n else None

    # ---------- drawing ----------
    def color(self):
        return CLEAR if self.erasing else self.ed.color

    def plot(self, x, y):
        b = self.ed.brush.value()
        lo = -((b - 1) // 2)
        pts = {(x + dx, y + dy) for dx in range(lo, lo + b) for dy in range(lo, lo + b)}
        m, n = self.ed.mirror.currentIndex(), self.n  # 0 off, 1 horizontal, 2 vertical, 3 both
        if m in (1, 3):
            pts |= {(n - 1 - px, py) for px, py in pts}
        if m in (2, 3):
            pts |= {(px, n - 1 - py) for px, py in pts}
        col = self.color()
        for px, py in pts:
            if 0 <= px < n and 0 <= py < n:
                self.img.setPixelColor(px, py, col)

    def fill(self, x, y):
        n = self.n
        seeds = {(x, y)}
        m = self.ed.mirror.currentIndex()
        if m in (1, 3):
            seeds |= {(n - 1 - sx, sy) for sx, sy in seeds}
        if m in (2, 3):
            seeds |= {(sx, n - 1 - sy) for sx, sy in seeds}
        new = self.color().rgba()
        for sx, sy in seeds:
            target = self.img.pixel(sx, sy)
            if target == new:
                continue
            todo = deque([(sx, sy)])
            while todo:
                px, py = todo.popleft()
                if 0 <= px < n and 0 <= py < n and self.img.pixel(px, py) == target:
                    self.img.setPixel(px, py, new)
                    todo.extend(((px + 1, py), (px - 1, py), (px, py + 1), (px, py - 1)))

    def snapshot(self):
        self.undo.append(self.img.copy())
        del self.undo[:-MAX_UNDO]
        self.redo.clear()

    def set_image(self, img, record=True):
        if record:
            self.snapshot()
        self.img = img
        self.changed.emit()
        self.update()

    def step(self, back):
        src, dst = (self.undo, self.redo) if back else (self.redo, self.undo)
        if src:
            dst.append(self.img.copy())
            self.img = src.pop()
            self.changed.emit()
            self.update()

    # ---------- mouse ----------
    def mousePressEvent(self, e):
        if e.button() not in (Qt.LeftButton, Qt.RightButton):
            return
        pt = self.cell_at(e.position().toPoint())
        if pt is None:
            return
        tool = self.ed.tool
        if tool == "Eyedropper":
            c = self.img.pixelColor(*pt)
            if c.alpha():
                self.picked.emit(c)
            return
        self.erasing = e.button() == Qt.RightButton or tool == "Eraser"
        if not self.erasing:
            self.ed.remember_color()
        self.before = self.img.copy()
        if tool == "Fill":
            self.fill(*pt)
            self.finish()
        elif tool in ("Line", "Rectangle"):
            self.start, self.base = pt, self.img.copy()
            self.plot(*pt)
        else:
            self.last = pt
            self.plot(*pt)
        self.changed.emit()
        self.update()

    def mouseMoveEvent(self, e):
        if self.before is None:
            return
        pt = self.cell_at(e.position().toPoint(), clamp=True)
        if self.start is not None:
            self.img = self.base.copy()
            pts = (line_points if self.ed.tool == "Line" else rect_points)(*self.start, *pt)
            for x, y in pts:
                self.plot(x, y)
        elif self.last is not None:
            for x, y in line_points(*self.last, *pt):
                self.plot(x, y)
            self.last = pt
        self.changed.emit()
        self.update()

    def mouseReleaseEvent(self, e):
        if self.before is not None:
            self.finish()

    def finish(self):
        """One undo step per stroke; strokes that changed nothing are dropped."""
        if self.img != self.before:
            self.undo.append(self.before)
            del self.undo[:-MAX_UNDO]
            self.redo.clear()
        self.before = self.last = self.start = self.base = None

    def paintEvent(self, _):
        p = QPainter(self)
        cell, ox, oy = self.geom()
        area = QRect(ox, oy, cell * self.n, cell * self.n)
        paint_background(p, self.rect(), "Dark")
        paint_background(p, area, "Checker", max(4, cell // 2))
        p.drawImage(area, self.img)  # nearest-neighbour: QPainter default without SmoothPixmapTransform
        if cell >= 4:
            p.setPen(QColor(0, 0, 0, 55))
            for i in range(self.n + 1):
                p.drawLine(ox + i * cell, oy, ox + i * cell, oy + area.height())
                p.drawLine(ox, oy + i * cell, ox + area.width(), oy + i * cell)
        # Center marker: the edge between the two middle pixels = the screen center the overlay uses.
        mid = self.n // 2 * cell
        p.setPen(QColor(255, 60, 60, 200))
        p.drawLine(ox + mid, oy, ox + mid, oy + area.height())
        p.drawLine(ox, oy + mid, ox + area.width(), oy + mid)


class EditorTab(QWidget):
    def __init__(self, on_apply, tr=lambda s: s):
        """on_apply(path): use this PNG as the current profile's crosshair."""
        super().__init__()
        self.on_apply, self.tr = on_apply, tr
        self.tool = "Pencil"
        self.color = QColor("#00FFFF")
        self.recent = []
        self.path = ""

        root = QHBoxLayout(self)
        self.canvas = Canvas(self)
        self.canvas.changed.connect(self.refresh_previews)
        self.canvas.picked.connect(self.pick)
        root.addWidget(self.canvas, 1)
        side = QVBoxLayout()
        root.addLayout(side)

        grid = QGridLayout()
        group = QButtonGroup(self)
        for i, t in enumerate(TOOLS):
            b = QPushButton(tr(t))
            b.setCheckable(True)
            b.setChecked(t == self.tool)
            b.clicked.connect(lambda _=False, t=t: setattr(self, "tool", t))
            group.addButton(b)
            grid.addWidget(b, i // 3, i % 3)
        side.addLayout(grid)

        row = QHBoxLayout()
        row.addWidget(QLabel(tr("Brush")))
        self.brush = QSpinBox()
        self.brush.setRange(1, 3)
        row.addWidget(self.brush)
        row.addWidget(QLabel(tr("Mirror")))
        self.mirror = QComboBox()
        self.mirror.addItems([tr("Off"), tr("Horizontal"), tr("Vertical"), tr("Both")])
        row.addWidget(self.mirror)
        row.addWidget(QLabel(tr("Grid")))
        self.size_box = QComboBox()
        self.size_box.addItems([f"{s}x{s}" for s in SIZES])
        self.size_box.setCurrentIndex(1)
        self.size_box.currentIndexChanged.connect(self.resize_canvas)
        row.addWidget(self.size_box)
        side.addLayout(row)

        row = QHBoxLayout()
        self.color_btn = QPushButton(tr("Color..."))
        self.color_btn.clicked.connect(self.choose_color)
        row.addWidget(self.color_btn)
        row.addWidget(QLabel(tr("Opacity")))
        self.alpha = QSlider(Qt.Horizontal)
        self.alpha.setRange(0, 255)
        self.alpha.setValue(255)
        self.alpha.valueChanged.connect(self.set_alpha)
        row.addWidget(self.alpha, 1)
        side.addLayout(row)
        self.recent_row = QHBoxLayout()
        side.addLayout(self.recent_row)
        self.recent_buttons = []
        for i in range(8):
            b = QPushButton()
            b.setFixedSize(24, 24)
            b.setVisible(False)
            b.clicked.connect(lambda _=False, i=i: self.pick(QColor.fromRgba(self.recent[i])))
            self.recent_row.addWidget(b)
            self.recent_buttons.append(b)
        self.recent_row.addStretch()

        side.addWidget(QLabel(tr("Preview: 1x = real in-game size, 4x zoom")))
        prev = QHBoxLayout()
        src = lambda: (self.canvas.img, self.canvas.n // 2)
        for z, size in ((1, 128), (4, 264)):
            v = PixelView(src, zoom=z, bg="Dark", size=size)
            v.setFixedSize(size, 264)
            prev.addWidget(v, 0, Qt.AlignTop)
            setattr(self, f"view{z}", v)
        prev.addStretch()
        side.addLayout(prev)

        buttons = QGridLayout()
        for i, (text, fn) in enumerate((
                ("Undo", lambda: self.canvas.step(True)), ("Redo", lambda: self.canvas.step(False)),
                ("Clear", self.clear), ("Load PNG to edit", self.load_png), ("Save as PNG", self.save_as),
                ("Save + Apply", self.save_apply), ("Add to Library", self.add_library))):
            b = QPushButton(tr(text))
            b.clicked.connect(fn)
            buttons.addWidget(b, i // 2, i % 2)
        side.addLayout(buttons)
        self.status = QLabel("")
        self.status.setWordWrap(True)
        side.addWidget(self.status)
        side.addStretch()

        # Ctrl+Z / Ctrl+Y: routed here by the settings window while this tab is open.
        self.update_color_button()

    # ---------- color ----------
    def update_color_button(self):
        c = self.color
        self.color_btn.setStyleSheet(f"background: rgba({c.red()},{c.green()},{c.blue()},{c.alpha()});")

    def pick(self, c):
        self.color = QColor(c)
        self.alpha.blockSignals(True)
        self.alpha.setValue(c.alpha())
        self.alpha.blockSignals(False)
        self.update_color_button()

    def choose_color(self):
        c = QColorDialog.getColor(self.color, self, self.tr("Brush color"), QColorDialog.ShowAlphaChannel)
        if c.isValid():
            self.pick(c)

    def set_alpha(self, a):
        self.color.setAlpha(a)
        self.update_color_button()

    def remember_color(self):
        rgba = self.color.rgba()
        self.recent = [rgba] + [r for r in self.recent if r != rgba][:7]
        for b, r in zip(self.recent_buttons, self.recent):
            c = QColor.fromRgba(r)
            b.setStyleSheet(f"background: rgba({c.red()},{c.green()},{c.blue()},{c.alpha()});")
            b.setVisible(True)

    # ---------- canvas ----------
    def refresh_previews(self):
        self.view1.update()
        self.view4.update()

    def is_empty(self):
        img = self.canvas.img
        return all(img.pixelColor(x, y).alpha() == 0 for y in range(img.height()) for x in range(img.width()))

    def resize_canvas(self, idx):
        n = SIZES[idx]
        if n == self.canvas.n:
            return
        if not self.is_empty() and QMessageBox.question(
                self, self.tr("Change grid size"), self.tr("Changing the grid size clears the canvas. Continue?")) \
                != QMessageBox.Yes:
            self.size_box.blockSignals(True)
            self.size_box.setCurrentIndex(SIZES.index(self.canvas.n))
            self.size_box.blockSignals(False)
            return
        self.canvas.set_image(Canvas.blank(n))

    def clear(self):
        self.canvas.set_image(Canvas.blank(self.canvas.n))

    def load_png(self):
        path, _ = QFileDialog.getOpenFileName(self, self.tr("Load PNG"), library.CUSTOM_DIR, "PNG (*.png)")
        if not path:
            return
        img = QImage(path)
        if img.isNull() or max(img.width(), img.height()) > SIZES[-1]:
            self.say(self.tr("Can't edit that image: it must be a PNG up to 64x64 pixels."), True)
            return
        img = img.convertToFormat(QImage.Format_ARGB32)
        n = next(s for s in SIZES if s >= max(img.width(), img.height()))
        canvas = Canvas.blank(n)
        p = QPainter(canvas)
        p.setCompositionMode(QPainter.CompositionMode_Source)
        # Keep the image's center pixel on the canvas center, same rule the overlay uses.
        p.drawImage(n // 2 - img.width() // 2, n // 2 - img.height() // 2, img)
        p.end()
        self.size_box.blockSignals(True)
        self.size_box.setCurrentIndex(SIZES.index(n))
        self.size_box.blockSignals(False)
        self.canvas.set_image(canvas)
        self.path = path

    # ---------- save ----------
    def say(self, text, error=False):
        self.status.setStyleSheet("color: #ef6b6b;" if error else "color: #52c98e;")
        self.status.setText(text)

    def write(self, path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if not self.canvas.img.save(path, "PNG"):
            self.say(self.tr("Could not save the PNG."), True)
            return False
        self.path = path
        self.say(self.tr("Saved") + f": {os.path.basename(path)}")
        return True

    def auto_path(self):
        return os.path.join(library.CUSTOM_DIR, time.strftime("editor_%Y%m%d_%H%M%S.png"))

    def save_as(self):
        start = self.path or self.auto_path()
        path, _ = QFileDialog.getSaveFileName(self, self.tr("Save as PNG"), start, "PNG (*.png)")
        if path:
            self.write(path if path.lower().endswith(".png") else path + ".png")

    def save_apply(self):
        if self.write(self.path if self.path.startswith(library.CUSTOM_DIR) else self.auto_path()):
            self.on_apply(self.path)

    def add_library(self):
        name, ok = QInputDialog.getText(self, self.tr("Add to Library"), self.tr("Name:"), text="Custom")
        if ok and name.strip() and self.write(self.auto_path()):
            cross = copy.deepcopy(DEFAULT_CROSSHAIR)
            cross["mode"] = "png"
            library.add(name.strip(), cross, self.path)
            self.say(self.tr("Added to library") + f": {name.strip()}")
