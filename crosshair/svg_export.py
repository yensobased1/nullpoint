"""Export the current crosshair as a clean vector .svg, built from the same parts as the shared renderer.

The app draws with "Source" composition (fill replaces the outline under it). SVG only blends, so every layer
here is the renderer's shape minus whatever is drawn on top of it: the file looks the same as the overlay.
"""
import base64
from xml.sax.saxutils import quoteattr  # nosec B406 - only escapes our own output, parses nothing

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, Qt
from PySide6.QtGui import QPainterPath

import overlay


def path_d(path):
    """QPainterPath -> SVG path data."""
    out, i, n = [], 0, path.elementCount()
    f = lambda v: f"{round(v, 3):g}"
    while i < n:
        e = path.elementAt(i)
        if e.type == QPainterPath.MoveToElement:
            out.append(f"M{f(e.x)} {f(e.y)}")
        elif e.type == QPainterPath.LineToElement:
            out.append(f"L{f(e.x)} {f(e.y)}")
        elif e.type == QPainterPath.CurveToElement and i + 2 < n:
            c2, end = path.elementAt(i + 1), path.elementAt(i + 2)
            out.append(f"C{f(e.x)} {f(e.y)} {f(c2.x)} {f(c2.y)} {f(end.x)} {f(end.y)}")
            i += 2
        i += 1
    return "".join(out)


def part_path(rects, path):
    return overlay.rect_path(rects) if rects else path


def union(paths):
    out = QPainterPath()
    out.setFillRule(Qt.WindingFill)
    for p in paths:
        out.addPath(p)
    return out.simplified()


def grown_path(parts, px):
    sharp, smooth = overlay.grown(parts, px)
    return union([sharp, smooth])


def color_attrs(col, alpha=None):
    a = col.alphaF() if alpha is None else alpha
    return f'fill="{col.name()}" fill-opacity="{round(a, 3):g}"'


def element(path, attrs, crisp):
    if path.isEmpty():
        return ""
    rule = "evenodd" if path.fillRule() == Qt.OddEvenFill else "nonzero"
    edges = ' shape-rendering="crispEdges"' if crisp else ""
    return f'<path d="{path_d(path)}" fill-rule="{rule}"{edges} {attrs}/>'


def image_svg(pixmap, cross):
    buf = QBuffer(data := QByteArray())
    buf.open(QIODevice.WriteOnly)
    pixmap.toImage().save(buf, "PNG")
    w, h = pixmap.width(), pixmap.height()
    uri = "data:image/png;base64," + base64.b64encode(bytes(data)).decode()
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
            f'<image width="{w}" height="{h}" opacity="{cross["png"]["alpha"]:g}" '
            f'style="image-rendering:pixelated" href={quoteattr(uri)}/></svg>\n')


def to_svg(cross, pixmap=None):
    """Crosshair dict -> SVG text. Image mode embeds the image itself (PNG data)."""
    if cross["mode"] == "png":
        return image_svg(pixmap, cross) if pixmap is not None and not pixmap.isNull() else ""
    c = overlay.extent(cross)
    size = 2 * c + 1
    parts = overlay.build_parts(cross, c)
    crisp = all(r for r, *_ in parts) and not cross["rot"]
    fills = [part_path(r, p) for r, p, *_ in parts]
    body, defs = [], []
    o = overlay.outline_px(cross)
    covered = union(fills)
    # Halo rings, outermost first: each ring = its grown area minus the next one in.
    steps = overlay.halo_steps(cross)
    for i, (k, col) in enumerate(steps):
        inner = grown_path(parts, o + k - 1) if k - 1 + o > 0 else covered
        body.append(element(grown_path(parts, o + k).subtracted(inner), color_attrs(col), crisp))
    if o:
        col = overlay.part_colors(cross)["outline"]
        body.append(element(grown_path(parts, o).subtracted(covered), color_attrs(col, cross["outline"]["alpha"]), crisp))
    for i, (rects, path, color, alpha, reach) in enumerate(parts):
        shape = fills[i]
        later = union(fills[i + 1:]) if i + 1 < len(fills) else None
        if later is not None and not later.isEmpty():
            shape = shape.subtracted(later)
        g = cross["gradient"]
        if reach and g["on"]:
            gid = f"g{i}"
            defs.append(f'<radialGradient id="{gid}" gradientUnits="userSpaceOnUse" cx="{c + 0.5}" cy="{c + 0.5}" '
                        f'r="{reach}"><stop offset="0" stop-color="{color.name()}"/>'
                        f'<stop offset="1" stop-color="#{g["c2"]}"/></radialGradient>')
            attrs = f'fill="url(#{gid})" fill-opacity="{round(alpha, 3):g}"'
        else:
            attrs = color_attrs(color, alpha)
        body.append(element(shape, attrs, crisp and rects is not None))
    head = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 {size} {size}">')
    return head + (f"<defs>{''.join(defs)}</defs>" if defs else "") + "".join(b for b in body if b) + "</svg>\n"
