"""v2.2 phase 9: release picking (no downgrades, beta channel), asset checks, checksums, verified launch."""
import hashlib
import os
import tempfile
import unittest

import updates

REPO = "yensobased1/nullpoint"


def rel(tag, pre=False, draft=False, assets=True, repo=REPO):
    base = f"https://github.com/{repo}/releases/download/{tag}/"
    a = [{"name": f"Nullpoint-Setup-{tag.lstrip('v')}.exe", "browser_download_url": base + f"Nullpoint-Setup-{tag.lstrip('v')}.exe"},
         {"name": "checksums.txt", "browser_download_url": base + "checksums.txt"}] if assets else []
    return {"tag_name": tag, "prerelease": pre, "draft": draft, "html_url": f"https://github.com/{repo}/releases/tag/{tag}",
            "body": "<b>notes</b>", "assets": a}


class ReleaseTests(unittest.TestCase):
    def test_pick_newest_never_downgrade(self):
        rels = [rel("v2.1.9"), rel("v2.3.0", pre=True), rel("v2.2.5"), rel("v9.0.0", draft=True), rel("junk")]
        self.assertEqual(updates.pick_release(rels, False, "2.2.0")["tag_name"], "v2.2.5")
        self.assertEqual(updates.pick_release(rels, True, "2.2.0")["tag_name"], "v2.3.0")
        self.assertIsNone(updates.pick_release([rel("v2.1.0")], True, "2.2.0"))
        self.assertIsNone(updates.pick_release("junk"))

    def test_assets_must_come_from_this_repo(self):
        info = updates.release_info(rel("v2.3.0"), REPO)
        self.assertTrue(info["installer"].startswith(f"https://github.com/{REPO}/releases/download/"))
        self.assertEqual(info["notes"], "<b>notes</b>")  # shown in a plain-text box
        evil = rel("v2.3.0")
        evil["assets"][0]["browser_download_url"] = "https://evil.example/Nullpoint-Setup-2.3.0.exe"
        self.assertEqual(updates.release_info(evil, REPO)["installer"], "")  # page only, no install button
        self.assertIsNone(updates.release_info(rel("v2.3.0", repo="someone/else"), REPO))

    def test_checksums(self):
        h = "a" * 64
        sums = updates.parse_checksums(f"{h}  Nullpoint-Setup-2.3.0.exe\n{h.upper()} *Nullpoint.exe\nbad line\n")
        self.assertEqual(sums, {"Nullpoint-Setup-2.3.0.exe": h, "Nullpoint.exe": h})

    def test_verified_launch_checks_the_file_on_disk(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "x.exe")
            with open(p, "wb") as f:
                f.write(b"MZ installer")
            good = hashlib.sha256(b"MZ installer").hexdigest()
            updates.run_verified(p, good, start=False)
            with self.assertRaises(ValueError):
                updates.run_verified(p, "0" * 64, start=False)
            self.assertFalse(updates.signed(p))  # unsigned file


if __name__ == "__main__":
    unittest.main()
