import unittest

import valorant
from share_code import ShareCodeError


def conv(code, scale=1.0):
    return valorant.convert(code, scale)


class ValorantTests(unittest.TestCase):
    def test_cyan_no_outline_short_lines(self):
        c = conv("0;P;c;5;h;0;0l;4;0o;2;0a;1;0f;0;1b;0")
        self.assertEqual(c["color"], "00FFFF")
        self.assertFalse(c["outline"]["on"])
        self.assertEqual((c["inner"]["len"], c["inner"]["gap"], c["inner"]["alpha"], c["inner"]["thick"]), (4, 2, 1.0, 2))
        self.assertFalse(c["outer"]["on"])
        self.assertFalse(c["dot"]["on"])

    def test_general_and_sniper_sections_are_ignored(self):
        c = conv("0;s;1;P;c;5;h;0;m;1;0l;4;0o;2;0a;1;0f;0;1b;0;S;c;4;o;1")
        self.assertEqual(c["color"], "00FFFF")  # S;c;4 (yellow) must not leak into primary
        self.assertEqual(c["outline"]["alpha"], 0.5)  # S;o;1 ignored, default stays
        self.assertEqual(c["inner"]["len"], 4)

    def test_custom_color_dot_and_outer(self):
        c = conv("0;P;c;8;u;F28D9FFF;h;0;d;1;b;1;a;0.254;0t;3;0l;5;0o;0;0a;0.755;0f;0;1t;5;1o;2;1a;1;1m;0;1f;0")
        self.assertEqual(c["color"], "F28D9F")
        self.assertTrue(c["dot"]["on"])
        self.assertEqual(c["dot"]["alpha"], 0.25)
        self.assertEqual((c["inner"]["thick"], c["inner"]["len"], c["inner"]["gap"]), (3, 5, 0))
        self.assertEqual((c["outer"]["thick"], c["outer"]["len"], c["outer"]["gap"], c["outer"]["alpha"]), (5, 2, 2, 1.0))
        self.assertTrue(c["outer"]["on"])

    def test_dot_only_style(self):
        c = conv("0;P;c;1;h;0;d;1;z;3;f;0;0t;3;0l;1;0o;1;0a;1;0f;0;1t;0;1l;0;1o;0;1a;0;1f;0")
        self.assertEqual(c["color"], "00FF00")
        self.assertEqual(c["dot"]["size"], 3)
        self.assertEqual((c["inner"]["len"], c["inner"]["thick"], c["inner"]["gap"]), (1, 3, 1))
        self.assertFalse(c["outer"]["on"])  # thickness 0 / length 0 = hidden

    def test_custom_color_without_index_and_vertical_length(self):
        c = conv("0;s;1;P;u;000000FF;h;0;m;1;0l;3;0v;3;0o;2;0a;1;0f;0;1b;0;S;c;0;o;1")
        self.assertEqual(c["color"], "000000")
        self.assertEqual(c["inner"]["vlen"], 3)
        self.assertFalse(c["inner"]["vsep"])

    def test_preset_index_wins_over_leftover_custom(self):
        c = conv("0;P;c;7;u;F97AC0FF;o;0.1;m;1;0t;5;0l;3;0o;1;0a;0.7;0f;0;1t;1;1l;5;1o;0;1a;0.7;1m;0;1f;0")
        self.assertEqual(c["color"], "FF0000")
        self.assertTrue(c["outline"]["on"])
        self.assertEqual(c["outline"]["alpha"], 0.1)
        self.assertEqual((c["outer"]["len"], c["outer"]["gap"], c["outer"]["thick"]), (5, 0, 1))

    def test_separate_vertical_length(self):
        c = conv("0;P;0l;4;0v;9;0g;1;1b;0")
        self.assertTrue(c["inner"]["vsep"])
        self.assertEqual((c["inner"]["len"], c["inner"]["vlen"]), (4, 9))

    def test_defaults_when_keys_missing(self):
        c = conv("0;P")
        self.assertEqual(c["color"], "FFFFFF")
        self.assertEqual((c["inner"]["len"], c["inner"]["thick"], c["inner"]["gap"], c["inner"]["alpha"]), (6, 2, 3, 0.8))
        self.assertEqual((c["outer"]["len"], c["outer"]["gap"], c["outer"]["alpha"]), (2, 10, 0.35))
        self.assertTrue(c["outline"]["on"])
        self.assertFalse(c["dot"]["on"])

    def test_whitespace_and_case(self):
        c = conv("  0;p;c;4;\n 0l;7;\r\n0o;5 ;0a;1 ")
        self.assertEqual((c["color"], c["inner"]["len"], c["inner"]["gap"]), ("FFFF00", 7, 5))

    def test_scaling_to_1440p(self):
        c = conv("0;P;0t;2;0l;6;0o;3", scale=1440 / 1080)
        self.assertEqual((c["inner"]["thick"], c["inner"]["len"], c["inner"]["gap"]), (3, 8, 4))

    def test_invalid_codes_raise_clean_errors(self):
        for bad in ("", "hello", "1;P;c;5", "0;P;c", "0;P;c;abc", "0;P;u;ZZZZZZZZ", "0;P;c;5;0l", "0;P;<b>;1"):
            with self.assertRaises(ShareCodeError, msg=bad):
                conv(bad)

    def test_import_any_detects_format(self):
        self.assertEqual(valorant.import_any("0;P;c;5")[1], "valorant")
        self.assertEqual(valorant.import_any("XH3;c:00FF00")[1], "nullpoint")



class ValorantLinkQrTests(unittest.TestCase):
    def test_links_and_qr_accept_valorant_codes(self):
        import os
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])  # noqa: F841
        import sharing
        code = "0;P;c;5;h;0;0l;4;0o;2;0a;1;0f;0;1b;0"
        self.assertEqual(sharing.code_from_link("nullpoint://import/" + code), code)
        self.assertIsNone(sharing.code_from_link("nullpoint://import/0;P;c;abc"))
        self.assertEqual(sharing.decode_qr(sharing.qr_image(code)), code)



class ValorantPixelTests(unittest.TestCase):
    def test_screenshot_code_renders_exact_pixels(self):
        """vcrdb 'yay': 0;P;h;0;f;0;0l;4;0o;0;0a;1;0f;0;1b;0 = solid 2 px plus, 4 px arms, no outline, at 1:1."""
        import os
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])  # noqa: F841
        import overlay
        from preview import render_image
        cr = valorant.convert("0;P;h;0;f;0;0l;4;0o;0;0a;1;0f;0;1b;0")
        c = overlay.extent(cr)
        img = render_image(lambda p, cc: overlay.render(p, cr, cc), c)
        px = {(x - c, y - c) for y in range(img.height()) for x in range(img.width()) if img.pixelColor(x, y).alpha()}
        want = {(x, y) for x in range(-4, 4) for y in (-1, 0)} | {(x, y) for y in range(-4, 4) for x in (-1, 0)}
        self.assertEqual(px, want)
        self.assertLess(c, 12)  # hidden outer lines no longer blow up the size


if __name__ == "__main__":
    unittest.main()
