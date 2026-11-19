import copy
import json
import os
import unittest
import urllib.request
from urllib.parse import quote

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication  # noqa: E402

import config  # noqa: E402
import sharing  # noqa: E402
from share_code import export_code  # noqa: E402
from stream_server import StreamServer  # noqa: E402

app = QApplication.instance() or QApplication([])
CODE = export_code(config.DEFAULT_CROSSHAIR)


class SharingTests(unittest.TestCase):
    def test_links_are_validated_strictly(self):
        self.assertEqual(sharing.code_from_link("nullpoint://import/" + CODE), CODE)
        self.assertEqual(sharing.code_from_link('"nullpoint://import/' + quote(CODE, safe="") + '/"'), CODE)
        for bad in ("nullpoint://import/", "nullpoint://import/XH3;c:ZZZZZZ", "nullpoint://run/calc.exe",
                    "https://evil.example/" + CODE, "nullpoint://import/XH3;c:00FFFF&x=<script>"):
            self.assertIsNone(sharing.code_from_link(bad), bad)

    def test_share_card_qr_round_trip(self):
        card = sharing.share_card(config.DEFAULT_CROSSHAIR, CODE)
        self.assertEqual((card.width(), card.height()), (1200, 630))
        self.assertEqual(sharing.decode_qr(card), CODE)

    def test_gallery_entries_are_cleaned(self):
        with open(os.path.join(os.path.dirname(__file__), "..", "gallery", "index.json"), encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(len(sharing.Gallery.clean(data["entries"])), 5)
        self.assertEqual(sharing.Gallery.clean([{"name": "x", "code": "rm -rf"}, "junk", {"code": CODE}])[0]["name"],
                         "Crosshair")

    def test_stream_page_is_local_and_serves_state(self):
        s = StreamServer()
        s.start(0)
        port = s.httpd.server_address[1]
        try:
            self.assertEqual(s.httpd.server_address[0], "127.0.0.1")
            s.publish(CODE, b"png")
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/state.json", timeout=3) as r:
                self.assertEqual(json.load(r)["code"], CODE)
        finally:
            s.stop()


if __name__ == "__main__":
    unittest.main()
