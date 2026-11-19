import unittest

import cs2
import valorant
from share_code import ShareCodeError


def encode(gap=0.0, outline=1.0, rgb=(0, 255, 0), alpha=255, color=1, outline_on=False, thickness=1.0, dot=False,
           use_alpha=True, t_style=False, style=4, size=2.0):
    """Test helper: the inverse of cs2.code_bytes/decode (same byte layout)."""
    b = [0] * 18
    b[1] = 1
    b[2] = round(gap * 10) & 0xFF
    b[3] = round(outline * 2)
    b[4], b[5], b[6] = rgb
    b[7] = alpha
    b[10] = (color & 7) | (8 if outline_on else 0)
    b[12] = round(thickness * 10)
    b[13] = (style << 1) | ((1 if dot else 0) | (4 if use_alpha else 0) | (8 if t_style else 0)) << 4
    n = round(size * 10)
    b[14], b[15] = n & 0xFF, (n >> 8) & 0x1F
    b[0] = sum(b[1:]) % 256
    num = int.from_bytes(bytes(b), "big")
    chars = []
    for _ in range(25):
        num, r = divmod(num, 57)
        chars.append(cs2.ALPHABET[r])
    s = "".join(chars)
    return "CSGO-" + "-".join(s[i:i + 5] for i in range(0, 25, 5))


class CS2Tests(unittest.TestCase):
    def test_decode_round_trip(self):
        code = encode(gap=-2.5, outline=1.5, rgb=(12, 200, 99), alpha=180, color=5, outline_on=True,
                      thickness=0.5, dot=True, t_style=True, size=3.0)
        d = cs2.decode(code)
        self.assertEqual((d["gap"], d["outline"], d["red"], d["green"], d["blue"], d["alpha"]), (-2.5, 1.5, 12, 200, 99, 180))
        self.assertEqual((d["color"], d["outline_on"], d["thickness"], d["dot"], d["t_style"], d["size"]),
                         (5, True, 0.5, True, True, 3.0))

    def test_convert_at_1080p_uses_source_scaling(self):
        # size 2 -> 2*1080/480 = 4.5 -> 4 (banker's) / thickness 1 -> 2.25 -> 2 / gap -2 -> YRES(2)=4.5 -> 4, +1
        c = cs2.convert(encode(gap=-2, thickness=1, size=2, color=1), 1080)
        self.assertEqual((c["inner"]["len"], c["inner"]["thick"], c["inner"]["gap"]), (4, 2, 5))
        self.assertEqual(c["color"], "32FA32")  # preset green (50, 250, 50)
        self.assertFalse(c["outer"]["on"])
        self.assertEqual(c["shape"], "cross")

    def test_custom_color_t_style_dot_alpha(self):
        c = cs2.convert(encode(rgb=(255, 0, 128), color=5, t_style=True, dot=True, alpha=128, use_alpha=True), 1080)
        self.assertEqual((c["color"], c["shape"], c["dot"]["on"]), ("FF0080", "t", True))
        self.assertEqual(c["inner"]["alpha"], 0.5)
        c = cs2.convert(encode(use_alpha=False, alpha=10), 1080)
        self.assertEqual(c["inner"]["alpha"], 0.78)  # cl_crosshairusealpha 0 = fixed 200

    def test_grows_with_resolution(self):
        code = encode(size=2, thickness=1, gap=0)
        self.assertGreater(cs2.convert(code, 1440)["inner"]["len"], cs2.convert(code, 1080)["inner"]["len"])

    def test_invalid_codes(self):
        good = encode()
        broken = good[:-1] + ("A" if good[-1] != "A" else "B")
        for bad in ("", "CSGO-", "CSGO-aaaaa-bbbbb", "CSGO-00000-00000-00000-00000-00000", broken, "XSGO-" + good[5:]):
            with self.assertRaises(ShareCodeError, msg=bad):
                cs2.convert(bad)

    def test_import_any_detects_cs2(self):
        self.assertEqual(valorant.import_any(encode())[1], "cs2")
        self.assertEqual(valorant.import_any("  " + encode() + "\n")[1], "cs2")



class CS2LinkQrTests(unittest.TestCase):
    def test_links_and_qr_accept_cs2_codes(self):
        import os
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])  # noqa: F841
        import sharing
        code = encode(size=3, color=4)
        self.assertEqual(sharing.code_from_link("nullpoint://import/" + code), code)
        self.assertEqual(sharing.decode_qr(sharing.qr_image(code)), code)


if __name__ == "__main__":
    unittest.main()
