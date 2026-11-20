"""Phase 8: fuzz + attack-case tests. Every parser gets random / huge / malformed input: it may only raise its own
clean error (a ValueError subclass), never crash or hang (> 1 s), and never write outside its folder."""
import base64
import json
import os
import tempfile
import time
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])

import config  # noqa: E402
import cs2  # noqa: E402
import game_detect  # noqa: E402
import library  # noqa: E402
import packfile  # noqa: E402
import safe_image  # noqa: E402
import sharing  # noqa: E402
import twitch  # noqa: E402
import valorant  # noqa: E402
from config import DEFAULT_CROSSHAIR  # noqa: E402
from share_code import export_code, import_code  # noqa: E402

FUZZ = settings(max_examples=150, deadline=1000, suppress_health_check=[HealthCheck.too_slow])
code_chars = st.sampled_from(list("XH1234;:,.%-_0PpcCSGOabcdefuxyz#\\n /") + ["XH4;", "0;P;", "CSGO-"])
code_like = st.lists(code_chars, max_size=400).map("".join)
any_text = st.one_of(st.text(max_size=3000), code_like)
json_like = st.recursive(st.none() | st.booleans() | st.integers() | st.floats(allow_nan=True) | st.text(max_size=40),
                         lambda c: st.lists(c, max_size=6) | st.dictionaries(st.text(max_size=12), c, max_size=6),
                         max_leaves=40)


class FuzzTests(unittest.TestCase):
    @FUZZ
    @given(any_text)
    def test_share_code(self, text):
        try:
            c = import_code(text)
        except ValueError:
            return
        self.assertEqual(import_code(export_code(c)), c)  # whatever loads, round-trips

    @FUZZ
    @given(any_text)
    def test_valorant_and_cs2_and_any(self, text):
        for fn in (valorant.convert, cs2.decode, valorant.import_any):
            try:
                fn(text)
            except ValueError:
                pass

    @FUZZ
    @given(st.lists(st.sampled_from(cs2.ALPHABET), min_size=25, max_size=25))
    def test_cs2_shaped_codes(self, chars):
        s = "".join(chars)
        try:
            cs2.convert("CSGO-" + "-".join(s[i:i + 5] for i in range(0, 25, 5)))
        except ValueError:
            pass

    @FUZZ
    @given(any_text)
    def test_links(self, text):
        for t in (text, "nullpoint://import/" + text):
            code = sharing.code_from_link(t)
            if code is not None:
                valorant.import_any(code)  # anything a link hands over is a valid code

    @FUZZ
    @given(st.one_of(st.binary(max_size=4000), json_like.map(lambda d: json.dumps(d).encode())))
    def test_packfile(self, raw):
        try:
            packfile.load(raw)
        except ValueError:
            pass

    @FUZZ
    @given(json_like)
    def test_config_library_gallery(self, data):
        try:
            cfg = config.normalize(data)
            self.assertIn("Default", cfg["profiles"])
        except ValueError:
            pass
        self.assertIsInstance(library.clean(data), list)
        self.assertIsInstance(sharing.Gallery.clean(data), list)
        self.assertIsInstance(config.clean_rules(data, {"Default": {}}), list)

    @FUZZ
    @given(st.binary(max_size=3000))
    def test_image_bytes(self, raw):
        try:
            safe_image.load_bytes(raw)
        except ValueError:
            pass

    @FUZZ
    @given(st.text(max_size=120), st.text(max_size=400))
    def test_title_rules_never_hang(self, pattern, title):
        rule = {"exe": "", "title": pattern, "match": "regex", "profile": "P"}
        game_detect.rule_matches(rule, "x.exe", title * 20)
        twitch.command_in(title, "chan")

    @FUZZ
    @given(st.dictionaries(st.text(max_size=60), st.one_of(st.text(max_size=40), st.integers()), max_size=8))
    def test_backup_images_stay_in_folder(self, images):
        good = base64.b64encode(PNG).decode()
        images.update({"../../evil.png": good, "C:\\Windows\\x.png": good, "\\\\srv\\share\\y.svg": good,
                       "a.png:stream.exe": good, "z.exe": good})
        with tempfile.TemporaryDirectory() as d:
            folder = os.path.join(d, "imported")
            moved = packfile.import_images(images, folder)
            for path in moved.values():
                self.assertEqual(os.path.dirname(os.path.abspath(path)), os.path.abspath(folder))
                self.assertTrue(path.endswith((".png", ".gif", ".svg")))
            self.assertEqual(sorted(os.listdir(d)), ["imported"] if moved else [])


class AttackCaseTests(unittest.TestCase):
    def fast(self, fn, *a):
        t = time.monotonic()
        try:
            fn(*a)
        except ValueError:
            pass
        self.assertLess(time.monotonic() - t, 1.0, fn.__name__)

    def test_one_megabyte_codes(self):
        big = "XH4;" + "c:00FF00;" * 120000
        for fn in (import_code, valorant.import_any, valorant.convert, cs2.decode):
            self.fast(fn, big)
            with self.assertRaises(ValueError):
                fn(big)
        self.assertIsNone(sharing.code_from_link("nullpoint://import/" + big))

    def test_link_launch_cannot_switch_modes(self):
        import main
        link = "nullpoint://import/" + export_code(DEFAULT_CROSSHAIR)
        self.assertEqual(main.parse_args([link, "--safe", "--autostart"]), (link, False, False))
        self.assertEqual(main.parse_args(['nullpoint://x" --safe']), ('nullpoint://x" --safe', False, False))
        self.assertEqual(main.parse_args(["--safe"]), ("", False, True))
        self.assertEqual(main.parse_args(["--autostart"]), ("", True, False))
        self.assertEqual(len(main.parse_args(["nullpoint://" + "a" * 10**6])[0]), 2000)

    def test_unc_paths_are_not_loaded_from_config(self):
        import overlay
        for p in ("\\\\attacker\\share\\x.png", "//attacker/share/x.png"):
            with self.assertRaises(safe_image.ImageError):
                safe_image.load(p)
            cross = dict(DEFAULT_CROSSHAIR, mode="png")
            self.assertIsNone(overlay.png_pixmap(p, cross["png"]))

    def test_html_in_gallery_names_stays_text(self):
        e = sharing.Gallery.clean([{"name": "<a href='x'>click</a>", "author": "<script>", "code": export_code(DEFAULT_CROSSHAIR)}])
        self.assertEqual(e[0]["name"], "<a href='x'>click</a>")  # kept as text; the UI shows it as plain text

    def test_network_allow_list(self):
        import net
        for bad in ("http://github.com/x", "https://evil.example/", "file:///C:/x", "https://user:pw@github.com/",
                    "https://github.com.evil.example/"):
            with self.assertRaises(net.NetError, msg=bad):
                net.check_url(bad)
        self.assertTrue(net.check_url("https://raw.githubusercontent.com/yensobased1/nullpoint/main/gallery/index.json"))


def _png():
    from PySide6.QtGui import QImage
    from PySide6.QtCore import QBuffer, QByteArray, QIODevice
    img = QImage(4, 4, QImage.Format_ARGB32)
    img.fill(0xFFFF0000)
    buf = QBuffer(data := QByteArray())
    buf.open(QIODevice.WriteOnly)
    img.save(buf, "PNG")
    return bytes(data)


PNG = _png()

if __name__ == "__main__":
    unittest.main()
