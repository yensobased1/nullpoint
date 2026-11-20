"""v2.2 phase 6: rotating backups, auto-repair of config / library, safe mode never saves."""
import json
import os
import tempfile
import types
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import config  # noqa: E402
import library  # noqa: E402


class RepairTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        d = self.dir.name
        self.cfg_path, self.lib_path = os.path.join(d, "config.json"), os.path.join(d, "library.json")
        self.patches = [mock.patch.object(config, "CONFIG_PATH", self.cfg_path),
                        mock.patch.object(config, "BACKUP_DIR", os.path.join(d, "backups")),
                        mock.patch.object(library, "LIBRARY_PATH", self.lib_path)]
        for p in self.patches:
            p.start()
        config.REPAIRED.clear()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        config.REPAIRED.clear()
        self.dir.cleanup()

    def write(self, path, text):
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)

    def test_backups_rotate_and_skip_duplicates(self):
        for i in range(14):
            self.write(self.cfg_path, json.dumps({"n": i}))
            config.backup(self.cfg_path)
            config.backup(self.cfg_path)  # same content: no new copy
        olds = config.backups_of(self.cfg_path)
        self.assertEqual(len(olds), config.MAX_BACKUPS)
        self.assertEqual(json.load(open(olds[0], encoding="utf-8")), {"n": 13})

    def test_damaged_config_restored_from_newest_good_backup(self):
        good = config.defaults()
        good["visible"] = False
        self.write(self.cfg_path, json.dumps(good))
        self.assertFalse(config.load()["visible"])  # loads fine and makes a backup
        self.write(self.cfg_path, '{"profiles": ')  # crash mid-edit / disk error
        cfg = config.load()
        self.assertFalse(cfg["visible"])
        self.assertEqual(config.REPAIRED[0][0], "config.json")
        self.assertTrue(config.REPAIRED[0][1])
        self.assertTrue(any(n.endswith(".corrupt") for n in os.listdir(self.dir.name)))
        self.assertFalse(json.load(open(self.cfg_path, encoding="utf-8"))["visible"])  # good file is back on disk

    def test_no_backup_means_defaults_and_a_notice(self):
        self.write(self.cfg_path, "not json")
        self.assertEqual(config.load()["profiles"].keys(), {"Default"})
        self.assertEqual(config.REPAIRED, [("config.json", "")])

    def test_huge_config_is_refused(self):
        self.write(self.cfg_path, " " * (config.MAX_JSON + 1))
        config.load()
        self.assertEqual(config.REPAIRED[0][1], "")

    def test_damaged_library_restored(self):
        self.write(self.lib_path, json.dumps([{"name": "Keep me", "crosshair": {}}]))
        config.backup(self.lib_path)
        self.write(self.lib_path, "[{broken")
        self.assertEqual([e["name"] for e in library.load()], ["Keep me"])
        self.assertEqual(config.REPAIRED[0][0], "library.json")

    def test_missing_library_is_just_empty(self):
        self.assertEqual(library.load(), [])
        self.assertEqual(config.REPAIRED, [])


class SafeModeTests(unittest.TestCase):
    def test_safe_mode_never_saves(self):
        from PySide6.QtWidgets import QApplication
        QApplication.instance() or QApplication([])
        import main
        with mock.patch.object(config, "save") as save:
            main.App.save(types.SimpleNamespace(safe=True, cfg={}))
            save.assert_not_called()
            main.App.save(types.SimpleNamespace(safe=False, cfg={}, notify=print))
            save.assert_called_once()


if __name__ == "__main__":
    unittest.main()
