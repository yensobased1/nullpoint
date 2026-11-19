"""Pixel crosshair editor tab: layers, animation frames (onion skin), shape tools, image import, recolor.
Saves exact-pixel transparent PNGs, or animated GIFs when there is more than one frame."""
import copy
import os
import time
from collections import deque

from PySide6.QtCore import QRect, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QColorDialog, QComboBox, QDialog, QDialogButtonBox,
                               QFileDialog, QFormLayout, QGridLayout, QHBoxLayout, QInputDialog, QLabel,
                               QListWidget, QListWidgetItem, QMessageBox, QPushButton, QSlider, QSpinBox,
                               QVBoxLayout, QWidget)

import library
import safe_image
from config import DEFAULT_CROSSHAIR
from preview import PixelView, paint_background
from ui import theme

SIZES = [16, 32, 64]
TOOLS = ["Pencil", "Eraser", "Line", "Rectangle", "Filled rectangle", "Circle", "Filled circle", "Fill", "Eyedropper"]
SHAPE_TOOLS = TOOLS[2:7]
CLEAR = QColor(0, 0, 0, 0)
MAX_UNDO = 50
MAX_LAYERS = 8
MAX_FRAMES = 60
ONION = 0.3  # previous frame opacity under the current one


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


def rect_points(x0, y0, x1, y1, filled=False):
    xa, xb, ya, yb = min(x0, x1), max(x0, x1), min(y0, y1), max(y0, y1)
    for y in range(ya, yb + 1):
        for x in range(xa, xb + 1):
            if filled or x in (xa, xb) or y in (ya, yb):
                yield x, y


def ellipse_points(x0, y0, x1, y1, filled=False):
    """Ellipse inside the box (x0,y0)-(x1,y1): cells whose center is inside it (midpoint rule, pixel exact and
    symmetric). Outline = inside cells with a 4-neighbour outside."""
    xa, xb, ya, yb = min(x0, x1), max(x0, x1), min(y0, y1), max(y0, y1)
    cx, cy = (xa + xb + 1) / 2, (ya + yb + 1) / 2
    rx, ry = (xb - xa + 1) / 2, (yb - ya + 1) / 2
    inside = lambda x, y: ((x + 0.5 - cx) / rx) ** 2 + ((y + 0.5 - cy) / ry) ** 2 <= 1.0 + 1e-9
    for y in range(ya, yb + 1):
        for x in range(xa, xb + 1):
            if inside(x, y) and (filled or not all(inside(x + dx, y + dy)
                                                   for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))):
                yield x, y


def shape_points(tool, a, b):
    if tool == "Line":
        return line_points(*a, *b)
    if tool in ("Rectangle", "Filled rectangle"):
        return rect_points(*a, *b, filled=tool == "Filled rectangle")
    return ellipse_points(*a, *b, filled=tool == "Filled circle")


def to_pixels(img, n, threshold=128, invert=False, keep_color=True, color=QColor("#00FFFF")):
    """Any image -> n x n pixel art: scaled to fit (centered), then each pixel solid or transparent.
    With transparency: alpha decides. Without: darkness decides (dark lines on white = solid)."""
    img = img.convertToFormat(QImage.Format_ARGB32)
    fit = img.scaled(n, n, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    has_alpha = any(fit.pixelColor(x, y).alpha() < 255 for y in range(fit.height()) for x in range(fit.width()))
    out = QImage(n, n, QImage.Format_ARGB32)
    out.fill(0)
    ox, oy = (n - fit.width()) // 2, (n - fit.height()) // 2
    for y in range(fit.height()):
        for x in range(fit.width()):
            c = fit.pixelColor(x, y)
            ink = c.alpha() if has_alpha else 255 - QColor(c).lightness()
            if (ink >= threshold) != invert:
                col = QColor(c.red(), c.green(), c.blue()) if keep_color else QColor(color)
                out.setPixelColor(ox + x, oy + y, col)
    return out


def close_colors(a, b, tol):
    """Same color within tol (0..1) of 255 per channel, alpha included."""
    lim = round(tol * 255)
    return all(abs(x - y) <= lim for x, y in zip(a.getRgb(), b.getRgb()))


def write_gif(path, frames, delays):
    """Composited QImages -> animated GIF (Pillow). GIF has 1-bit transparency: alpha < 128 = transparent."""
    from PIL import Image
    out = []
    for img in frames:
        img = img.convertToFormat(QImage.Format_RGBA8888)
        rgba = Image.frombuffer("RGBA", (img.width(), img.height()), bytes(img.constBits()), "raw", "RGBA", 0, 1)
        p = rgba.convert("RGB").quantize(colors=255)
        pal = p.getpalette()[:255 * 3]
        p.putpalette(pal + [0] * (768 - len(pal)))
        p.paste(255, mask=rgba.getchannel("A").point(lambda a: 255 if a < 128 else 0))
        out.append(p)
    out[0].save(path, save_all=True, append_images=out[1:], duration=[max(20, d) for d in delays], loop=0,
                disposal=2, transparency=255)


class Canvas(QWidget):
    changed = Signal()
    picked = Signal(QColor)

    def __init__(self, editor):
        super().__init__()
        self.ed = editor
        self.undo, self.redo = [], []
        self.last = self.start = self.base = self.before = None
        self.erasing = False
        self.onion = False
        self.reset(self.blank(32))
        self.setMinimumSize(384, 384)
        self.setMouseTracking(False)

    @staticmethod
    def blank(n):
        img = QImage(n, n, QImage.Format_ARGB32)
        img.fill(0)
        return img

    # ---------- document: layers x frames ----------
    def reset(self, img):
        self.layers = [{"name": "Layer 1", "visible": True, "opacity": 1.0}]
        self.frames = [{"delay": 100, "imgs": [img]}]
        self.cl = self.cf = 0

    @property
    def img(self):
        return self.frames[self.cf]["imgs"][self.cl]

    @img.setter
    def img(self, value):
        self.frames[self.cf]["imgs"][self.cl] = value

    @property
    def n(self):
        return self.img.width()

    def composite(self, f=None):
        f = self.cf if f is None else f
        out = self.blank(self.n)
        p = QPainter(out)
        for layer, img in zip(self.layers, self.frames[f]["imgs"]):
            if layer["visible"]:
                p.setOpacity(layer["opacity"])
                p.drawImage(0, 0, img)
        p.end()
        return out

    def state(self):
        return (copy.deepcopy(self.layers), [{"delay": fr["delay"], "imgs": [i.copy() for i in fr["imgs"]]}
                                             for fr in self.frames], self.cl, self.cf)

    def restore(self, st):
        self.layers, self.frames, self.cl, self.cf = st

    def push(self, entry):
        self.undo.append(entry)
        del self.undo[:-MAX_UNDO]
        self.redo.clear()

    def record_doc(self):
        """Before a change to layers / frames / size: whole-document undo step."""
        self.push(("doc", self.state()))

    def set_image(self, img, record=True):
        """Replace the current layer's image (same size)."""
        if record:
            self.push(("img", self.cf, self.cl, self.img.copy()))
        self.img = img
        self.touched()

    def set_doc(self, img):
        """New single-layer, single-frame document (grid size change / loaded PNG)."""
        self.record_doc()
        self.reset(img)
        self.touched()

    def touched(self):
        self.changed.emit()
        self.update()

    def step(self, back):
        src, dst = (self.undo, self.redo) if back else (self.redo, self.undo)
        if not src:
            return
        e = src.pop()
        if e[0] == "doc":
            dst.append(("doc", self.state()))
            self.restore(e[1])
        else:
            _, f, l, img = e
            if f < len(self.frames) and l < len(self.layers):
                dst.append(("img", f, l, self.frames[f]["imgs"][l].copy()))
                self.cf, self.cl = f, l
                self.img = img
        self.ed.sync_panels()
        self.touched()

    # ---------- drawing ----------
    def color(self):
        return CLEAR if self.erasing else self.ed.color

    def mirrored(self, pts):
        m, n = self.ed.mirror.currentIndex(), self.n  # 0 off, 1 horizontal, 2 vertical, 3 both
        if m in (1, 3):
            pts |= {(n - 1 - px, py) for px, py in pts}
        if m in (2, 3):
            pts |= {(px, n - 1 - py) for px, py in pts}
        return pts

    def plot(self, x, y):
        b = self.ed.brush.value()
        lo = -((b - 1) // 2)
        pts = self.mirrored({(x + dx, y + dy) for dx in range(lo, lo + b) for dy in range(lo, lo + b)})
        col, n = self.color(), self.n
        for px, py in pts:
            if 0 <= px < n and 0 <= py < n:
                self.img.setPixelColor(px, py, col)

    def fill(self, x, y):
        n = self.n
        new = self.color().rgba()
        for sx, sy in self.mirrored({(x, y)}):
            target = self.img.pixel(sx, sy)
            if target == new:
                continue
            todo = deque([(sx, sy)])
            while todo:
                px, py = todo.popleft()
                if 0 <= px < n and 0 <= py < n and self.img.pixel(px, py) == target:
                    self.img.setPixel(px, py, new)
                    todo.extend(((px + 1, py), (px - 1, py), (px, py + 1), (px, py - 1)))

    def draw_shape(self, tool, a, b):
        for x, y in shape_points(tool, a, b):
            self.plot(x, y)

    def recolor(self, src, dst, tol, all_layers):
        """Replace every pixel close to src with dst. Returns how many pixels changed."""
        if all_layers:
            self.record_doc()
            targets = [(fr, i) for fr in self.frames for i in range(len(self.layers))]
        else:
            self.push(("img", self.cf, self.cl, self.img.copy()))
            targets = [(self.frames[self.cf], self.cl)]
        count = 0
        for fr, i in targets:
            img = fr["imgs"][i]
            for y in range(img.height()):
                for x in range(img.width()):
                    c = img.pixelColor(x, y)
                    if c.alpha() and close_colors(c, src, tol):
                        img.setPixelColor(x, y, dst)
                        count += 1
        self.touched()
        return count

    # ---------- layers / frames ----------
    def add_layer(self):
        if len(self.layers) >= MAX_LAYERS:
            return False
        self.record_doc()
        self.layers.insert(self.cl + 1, {"name": f"Layer {len(self.layers) + 1}", "visible": True, "opacity": 1.0})
        for fr in self.frames:
            fr["imgs"].insert(self.cl + 1, self.blank(self.n))
        self.cl += 1
        self.touched()
        return True

    def delete_layer(self):
        if len(self.layers) <= 1:
            return
        self.record_doc()
        del self.layers[self.cl]
        for fr in self.frames:
            del fr["imgs"][self.cl]
        self.cl = max(0, self.cl - 1)
        self.touched()

    def move_layer(self, d):
        j = self.cl + d
        if not 0 <= j < len(self.layers):
            return
        self.record_doc()
        self.layers[self.cl], self.layers[j] = self.layers[j], self.layers[self.cl]
        for fr in self.frames:
            fr["imgs"][self.cl], fr["imgs"][j] = fr["imgs"][j], fr["imgs"][self.cl]
        self.cl = j
        self.touched()

    def merge_down(self):
        """Current layer onto the one below it (with its visibility and opacity), in every frame."""
        if self.cl == 0:
            return
        self.record_doc()
        top = self.layers[self.cl]
        for fr in self.frames:
            p = QPainter(fr["imgs"][self.cl - 1])
            p.setOpacity(top["opacity"] if top["visible"] else 0.0)
            p.drawImage(0, 0, fr["imgs"][self.cl])
            p.end()
            del fr["imgs"][self.cl]
        del self.layers[self.cl]
        self.cl -= 1
        self.touched()

    def add_frame(self):
        """New frame = copy of the current one (easier to animate small changes)."""
        if len(self.frames) >= MAX_FRAMES:
            return False
        self.record_doc()
        fr = self.frames[self.cf]
        self.frames.insert(self.cf + 1, {"delay": fr["delay"], "imgs": [i.copy() for i in fr["imgs"]]})
        self.cf += 1
        self.touched()
        return True

    def delete_frame(self):
        if len(self.frames) <= 1:
            return
        self.record_doc()
        del self.frames[self.cf]
        self.cf = min(self.cf, len(self.frames) - 1)
        self.touched()

    # ---------- mouse ----------
    def geom(self):
        cell = max(1, min(self.width(), self.height()) // self.n)
        return cell, (self.width() - cell * self.n) // 2, (self.height() - cell * self.n) // 2

    def cell_at(self, pos, clamp=False):
        cell, ox, oy = self.geom()
        x, y = (pos.x() - ox) // cell, (pos.y() - oy) // cell
        if clamp:
            return min(max(x, 0), self.n - 1), min(max(y, 0), self.n - 1)
        return (x, y) if 0 <= x < self.n and 0 <= y < self.n else None

    def mousePressEvent(self, e):
        if e.button() not in (Qt.LeftButton, Qt.RightButton):
            return
        pt = self.cell_at(e.position().toPoint())
        if pt is None:
            return
        tool = self.ed.tool
        if tool == "Eyedropper":
            c = self.composite().pixelColor(*pt)
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
        elif tool in SHAPE_TOOLS:
            self.start, self.base = pt, self.img.copy()
            self.draw_shape(tool, pt, pt)
        else:
            self.last = pt
            self.plot(*pt)
        self.touched()

    def mouseMoveEvent(self, e):
        if self.before is None:
            return
        pt = self.cell_at(e.position().toPoint(), clamp=True)
        if self.start is not None:  # live preview of the shape while dragging
            self.img = self.base.copy()
            self.draw_shape(self.ed.tool, self.start, pt)
        elif self.last is not None:
            for x, y in line_points(*self.last, *pt):
                self.plot(x, y)
            self.last = pt
        self.touched()

    def mouseReleaseEvent(self, e):
        if self.before is not None:
            self.finish()

    def finish(self):
        """One undo step per stroke; strokes that changed nothing are dropped."""
        if self.img != self.before:
            self.push(("img", self.cf, self.cl, self.before))
        self.before = self.last = self.start = self.base = None

    def paintEvent(self, _):
        p = QPainter(self)
        cell, ox, oy = self.geom()
        area = QRect(ox, oy, cell * self.n, cell * self.n)
        paint_background(p, self.rect(), "Dark")
        paint_background(p, area, "Checker", max(4, cell // 2))
        if self.onion and self.cf > 0:
            p.setOpacity(ONION)
            p.drawImage(area, self.composite(self.cf - 1))
            p.setOpacity(1.0)
        p.drawImage(area, self.composite())  # nearest-neighbour: QPainter default without SmoothPixmapTransform
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


class ImportDialog(QDialog):
    """Image -> pixels: threshold + invert + keep colors, with a live preview."""

    def __init__(self, parent, img, n, color, tr):
        super().__init__(parent)
        self.setWindowTitle(tr("Import image as pixels"))
        self.src, self.n, self.color = img, n, color
        self.result_img = None
        lay = QVBoxLayout(self)
        self.view = PixelView(lambda: (self.result_img or Canvas.blank(n), n // 2), zoom=max(1, 256 // n),
                              bg="Dark", size=256)
        self.view.setFixedSize(264, 264)
        lay.addWidget(self.view, 0, Qt.AlignCenter)
        form = QFormLayout()
        self.thr = QSlider(Qt.Horizontal)
        self.thr.setRange(1, 255)
        self.thr.setValue(128)
        self.inv = QCheckBox()
        self.keep = QCheckBox()
        self.keep.setChecked(True)
        form.addRow(tr("Threshold"), self.thr)
        form.addRow(tr("Invert"), self.inv)
        form.addRow(tr("Keep image colors"), self.keep)
        lay.addLayout(form)
        for w in (self.thr, self.inv, self.keep):
            (w.valueChanged if w is self.thr else w.toggled).connect(self.update_preview)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self.update_preview()

    def update_preview(self):
        self.result_img = to_pixels(self.src, self.n, self.thr.value(), self.inv.isChecked(), self.keep.isChecked(),
                                    self.color)
        self.view.update()


class RecolorDialog(QDialog):
    def __init__(self, parent, src, dst, tr):
        super().__init__(parent)
        self.setWindowTitle(tr("Recolor"))
        self.src, self.dst = QColor(src), QColor(dst)
        form = QFormLayout(self)
        self.src_btn, self.dst_btn = QPushButton(), QPushButton()
        for b, attr in ((self.src_btn, "src"), (self.dst_btn, "dst")):
            b.clicked.connect(lambda _=False, a=attr: self.pick(a, tr))
        self.tol = QSpinBox()
        self.tol.setRange(0, 20)
        self.tol.setSuffix(" %")
        self.scope = QComboBox()
        self.scope.addItems([tr("Current layer"), tr("All layers and frames")])
        form.addRow(tr("Replace color"), self.src_btn)
        form.addRow(tr("With color"), self.dst_btn)
        form.addRow(tr("Tolerance"), self.tol)
        form.addRow(tr("Where"), self.scope)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        form.addRow(bb)
        self.paint_buttons()

    def pick(self, attr, tr):
        c = QColorDialog.getColor(getattr(self, attr), self, tr("Color..."), QColorDialog.ShowAlphaChannel)
        if c.isValid():
            setattr(self, attr, c)
            self.paint_buttons()

    def paint_buttons(self):
        for b, c in ((self.src_btn, self.src), (self.dst_btn, self.dst)):
            b.setStyleSheet(f"background: rgba({c.red()},{c.green()},{c.blue()},{c.alpha()});")


class EditorTab(QWidget):
    def __init__(self, on_apply, tr=lambda s: s):
        """on_apply(path): use this PNG / GIF as the current profile's crosshair."""
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

        # Layers (top of the list = top layer)
        lrow = QHBoxLayout()
        self.layer_list = QListWidget()
        self.layer_list.setFixedHeight(92)
        self.layer_list.currentRowChanged.connect(self._pick_layer)
        self.layer_list.itemChanged.connect(self._layer_visible)
        lrow.addWidget(self.layer_list, 1)
        lbtn = QVBoxLayout()
        for text, tip, fn in (("+", "Add layer", self.canvas.add_layer), ("-", "Delete layer", self.canvas.delete_layer),
                              ("▲", "Move layer up", lambda: self.canvas.move_layer(1)),
                              ("▼", "Move layer down", lambda: self.canvas.move_layer(-1)),
                              ("⤓", "Merge down", self.canvas.merge_down)):
            b = QPushButton(text)
            b.setFixedWidth(30)
            b.setToolTip(tr(tip))
            b.setAccessibleName(tr(tip))
            b.clicked.connect(lambda _=False, fn=fn: (fn(), self.sync_panels()))
            lbtn.addWidget(b)
        lrow.addLayout(lbtn)
        side.addWidget(QLabel(tr("Layers")))
        side.addLayout(lrow)
        row = QHBoxLayout()
        row.addWidget(QLabel(tr("Layer opacity")))
        self.layer_alpha = QSlider(Qt.Horizontal)
        self.layer_alpha.setRange(0, 100)
        self.layer_alpha.valueChanged.connect(self._layer_opacity)
        row.addWidget(self.layer_alpha, 1)
        side.addLayout(row)

        # Frames
        row = QHBoxLayout()
        self.frame_label = QLabel()
        for text, tip, fn in (("◀", "Previous frame", lambda: self._go_frame(-1)),
                              ("▶", "Next frame", lambda: self._go_frame(1)),
                              ("+", "Add frame", self.canvas.add_frame), ("-", "Delete frame", self.canvas.delete_frame)):
            b = QPushButton(text)
            b.setFixedWidth(30)
            b.setToolTip(tr(tip))
            b.setAccessibleName(tr(tip))
            b.clicked.connect(lambda _=False, fn=fn: (fn(), self.sync_panels()))
            row.addWidget(b)
        row.addWidget(self.frame_label)
        self.delay = QSpinBox()
        self.delay.setRange(20, 2000)
        self.delay.setSingleStep(10)
        self.delay.setSuffix(" ms")
        self.delay.setToolTip(tr("Frame delay"))
        self.delay.valueChanged.connect(self._set_delay)
        row.addWidget(self.delay)
        side.addLayout(row)
        row = QHBoxLayout()
        self.onion = QCheckBox(tr("Onion skin"))
        self.onion.toggled.connect(lambda v: (setattr(self.canvas, "onion", v), self.canvas.update()))
        self.play_btn = QPushButton(tr("Play"))
        self.play_btn.setCheckable(True)
        self.play_btn.toggled.connect(self._play)
        self.play_timer = QTimer(self)
        self.play_timer.timeout.connect(self._next_play_frame)
        row.addWidget(self.onion)
        row.addWidget(self.play_btn)
        row.addStretch()
        side.addLayout(row)

        side.addWidget(QLabel(tr("Preview: 1x = real in-game size, 4x zoom")))
        prev = QHBoxLayout()
        src = lambda: (self.canvas.composite(), self.canvas.n // 2)
        for z, size in ((1, 96), (4, 264)):
            v = PixelView(src, zoom=z, bg="Dark", size=size)
            v.setFixedSize(size, 264)
            prev.addWidget(v, 0, Qt.AlignTop)
            setattr(self, f"view{z}", v)
        prev.addStretch()
        side.addLayout(prev)

        buttons = QGridLayout()
        for i, (text, fn) in enumerate((
                ("Undo", lambda: self.canvas.step(True)), ("Redo", lambda: self.canvas.step(False)),
                ("Clear layer", self.clear), ("Load PNG to edit", self.load_png),
                ("Import image...", self.import_image), ("Recolor...", self.recolor),
                ("Save as...", self.save_as), ("Save + Apply", self.save_apply), ("Add to Library", self.add_library))):
            b = QPushButton(tr(text))
            b.clicked.connect(fn)
            buttons.addWidget(b, i // 3, i % 3)
        side.addLayout(buttons)
        self.status = QLabel("")
        self.status.setWordWrap(True)
        side.addWidget(self.status)
        side.addStretch()

        # Ctrl+Z / Ctrl+Y: routed here by the settings window while this tab is open.
        self.update_color_button()
        self.sync_panels()

    # ---------- layer / frame panels ----------
    def sync_panels(self):
        c = self.canvas
        self.layer_list.blockSignals(True)
        self.layer_list.clear()
        for layer in reversed(c.layers):
            it = QListWidgetItem(layer["name"])
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Checked if layer["visible"] else Qt.Unchecked)
            self.layer_list.addItem(it)
        self.layer_list.setCurrentRow(len(c.layers) - 1 - c.cl)
        self.layer_list.blockSignals(False)
        for w, v in ((self.layer_alpha, round(c.layers[c.cl]["opacity"] * 100)), (self.delay, c.frames[c.cf]["delay"])):
            w.blockSignals(True)
            w.setValue(v)
            w.blockSignals(False)
        self.frame_label.setText(f"{self.tr('Frame')} {c.cf + 1}/{len(c.frames)}")
        self.refresh_previews()

    def _pick_layer(self, row):
        if row >= 0:
            self.canvas.cl = len(self.canvas.layers) - 1 - row
            self.sync_panels()

    def _layer_visible(self, item):
        i = len(self.canvas.layers) - 1 - self.layer_list.row(item)
        self.canvas.layers[i]["visible"] = item.checkState() == Qt.Checked
        self.canvas.touched()

    def _layer_opacity(self, v):
        self.canvas.layers[self.canvas.cl]["opacity"] = v / 100
        self.canvas.touched()

    def _go_frame(self, d):
        c = self.canvas
        c.cf = (c.cf + d) % len(c.frames)
        c.touched()

    def _set_delay(self, v):
        self.canvas.frames[self.canvas.cf]["delay"] = v

    def _play(self, on):
        if on and len(self.canvas.frames) > 1:
            self._next_play_frame()
        else:
            self.play_timer.stop()
            self.play_btn.setChecked(False)

    def _next_play_frame(self):
        self._go_frame(1)
        self.sync_panels()
        self.play_timer.start(max(66, self.canvas.frames[self.canvas.cf]["delay"]))  # ~15 fps cap

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
        return all(img.pixelColor(x, y).alpha() == 0 for fr in self.canvas.frames for img in fr["imgs"]
                   for y in range(img.height()) for x in range(img.width()))

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
        self.canvas.set_doc(Canvas.blank(n))
        self.sync_panels()

    def clear(self):
        self.canvas.set_image(Canvas.blank(self.canvas.n))

    def load_png(self):
        path, _ = QFileDialog.getOpenFileName(self, self.tr("Load PNG"), library.CUSTOM_DIR, "PNG (*.png)")
        if not path:
            return
        try:
            img = safe_image.load(path)
        except safe_image.ImageError as e:
            self.say(self.tr(str(e)), True)
            return
        if max(img.width(), img.height()) > SIZES[-1]:
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
        self.canvas.set_doc(canvas)
        self.sync_panels()
        self.path = path

    def import_image(self):
        path, _ = QFileDialog.getOpenFileName(self, self.tr("Import image..."), "",
                                              self.tr("Images") + " (*.png *.jpg *.jpeg *.bmp *.gif *.svg)")
        if not path:
            return
        try:
            img = safe_image.load(path)
        except safe_image.ImageError as e:
            self.say(self.tr(str(e)), True)
            return
        dlg = ImportDialog(self, img, self.canvas.n, self.color, self.tr)
        if dlg.exec() == QDialog.Accepted and dlg.result_img is not None:
            self.canvas.set_image(dlg.result_img)
            self.say(self.tr("Image imported into the current layer."))

    def recolor(self):
        dlg = RecolorDialog(self, self.color, self.color, self.tr)
        if dlg.exec() == QDialog.Accepted:
            n = self.canvas.recolor(dlg.src, dlg.dst, dlg.tol.value() / 100, dlg.scope.currentIndex() == 1)
            self.say(f"{self.tr('Pixels changed')}: {n}")

    # ---------- save ----------
    def say(self, text, error=False):
        self.status.setStyleSheet(f"color: {theme.tokens['danger' if error else 'ok']};")
        self.status.setText(text)

    def animated(self):
        return len(self.canvas.frames) > 1

    def write(self, path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        try:
            if path.lower().endswith(".gif"):
                c = self.canvas
                write_gif(path, [c.composite(f) for f in range(len(c.frames))], [fr["delay"] for fr in c.frames])
            elif not self.canvas.composite().save(path, "PNG"):
                raise OSError
        except (OSError, ValueError, ImportError):
            self.say(self.tr("Could not save the image."), True)
            return False
        self.path = path
        self.say(self.tr("Saved") + f": {os.path.basename(path)}")
        return True

    def auto_path(self):
        ext = "gif" if self.animated() else "png"
        return os.path.join(library.CUSTOM_DIR, time.strftime(f"editor_%Y%m%d_%H%M%S.{ext}"))

    def save_as(self):
        start = self.path or self.auto_path()
        filters = "GIF (*.gif);;PNG (*.png)" if self.animated() else "PNG (*.png);;GIF (*.gif)"
        path, chosen = QFileDialog.getSaveFileName(self, self.tr("Save as..."), start, filters)
        if path:
            ext = ".gif" if "gif" in chosen.lower() else ".png"
            self.write(path if path.lower().endswith((".png", ".gif")) else path + ext)

    def save_apply(self):
        ext = ".gif" if self.animated() else ".png"
        keep = self.path.startswith(library.CUSTOM_DIR) and self.path.lower().endswith(ext)
        if self.write(self.path if keep else self.auto_path()):
            self.on_apply(self.path)

    def add_library(self):
        name, ok = QInputDialog.getText(self, self.tr("Add to Library"), self.tr("Name:"), text="Custom")
        if ok and name.strip() and self.write(self.auto_path()):
            cross = copy.deepcopy(DEFAULT_CROSSHAIR)
            cross["mode"] = "png"
            library.add(name.strip(), cross, self.path)
            self.say(self.tr("Added to library") + f": {name.strip()}")
