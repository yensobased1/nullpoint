"""v2.2 games/display/tools: title rules, safe regex, install detection parsers, variants, HDR boost, sens."""
import copy
import json
import os
import tempfile
import time
import unittest

import config
import game_detect
import hdr
import installs
import tools
from config import DEFAULT_CROSSHAIR


class RuleTests(unittest.TestCase):
    def test_rules_first_then_process_list(self):
        rules = [{"exe": "javaw.exe", "title": "Lunar", "match": "contains", "profile": "PvP"},
                 {"exe": "", "title": r"^Minecraft\* 1\.\d+", "match": "regex", "profile": "MC"},
                 {"exe": "game.exe", "title": "Lobby", "match": "exact", "profile": "Menu"}]
        games = {"game.exe": "Game"}
        m = lambda exe, title: game_detect.match_game(games, exe, None, rules, title)
        self.assertEqual(m("javaw.exe", "Lunar Client 1.8"), "PvP")
        self.assertEqual(m("javaw.exe", "Minecraft* 1.21"), "MC")
        self.assertEqual(m("game.exe", "lobby"), "Menu")  # exact, case-insensitive
        self.assertEqual(m("game.exe", "Lobby 2"), "Game")  # falls through to the process list
        self.assertIsNone(m("notepad.exe", "x"))

    def test_safe_regex_refuses_slow_patterns(self):
        for bad in ("(a+)+$", "(a*)*b", r"(\w+\s?)+$", r"(x)\1", "(?=a)a", "a**", "x" * 101, "("):
            self.assertIsNone(game_detect.safe_regex(bad), bad)
        self.assertIsNotNone(game_detect.safe_regex(r"^Valorant\s+\d+"))
        t = time.monotonic()
        rule = {"exe": "", "title": "(a|b)+c", "match": "regex", "profile": "P"}
        game_detect.rule_matches(rule, "x.exe", "a" * 100000)  # title is cut to 256 chars
        self.assertLess(time.monotonic() - t, 0.5)

    def test_clean_rules(self):
        profiles = {"Default": {}, "P": {}}
        rules = [{"exe": "A.EXE", "title": "", "match": "nope", "profile": "P"},
                 {"exe": "", "title": "", "profile": "P"},  # empty rule
                 {"exe": "x.exe", "profile": "Missing"},
                 {"title": "(a+)+", "match": "regex", "profile": "P"}, "junk", 5]
        self.assertEqual(config.clean_rules(rules, profiles),
                         [{"exe": "a.exe", "title": "", "match": "contains", "profile": "P"}])


class InstallTests(unittest.TestCase):
    def test_epic_manifests(self):
        with tempfile.TemporaryDirectory() as d:
            for i, data in enumerate(({"DisplayName": "Fortnite", "LaunchExecutable":
                                       "FortniteGame/Binaries/Win64/FortniteClient-Win64-Shipping.exe"},
                                      {"DisplayName": 5}, "not json", {"DisplayName": "Evil", "LaunchExecutable": "a:b"})):
                with open(os.path.join(d, f"{i}.item"), "w", encoding="utf-8") as f:
                    f.write(data if isinstance(data, str) else json.dumps(data))
            with open(os.path.join(d, "big.item"), "w") as f:
                f.write(" " * (installs.MAX_FILE + 1))
            self.assertEqual(installs.epic(d), [{"name": "Fortnite", "exe": "fortniteclient-win64-shipping.exe",
                                                 "source": "Epic"}])

    def test_riot_file(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "r.json")
            with open(p, "w") as f:
                json.dump({"associated_client": {"D:/Riot Games/VALORANT/live/": "x", 5: "y"}}, f)
            self.assertIn("valorant-win64-shipping.exe", [g["exe"] for g in installs.riot(p)])

    def test_detect_never_raises(self):
        self.assertIsInstance(installs.detect(["cs2.exe"]), list)


class VariantTests(unittest.TestCase):
    def test_variants_cleaned_and_picked(self):
        cfg = copy.deepcopy(config.DEFAULT_CONFIG)
        v = copy.deepcopy(DEFAULT_CROSSHAIR)
        v["color"] = "FF0000"
        cfg["profiles"]["Default"] = dict(copy.deepcopy(config.DEFAULT_PROFILE),
                                          variants={"1440x1080": v, "bad": v, "9x9": v, "1920x1080": "junk"})
        p = config.normalize(cfg)["profiles"]["Default"]
        self.assertEqual(list(p["variants"]), ["1440x1080"])
        self.assertEqual(config.active_cross(p, "1440x1080")["color"], "FF0000")
        self.assertIs(config.active_cross(p, "2560x1440"), p["crosshair"])
        self.assertIs(config.active_cross(p, None), p["crosshair"])

    def test_old_config_gets_new_defaults(self):
        cfg = config.normalize({"profiles": {"Default": {}}, "hdr": {"mode": "Evil", "mult": 99}, "startup_delay": 999})
        self.assertEqual((cfg["hdr"]["mode"], cfg["hdr"]["mult"], cfg["startup_delay"]), ("Off", 3.0, 120))
        self.assertEqual(cfg["hotkeys"]["nudge"], "")
        self.assertEqual(cfg["rules"], [])


class ProfileMigrationTests(unittest.TestCase):
    def test_builtin_game_profiles_removed_games_kept(self):
        changed = copy.deepcopy(config.DEFAULT_PROFILE)
        changed["crosshair"] = dict(copy.deepcopy(DEFAULT_CROSSHAIR), color="FF0000")
        old = {"games_version": 2, "active_profile": "VALORANT",
               "profiles": {"Default": {}, "VALORANT": changed, "Fortnite": {}, "Mine": {}},
               "games": {"valorant-win64-shipping.exe": "VALORANT", "my.exe": "Mine"},
               "rules": [{"exe": "x.exe", "profile": "Fortnite"}],
               "game_offsets": {"cs2.exe": [3, -2], "bad": "x", "zero.exe": [0, 0]}}
        cfg = config.normalize(old)
        self.assertEqual(sorted(cfg["profiles"]), ["Default", "Mine"])
        self.assertEqual(cfg["active_profile"], "Default")
        self.assertEqual(cfg["games"]["valorant-win64-shipping.exe"], "")
        self.assertEqual(cfg["games"]["my.exe"], "Mine")  # your own profiles stay linked
        self.assertIn("cs2.exe", cfg["games"])
        self.assertEqual(cfg["rules"], [])
        self.assertEqual(cfg["game_offsets"], {"cs2.exe": [3, -2]})
        again = config.normalize(cfg)  # already migrated: nothing else removed
        self.assertEqual(sorted(again["profiles"]), ["Default", "Mine"])

    def test_new_config_has_only_default(self):
        cfg = config.normalize({})
        self.assertEqual(list(cfg["profiles"]), ["Default"])
        self.assertEqual(set(cfg["games"].values()), {""})

    def test_game_without_profile_still_counts_as_game(self):
        self.assertEqual(game_detect.match_game({"cs2.exe": ""}, "cs2.exe", None, (), "x"), "")
        self.assertIsNone(game_detect.match_game({"javaw.exe": ""}, "javaw.exe", None, (), "Other java app"))
        self.assertEqual(game_detect.match_game({"javaw.exe": ""}, "javaw.exe", None, (), "Minecraft 1.21"), "")


class HdrTests(unittest.TestCase):
    def test_boost(self):
        c = copy.deepcopy(DEFAULT_CROSSHAIR)
        c["color"] = "806040"
        c["inner"]["alpha"] = 0.5
        b = hdr.boost(c, 2.0)
        self.assertEqual((b["color"], b["inner"]["alpha"], b["dot"]["alpha"]), ("FFC080", 1.0, 1.0))
        self.assertEqual(c["color"], "806040")  # original untouched
        self.assertIs(hdr.boost(c, 1.0), c)
        self.assertEqual(hdr.multiplier({"mode": "Manual", "mult": 9}, 0, 0), 3.0)
        self.assertEqual(hdr.multiplier({"mode": "Off", "mult": 2}, 0, 0), 1.0)
        self.assertIsInstance(hdr.is_hdr_at(0, 0), bool)  # real Windows call must not raise


class SensTests(unittest.TestCase):
    def test_conversions(self):
        self.assertAlmostEqual(tools.convert_sens(1.0, "CS2", "VALORANT"), 1 / 3.1818, places=3)
        self.assertAlmostEqual(tools.convert_sens(1.0, "CS2", "Overwatch 2"), 3.3333, places=3)
        self.assertAlmostEqual(tools.convert_sens(2.0, "CS2", "Apex Legends"), 2.0)
        self.assertAlmostEqual(tools.cm_per_360(800, 0.35, "VALORANT"), 46.65, places=2)


if __name__ == "__main__":
    unittest.main()
