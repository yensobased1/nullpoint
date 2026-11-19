import copy
import unittest

from config import DEFAULT_CROSSHAIR
from share_code import ShareCodeError, export_code, import_code


class ShareCodeTests(unittest.TestCase):
    def test_default_round_trip(self):
        self.assertEqual(import_code(export_code(DEFAULT_CROSSHAIR)), DEFAULT_CROSSHAIR)

    def test_custom_round_trip(self):
        c = copy.deepcopy(DEFAULT_CROSSHAIR)
        c.update(mode="png", color="FF00AA")
        c["outline"].update(on=False, thick=3, alpha=0.27)
        c["inner"].update(len=12, gap=0, vsep=True, vlen=20, alpha=0.05)
        c["outer"].update(on=True, thick=7)
        c["png"].update(scale=250, alpha=0.6, rot=270)
        c.update(shape="chevron", rot=33)
        c["ring"].update(on=True, radius=14, thick=3, alpha=0.4, gaps=4, gapsize=30, gaprot=45)
        c["colors"].update(same=False, lines="112233", dot="ABCDEF", ring="00FF00", outline="FFFFFF")
        c["rainbow"].update(on=True, speed=9, sat=0.55)
        self.assertEqual(import_code(export_code(c)), c)

    def test_xh3_fields_round_trip(self):
        c = copy.deepcopy(DEFAULT_CROSSHAIR)
        c.update(mode="text", shape="hexagon")
        c["shadow"].update(on=True, size=4, alpha=0.7)
        c["gradient"].update(on=True, c2="FF8800")
        c["style"].update(kind="dashed", dash=3, gap=2)
        c["text"].update(chars="×;,", size=40, bold=False, alpha=0.9, font="Segoe UI, Bold")
        code = export_code(c)
        self.assertTrue(code.startswith("XH3;"))
        self.assertEqual(import_code(code), c)

    def test_xh2_codes_still_load(self):
        c = import_code("XH2;m:l;c:00FF00;s:v;r:10;k:1,00FFFF,00FFFF,00FFFF,000000;w:0,5,1")
        self.assertEqual((c["color"], c["shape"], c["rot"]), ("00FF00", "chevron", 10))
        self.assertEqual(c["shadow"], DEFAULT_CROSSHAIR["shadow"])

    def test_old_xh1_codes_still_load(self):
        c = import_code("XH1;m:l;c:FF0000;o:1,1,0.5;d:1,2,1;i:1,6,2,3,0.8,0,6;e:0,2,2,10,0.35,0,2;p:100,1,0")
        self.assertEqual(c["color"], "FF0000")
        self.assertEqual(c["shape"], "cross")
        self.assertEqual(c["ring"], DEFAULT_CROSSHAIR["ring"])

    def test_missing_and_unknown_keys(self):
        c = import_code("XH1;c:ff0000;zz:whatever;i:0")
        self.assertEqual(c["color"], "FF0000")
        self.assertFalse(c["inner"]["on"])
        self.assertEqual(c["inner"]["len"], DEFAULT_CROSSHAIR["inner"]["len"])
        self.assertEqual(c["dot"], DEFAULT_CROSSHAIR["dot"])

    def test_invalid_codes_raise_clean_error(self):
        for bad in ["", "hello", "0;P;c;1", "XH1;c:GGGGGG", "XH1;d:1,abc", "XH1;nocolon"]:
            with self.assertRaises(ShareCodeError):
                import_code(bad)

    def test_out_of_range_is_clamped(self):
        c = import_code("XH1;d:1,999,5;p:1,1,95")
        self.assertEqual(c["dot"]["size"], 10)
        self.assertEqual(c["dot"]["alpha"], 1)
        self.assertEqual(c["png"]["scale"], 10)
        self.assertEqual(c["png"]["rot"], 90)


if __name__ == "__main__":
    unittest.main()
