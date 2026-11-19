import json
import os
import unittest

from updates import version_tuple

LANG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lang")


class LangTests(unittest.TestCase):
    def test_arabic_covers_every_english_key(self):
        en = json.load(open(os.path.join(LANG, "en.json"), encoding="utf-8"))
        ar = json.load(open(os.path.join(LANG, "ar.json"), encoding="utf-8"))
        self.assertEqual(set(en) - set(ar), set())

    def test_version_compare(self):
        self.assertGreater(version_tuple("v2.1.0"), version_tuple("2.0.0"))
        self.assertEqual(version_tuple("release-2.0.0"), (2, 0, 0))


if __name__ == "__main__":
    unittest.main()
