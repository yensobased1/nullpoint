import json
import os
import unittest

from updates import version_tuple

LANG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lang")


class LangTests(unittest.TestCase):
    def test_arabic_covers_every_english_key(self):
        with open(os.path.join(LANG, "en.json"), encoding="utf-8") as f:
            en = json.load(f)
        for code in ("ar", "es", "pt_BR", "fr", "tr"):
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



class ToolsTests(unittest.TestCase):
    def test_edpi_and_portable_copy(self):
        import tempfile
        import tools
        self.assertEqual(tools.edpi(800, 0.35), 280)
        self.assertIsInstance(tools.on_battery(), bool)
        with tempfile.TemporaryDirectory() as d:
            exe, data = os.path.join(d, "x.exe"), os.path.join(d, "appdata")
            os.makedirs(data)
            open(exe, "wb").write(b"MZ")
            open(os.path.join(data, "config.json"), "w").write("{}")
            tools.make_portable(os.path.join(d, "out"), exe, data)
            for name in ("Nullpoint.exe", "portable.txt", os.path.join("data", "config.json")):
                self.assertTrue(os.path.exists(os.path.join(d, "out", name)), name)



class OnboardingTests(unittest.TestCase):
    def test_reports_hide_user_paths_and_changelog_has_this_version(self):
        import getpass
        import onboarding
        from updates import VERSION
        text = onboarding.scrub("File " + os.path.join(os.path.expanduser("~"), "x.py") + ", user " + getpass.getuser())
        self.assertNotIn(os.path.expanduser("~"), text)
        self.assertNotIn(getpass.getuser(), text)
        self.assertIn(f"## v{VERSION}", onboarding.changelog_text())
        self.assertLess(len(onboarding.issue_url("t", "x" * 10000)), 12000)


if __name__ == "__main__":
    unittest.main()
