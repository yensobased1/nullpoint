"""Web builder (docs/builder) must match the app: same share codes, same pixels.

docs/builder/vectors.json = crosshairs + the app's code + every drawn pixel. This test checks the app still
produces exactly that, and runs the JS side (run_tests.js) with Node when Node is installed.
Regenerate after an intended renderer change:  python test_builder.py --write
"""
import copy
import json
import os
import shutil
import subprocess
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])

import overlay  # noqa: E402
from config import DEFAULT_CROSSHAIR  # noqa: E402
from preview import render_image  # noqa: E402
from share_code import export_code  # noqa: E402

BUILDER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "builder")
VECTORS = os.path.join(BUILDER, "vectors.json")


def cross(**kw):
    c = copy.deepcopy(DEFAULT_CROSSHAIR)
    for k, v in kw.items():
        c[k].update(v) if isinstance(v, dict) else c.__setitem__(k, v)
    return c


CASES = {
    "default": cross(),
    "per-arm + glow": cross(arms={"link": False, "t": 2, "r": 9, "b": 5, "l": 0, "cr": "FF0000", "cb": "FFFF00"},
                            shadow={"on": True, "size": 3, "alpha": 0.6, "mode": "glow", "color": "FF00FF"}),
    "round dot + shadow": cross(shape="dot", dot={"size": 6, "shape": "circle"}, outline={"thick": 2, "alpha": 1.0},
                                shadow={"on": True, "size": 2, "alpha": 0.5}),
    "dashed T": cross(shape="t", style={"kind": "dashed", "dash": 3, "gap": 2}, inner={"len": 12, "thick": 1},
                      color="FFFF00"),
    "square": cross(shape="square", inner={"len": 5, "gap": 3, "thick": 1}, dot={"on": False}),
    "plus + diamond dot": cross(shape="plus", inner={"len": 3, "gap": 0, "thick": 3}, dot={"size": 5, "shape": "diamond"},
                                colors={"same": False, "lines": "112233", "dot": "FFFFFF", "outline": "FF0000"}),
    "dotted two layers": cross(style={"kind": "dotted", "gap": 1}, outline={"on": False},
                               outer={"on": True, "len": 6, "gap": 12, "thick": 2, "alpha": 0.4}, inner={"vsep": True, "vlen": 9}),
}


def pixels(c):
    n = overlay.extent(c)
    img = render_image(lambda p, cc: overlay.render(p, c, cc), n)
    out = []
    for y in range(img.height()):
        for x in range(img.width()):
            col = img.pixelColor(x, y)
            if col.alpha():
                out.append([x - n, y - n, col.red(), col.green(), col.blue(), col.alpha()])
    return out


def make_vectors():
    return [{"name": name, "cross": c, "code": export_code(c), "pixels": pixels(c)} for name, c in CASES.items()]


class BuilderVectorTests(unittest.TestCase):
    def test_app_matches_vectors(self):
        with open(VECTORS, encoding="utf-8") as f:
            self.assertEqual(json.load(f), make_vectors())

    @unittest.skipUnless(shutil.which("node"), "Node.js not installed")
    def test_js_matches_vectors(self):
        r = subprocess.run([shutil.which("node"), os.path.join(BUILDER, "run_tests.js")], capture_output=True,
                           text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


if __name__ == "__main__":
    if "--write" in sys.argv:
        with open(VECTORS, "w", encoding="utf-8") as f:
            json.dump(make_vectors(), f, separators=(",", ":"))
        print("wrote", VECTORS)
    else:
        unittest.main()
