"""v2.2 phase 4: exporters, .nullpoint files, duplicate check, Discord snippet, animated card, starter packs."""
import base64
import copy
import json
import os
import re
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])

import config  # noqa: E402
import cs2  # noqa: E402
import exporters  # noqa: E402
import library  # noqa: E402
import packfile  # noqa: E402
import presets  # noqa: E402
import safe_image  # noqa: E402
import sharing  # noqa: E402
import valorant  # noqa: E402
from config import DEFAULT_CROSSHAIR  # noqa: E402
from share_code import export_code, import_code  # noqa: E402
from test_cs2 import encode  # noqa: E402

VAL_CODES = ["0;P;c;5;h;0;0l;4;0o;2;0a;1;0f;0;1b;0",
             "0;P;c;8;u;F28D9FFF;h;0;d;1;b;1;a;0.254;0t;3;0l;5;0o;0;0a;0.755;0f;0;1t;5;1o;2;1a;1;1m;0;1f;0",
             "0;P;c;1;h;0;d;1;z;3;f;0;0t;3;0l;1;0o;1;0a;1;0f;0;1t;0;1l;0;1o;0;1a;0;1f;0",
             "0;P;0l;4;0v;9;0g;1;1b;0", "0;P"]


class ExportTests(unittest.TestCase):
    def test_valorant_round_trip(self):
        for code in VAL_CODES:
            cross = valorant.convert(code)
            out, warn = exporters.to_valorant(cross)
            self.assertEqual(valorant.convert(out), cross, code)
            self.assertEqual(warn, [], code)

    def test_valorant_warns_and_refuses(self):
        c = copy.deepcopy(DEFAULT_CROSSHAIR)
        c["ring"]["on"] = True
        c["inner"]["len"] = 28
        out, warn = exporters.to_valorant(c)
        self.assertEqual(len(warn), 2)
        self.assertEqual(valorant.convert(out)["inner"]["len"], 20)
        c["mode"] = "text"
        with self.assertRaises(ValueError):
            exporters.to_valorant(c)

    def test_cs2_commands_match_the_code(self):
        code = encode(gap=-1.0, thickness=1.0, size=3.0, rgb=(10, 200, 30), color=5, alpha=200, outline_on=True,
                      outline=1.0, dot=True)
        d = cs2.decode(code)
        text, _ = exporters.to_cs2_commands(cs2.convert(code, 1080), 1080)
        vals = dict(re.findall(r"(\w+) (-?[\d.]+)", text))
        self.assertAlmostEqual(float(vals["cl_crosshairsize"]), d["size"], delta=0.25)
        self.assertAlmostEqual(float(vals["cl_crosshairthickness"]), d["thickness"], delta=0.25)
        self.assertAlmostEqual(float(vals["cl_crosshairgap"]), d["gap"], delta=0.5)
        self.assertEqual((vals["cl_crosshaircolor_r"], vals["cl_crosshaircolor_g"], vals["cl_crosshairdot"]),
                         ("10", "200", "1"))


class PackFileTests(unittest.TestCase):
    def png_bytes(self, w=8, h=8):
        img = QImage(w, h, QImage.Format_ARGB32)
        img.fill(QColor("red"))
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "a.png")
            img.save(p)
            return open(p, "rb").read()

    def test_round_trip_with_image(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "x.png")
            open(p, "wb").write(self.png_bytes())
            cross = copy.deepcopy(DEFAULT_CROSSHAIR)
            cross["mode"] = "png"
            name, back, img, ext = packfile.load(packfile.dump("My <b>one</b>", cross, p))
            self.assertEqual((name, back, ext), ("My <b>one</b>", cross, "png"))
            stored = packfile.store_image(img, ext, d)
            self.assertTrue(os.path.dirname(stored) == d and os.path.basename(stored).startswith("imported_"))

    def test_hostile_files(self):
        good = {"format": "nullpoint-crosshair", "code": export_code(DEFAULT_CROSSHAIR)}
        big = QImage(5000, 4, QImage.Format_ARGB32)  # wider than 4096
        big.fill(0)
        with tempfile.TemporaryDirectory() as d:
            big.save(os.path.join(d, "b.png"))
            bomb = open(os.path.join(d, "b.png"), "rb").read()
        svg = b'<svg xmlns="http://www.w3.org/2000/svg"><image href="file:///C:/x.png"/></svg>'
        bad = [b"x" * (packfile.MAX_FILE + 1), b"not json", json.dumps([1]).encode(),
               json.dumps(dict(good, format="other")).encode(), json.dumps(dict(good, code="XH4;c:ZZ")).encode(),
               json.dumps(dict(good, image="!!", ext="png")).encode(),
               json.dumps(dict(good, image=base64.b64encode(bomb).decode(), ext="png")).encode(),
               json.dumps(dict(good, image=base64.b64encode(svg).decode(), ext="svg")).encode(),
               json.dumps(dict(good, image="AAAA", ext="exe")).encode()]
        for raw in bad:
            with self.assertRaises(ValueError, msg=raw[:40]):
                packfile.load(raw)

    def test_svg_rules(self):
        ok = b'<svg xmlns="http://www.w3.org/2000/svg" width="8" height="8"><rect width="4" height="4"/></svg>'
        self.assertFalse(safe_image.load_bytes(ok).isNull())
        for bad in (b'<svg><script>x</script></svg>', b'<svg width="99999" height="5"></svg>',
                    b'<svg xmlns:xlink="http://www.w3.org/1999/xlink"><use xlink:href="http://e.com/a.svg#x"/></svg>'):
            with self.assertRaises(safe_image.ImageError):
                safe_image.load_bytes(bad)


class LibraryTests(unittest.TestCase):
    def test_duplicates(self):
        a = copy.deepcopy(DEFAULT_CROSSHAIR)
        near = copy.deepcopy(a)
        near["inner"]["alpha"] = 0.81
        other = copy.deepcopy(a)
        other["inner"]["len"] = 9
        entries = [{"name": "x", "crosshair": a, "image": ""}]
        self.assertEqual(library.find_duplicate(entries, near), 0)
        self.assertIsNone(library.find_duplicate(entries, other))

    def test_recent_cleaned(self):
        cfg = config.normalize({"recent": [{"name": "a", "code": "XH4"}, "junk"] + [{"name": str(i)} for i in range(9)]})
        self.assertEqual(len(cfg["recent"]), 5)
        self.assertEqual(cfg["recent"][0], {"name": "a", "code": "XH4", "image": ""})


class SharingTests(unittest.TestCase):
    def test_discord_snippet_link_imports(self):
        code = export_code(DEFAULT_CROSSHAIR)
        text = sharing.discord_snippet("**Mine**`", code)
        self.assertIn(f"```\n{code}\n```", text)
        link = re.search(r"nullpoint://\S+", text).group(0)
        self.assertEqual(sharing.code_from_link(link), code)

    def test_animated_card(self):
        from editor import write_gif
        f1, f2 = QImage(8, 8, QImage.Format_ARGB32), QImage(8, 8, QImage.Format_ARGB32)
        f1.fill(QColor("red"))
        f2.fill(QColor("blue"))
        cross = copy.deepcopy(DEFAULT_CROSSHAIR)
        cross["mode"] = "png"
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "a.gif")
            write_gif(p, [f1, f2], [100, 200])
            frames, delays = sharing.share_card_frames(cross, export_code(cross), p)
        self.assertEqual(len(frames), 2)
        self.assertEqual(frames[0].size().width(), 1200)


class PresetTests(unittest.TestCase):
    def test_packs_are_valid(self):
        self.assertEqual(len(presets.PACKS), 6)
        for pack, items in presets.PACKS.items():
            self.assertTrue(5 <= len(items) <= 8, pack)
            for name, cross in items:
                self.assertEqual(import_code(export_code(cross)), cross, name)  # all values in range


if __name__ == "__main__":
    unittest.main()
