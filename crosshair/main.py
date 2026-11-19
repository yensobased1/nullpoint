"""Nullpoint entry point: tray icon, global hotkeys, foreground-game polling."""
import ctypes
import os
import re
import sys
import time
import traceback

# Physical pixels everywhere: the overlay stays pixel-perfect and centered at 125%/150% scaling.
# Qt still runs per-monitor DPI aware, so Win32 coordinates are physical too.
os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "0"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import copy

from PySide6.QtCore import QPoint, QTimer, Qt, QUrl
from PySide6.QtGui import QAction, QColor, QDesktopServices, QIcon, QKeySequence, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

import config
import game_detect
from overlay import Overlay
from alignment import AlignmentWindow
from hotkeys import hold_vk, is_down, to_win_hotkey
from popups import InfoCard, QuickSwitcher
import library
from settings_ui import SettingsWindow, app_icon, asset, migrate_startup, screens
from ui import i18n, theme
from ui.i18n import tr
from updates import VERSION, UpdateChecker

user32 = ctypes.windll.user32
user32.RegisterHotKey.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_uint, ctypes.c_uint]
user32.UnregisterHotKey.argtypes = [ctypes.c_void_p, ctypes.c_int]
HOTKEY_IDS = {"toggle": 1, "settings": 2, "switcher": 3}
HOTKEY_LABELS = {"toggle": "Toggle overlay", "settings": "Open settings", "switcher": "Quick switcher",
                 "hold_hide": "Hide while held", "cheat": "Show this cheat sheet (hold)"}
# Shell windows that grab focus when you click the tray: never "the current game".
SHELL_EXES = {"explorer.exe", "searchhost.exe", "shellexperiencehost.exe", "startmenuexperiencehost.exe",
              "textinputhost.exe", "lockapp.exe", ""}
EXCLUSIVE_MSG = "Switch the game to Windowed Fullscreen / Borderless for the overlay to show."


def log_errors(*exc):
    os.makedirs(config.CONFIG_DIR, exist_ok=True)
    with open(os.path.join(config.CONFIG_DIR, "error.log"), "a", encoding="utf-8") as f:
        f.write("".join(traceback.format_exception(*exc)) + "\n")
    sys.__excepthook__(*exc)


def tray_icon():
    for name in ("nullpoint_tray.ico", "nullpoint_tray_16.png"):
        if os.path.exists(asset(name)):
            return QIcon(asset(name))
    pm = QPixmap(32, 32)  # fallback when assets/ is missing
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    for x, y, w, h in ((14, 2, 4, 10), (14, 20, 4, 10), (2, 14, 10, 4), (20, 14, 10, 4)):
        p.fillRect(x - 1, y - 1, w + 2, h + 2, QColor("black"))
        p.fillRect(x, y, w, h, QColor("#00FFFF"))
    p.end()
    return QIcon(pm)


class App:
    def __init__(self):
        self.qt = QApplication(sys.argv)
        self.qt.setQuitOnLastWindowClosed(False)
        self.qt.setApplicationName("Nullpoint")
        self.qt.setWindowIcon(app_icon())
        if config.migrate_old_folder():
            migrate_startup()
        self.cfg = config.load()
        i18n.set_language(self.cfg["language"])
        self.qt.setLayoutDirection(Qt.RightToLeft if i18n.is_rtl() else Qt.LeftToRight)
        self.ov = Overlay()
        self.ov.hotkey.connect(self.on_hotkey)
        self.settings = None
        self.base_center = game_detect.monitor_center(None)
        self.last_hwnd = None
        self.last_target = None
        self.game_active = False
        self.warned_hwnd = None
        self.last_external = None  # (exe, title) of the last focused non-shell window, for "Add current game"
        self.native = (0, 0)
        self.align = None  # alignment test window while open
        self.held_hidden = False  # hide-while-held key is down
        self.card = InfoCard()
        self.switcher = None
        self.hold_timer = QTimer(interval=40)  # polls only the hold keys' up/down state
        self.hold_timer.timeout.connect(self.poll_hold_keys)
        self.update_url = ""

        self.save_timer = QTimer(singleShot=True, interval=300)
        self.save_timer.timeout.connect(self.save)

        self.tray = QSystemTrayIcon(tray_icon())
        self.tray.setToolTip(f"Nullpoint {VERSION}")
        self.build_menu()
        self.tray.activated.connect(
            lambda r: self.open_settings() if r == QSystemTrayIcon.DoubleClick else None)
        self.tray.messageClicked.connect(
            lambda: QDesktopServices.openUrl(QUrl(self.update_url)) if self.update_url else None)
        self.tray.show()

        self.apply()
        self.apply_stream_safe(quiet=True)
        self.updates = UpdateChecker()
        self.updates.found.connect(self.on_update)
        if self.cfg["update_repo"] and time.time() - self.cfg["last_update_check"] > 86400:  # max once a day
            self.cfg["last_update_check"] = int(time.time())
            self.save_timer.start()
            self.updates.check(self.cfg["update_repo"])
        self.register_hotkeys()
        self.timer = QTimer(interval=500)  # cheap poll: a few Win32 calls, no redraw unless something moved
        self.timer.timeout.connect(self.poll)
        self.timer.start()
        self.poll()
        self.hold_timer.start()

    def build_menu(self):
        menu = QMenu()
        self.show_action = QAction(tr("Show overlay"), menu, checkable=True)
        self.show_action.setChecked(self.cfg["visible"])
        self.show_action.triggered.connect(lambda: self.toggle())
        menu.addAction(self.show_action)
        menu.addAction(tr("Open Settings"), self.open_settings)
        menu.addAction(tr("Add current game"), self.add_current_game)
        menu.addAction(tr("Alignment test"), self.alignment_test)
        self.profile_menu = menu.addMenu(tr("Switch Profile"))
        self.profile_menu.aboutToShow.connect(self.fill_profile_menu)
        menu.addSeparator()
        menu.addAction(tr("Exit"), self.exit)
        menu.setLayoutDirection(self.qt.layoutDirection())
        self.tray.setContextMenu(menu)
        self.menu = menu

    def notify(self, text, icon=QSystemTrayIcon.Information, ms=5000):
        self.tray.showMessage("Nullpoint", text, icon, ms)

    # ---------- state ----------
    def profile(self):
        return self.cfg["profiles"][self.cfg["active_profile"]]

    def apply(self):
        p = self.profile()
        self.ov.set_crosshair(p["crosshair"], p["png_path"], self.stretch_factor(), p["anim_paused"])
        self.place()

    def stretch_factor(self):
        """Stretched res: in-game pixels are native_w / w wide, so the crosshair is too."""
        st = self.profile()["stretch"]
        native = st["native_w"] or self.native[0]
        return native / st["w"] if st["on"] and native and st["w"] else 1.0

    def center(self):
        """Base center: alignment test screen, chosen monitor, else the game window / focused monitor."""
        if self.align:
            g = self.align.geometry()
            return g.x() + g.width() // 2, g.y() + g.height() // 2
        m = self.profile()["monitor"]
        scr = screens()
        if 1 <= m <= len(scr):
            g = scr[m - 1].geometry()
            return g.x() + g.width() // 2, g.y() + g.height() // 2
        return self.base_center

    def place(self):
        p = self.profile()
        cx, cy = self.center()
        sc = QApplication.screenAt(QPoint(cx, cy)) or QApplication.primaryScreen()
        native = (sc.geometry().width(), sc.geometry().height())
        if native != self.native:
            self.native = native
            if self.settings:
                self.settings.update_display_info()
        if abs(self.stretch_factor() - self.ov.sx) > 1e-9:
            self.ov.set_crosshair(p["crosshair"], p["png_path"], self.stretch_factor(), p["anim_paused"])
        self.ov.set_center(cx + p["offset_x"], cy + p["offset_y"])
        want = bool(self.align) or (self.cfg["visible"] and not self.held_hidden
                                    and (self.game_active or not self.cfg["show_only_in_games"]))
        if want != self.ov.isVisible():
            self.ov.setVisible(want)
            if want:
                self.ov.raise_top()
        self.show_action.setChecked(self.cfg["visible"])

    def set_profile(self, name):
        if name in self.cfg["profiles"] and name != self.cfg["active_profile"]:
            self.cfg["active_profile"] = name
            self.apply()
            self.save_timer.start()
            if self.settings:
                self.settings.refresh()

    def save(self):
        try:
            config.save(self.cfg)
        except OSError as e:
            self.notify(f"{tr('Could not save config')}: {e}")

    def on_change(self, kind):
        if kind in ("crosshair", "profile"):
            self.apply()
        elif kind == "hotkeys":
            self.register_hotkeys()
        elif kind == "stream":
            self.apply_stream_safe()
        elif kind == "theme":
            self.set_language()  # rebuilds the settings window so icons re-tint for dark / light
        elif kind == "language":
            self.set_language()
        else:
            self.last_hwnd = self.last_target = None  # re-evaluate game mapping on next poll
            self.place()
        self.save_timer.start()

    def apply_stream_safe(self, quiet=False):
        on = self.cfg["stream_safe"]
        if not self.ov.set_capture_hidden(on) and on and not quiet:
            msg = tr("Hiding from recordings needs Windows 10 version 2004 or newer. Viewers will see the crosshair.")
            self.notify(msg, QSystemTrayIcon.Warning)
            if self.settings:
                self.settings.say(msg, True)

    def set_language(self):
        i18n.set_language(self.cfg["language"])
        self.qt.setLayoutDirection(Qt.RightToLeft if i18n.is_rtl() else Qt.LeftToRight)
        self.build_menu()
        if self.settings:  # rebuild the window so every label is re-translated; state lives in cfg
            pos, tab, was_open = self.settings.pos(), self.settings.tabs.currentIndex(), self.settings.isVisible()
            self.settings.deleteLater()
            self.settings = None
            if was_open:
                self.open_settings()
                self.settings.move(pos)
                self.settings.tabs.setCurrentIndex(tab)

    def on_update(self, version, url):
        self.update_url = url
        self.notify(f"{tr('A new version is available')}: {version}. {tr('Click to open the release page.')}")

    def alignment_test(self):
        if self.align:
            return
        m = self.profile()["monitor"]
        scr = screens()
        if 1 <= m <= len(scr):
            screen = scr[m - 1]
        else:
            screen = QApplication.screenAt(QPoint(*self.base_center)) or QApplication.primaryScreen()
        self.align = AlignmentWindow(screen)
        self.align.closed.connect(self._alignment_closed)
        self.align.show()
        self.align.activateWindow()
        self.place()
        self.ov.raise_top()

    def _alignment_closed(self):
        self.align = None
        self.place()

    # ---------- foreground polling ----------
    def poll(self):
        hwnd, pid, exe = game_detect.foreground()
        if not hwnd or pid == os.getpid():
            return  # our own settings window / tray menu: keep the current profile
        if exe not in SHELL_EXES:
            self.last_external = (exe, game_detect.window_title(hwnd))
        game_profile = game_detect.match_game(self.cfg["games"], exe, hwnd)
        if hwnd != self.last_hwnd:
            self.last_hwnd = hwnd
            self.game_active = game_profile is not None
            target = game_profile or "Default"
            if target != self.last_target:  # manual pick survives hopping between non-game apps
                self.last_target = target
                self.set_profile(target)
            self.ov.raise_top()  # re-assert topmost on every focus change (fixes Alt+Tab)
        if self.game_active:
            center = game_detect.client_center(hwnd)
            self.check_fullscreen(hwnd)
        else:
            center = game_detect.monitor_center(hwnd)
        if center:
            self.base_center = center
        self.place()

    def check_fullscreen(self, hwnd):
        mode = self.cfg["fullscreen_mode"]
        if self.warned_hwnd == hwnd or mode == "Borderless":
            return
        if mode == "Exclusive" or game_detect.exclusive_fullscreen():
            self.warned_hwnd = hwnd
            self.notify(tr(EXCLUSIVE_MSG), QSystemTrayIcon.Warning, 6000)

    # ---------- hotkeys / tray ----------
    def register_hotkeys(self):
        bad = []
        for name, hid in HOTKEY_IDS.items():
            user32.UnregisterHotKey(self.ov.hwnd, hid)
            text = self.cfg["hotkeys"].get(name, "")
            hk = to_win_hotkey(text)
            if hk is None or not user32.RegisterHotKey(self.ov.hwnd, hid, *hk):
                bad.append(text or "(empty)")
        if bad:
            self.notify(f"{tr('Hotkey not available')}: {', '.join(bad)}. "
                        + tr("Use F1-F24, A-Z, 0-9 or Insert/Home/End/PgUp/PgDn with modifiers."))

    def poll_hold_keys(self):
        hide = hold_vk(self.cfg["hotkeys"].get("hold_hide"))
        down = bool(hide) and is_down(hide)
        if down != self.held_hidden:
            self.held_hidden = down
            self.place()
        cheat = hold_vk(self.cfg["hotkeys"].get("cheat"))
        show = bool(cheat) and is_down(cheat)
        if show and not self.card.isVisible():
            lines = [f"{tr(HOTKEY_LABELS[k])}:  {v}" for k, v in self.cfg["hotkeys"].items() if v and k in HOTKEY_LABELS]
            self.card.show_lines(tr("Nullpoint hotkeys"), lines, self.center())
        elif not show and self.card.isVisible():
            self.card.hide()

    def open_switcher(self):
        if self.switcher and self.switcher.isVisible():
            return
        from settings_ui import SettingsWindow
        favs = [e for e in library.load() if e.get("fav")][:8]
        prev = game_detect.foreground()[0]
        self.switcher = QuickSwitcher(favs, [SettingsWindow.thumbnail(e["crosshair"], e["image"]) for e in favs],
                                      self.center(), prev)
        self.switcher.picked.connect(lambda i: self.apply_entry(favs[i]))
        self.switcher.show()
        self.switcher.raise_()
        self.switcher.activateWindow()

    def apply_entry(self, e):
        """Library entry -> active profile (used by the quick switcher)."""
        p = self.profile()
        p["crosshair"] = copy.deepcopy(e["crosshair"])
        if e["image"]:
            p["png_path"] = e["image"]
        self.apply()
        self.save_timer.start()
        if self.settings:
            self.settings.refresh()

    def on_hotkey(self, hid):
        if hid == HOTKEY_IDS["switcher"]:
            self.open_switcher()
        elif hid == HOTKEY_IDS["toggle"]:
            self.toggle()
        elif hid == HOTKEY_IDS["settings"]:
            self.open_settings()

    def toggle(self):
        self.cfg["visible"] = not self.cfg["visible"]
        self.place()
        self.save_timer.start()

    def open_settings(self):
        if self.settings is None:
            qss = theme.use(self.cfg["theme"])  # tokens first: feature icons are tinted while the window builds
            self.settings = SettingsWindow(self)
            self.settings.setStyleSheet(qss)
        self.settings.refresh()
        self.settings.show()
        self.settings.raise_()
        self.settings.activateWindow()

    def add_current_game(self):
        """Map the last focused program to a new profile (copy of Default) named after its window."""
        if not self.last_external:
            self.notify(tr("Focus the game first, then use Add current game."))
            return
        exe, title = self.last_external
        if exe in self.cfg["games"]:
            self.notify(f"{exe}: {tr('already uses profile')} '{self.cfg['games'][exe]}'.")
            return
        base = re.sub(r"[\x00-\x1f]", "", title).strip()[:40] or os.path.splitext(exe)[0]
        name, n = base, 2
        while name in self.cfg["profiles"]:
            name, n = f"{base} ({n})", n + 1
        self.cfg["profiles"][name] = copy.deepcopy(self.cfg["profiles"]["Default"])
        self.cfg["games"][exe] = name
        self.on_change("general")
        if self.settings:
            self.settings.refresh()
        self.notify(f"{tr('Added')} {exe}: '{name}'. {tr('Rename it in Settings > Games & Display.')}")

    def fill_profile_menu(self):
        self.profile_menu.clear()
        for name in sorted(self.cfg["profiles"], key=lambda n: (n != "Default", n.lower())):
            a = self.profile_menu.addAction(name, lambda n=name: self.set_profile(n))
            a.setCheckable(True)
            a.setChecked(name == self.cfg["active_profile"])

    def exit(self):
        self.save_timer.stop()
        self.save()
        for hid in HOTKEY_IDS.values():
            user32.UnregisterHotKey(self.ov.hwnd, hid)
        self.tray.hide()
        self.qt.quit()


def main():
    sys.excepthook = log_errors
    # Own taskbar identity, so Windows shows the Nullpoint icon instead of python.exe's.
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Nullpoint.Overlay")
    # One instance only: a second copy would double-draw and fail to get the hotkeys.
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateMutexW.restype = ctypes.c_void_p
    _mutex = k32.CreateMutexW(None, False, "Nullpoint.SingleInstance")  # held until exit
    if ctypes.get_last_error() == 183:  # ERROR_ALREADY_EXISTS
        return
    app = App()
    sys.exit(app.qt.exec())


if __name__ == "__main__":
    main()
