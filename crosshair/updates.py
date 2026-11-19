"""Once-a-day check for a newer GitHub release. Notifies only: never downloads or installs anything."""
import json
import re
import threading
import urllib.request

from PySide6.QtCore import QObject, Signal

VERSION = "2.1.0"
REPO_RE = re.compile(r"[\w.-]+/[\w.-]+")


def version_tuple(text):
    return tuple(int(n) for n in re.findall(r"\d+", text)[:3])


class UpdateChecker(QObject):
    found = Signal(str, str)  # (version, release page url)

    def check(self, repo):
        if REPO_RE.fullmatch(repo or ""):
            threading.Thread(target=self._run, args=(repo,), daemon=True).start()

    def _run(self, repo):
        try:
            req = urllib.request.Request(f"https://api.github.com/repos/{repo}/releases/latest",
                                         headers={"User-Agent": "Nullpoint-update-check",
                                                  "Accept": "application/vnd.github+json"})
            with urllib.request.urlopen(req, timeout=5) as r:
                data = json.load(r)
            tag, url = str(data.get("tag_name", "")), str(data.get("html_url", ""))
            if url.startswith("https://github.com/") and version_tuple(tag) > version_tuple(VERSION):
                self.found.emit(tag, url)  # queued to the GUI thread
        except Exception:
            pass  # offline / no releases / rate limited: stay silent
