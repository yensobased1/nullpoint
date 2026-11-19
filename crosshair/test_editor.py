"""v2.2 editor: shape tools, mirror with every tool, layers, frames + GIF, image import, recolor."""
import os
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtGui import QColor, QImage, QImageReader
from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])

import editor  # noqa: E402
from editor import EditorTab, ellipse_points, rect_points, to_pixels  # noqa: E402

RED, GREEN = QColor("#ff0000"), QColor("#00ff00")


def solid(img):
    return {(x, y) for y in range(img.height()) for x in range(img.width()) if img.pixelColor(x, y).alpha()}


class ShapeTests(unittest.TestCase):
    def test_rectangles(self):
        self.assertEqual(len(set(rect_points(0, 0, 4, 2))), 12)  # outline of 5x3
        self.assertEqual(len(set(rect_points(4, 2, 0, 0, filled=True))), 15)

    def test_ellipse_symmetric_and_filled_contains_outline(self):
        for box in ((0, 0, 8, 8), (0, 0, 9, 5), (3, 3, 4, 4)):
            out, fill = set(ellipse_points(*box)), set(ellipse_points(*box, filled=True))
            self.assertTrue(out <= fill and out)
            x0, y0, x1, y1 = box
            for s in (out, fill):
                self.assertEqual(s, {(x0 + x1 - x, y) for x, y in s})
                self.assertEqual(s, {(x, y0 + y1 - y) for x, y in s})
        self.assertNotIn((0, 0), set(ellipse_points(0, 0, 8, 8)))  # corners cut


class CanvasTests(unittest.TestCase):
    def setUp(self):
        self.ed = EditorTab(lambda path: None)
        self.c = self.ed.canvas
        self.ed.color = QColor(RED)

    def test_mirror_both_works_with_every_tool(self):
        n = self.c.n
        self.ed.mirror.setCurrentIndex(3)
        for tool in editor.SHAPE_TOOLS:
            self.c.set_image(self.c.blank(n))
            self.c.draw_shape(tool, (2, 3), (6, 9))
            px = solid(self.c.img)
            self.assertEqual(px, {(n - 1 - x, y) for x, y in px}, tool)
            self.assertEqual(px, {(x, n - 1 - y) for x, y in px}, tool)
        self.c.set_image(self.c.blank(n))
        self.c.fill(0, 0)  # whole empty canvas
        self.assertEqual(len(solid(self.c.img)), n * n)
        self.c.set_image(self.c.blank(n))
        self.c.plot(1, 1)
        self.assertEqual(solid(self.c.img), {(1, 1), (n - 2, 1), (1, n - 2), (n - 2, n - 2)})

    def test_layers_composite_merge_and_undo(self):
        self.c.plot(5, 5)
        self.assertTrue(self.c.add_layer())
        self.ed.color = QColor(GREEN)
        self.c.plot(5, 5)
        self.assertEqual(self.c.composite().pixelColor(5, 5).name(), "#00ff00")  # top layer wins
        self.c.layers[1]["visible"] = False
        self.assertEqual(self.c.composite().pixelColor(5, 5).name(), "#ff0000")
        self.c.layers[1]["visible"] = True
        self.c.layers[1]["opacity"] = 0.0
        self.c.merge_down()
        self.assertEqual(len(self.c.layers), 1)
        self.assertEqual(self.c.composite().pixelColor(5, 5).name(), "#ff0000")  # 0 % opacity merged = no change
        self.c.step(True)  # undo merge
        self.assertEqual(len(self.c.layers), 2)
        for _ in range(10):
            self.c.add_layer()
        self.assertEqual(len(self.c.layers), editor.MAX_LAYERS)

    def test_frames_onion_and_gif_export(self):
        self.c.plot(1, 1)
        self.c.add_frame()
        self.c.plot(2, 2)
        self.assertEqual(len(self.c.frames), 2)
        self.assertEqual(solid(self.c.composite(0)), {(1, 1)})
        self.assertEqual(solid(self.c.composite(1)), {(1, 1), (2, 2)})
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "a.gif")
            self.assertTrue(self.ed.write(path))
            r = QImageReader(path)
            count = r.imageCount()
            first = r.read().convertToFormat(QImage.Format_ARGB32)
            del r  # Windows: release the file before the temp folder is removed
            self.assertEqual(count, 2)
            self.assertEqual(first.pixelColor(1, 1).name(), "#ff0000")
            self.assertEqual(first.pixelColor(0, 0).alpha(), 0)  # transparent background survives

    def test_recolor_tolerance_and_scope(self):
        self.ed.color = QColor("#ff0000")
        self.c.plot(1, 1)
        self.ed.color = QColor("#f80a00")  # ~4 % off
        self.c.plot(2, 2)
        self.assertEqual(self.c.recolor(RED, GREEN, 0.0, False), 1)
        self.assertEqual(self.c.recolor(QColor("#f80a00"), GREEN, 0.05, False), 1)
        self.assertEqual(self.c.img.pixelColor(2, 2).name(), "#00ff00")
        self.c.add_frame()
        self.assertEqual(self.c.recolor(GREEN, RED, 0.0, True), 4)  # 2 px x 2 frames

    def test_import_threshold(self):
        img = QImage(20, 10, QImage.Format_ARGB32)
        img.fill(QColor("white"))
        for x in range(20):
            img.setPixelColor(x, 5, QColor("black"))  # a dark line on white
        out = to_pixels(img, 16, 128, False, False, QColor(RED))
        px = solid(out)
        self.assertTrue(px)
        self.assertEqual(len({y for _, y in px}), 1)  # one row
        self.assertEqual(out.pixelColor(*next(iter(px))).name(), "#ff0000")
        inv = solid(to_pixels(img, 16, 128, True, False, QColor(RED)))
        self.assertFalse(px & inv)


if __name__ == "__main__":
    unittest.main()
