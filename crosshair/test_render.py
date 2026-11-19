"""Pixel tests for the shared renderer and the editor PNG round trip. Run: python -m unittest test_render"""
import copy
import os
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtGui import QColor, QImage  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

import config  # noqa: E402
import overlay  # noqa: E402
from editor import EditorTab, line_points  # noqa: E402
from preview import render_image  # noqa: E402

app = QApplication.instance() or QApplication([])


def cross(**kw):
    c = copy.deepcopy(config.DEFAULT_CROSSHAIR)
    c["dot"]["on"] = c["outline"]["on"] = False
    for k, v in kw.items():
        sec, field = k.split("__")
        c[sec][field] = v
    return c


def draw(cr, pixmap=None):
    c = overlay.extent(cr, pixmap)
    return render_image(lambda p, cc: overlay.render(p, cr, cc, pixmap), c), c


def pixels(img, c, test):
    return {(x - c, y - c) for y in range(img.height()) for x in range(img.width())
            if test(img.pixelColor(x, y))}


def rect_set(*rects):
    """Expected pixels, written by hand relative to the center pixel."""
    return {(x + i, y + j) for x, y, w, h in rects for i in range(w) for j in range(h)}


is_fill = lambda col: col.alpha() > 0 and col.green() > 0  # cyan
is_outline = lambda col: col.alpha() > 0 and col.green() == 0  # black


class RenderTests(unittest.TestCase):
    def check(self, cr, expected):
        img, c = draw(cr)
        self.assertEqual(pixels(img, c, is_fill), expected)

    def test_even_thickness_centered_on_screen_center(self):
        # thick 2 -> rows -1..0 (pixel 0's top edge is the true center); gap 3; len 4
        self.check(cross(inner__len=4, inner__thick=2, inner__gap=3),
                   rect_set((3, -1, 4, 2), (-7, -1, 4, 2), (-1, 3, 2, 4), (-1, -7, 2, 4)))

    def test_odd_thickness_centered_on_center_pixel(self):
        # thick 1 -> row 0; arms mirror around pixel 0: +4..+7 and -7..-4 (3 empty px each side)
        self.check(cross(inner__len=4, inner__thick=1, inner__gap=3),
                   rect_set((4, 0, 4, 1), (-7, 0, 4, 1), (0, 4, 1, 4), (0, -7, 1, 4)))

    def test_thick3_gap0(self):
        self.check(cross(inner__len=5, inner__thick=3, inner__gap=0),
                   rect_set((1, -1, 5, 3), (-5, -1, 5, 3), (-1, 1, 3, 5), (-1, -5, 3, 5)))

    def test_smallest_values_still_visible(self):
        self.check(cross(inner__len=1, inner__thick=1, inner__gap=0),
                   rect_set((1, 0, 1, 1), (-1, 0, 1, 1), (0, 1, 1, 1), (0, -1, 1, 1)))

    def test_outline_wraps_without_resizing(self):
        cr = cross(inner__len=4, inner__thick=2, inner__gap=3, outline__on=True, outline__thick=1,
                   outline__alpha=1.0)
        img, c = draw(cr)
        fill = rect_set((3, -1, 4, 2), (-7, -1, 4, 2), (-1, 3, 2, 4), (-1, -7, 2, 4))
        grown = rect_set((2, -2, 6, 4), (-8, -2, 6, 4), (-2, 2, 4, 6), (-2, -8, 4, 6))
        self.assertEqual(pixels(img, c, is_fill), fill)
        self.assertEqual(pixels(img, c, is_outline), grown - fill)

    def test_t_shape_has_no_top_arm(self):
        cr = cross(inner__len=4, inner__thick=1, inner__gap=3)
        cr["shape"] = "t"
        self.check(cr, rect_set((4, 0, 4, 1), (-7, 0, 4, 1), (0, 4, 1, 4)))

    def test_square_box(self):
        cr = cross(inner__len=2, inner__thick=1, inner__gap=2)
        cr["shape"] = "square"
        self.check(cr, rect_set((-4, -4, 9, 1), (-4, 4, 9, 1), (-4, -3, 1, 7), (4, -3, 1, 7)))

    def test_ring_and_rotated_shapes_draw(self):
        for shape, extra in (("circle", {}), ("x", {}), ("chevron", {}), ("cross", {"rot": 30})):
            cr = cross(inner__len=5, inner__thick=2, inner__gap=2)
            cr["shape"] = shape
            cr.update(extra)
            cr["ring"].update(radius=8, thick=2)
            img, c = draw(cr)
            px = pixels(img, c, is_fill)
            self.assertGreater(len(px), 10, shape)
            if shape == "circle":  # pixels sit on the radius, nothing at the center
                self.assertNotIn((0, 0), px)
                self.assertIn((8, 0), px)

    def test_dashed_lines(self):
        cr = cross(inner__len=6, inner__thick=1, inner__gap=3, inner__vlen=0, inner__vsep=True)
        cr["style"].update(kind="dashed", dash=2, gap=1)
        self.check(cr, rect_set((4, 0, 2, 1), (7, 0, 2, 1), (-5, 0, 2, 1), (-8, 0, 2, 1)))

    def test_plus_is_solid_through_center(self):
        cr = cross(inner__len=2, inner__thick=1, inner__gap=1)
        cr["shape"] = "plus"
        self.check(cr, rect_set((-3, 0, 7, 1), (0, -3, 1, 7)))

    def test_shadow_sits_outside_outline_and_never_on_fill(self):
        cr = cross(inner__len=4, inner__thick=2, inner__gap=3, outline__on=True, outline__thick=1,
                   outline__alpha=1.0)
        cr["shadow"].update(on=True, size=2, alpha=1.0)
        img, c = draw(cr)
        fill = rect_set((3, -1, 4, 2), (-7, -1, 4, 2), (-1, 3, 2, 4), (-1, -7, 2, 4))
        self.assertEqual(pixels(img, c, is_fill), fill)
        dark = pixels(img, c, is_outline)
        self.assertIn((8, 0), dark)  # 1 px outline + 1 px shadow to the right of the right arm (ends at +6)
        self.assertIn((9, 0), dark)
        self.assertNotIn((10, 0), dark)

    def test_text_is_centered(self):
        cr = cross()
        cr["mode"] = "text"
        cr["text"].update(chars="+", size=30)
        img, c = draw(cr)
        px = pixels(img, c, is_fill)
        xs, ys = [x for x, _ in px], [y for _, y in px]
        self.assertLessEqual(abs((min(xs) + max(xs)) / 2), 1)
        self.assertLessEqual(abs((min(ys) + max(ys)) / 2), 1)

    def test_new_polygon_shapes_draw(self):
        for shape in ("hexagon", "triangle", "diamond"):
            cr = cross(inner__len=6, inner__thick=2, inner__gap=2)
            cr["shape"] = shape
            img, c = draw(cr)
            px = pixels(img, c, is_fill)
            self.assertGreater(len(px), 20, shape)
            self.assertNotIn((0, 0), px, shape)

    def test_dot_sizes_and_opacity(self):
        for size, rect in ((1, (0, 0, 1, 1)), (2, (-1, -1, 2, 2)), (3, (-1, -1, 3, 3))):
            cr = cross(inner__on=False, dot__on=True, dot__size=size, dot__alpha=0.5)
            img, c = draw(cr)
            self.assertEqual(pixels(img, c, is_fill), rect_set(rect), size)
            self.assertEqual(img.pixelColor(c, c).alpha(), 128)


class EditorTests(unittest.TestCase):
    def test_strokes_have_no_gaps(self):
        pts = list(line_points(0, 0, 13, 5))
        self.assertEqual(pts[-1], (13, 5))
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            self.assertLessEqual(max(abs(x1 - x0), abs(y1 - y0)), 1)

    def test_saved_png_shows_same_pixels_in_image_mode(self):
        ed = EditorTab(lambda path: None)
        img = ed.canvas.img
        n = img.width()
        for x, y, col in ((n // 2, n // 2, "#ff0000"), (n // 2 - 1, n // 2 - 1, "#00ff00"), (0, 0, "#0000ff"),
                          (n - 1, 3, "#ffffff")):
            img.setPixelColor(x, y, QColor(col))
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "t.png")
            self.assertTrue(ed.write(path))
            saved = QImage(path).convertToFormat(QImage.Format_ARGB32)
            self.assertEqual(saved, img.convertToFormat(QImage.Format_ARGB32))  # exact pixels, transparent bg
            cr = copy.deepcopy(config.DEFAULT_CROSSHAIR)
            cr["mode"] = "png"
            pm = overlay.png_pixmap(path, cr["png"])
            out, c = draw(cr, pm)
        for y in range(n):
            for x in range(n):
                want, got = img.pixelColor(x, y), out.pixelColor(c - n // 2 + x, c - n // 2 + y)
                self.assertEqual(want.rgba(), got.rgba(), (x, y))


if __name__ == "__main__":
    unittest.main()
