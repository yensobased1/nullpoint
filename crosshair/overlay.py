"""Transparent click-through overlay window + the ONE crosshair renderer.

Plain separate top-level window only: no injection, no DirectX hooks, no game memory or pixel access.
The settings preview, library thumbnails and the overlay all draw through render().
"""
import ctypes
import json
import math
import os
import re
import time
from ctypes import wintypes

from PySide6.QtCore import QPointF, QRect, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import (QBrush, QColor, QFont, QGuiApplication, QImage, QMovie, QPainter, QPainterPath,
                           QPainterPathStroker, QPixmap, QPolygonF, QRadialGradient, QTransform)
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


def dash_segments(length, style, thick):
    """[(offset from the center side, length)] for Solid / Dashed / Dotted lines (whole pixels)."""
    if style["kind"] == "solid":
        return [(0, length)]
    # Dots are square (thick x thick). Dashes are always at least 1 px longer, so they never look like dots.
    dash = thick if style["kind"] == "dotted" else max(style["dash"], thick + 1)
    out, pos = [], 0
    while pos < length:
        out.append((pos, min(dash, length - pos)))
        pos += dash + style["gap"]
    return out


def arm_rects(sec, c, top=True, style=None, lens=None):
    """{arm: [rects (x, y, w, h)]} for arms r/l/b/t. gap = px from center to the first pixel of each arm,
    len = px of each arm, thick = px width. lens = per-arm lengths {t, r, b, l} (None = len / vlen)."""
    if not sec["on"]:
        return {}
    t, g = sec["thick"], sec["gap"]
    hl = sec["len"]
    vl = sec["vlen"] if sec["vsep"] else hl
    lens = lens or {"r": hl, "l": hl, "b": vl, "t": vl}
    b = band(c, t)
    near = c + g + t % 2  # first pixel on the +x/+y side (odd sizes skip the center pixel itself)
    far = c - g  # exclusive end on the -x/-y side
    style = style or {"kind": "solid"}
    seg = lambda n: dash_segments(n, style, t) if n > 0 else []
    out = {"r": [(near + off, b, n, t) for off, n in seg(lens["r"])],
           "l": [(far - off - n, b, n, t) for off, n in seg(lens["l"])],
           "b": [(b, near + off, t, n) for off, n in seg(lens["b"])]}
    if top:
        out["t"] = [(b, far - off - n, t, n) for off, n in seg(lens["t"])]
    return out


def line_rects(sec, c, top=True, style=None):
    """All arm rects in one list (mirror-image arms)."""
    return [r for rects in arm_rects(sec, c, top, style).values() for r in rects]


def dot_rects(size, c, shape="square"):
    """Center dot as whole-pixel rows: square, circle or diamond. Pixel-exact at any size (no antialiasing)."""
    a = band(c, size)
    if shape == "square" or size <= 2:
        return [(a, a, size, size)]
    h = size / 2
    out = []
    for j in range(size):
        dy = abs(j + 0.5 - h)
        # Circle: pixel centers inside radius h - 0.25 (keeps 3 px from being a square). Diamond: |dx|+|dy| <= h.
        if shape == "circle":
            w = math.sqrt(max(0.0, (h - 0.25) ** 2 - dy * dy))
        else:
            w = h - dy
        n = sum(1 for i in range(size) if abs(i + 0.5 - h) <= w + 1e-9)
        if n:
            out.append((a + (size - n) // 2, a + j, n, 1))
    return out


def plus_rects(sec, c):
    """Thick '+': two solid bars through the center, no gap."""
    if not sec["on"]:
        return []
    t, r = sec["thick"], sec["gap"] + sec["len"]
    b, w = band(c, t), 2 * r + t % 2
    return [(c - r, b, w, t), (b, c - r, t, w)]


def polygon_path(sec, c, shape):
    """Hexagon / Triangle / Diamond outline: corners gap+len px from the center, line thickness thick."""
    path = QPainterPath()
    r = sec["gap"] + sec["len"]
    if not sec["on"] or r <= 0:
        return path
    n, start = {"hexagon": (6, 0), "triangle": (3, -90), "diamond": (4, -90)}[shape]
    cc = center_point(c, sec["thick"])
    pts = [QPointF(cc + r * math.cos(math.radians(start + i * 360 / n)),
                   cc + r * math.sin(math.radians(start + i * 360 / n))) for i in range(n)]
    poly = QPainterPath()
    poly.addPolygon(QPolygonF(pts + pts[:1]))
    poly.closeSubpath()
    stroker = QPainterPathStroker()
    stroker.setWidth(sec["thick"])
    stroker.setJoinStyle(Qt.MiterJoin)
    return stroker.createStroke(poly)


def text_path(cross, c):
    """1-3 characters, their bounding box centered on pixel c's middle."""
    tx = cross["text"]
    path = QPainterPath()
    if not tx["chars"]:
        return path
    font = QFont(tx["font"]) if tx["font"] else QFont(QGuiApplication.font().family())
    font.setPixelSize(tx["size"])
    font.setBold(tx["bold"])
    path.addText(0, 0, font, tx["chars"])
    box = path.boundingRect()
    return path.translated(c + 0.5 - box.center().x(), c + 0.5 - box.center().y())


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
    o += cross["shadow"]["size"] if cross["shadow"]["on"] else 0
    o += cross["expand"]["px"] if cross["expand"]["on"] else 0  # room for the fully expanded lines
    if cross["mode"] == "text":
        return int(cross["text"]["size"] * 1.2) + o + 2
    r = cross["dot"]["size"] if cross["dot"]["on"] else 1
    arms = cross["arms"]
    for k in ("inner", "outer"):
        s = cross[k]
        if s["on"]:
            r = max(r, s["gap"] + max(s["len"], s["vlen"] if s["vsep"] else s["len"]) + s["thick"])
            if k == "inner" and not arms["link"]:
                r = max(r, s["gap"] + max(arms[a] for a in "trbl") + s["thick"])
    if cross["shape"] in ("square", "chevron", "x", "hexagon", "triangle", "diamond", "plus") or cross["rot"]:
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
def grown(parts, grow):
    """Union of every part grown by `grow` px: rects stay pixel-exact, paths use a miter stroke."""
    sharp, smooth = QPainterPath(), QPainterPath()
    stroker = QPainterPathStroker()
    stroker.setWidth(2 * grow)
    stroker.setJoinStyle(Qt.MiterJoin)
    stroker.setCapStyle(Qt.SquareCap)
    for rects, path, _, _, _ in parts:
        if rects:
            for x, y, w, h in rects:
                sharp.addRect(x - grow, y - grow, w + 2 * grow, h + 2 * grow)
        elif not path.isEmpty():
            smooth.addPath(stroker.createStroke(path).united(path))
    sharp.setFillRule(Qt.WindingFill)
    smooth.setFillRule(Qt.WindingFill)
    return sharp.simplified(), smooth.simplified()


def fill_union(p, sharp, smooth, color):
    p.fillPath(sharp, color)
    if not smooth.isEmpty():
        p.setRenderHint(QPainter.Antialiasing, True)
        p.fillPath(smooth, color)
        p.setRenderHint(QPainter.Antialiasing, False)


def part_brush(cross, color, alpha, reach, c, hue):
    """Solid color, or the center->tip gradient for lines (rainbow wins over gradient)."""
    col = QColor(color)
    col.setAlpha(round(255 * alpha))
    g = cross["gradient"]
    if not reach or not g["on"] or hue is not None:
        return QBrush(col)
    end = QColor("#" + g["c2"])
    end.setAlpha(col.alpha())
    grad = QRadialGradient(QPointF(c + 0.5, c + 0.5), reach)
    grad.setColorAt(0, col)
    grad.setColorAt(1, end)
    return QBrush(grad)


HEX = re.compile(r"[0-9A-Fa-f]{6}")
_halo_cache = {}  # (crosshair, c, spread) -> QImage of the shadow / glow layer: built once, not per frame


def with_spread(cross, spread):
    """Fire expand: the same crosshair with inner/outer gaps grown by spread px."""
    if not spread:
        return cross
    out = dict(cross)
    for k in ("inner", "outer"):
        out[k] = dict(cross[k], gap=cross[k]["gap"] + spread)
    return out


def build_parts(cross, c, hue=None):
    """-> [(rects or None, path or None, QColor, alpha, gradient reach)] in draw order (later parts on top)."""
    cols = part_colors(cross, hue)
    shape = cross["shape"]
    rot = (cross["rot"] + (45 if shape == "x" else 0)) % 360
    parts = []
    if cross["mode"] == "text":
        parts.append((None, text_path(cross, c), cols["lines"], cross["text"]["alpha"], 0))
        return parts
    arms = cross["arms"]
    per_arm = not arms["link"] and shape in ("cross", "t", "x")
    if shape not in ("dot", "circle"):
        for k in ("inner", "outer"):
            sec = cross[k]
            if not sec["on"]:
                continue
            lens = {a: arms[a] for a in "trbl"} if per_arm and k == "inner" else None
            reach = sec["gap"] + (max(lens.values()) if lens else max(sec["len"], sec["vlen"]))
            cc = center_point(c, sec["thick"])
            turn = QTransform().translate(cc, cc).rotate(rot).translate(-cc, -cc)

            def add(rects, color, alpha=sec["alpha"], reach=reach, turn=turn):
                if rot:
                    parts.append((None, turn.map(rect_path(rects)), color, alpha, reach))
                elif rects:
                    parts.append((rects, None, color, alpha, reach))

            if shape in ("chevron", "hexagon", "triangle", "diamond"):
                path = chevron_path(sec, c) if shape == "chevron" else polygon_path(sec, c, shape)
                parts.append((None, turn.map(path) if rot else path, cols["lines"], sec["alpha"], reach))
            elif shape == "square":
                add(square_rects(sec, c), cols["lines"])
            elif shape == "plus":
                add(plus_rects(sec, c), cols["lines"])
            elif per_arm:
                for a, rects in arm_rects(sec, c, top=shape != "t", style=cross["style"], lens=lens).items():
                    v = arms["c" + a]
                    use = hue is None and isinstance(v, str) and HEX.fullmatch(v)
                    add(rects, QColor("#" + v) if use else cols["lines"])
            else:
                add(line_rects(sec, c, top=shape != "t", style=cross["style"]), cols["lines"])
    ring = cross["ring"]
    if ring["on"] or shape == "circle":
        parts.append((None, ring_path(ring, c), cols["ring"], ring["alpha"], 0))
    d = cross["dot"]
    if d["on"]:
        parts.append((dot_rects(d["size"], c, d["shape"]), None, cols["dot"], d["alpha"], 0))
    return parts


def halo_steps(cross):
    """[(grow px beyond the outline, QColor)] outermost first: the shadow (black) or glow (color) rings."""
    sh = cross["shadow"]
    if not (sh["on"] and sh["size"] > 0 and sh["alpha"] > 0):
        return []
    glow = sh["mode"] == "glow"
    base = QColor("#" + sh["color"]) if glow and HEX.fullmatch(str(sh["color"])) else QColor(0, 0, 0)
    n, out = sh["size"], []
    for k in range(n, 0, -1):
        f = (n - k + 1) / n
        col = QColor(base)
        col.setAlpha(round(255 * sh["alpha"] * (f * f if glow else f)))  # glow fades out softer
        out.append((k, col))
    return out


def outline_px(cross):
    ol = cross["outline"]
    return ol["thick"] if ol["on"] and ol["thick"] > 0 else 0


def halo_layer(cross, parts, c, spread):
    """Shadow / glow as one cached image (size 2c+1). Hard-edged steps, so it never blurs into the center."""
    key = (json.dumps(cross, sort_keys=True), c, spread)
    img = _halo_cache.get(key)
    if img is None:
        img = QImage(2 * c + 1, 2 * c + 1, QImage.Format_ARGB32_Premultiplied)
        img.fill(0)
        q = QPainter(img)
        q.setPen(Qt.NoPen)
        q.setCompositionMode(QPainter.CompositionMode_Source)
        o = outline_px(cross)
        for k, col in halo_steps(cross):
            fill_union(q, *grown(parts, o + k), col)
        q.end()
        if len(_halo_cache) >= 24:
            _halo_cache.clear()
        _halo_cache[key] = img
    return img


def render(p: QPainter, cross, c, pixmap=None, sx=1.0, hue=None, spread=0):
    """Draw the crosshair with its center on pixel (c, c). Layers: shadow/glow, outline, fill.
    Lines/dot/box/plus: integer rects, antialiasing off = pixel exact. Ring/polygons/text/rotated: antialiased.
    sx != 1 stretches horizontally (stretched-resolution helper). hue = rainbow color (0..1) or None.
    spread = fire-expand px added to the line gaps."""
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
    shaped = with_spread(cross, spread)
    parts = build_parts(shaped, c, hue)
    if halo_steps(cross):
        p.drawImage(0, 0, halo_layer(shaped, parts, c, spread))
    o = outline_px(cross)
    if o:
        col = QColor(part_colors(cross, hue)["outline"])
        col.setAlpha(round(255 * cross["outline"]["alpha"]))
        p.setCompositionMode(QPainter.CompositionMode_Source)
        fill_union(p, *grown(parts, o), col)  # union: overlaps don't double the opacity
    # Source mode: fill replaces the outline under it, so fill opacity is exactly what you set.
    p.setCompositionMode(QPainter.CompositionMode_Source)
    for rects, path, color, alpha, reach in parts:
        brush = part_brush(cross, color, alpha, reach, c, hue)
        if rects:
            for x, y, w, h in rects:
                p.fillRect(QRect(x, y, w, h), brush)
        elif not path.isEmpty():
            p.setRenderHint(QPainter.Antialiasing, True)
            p.fillPath(path, brush)
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
        self.low_power = False  # set by the app: pauses rainbow / GIF animation
        self.reduce_motion = False  # set by the app: no rainbow, first GIF frame only, instant fire expand
        self.spread = 0.0  # current fire-expand px
        self.firing = False
        self._fire_from, self._fire_t0 = 0.0, 0.0
        self.fire_timer = QTimer(self, interval=FRAME_MS)  # runs only while the lines are moving
        self.fire_timer.timeout.connect(self._fire_tick)
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
            self.movie.setPaused(paused or self.reduce_motion)
            if self.reduce_motion and self.movie.currentFrameNumber() != 0:
                self.movie.jumpToFrame(0)
                self.pixmap = transform_image(self.movie.currentImage(), cross["png"])
        if not (cross["mode"] == "lines" and cross["expand"]["on"]):
            self.firing, self.spread = False, 0.0
            self.fire_timer.stop()
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
        if (now - self._last_frame) * 1000 < FRAME_MS or not self.isVisible() or self.low_power \
                or self.reduce_motion:
            return  # cap at ~15 fps and skip work while hidden
        self._last_frame = now
        self.pixmap = transform_image(self.movie.currentImage(), self.cross["png"])
        self.update()
        self.frame.emit()

    def _update_timer(self):
        want = self.isVisible() and self.cross is not None and self.cross["mode"] != "png" \
            and self.cross["rainbow"]["on"] and not self.low_power and not self.reduce_motion
        self.hue = (self.hue or 0.0) if want else None
        if want and not self.timer.isActive():
            self.timer.start()
        elif not want:
            self.timer.stop()

    def _tick(self):
        self.hue = (self.hue + 0.004 * self.cross["rainbow"]["speed"]) % 1.0
        self.update()
        self.frame.emit()

    def set_firing(self, down):
        """Left mouse held in a game (from the app's key poll): move the lines out, back on release."""
        cross = self.cross
        down = bool(down) and cross is not None and cross["mode"] == "lines" and cross["expand"]["on"]
        if down == self.firing:
            return
        self.firing = down
        self._fire_from, self._fire_t0 = self.spread, time.monotonic()
        self._fire_tick()

    def _fire_tick(self):
        ex = self.cross["expand"]
        target = float(ex["px"]) if self.firing else 0.0
        if self.reduce_motion or ex["ms"] <= 0:
            val = target
        else:
            f = min(1.0, (time.monotonic() - self._fire_t0) * 1000 / ex["ms"])
            val = self._fire_from + (target - self._fire_from) * f
        changed = round(val) != round(self.spread)
        self.spread = val
        if changed:
            self.update()
            self.frame.emit()
        if val == target:
            self.fire_timer.stop()
        elif not self.fire_timer.isActive():
            self.fire_timer.start()

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
        render(p, self.cross, self.c if c is None else c, self.pixmap, self.sx, self.hue, round(self.spread))

    def nativeEvent(self, event_type, message):
        msg = wintypes.MSG.from_address(int(message))
        if msg.message == WM_HOTKEY:
            self.hotkey.emit(msg.wParam)
            return True, 0
        return False, 0
