import json
import os
import unittest

from updates import version_tuple

LANG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lang")


class LangTests(unittest.TestCase):
    def test_arabic_covers_every_english_key(self):
        with open(os.path.join(LANG, "en.json"), encoding="utf-8") as f:
            en = json.load(f)
        for code in ("ar",):
            with open(os.path.join(LANG, code + ".json"), encoding="utf-8") as f:
                self.assertEqual(set(en) - set(json.load(f)), set(), code)

    def test_version_compare(self):
        self.assertGreater(version_tuple("v2.1.0"), version_tuple("2.0.0"))
        self.assertEqual(version_tuple("release-2.0.0"), (2, 0, 0))


class HotkeyTests(unittest.TestCase):
    def test_hold_key_names(self):
        from hotkeys import hold_vk
        self.assertEqual(hold_vk("Mouse2"), 0x02)
        self.assertEqual(hold_vk("F1"), 0x70)
        self.assertEqual(hold_vk("shift"), 0x10)
        self.assertIsNone(hold_vk(""))
        self.assertIsNone(hold_vk("nonsense"))


if __name__ == "__main__":
    unittest.main()
