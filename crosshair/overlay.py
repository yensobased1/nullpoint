"""Transparent click-through overlay window + the ONE crosshair renderer.

Plain separate top-level window only: no injection, no DirectX hooks, no game memory or pixel access.
The settings preview, library thumbnails and the overlay all draw through render().
"""
import ctypes
import os
import time
from ctypes import wintypes

from PySide6.QtCore import QRect, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import (QColor, QImage, QMovie, QPainter, QPainterPath, QPainterPathStroker, QPixmap,
                           QTransform)
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QWidget

user32 = ctypes.windll.user32
user32.SetWindowLongPtrW.restype = ctypes.c_ssize_t
user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                                ctypes.c_int, ctypes.c_int, ctypes.c_uint]
user32.SetWindowDisplayAffinity.argtypes = [wintypes.HWND, wintypes.DWORD]

GWL_EXSTYLE = -20
WS_EX_LAYERED, WS_EX_TRANSPARENT, WS_EX_TOOLWINDOW, WS_EX_NOACTIVATE, WS_EX_TOPMOST = (
    0x80000, 0x20, 0x80, 0x08000000, 0x8)
HWND_TOPMOST = wintypes.HWND(-1)
SWP_NOSIZE, SWP_NOMOVE, SWP_NOACTIVATE, SWP_SHOWWINDOW = 0x1, 0x2, 0x10, 0x40
WM_HOTKEY = 0x0312
WDA_NONE, WDA_EXCLUDEFROMCAPTURE = 0x0, 0x11
FRAME_MS = 66  # ~15 fps cap for rainbow / GIF


# ---------- geometry ----------
def band(c, size):
    """First pixel of a size-px band centered on the screen center.
    Pixel c's left/top edge IS the true screen center (window placed at W//2), so even sizes are
    exactly centered on that edge and odd sizes on pixel c: never more than 0.5 px apart, never 1 px drift."""
    return c - size // 2


def center_point(c, size):
    """Float center matching band(): pixel c's middle for odd sizes, its top-left edge for even."""
    return c + 0.5 * (size % 2)


def line_rects(sec, c, top=True):
    """Rects (x, y, w, h) for the arms. gap = px from center to the first pixel of each arm,
    len = px of each arm, thick = px width. All arms are mirror images of each other."""
    if not sec["on"]:
        return []
    t, g = sec["thick"], sec["gap"]
    hl = sec["len"]
    vl = sec["vlen"] if sec["vsep"] else hl
    b = band(c, t)
    near = c + g + t % 2  # first pixel on the +x/+y side (odd sizes skip the center pixel itself)
    far = c - g  # exclusive end on the -x/-y side
    out = []
    if hl > 0:
        out += [(near, b, hl, t), (far - hl, b, hl, t)]  # right, left
    if vl > 0:
        out.append((b, near, t, vl))  # down
        if top:
            out.append((b, far - vl, t, vl))  # up
    return out


def square_rects(sec, c):
    """Box outline: outer edge gap+len px from the center, line thickness thick."""
    if not sec["on"] or sec["len"] + sec["gap"] <= 0:
        return []
    t, r = sec["thick"], sec["gap"] + sec["len"]
    x0 = c - r
    w = 2 * r + t % 2
    if w <= 2 * t:
        return [(x0, x0, w, w)]
    return [(x0, x0, w, t), (x0, x0 + w - t, w, t), (x0, x0 + t, t, w - 2 * t), (x0 + w - t, x0 + t, t, w - 2 * t)]


def chevron_path(sec, c):
    """'^': two arms from the apex at the center, going down-left and down-right at 45 degrees."""
    path = QPainterPath()
    if not sec["on"] or sec["len"] <= 0:
        return path
    t = sec["thick"]
    cc = center_point(c, t)
    for angle in (45, 135):
        arm = QPainterPath()
        arm.addRect(QRectF(sec["gap"], -t / 2, sec["len"], t))
        path.addPath(QTransform().translate(cc, cc).rotate(angle).map(arm))
    return path


def ring_path(ring, c):
    t = ring["thick"]
    cc = center_point(c, t)
    big, small = ring["radius"] + t / 2, max(0.0, ring["radius"] - t / 2)
    outer = QRectF(cc - big, cc - big, 2 * big, 2 * big)
    inner = QRectF(cc - small, cc - small, 2 * small, 2 * small)
    n = ring["gaps"]
    segs = [(0.0, 360.0)] if n == 0 else [
        (ring["gaprot"] + i * 360 / n + ring["gapsize"] / 2, 360 / n - ring["gapsize"]) for i in range(n)]
    path = QPainterPath()
    for a0, span in segs:
        if span <= 0:
            continue
        path.arcMoveTo(outer, a0)
        path.arcTo(outer, a0, span)
        if small > 0:
            path.arcTo(inner, a0 + span, -span)
        else:
            path.lineTo(cc, cc)
        path.closeSubpath()
    return path


def rect_path(rects):
    path = QPainterPath()
    for x, y, w, h in rects:
        path.addRect(x, y, w, h)
    return path


def extent(cross, pixmap=None):
    """Half-size in px the window needs so nothing is clipped (rotation-safe)."""
    if cross["mode"] == "png":
        if pixmap is None or pixmap.isNull():
            return 8
        return max(pixmap.width(), pixmap.height()) // 2 + 2
    o = cross["outline"]["thick"] if cross["outline"]["on"] else 0
    r = cross["dot"]["size"]
    for k in ("inner", "outer"):
        s = cross[k]
        r = max(r, s["gap"] + max(s["len"], s["vlen"]) + s["thick"])
    if cross["shape"] in ("square", "chevron", "x") or cross["rot"]:
        r = int(r * 1.42) + 1  # diagonal of a box / rotated arm
    ring = cross["ring"]
    if ring["on"] or cross["shape"] == "circle":
        r = max(r, ring["radius"] + ring["thick"])
    return r + o + 2


def part_colors(cross, hue=None):
    """-> dict lines/dot/ring/outline QColor (alpha applied later per part)."""
    cols = cross["colors"]
    if hue is not None:
        main = QColor.fromHsvF(hue, cross["rainbow"]["sat"], 1.0)
        parts = dict.fromkeys(("lines", "dot", "ring"), main)
    elif cols["same"]:
        parts = dict.fromkeys(("lines", "dot", "ring"), QColor("#" + cross["color"]))
    else:
        parts = {k: QColor("#" + cols[k]) for k in ("lines", "dot", "ring")}
    parts["outline"] = QColor("#000000") if cols["same"] else QColor("#" + cols["outline"])
    return parts


# ---------- images ----------
def transform_image(img, png, allow_scale=True):
    scale = png["scale"] / 100.0 if allow_scale else 1.0
    if scale != 1.0:
        w, h = max(1, round(img.width() * scale)), max(1, round(img.height() * scale))
        # Whole-number scales stay pixel-sharp; others are smoothed.
        mode = Qt.FastTransformation if png["scale"] % 100 == 0 else Qt.SmoothTransformation
        img = img.scaled(w, h, Qt.IgnoreAspectRatio, mode)
    if png["rot"]:
        img = img.transformed(QTransform().rotate(png["rot"]))
    return QPixmap.fromImage(img)


def png_pixmap(path, png):
    """Load + scale + rotate a PNG/SVG (or a GIF's first frame) once; caller caches the result."""
    if not path or not os.path.exists(path):
        return None
    if path.lower().endswith(".svg"):
        r = QSvgRenderer(path)
        if not r.isValid():
            return None
        size = r.defaultSize() * (png["scale"] / 100.0)
        img = QImage(max(1, size.width()), max(1, size.height()), QImage.Format_ARGB32_Premultiplied)
        img.fill(0)
        p = QPainter(img)
        r.render(p)  # vector render at the exact target size: crisp at any scale
        p.end()
        return transform_image(img, png, allow_scale=False)
    img = QImage(path)
    return None if img.isNull() else transform_image(img, png)


# ---------- the renderer ----------
def render(p: QPainter, cross, c, pixmap=None, sx=1.0, hue=None):
    """Draw the crosshair with its center on pixel (c, c).
    Lines/dot/box: integer rects, antialiasing off = pixel exact. Ring/chevron/rotated: antialiased.
    sx != 1 stretches horizontally (stretched-resolution helper). hue = rainbow color (0..1) or None."""
    p.setRenderHint(QPainter.Antialiasing, False)
    p.setPen(Qt.NoPen)
    if sx != 1.0:
        p.translate(c, 0)  # stretch around the true center (pixel c's left edge)
        p.scale(sx, 1)
        p.translate(-c, 0)
    if cross["mode"] == "png":
        if pixmap is not None and not pixmap.isNull():
            p.setOpacity(cross["png"]["alpha"])
            # Image center pixel (w//2, h//2) lands on (c, c).
            p.drawPixmap(c - pixmap.width() // 2, c - pixmap.height() // 2, pixmap)
            p.setOpacity(1.0)
        return
    cols = part_colors(cross, hue)
    shape = cross["shape"]
    rot = (cross["rot"] + (45 if shape == "x" else 0)) % 360
    parts = []  # (rects or None, path or None, color, alpha)
    if shape not in ("dot", "circle"):
        for k in ("inner", "outer"):
            sec = cross[k]
            if not sec["on"]:
                continue
            if shape == "chevron":
                path = chevron_path(sec, c)
                if rot:
                    cc = center_point(c, sec["thick"])
                    path = QTransform().translate(cc, cc).rotate(rot).translate(-cc, -cc).map(path)
                parts.append((None, path, cols["lines"], sec["alpha"]))
                continue
            rects = square_rects(sec, c) if shape == "square" else line_rects(sec, c, top=shape != "t")
            if rot:
                cc = center_point(c, sec["thick"])
                path = QTransform().translate(cc, cc).rotate(rot).translate(-cc, -cc).map(rect_path(rects))
                parts.append((None, path, cols["lines"], sec["alpha"]))
            elif rects:
                parts.append((rects, None, cols["lines"], sec["alpha"]))
    ring = cross["ring"]
    if ring["on"] or shape == "circle":
        parts.append((None, ring_path(ring, c), cols["ring"], ring["alpha"]))
    d = cross["dot"]
    if d["on"]:
        a = band(c, d["size"])
        parts.append(([(a, a, d["size"], d["size"])], None, cols["dot"], d["alpha"]))

    ol = cross["outline"]
    if ol["on"] and ol["thick"] > 0:
        o = ol["thick"]
        col = QColor(cols["outline"])
        col.setAlpha(round(255 * ol["alpha"]))
        # Union so overlaps don't double the opacity. Rect outlines = rects grown o px on every side.
        sharp, smooth = QPainterPath(), QPainterPath()
        stroker = QPainterPathStroker()
        stroker.setWidth(2 * o)
        stroker.setJoinStyle(Qt.MiterJoin)
        stroker.setCapStyle(Qt.SquareCap)
        for rects, path, _, _ in parts:
            if rects:
                for x, y, w, h in rects:
                    sharp.addRect(x - o, y - o, w + 2 * o, h + 2 * o)
            else:
                smooth.addPath(stroker.createStroke(path).united(path))
        sharp.setFillRule(Qt.WindingFill)
        smooth.setFillRule(Qt.WindingFill)
        p.fillPath(sharp.simplified(), col)
        if not smooth.isEmpty():
            p.setRenderHint(QPainter.Antialiasing, True)
            p.fillPath(smooth.simplified(), col)
            p.setRenderHint(QPainter.Antialiasing, False)
    # Source mode: fill replaces the outline under it, so fill opacity is exactly what you set.
    p.setCompositionMode(QPainter.CompositionMode_Source)
    for rects, path, color, alpha in parts:
        col = QColor(color)
        col.setAlpha(round(255 * alpha))
        if rects:
            for x, y, w, h in rects:
                p.fillRect(QRect(x, y, w, h), col)
        else:
            p.setRenderHint(QPainter.Antialiasing, True)
            p.fillPath(path, col)
            p.setRenderHint(QPainter.Antialiasing, False)
    p.setCompositionMode(QPainter.CompositionMode_SourceOver)


class Overlay(QWidget):
    hotkey = Signal(int)
    frame = Signal()  # an animation frame was drawn (rainbow/GIF); the preview listens

    def __init__(self):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
                         | Qt.WindowTransparentForInput | Qt.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.cross = None
        self.pixmap = None
        self._png_key = None
        self.movie = None
        self.paused = False
        self.hue = None
        self.c = 8
        self.sx = 1.0
        self.center = (0, 0)
        self._last_frame = 0.0
        self.timer = QTimer(self, interval=FRAME_MS)  # rainbow only; runs only while needed
        self.timer.timeout.connect(self._tick)
        self.hwnd = int(self.winId())
        ex = user32.GetWindowLongPtrW(self.hwnd, GWL_EXSTYLE)
        user32.SetWindowLongPtrW(self.hwnd, GWL_EXSTYLE, ex | WS_EX_LAYERED | WS_EX_TRANSPARENT
                                 | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE | WS_EX_TOPMOST)

    def set_capture_hidden(self, hidden):
        """Stream-safe: hide from OBS/screenshots (Windows 10 2004+). Returns False if unsupported."""
        return bool(user32.SetWindowDisplayAffinity(self.hwnd, WDA_EXCLUDEFROMCAPTURE if hidden else WDA_NONE))

    def set_crosshair(self, cross, png_path, sx=1.0, paused=False):
        self.cross = cross
        self.sx = sx
        self.paused = paused
        img_mode = cross["mode"] == "png"
        gif = img_mode and png_path.lower().endswith(".gif") and os.path.exists(png_path)
        key = (png_path, cross["png"]["scale"], cross["png"]["rot"]) if img_mode else None
        if key != self._png_key:  # only touch the disk when the image itself changes
            self._png_key = key
            self._set_movie(png_path if gif else None)
            self.pixmap = png_pixmap(png_path, cross["png"]) if key else None
        if self.movie:
            self.movie.setPaused(paused)
        self.c = round(extent(cross, self.pixmap) * max(1.0, sx))
        self._update_timer()
        self._place()
        self.update()

    def _set_movie(self, path):
        if self.movie:
            self.movie.stop()
            self.movie.deleteLater()
            self.movie = None
        if path:
            self.movie = QMovie(path)
            self.movie.frameChanged.connect(self._gif_frame)
            self.movie.start()

    def _gif_frame(self, _):
        now = time.monotonic()
        if (now - self._last_frame) * 1000 < FRAME_MS or not self.isVisible():
            return  # cap at ~15 fps and skip work while hidden
        self._last_frame = now
        self.pixmap = transform_image(self.movie.currentImage(), self.cross["png"])
        self.update()
        self.frame.emit()

    def _update_timer(self):
        want = self.isVisible() and self.cross is not None and self.cross["mode"] == "lines" \
            and self.cross["rainbow"]["on"]
        self.hue = (self.hue or 0.0) if want else None
        if want and not self.timer.isActive():
            self.timer.start()
        elif not want:
            self.timer.stop()

    def _tick(self):
        self.hue = (self.hue + 0.004 * self.cross["rainbow"]["speed"]) % 1.0
        self.update()
        self.frame.emit()

    def showEvent(self, e):
        super().showEvent(e)
        self._update_timer()

    def hideEvent(self, e):
        super().hideEvent(e)
        self._update_timer()

    def set_center(self, x, y):
        """(x, y) = physical screen pixel the crosshair center must sit on."""
        if (x, y) != self.center:
            self.center = (x, y)
            self._place()

    def _place(self):
        size = 2 * self.c + 1
        x, y = self.center[0] - self.c, self.center[1] - self.c
        if self.geometry() != QRect(x, y, size, size):
            self.setGeometry(x, y, size, size)
        self.raise_top()

    def raise_top(self):
        flags = SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE
        if self.isVisible():
            flags |= SWP_SHOWWINDOW
        user32.SetWindowPos(self.hwnd, HWND_TOPMOST, 0, 0, 0, 0, flags)

    def paintEvent(self, _):
        if self.cross is None:
            return
        p = QPainter(self)
        self.draw(p)
        p.end()

    def draw(self, p, c=None):
        """Render the current state; the settings preview uses this too."""
        render(p, self.cross, self.c if c is None else c, self.pixmap, self.sx, self.hue)

    def nativeEvent(self, event_type, message):
        msg = wintypes.MSG.from_address(int(message))
        if msg.message == WM_HOTKEY:
            self.hotkey.emit(msg.wParam)
            return True, 0
        return False, 0
