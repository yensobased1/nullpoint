"""v2.2 phase 5: gallery data, submit link, Twitch parsing, Credential Manager, stream page config."""
import copy
import unittest
from urllib.parse import parse_qs, urlparse

import config
import credman
import sharing
import twitch
from config import DEFAULT_CROSSHAIR
from share_code import export_code

CODE = export_code(DEFAULT_CROSSHAIR)


class GalleryTests(unittest.TestCase):
    def test_clean_keeps_dates_and_plain_fields(self):
        e = sharing.Gallery.clean([{"name": "<img src=x>", "code": CODE, "added": "2026-11-20", "tags": ["a"] * 20},
                                   {"code": CODE, "added": "yesterday"}])
        self.assertEqual((e[0]["name"], e[0]["added"], len(e[0]["tags"])), ("<img src=x>", "2026-11-20", 8))
        self.assertEqual(e[1]["added"], "")
        self.assertEqual(len(sharing.Gallery.clean([{"code": CODE}] * 900)), 500)

    def test_submit_link(self):
        url = sharing.submit_url("My cross & more", CODE)
        u = urlparse(url)
        self.assertEqual((u.scheme, u.netloc, u.path), ("https", "github.com", "/yensobased1/nullpoint/issues/new"))
        q = parse_qs(u.query)
        self.assertEqual((q["template"][0], q["code"][0], q["name"][0]), ("gallery-submission.yml", CODE, "My cross & more"))


class TwitchTests(unittest.TestCase):
    def test_only_the_exact_command_in_our_channel(self):
        line = ":viewer!viewer@viewer.tmi.twitch.tv PRIVMSG #me :!crosshair"
        tagged = "@badge-info=;color=#FF0000 " + line
        self.assertTrue(twitch.command_in(line, "me"))
        self.assertTrue(twitch.command_in(tagged, "me"))
        for bad in (line + " please", line.replace("#me", "#other"), line.replace(":!crosshair", ":hi !crosshair"),
                    "PING :tmi.twitch.tv", "x" * 5000, line.replace("PRIVMSG", "NOTICE")):
            self.assertFalse(twitch.command_in(bad, "me"), bad[:60])

    def test_reply_never_carries_chat_or_newlines(self):
        r = twitch.reply_text(CODE + "\r\nPRIVMSG #x :evil")
        self.assertNotIn("\r", r)
        self.assertNotIn("\n", r)
        self.assertNotIn(" :evil", r)
        self.assertLess(len(r), 500)

    def test_tokens(self):
        self.assertEqual(twitch.clean_token(" oauth:ABCdef0123456789abcdef01 "), "abcdef0123456789abcdef01")
        for bad in ("", "short", "has space in it 0123456789", "x" * 100):
            self.assertEqual(twitch.clean_token(bad), "")

    def test_bad_channel_does_not_connect(self):
        msgs = []
        bot = twitch.TwitchBot(msgs.append)
        bot.start("bad name!", "abcdef0123456789abcdef01")
        self.assertIsNone(bot.thread)
        self.assertIn("invalid", msgs[0])


class CredentialTests(unittest.TestCase):
    def test_round_trip(self):
        name = "unit-test-delete-me"
        credman.save(name, "secret-value-123")
        try:
            self.assertEqual(credman.load(name), "secret-value-123")
        finally:
            credman.delete(name)
        self.assertEqual(credman.load(name), "")


class StreamConfigTests(unittest.TestCase):
    def test_stream_and_twitch_config_cleaned(self):
        cfg = config.normalize({"stream_page": {"on": True, "port": 80, "theme": "<x>", "pos": "middle", "size": 9999,
                                                "token": "short"},
                                "twitch": {"on": True, "channel": "Bad Name!", "cooldown": 1, "token": "leak"}})
        sp, tw = cfg["stream_page"], cfg["twitch"]
        self.assertEqual((sp["port"], sp["theme"], sp["pos"], sp["size"]), (1024, "dark", "top-left", 256))
        self.assertGreaterEqual(len(sp["token"]), 22)
        self.assertEqual((tw["channel"], tw["cooldown"]), ("", 5))
        token = sp["token"]
        self.assertEqual(config.normalize(copy.deepcopy(cfg))["stream_page"]["token"], token)  # stable across loads


if __name__ == "__main__":
    unittest.main()
