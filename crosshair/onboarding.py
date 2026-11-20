"""First-run wizard, changelog popup, feedback link, crash reporter. Nothing is sent anywhere automatically."""
import copy
import getpass
import os
import platform
import re
import sys
import time
import traceback
from urllib.parse import quote

from PySide6.QtCore import QSize, QUrl, Qt
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtWidgets import (QApplication, QDialog, QGridLayout, QHBoxLayout, QLabel, QListWidget,
                               QListWidgetItem, QMessageBox, QPushButton, QStackedWidget, QTextBrowser, QToolButton,
                               QVBoxLayout)

import config
from ui.i18n import tr
from ui.icons import icon

REPO = "yensobased1/nullpoint"


def _preset(**kw):
    c = copy.deepcopy(config.DEFAULT_CROSSHAIR)
    for k, v in kw.items():
        c[k].update(v) if isinstance(v, dict) else c.__setitem__(k, v)
    return c


PRESETS = [("Classic", _preset()),
           ("Tiny dot", _preset(shape="dot", color="FFFFFF", dot={"size": 2})),
           ("Green plus", _preset(shape="plus", color="00FF00", inner={"len": 4, "thick": 2, "gap": 0})),
           ("Ring", _preset(color="FFFF00", ring={"on": True, "radius": 12, "gaps": 4, "gapsize": 30, "gaprot": 45})),
           ("T-shape", _preset(shape="t", color="FF4D8D", shadow={"on": True, "size": 2})),
           ("High contrast", _preset(color="FFFFFF", outline={"on": True, "thick": 2, "alpha": 1.0}))]


# ---------- privacy-safe text ----------
def scrub(text):
    """Remove the Windows user name and home folder from text before it is shown or shared."""
    home = os.path.expanduser("~")
    for secret in {home, home.replace("\\", "/")}:
        text = text.replace(secret, "<home>")
    user = getpass.getuser()
    if len(user) > 2:
        text = re.sub(re.escape(user), "<user>", text, flags=re.IGNORECASE)
    return text


def system_line(version):
    return f"Nullpoint {version} | Windows {platform.release()} ({platform.version()}) | Python {platform.python_version()}"


def issue_url(title, body):
    return (f"https://github.com/{REPO}/issues/new?title={quote(title[:120])}"
            f"&body={quote(body[:3500])}")  # short enough for every browser's URL limit


def open_feedback(version, profile):
    body = (f"**What happened / what would you like?**\n\n\n**Steps to reproduce (if a bug)**\n\n\n---\n"
            f"{system_line(version)}\nActive profile: {scrub(profile)[:40]}\n")
    QDesktopServices.openUrl(QUrl(issue_url("Feedback: ", body)))


# ---------- crash reporter ----------
_in_crash = False


def install_crash_hook(version):
    def hook(*exc):
        global _in_crash
        report = scrub(f"{system_line(version)}\n{time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                       + "".join(traceback.format_exception(*exc)))
        try:
            folder = os.path.join(config.CONFIG_DIR, "crashes")
            os.makedirs(folder, exist_ok=True)
            with open(os.path.join(folder, time.strftime("crash-%Y%m%d-%H%M%S.txt")), "w", encoding="utf-8") as f:
                f.write(report)
            for old in sorted(os.listdir(folder))[:-5]:  # keep the last 5
                os.remove(os.path.join(folder, old))
        except OSError:
            pass
        sys.__excepthook__(*exc)
        if _in_crash or QApplication.instance() is None:
            return
        _in_crash = True
        try:
            box = QMessageBox()
            box.setIcon(QMessageBox.Warning)
            box.setWindowTitle(tr("Nullpoint hit a problem"))
            box.setText(tr("Something went wrong. The app keeps running. A report was saved on this PC only; "
                           "user names and folders are removed from it."))
            box.setDetailedText(report)
            copy_btn = box.addButton(tr("Copy report"), QMessageBox.ActionRole)
            issue_btn = box.addButton(tr("Open GitHub issue"), QMessageBox.ActionRole)
            box.addButton(QMessageBox.Close)
            box.exec()
            if box.clickedButton() is copy_btn:
                QGuiApplication.clipboard().setText(report)
            elif box.clickedButton() is issue_btn:
                QDesktopServices.openUrl(QUrl(issue_url("Crash: " + str(exc[1])[:80], "```\n" + report + "\n```")))
        finally:
            _in_crash = False

    sys.excepthook = hook


# ---------- changelog ----------
def changelog_text():
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    try:
        with open(os.path.join(base, "CHANGELOG.md"), encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


def show_changelog(parent, version, qss=""):
    text = changelog_text()
    m = re.search(rf"^## v{re.escape(version)}\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    dlg = QDialog(parent)
    dlg.setWindowTitle(f"{tr('What is new in Nullpoint')} {version}")
    dlg.setWindowIcon(icon("changelog"))
    if qss:
        dlg.setStyleSheet(qss)
    v = QVBoxLayout(dlg)
    view = QTextBrowser()
    view.setOpenExternalLinks(True)
    view.setMarkdown(f"## v{version}\n" + (m.group(1) if m else text))
    v.addWidget(view)
    b = QPushButton(tr("Close"))
    b.clicked.connect(dlg.accept)
    v.addWidget(b)
    dlg.resize(560, 420)
    dlg.exec()


# ---------- first-run wizard ----------
class Wizard(QDialog):
    """1) games  2) starting crosshair  3) hotkeys. Skippable; on_done(games_kept, preset or None)."""

    def __init__(self, cfg, thumbnail, on_done):
        super().__init__()
        self.cfg, self.on_done = cfg, on_done
        self.setWindowTitle(tr("Welcome to Nullpoint"))
        self.setWindowIcon(icon("wizard"))
        self.choice = None
        v = QVBoxLayout(self)
        self.pages = QStackedWidget()
        v.addWidget(self.pages, 1)

        p1 = QListWidget()
        p1.setAccessibleName(tr("Games"))
        from config import BUILTIN_GAMES
        name = lambda exe: cfg["games"][exe] or BUILTIN_GAMES.get(exe) or exe
        for exe in sorted(cfg["games"], key=name):
            it = QListWidgetItem(f"{name(exe)}  ({exe})")
            it.setData(Qt.UserRole, exe)
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Checked)
            p1.addItem(it)
        self.games = p1
        self.pages.addWidget(self._page(tr("1 / 3  Which games do you play?"),
                                        tr("Nullpoint centers the crosshair on these games' windows while you play."), p1))
        grid = QGridLayout()
        self.preset_buttons = []
        for i, (name, cross) in enumerate(PRESETS):
            b = QToolButton()
            b.setIcon(thumbnail(cross))
            b.setIconSize(QSize(64, 64))
            b.setText(tr(name))
            b.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
            b.setCheckable(True)
            b.setAutoExclusive(True)
            b.setAccessibleName(tr(name))
            b.clicked.connect(lambda _=False, c=cross: setattr(self, "choice", c))
            grid.addWidget(b, i // 3, i % 3)
            self.preset_buttons.append(b)
        self.pages.addWidget(self._page(tr("2 / 3  Pick a starting crosshair"),
                                        tr("You can change everything later in Settings."), grid))
        keys = QLabel("\n".join(f"{k}:  {v_}" for k, v_ in cfg["hotkeys"].items() if v_))
        self.pages.addWidget(self._page(tr("3 / 3  Your hotkeys"),
                                        tr("Change them any time in App Settings. Hold F1 in game to see them."), keys))
        row = QHBoxLayout()
        self.skip = QPushButton(tr("Skip"))
        self.skip.clicked.connect(self.finish_skip)
        self.back = QPushButton(tr("Back"))
        self.back.clicked.connect(lambda: self.go(-1))
        self.next = QPushButton(tr("Next"))
        self.next.setDefault(True)
        self.next.clicked.connect(lambda: self.go(1))
        row.addWidget(self.skip)
        row.addStretch()
        row.addWidget(self.back)
        row.addWidget(self.next)
        v.addLayout(row)
        self.go(0)
        self.resize(520, 420)

    @staticmethod
    def _page(title, hint, content):
        from PySide6.QtWidgets import QWidget
        w = QWidget()
        v = QVBoxLayout(w)
        t = QLabel(title)
        f = t.font()
        f.setPointSize(f.pointSize() + 3)
        f.setBold(True)
        t.setFont(f)
        v.addWidget(t)
        h = QLabel(hint)
        h.setWordWrap(True)
        v.addWidget(h)
        from PySide6.QtWidgets import QLayout
        v.addLayout(content) if isinstance(content, QLayout) else v.addWidget(content)
        v.addStretch()
        return w

    def go(self, step):
        i = self.pages.currentIndex() + step
        if i >= self.pages.count():
            self.finish()
            return
        self.pages.setCurrentIndex(max(0, i))
        self.back.setEnabled(self.pages.currentIndex() > 0)
        self.next.setText(tr("Finish") if self.pages.currentIndex() == self.pages.count() - 1 else tr("Next"))

    def finish(self):
        kept = {self.games.item(i).data(Qt.UserRole) for i in range(self.games.count())
                if self.games.item(i).checkState() == Qt.Checked}
        self.on_done(kept, self.choice)
        self.accept()

    def finish_skip(self):
        self.on_done(None, None)
        self.accept()
