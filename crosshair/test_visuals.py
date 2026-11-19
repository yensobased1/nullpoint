"""v2.2 visuals: XH4 fields, per-arm, dot shapes, glow, fire expand, SVG export."""
import copy
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])

import overlay  # noqa: E402
import svg_export  # noqa: E402
from config import DEFAULT_CROSSHAIR  # noqa: E402
from preview import render_image  # noqa: E402
from share_code import ShareCodeError, export_code, import_code  # noqa: E402


def cross(**kw):
    c = copy.deepcopy(DEFAULT_CROSSHAIR)
    c["outline"]["on"] = False
    c["dot"]["on"] = False
    for k, v in kw.items():
        c[k].update(v) if isinstance(v, dict) else c.__setitem__(k, v)
    return c


def pixels(cr, spread=0):
    c = overlay.extent(cr)
    img = render_image(lambda p, cc: overlay.render(p, cr, cc, spread=spread), c)
    return c, img, {(x - c, y - c) for y in range(img.height()) for x in range(img.width())
                    if img.pixelColor(x, y).alpha()}


class ShareCodeV4Tests(unittest.TestCase):
    def test_xh4_round_trip(self):
        c = copy.deepcopy(DEFAULT_CROSSHAIR)
        c["dot"]["shape"] = "diamond"
        c["shadow"].update(on=True, size=8, alpha=0.6, mode="glow", color="FF00AA")
        c["arms"].update(link=False, t=0, r=12, b=3, l=30, ct="", cr="00FF00", cb="", cl="123ABC")
        c["expand"].update(on=True, px=9, ms=250)
        code = export_code(c)
        self.assertTrue(code.startswith("XH4;"))
        self.assertEqual(import_code(code), c)

    def test_xh3_code_keeps_new_defaults(self):
        c = import_code("XH3;m:l;c:00FF00;h:1,4,0.7")
        self.assertEqual((c["color"], c["shadow"]["size"], c["shadow"]["mode"]), ("00FF00", 4, "shadow"))
        self.assertEqual(c["arms"], DEFAULT_CROSSHAIR["arms"])
        self.assertEqual(c["expand"], DEFAULT_CROSSHAIR["expand"])

    def test_bad_new_fields(self):
        for bad in ("XH4;u:ZZZZZZ", "XH4;q:g,12", "XH4;" + "a" * 3000):
            with self.assertRaises(ShareCodeError, msg=bad[:20]):
                import_code(bad)
        c = import_code("XH4;a:0,99,-5,1,1;f:1,999,-1;z:nope")
        self.assertEqual((c["arms"]["t"], c["arms"]["r"]), (30, 0))
        self.assertEqual((c["expand"]["px"], c["expand"]["ms"]), (20, 0))
        self.assertEqual(c["dot"]["shape"], "square")

    def test_bad_config_colors_export_cleanly(self):
        c = copy.deepcopy(DEFAULT_CROSSHAIR)
        c["arms"]["cr"] = "<b>"
        c["shadow"]["color"] = 5
        self.assertEqual(import_code(export_code(c))["arms"]["cr"], "")


class ShapeTests(unittest.TestCase):
    def test_dot_shapes_pixel_exact(self):
        self.assertEqual(len(overlay.dot_rects(2, 10, "circle")), 1)  # tiny sizes stay square
        _, _, sq = pixels(cross(dot={"on": True, "size": 5, "shape": "square"}, inner={"on": False}))
        _, _, ci = pixels(cross(dot={"on": True, "size": 5, "shape": "circle"}, inner={"on": False}))
        _, _, di = pixels(cross(dot={"on": True, "size": 5, "shape": "diamond"}, inner={"on": False}))
        self.assertEqual(len(sq), 25)
        self.assertEqual(len(di), 13)  # 1+3+5+3+1
        self.assertTrue(di < ci < sq)
        for s in (ci, di):  # symmetric around the center pixel
            self.assertEqual(s, {(-x, y) for x, y in s})
            self.assertEqual(s, {(x, -y) for x, y in s})

    def test_per_arm_length_and_color(self):
        cr = cross(inner={"thick": 1, "gap": 2, "len": 6},
                   arms={"link": False, "t": 0, "r": 3, "b": 5, "l": 1, "cr": "FF0000"})
        c, img, px = pixels(cr)
        self.assertEqual({x for x, y in px if y == 0 and x > 0}, {3, 4, 5})  # right: 3 px after gap 2
        self.assertEqual({x for x, y in px if y == 0 and x < 0}, {-3})  # left: 1 px
        self.assertFalse([1 for x, y in px if y < 0])  # top: 0 px
        self.assertEqual(img.pixelColor(c + 3, c).name(), "#ff0000")
        self.assertEqual(img.pixelColor(c, c + 3).name(), "#00ffff")

    def test_linked_arms_ignore_overrides(self):
        a = pixels(cross())[2]
        b = pixels(cross(arms={"link": True, "r": 30, "cr": "FF0000"}))[2]
        self.assertEqual(a, b)

    def test_glow_uses_its_color_and_is_cached(self):
        overlay._halo_cache.clear()
        cr = cross(shadow={"on": True, "size": 3, "alpha": 1.0, "mode": "glow", "color": "FF0000"})
        c, img, _ = pixels(cr)
        x = c + cr["inner"]["gap"] + 1 + 1
        self.assertEqual(img.pixelColor(x, c - 2).red(), 255)  # 1 px outside the 2 px line
        n = len(overlay._halo_cache)
        pixels(cr)
        self.assertEqual(len(overlay._halo_cache), n)  # second draw reuses the cached layer

    def test_fire_expand_moves_lines_out(self):
        cr = cross(expand={"on": True, "px": 4, "ms": 100})
        base = pixels(cr)[2]
        moved = pixels(cr, spread=4)[2]
        self.assertEqual(min(x for x, y in moved if y == 0 and x > 0), min(x for x, y in base if y == 0 and x > 0) + 4)

    def test_overlay_firing_instant_with_reduce_motion(self):
        ov = overlay.Overlay()
        ov.reduce_motion = True
        ov.set_crosshair(cross(expand={"on": True, "px": 6, "ms": 200}), "")
        ov.set_firing(True)
        self.assertEqual(ov.spread, 6)
        self.assertFalse(ov.fire_timer.isActive())
        ov.set_firing(False)
        self.assertEqual(ov.spread, 0)


class SvgTests(unittest.TestCase):
    def test_svg_is_vector_and_matches_parts(self):
        cr = copy.deepcopy(DEFAULT_CROSSHAIR)
        cr["shadow"]["on"] = True
        svg = svg_export.to_svg(cr)
        self.assertTrue(svg.startswith("<svg"))
        self.assertNotIn("<image", svg)
        self.assertGreaterEqual(svg.count("<path"), 4)  # shadow rings + outline + lines + dot

    def test_svg_ring_text_gradient(self):
        cr = cross(shape="circle", gradient={"on": True})
        self.assertIn("<path", svg_export.to_svg(cr))
        cr = cross(inner={"on": True}, gradient={"on": True, "c2": "FF0000"})
        self.assertIn("radialGradient", svg_export.to_svg(cr))
        cr = cross(mode="text")
        self.assertIn("<path", svg_export.to_svg(cr))


if __name__ == "__main__":
    unittest.main()
