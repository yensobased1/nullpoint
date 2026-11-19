"""Settings window. Layout inspired by VALORANT's crosshair menu, our own design."""
import base64
import copy
import json
import os
import re
import sys
import time
import winreg

from PySide6.QtCore import QSize, Qt, QTimer, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QFont, QGuiApplication, QIcon, QImage, QKeySequence, QPainter, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QFormLayout, QGridLayout, QGroupBox,
    QCompleter, QDialog, QDialogButtonBox, QFontComboBox, QHBoxLayout, QHeaderView, QInputDialog, QKeySequenceEdit, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMessageBox, QPlainTextEdit, QPushButton,
    QScrollArea, QSlider, QSpinBox, QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget)

import config
import library
import overlay
import game_detect
import installs
import sharing
import svg_export
import cs2
import valorant
from editor import EditorTab
import tools
import onboarding
from updates import VERSION
from hotkeys import HOLD_CHOICES, hold_vk
from preview import PixelView, PreviewPanel, render_image
from share_code import FIELDS, ShareCodeError, export_code, import_code
from ui import theme
from ui.icons import icon
from ui.i18n import LANGUAGES, tr

SHAPES = [("cross", "Cross"), ("t", "T-Shape"), ("dot", "Dot only"), ("circle", "Circle"),
          ("hexagon", "Hexagon"), ("triangle", "Triangle"), ("diamond", "Diamond"), ("plus", "Plus (thick +)"),
          ("square", "Square"), ("chevron", "Chevron (^)"), ("x", "X")]
LINE_STYLES = [("solid", "Solid"), ("dashed", "Dashed"), ("dotted", "Dotted")]
DOT_SHAPES = [("square", "Square"), ("circle", "Circle"), ("diamond", "Diamond")]
HALO_MODES = [("shadow", "Shadow"), ("glow", "Glow")]
ARMS = [("t", "Top"), ("r", "Right"), ("b", "Bottom"), ("l", "Left")]
# Colorblind-friendly palettes: main color + outline color. Applying changes colors only.
COLORBLIND = [("Protanopia", "00FFFF", "000000"), ("Deuteranopia", "FFFF00", "000000"),
              ("Tritanopia", "FF4D8D", "000000"), ("High contrast", "FFFFFF", "000000")]
MODES = ["lines", "png", "text"]
PRESETS = ["FFFFFF", "00FF00", "7FFF00", "DFFF00", "FFFF00", "00FFFF", "FF00FF", "FF0000"]
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "Nullpoint"
OLD_RUN_NAME = "CrosshairOverlay"


def run_command():
    """The 'Start with Windows' entry: same program, plus a flag so the startup delay applies."""
    return startup_command() + " --autostart"


def startup_command():
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    exe = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    return f'"{exe}" "{os.path.abspath(sys.argv[0])}"'


def asset(name):
    """assets/ next to the crosshair/ folder, or inside the PyInstaller bundle."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base, "assets", name)


def app_icon():
    path = asset("nullpoint.ico")
    return QIcon(path) if os.path.exists(path) else QIcon()


def migrate_startup():
    """Rename the old 'Start with Windows' entry so it launches Nullpoint."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_READ | winreg.KEY_SET_VALUE) as k:
            winreg.QueryValueEx(k, OLD_RUN_NAME)
            winreg.DeleteValue(k, OLD_RUN_NAME)
            winreg.SetValueEx(k, APP_NAME, 0, winreg.REG_SZ, run_command())
    except OSError:
        pass  # no old entry
    if startup_enabled():  # entries from before 2.2 have no --autostart flag
        set_startup(True)


def startup_enabled():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            winreg.QueryValueEx(k, APP_NAME)
            return True
    except OSError:
        return False


def set_startup(on):
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
        if on:
            winreg.SetValueEx(k, APP_NAME, 0, winreg.REG_SZ, run_command())
        else:
            try:
                winreg.DeleteValue(k, APP_NAME)
            except FileNotFoundError:
                pass


def screens():
    """Monitors numbered left-to-right, top-to-bottom (Monitor 1, 2, ...)."""
    return sorted(QGuiApplication.screens(), key=lambda sc: (sc.geometry().x(), sc.geometry().y()))


def field_range(sec, key):
    for _, (s, fields) in FIELDS.items():
        if s == sec:
            for name, _t, lo, hi in fields:
                if name == key:
                    return lo, hi
    raise KeyError((sec, key))


class SettingsWindow(QWidget):
    def __init__(self, app):
        """app: main.App (cfg, ov, on_change(kind) with kind in crosshair/profile/hotkeys/general, native)."""
        super().__init__()
        self.app = app
        self.cfg, self.ov, self.on_change = app.cfg, app.ov, app.on_change
        self.loaders = []
        self.loading = False
        self.variant = ""  # "" = default crosshair, else a resolution variant key
        self.setWindowTitle(tr("Nullpoint - Settings"))
        self.setWindowIcon(app_icon())
        self.resize(940, 620)

        root = QHBoxLayout(self)
        self.left = QWidget()
        self.left.setFixedWidth(340)
        left = QVBoxLayout(self.left)
        left.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self.left)
        top = QHBoxLayout()
        self.profile_box = QComboBox()
        self.profile_box.currentTextChanged.connect(self._pick_profile)
        self.mode_box = QComboBox()
        self.mode_box.addItems([tr("Line crosshair"), tr("Image"), tr("Text")])
        self.mode_box.currentIndexChanged.connect(self._pick_mode)
        top.addWidget(QLabel(tr("Profile")))
        top.addWidget(self.profile_box, 1)
        top.addWidget(QLabel(tr("Mode")))
        top.addWidget(self.mode_box, 1)
        left.addLayout(top)
        self.search_items = []  # (label, widget, tab index), filled as tabs are built
        self.search = QLineEdit()
        self.search.setPlaceholderText(tr("Search settings..."))
        self.search.setAccessibleName(tr("Search settings"))
        self.search.addAction(icon("search"), QLineEdit.LeadingPosition)
        self.search.returnPressed.connect(lambda: self.jump_to(self.search.text()))
        left.insertWidget(0, self.search)

        # Same draw call as the overlay window, on the same settings object.
        self.preview = PreviewPanel(lambda: (render_image(self.ov.draw, self.ov.c), self.ov.c), tr)
        self.ov.frame.connect(lambda: self.preview.update() if self.isVisible() else None)  # rainbow / GIF
        left.addWidget(self.preview, 1)
        row = QHBoxLayout()
        for text, back in (("Undo", True), ("Redo", False)):
            b = QPushButton(tr(text))
            b.clicked.connect(lambda _=False, b_=back: self.undo_redo(b_))
            row.addWidget(b)
        left.addLayout(row)
        self.status = QLabel("")
        self.status.setWordWrap(True)
        left.addWidget(self.status)
        self.undo_stack, self.redo_stack = [], []
        self._last_record = (None, 0.0)
        for seq, back in ((QKeySequence.Undo, True), (QKeySequence.Redo, False), ("Ctrl+Y", False)):
            QShortcut(QKeySequence(seq), self, activated=lambda b_=back: self.undo_redo(b_))

        self.tabs = QTabWidget()
        self.crosshair_page = self.scroll(self._crosshair_tab())
        self.tabs.addTab(self.crosshair_page, tr("Crosshair"))
        self.image_page = self.scroll(self._image_tab())
        self.tabs.addTab(self.image_page, tr("Image"))
        self.editor = EditorTab(self.apply_image, tr)
        self.tabs.addTab(self.editor, tr("Editor"))
        self.library_page = self._library_tab()
        self.tabs.addTab(self.library_page, tr("Library"))
        self.tabs.addTab(self.scroll(self._games_tab()), tr("Games & Display").replace("&", "&&"))
        self.tabs.addTab(self.scroll(self._share_tab()), tr("Share"))
        self.gallery_page = self._gallery_tab()
        self.tabs.addTab(self.gallery_page, icon("gallery"), tr("Gallery"))
        self.tools_page = tools.ToolsTab(self.cfg, self.on_change)
        self.tabs.addTab(self.tools_page, icon("calculator"), tr("Tools"))
        self.app_page = self.scroll(self._app_tab())
        self.tabs.addTab(self.app_page, tr("App Settings"))
        self.monitor_timer = QTimer(self, interval=2000)  # resource monitor: only while App Settings is open
        self.monitor_timer.timeout.connect(self.update_monitor)
        self.tabs.currentChanged.connect(lambda i: self.monitor_timer.start() if self.tabs.widget(i) is self.app_page
                                         else self.monitor_timer.stop())
        # The editor has its own 1x/4x preview and needs the room.
        self.tabs.currentChanged.connect(lambda i: self.left.setVisible(self.tabs.widget(i) is not self.editor))
        self.tabs.currentChanged.connect(
            lambda i: self.load_library() if self.tabs.widget(i) is self.library_page else None)
        self.tabs.currentChanged.connect(
            lambda i: self.gallery.fetch() if self.tabs.widget(i) is self.gallery_page else None)
        self.setAcceptDrops(True)  # drop a QR screenshot anywhere on the window
        root.addWidget(self.tabs, 1)
        self.finish_search_index()
        self.refresh()

    def scroll(self, page):
        self.index_page(page, self.tabs.count())  # the page is added as the next tab
        sc = QScrollArea()
        sc.setWidgetResizable(True)
        sc.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        sc.setWidget(page)
        return sc

    # ---------- settings search ----------
    def index_page(self, page, tab):
        for g in page.findChildren(QGroupBox):
            self.search_items.append((g.title(), g, tab))
        for form in page.findChildren(QFormLayout):
            for r in range(form.rowCount()):
                lab, fld = form.itemAt(r, QFormLayout.LabelRole), form.itemAt(r, QFormLayout.FieldRole)
                if lab and isinstance(lab.widget(), QLabel) and lab.widget().text() and fld:
                    w = fld.widget() or (fld.layout().itemAt(0).widget() if fld.layout() and fld.layout().count() else None)
                    if w:
                        self.search_items.append((lab.widget().text(), w, tab))

    def finish_search_index(self):
        comp = QCompleter(sorted({label for label, _, _ in self.search_items}), self)
        comp.setCaseSensitivity(Qt.CaseInsensitive)
        comp.setFilterMode(Qt.MatchContains)
        comp.activated.connect(self.jump_to)
        self.search.setCompleter(comp)

    def jump_to(self, text):
        """Open the setting's tab, scroll to it and flash a border around it."""
        text = text.strip().lower()
        hit = next((x for x in self.search_items if x[0].lower() == text), None) or \
            next((x for x in self.search_items if text and text in x[0].lower()), None)
        if not hit:
            return
        _, w, tab = hit
        self.tabs.setCurrentIndex(tab)
        area = self.tabs.widget(tab)
        if isinstance(area, QScrollArea):
            area.ensureWidgetVisible(w, 0, 80)
        old = w.styleSheet()
        w.setStyleSheet(old + f"border: 2px solid {theme.tokens['accent']};")
        QTimer.singleShot(1500, lambda: w.setStyleSheet(old))
        w.setFocus()

    # ---------- data access ----------
    def profile(self):
        return self.cfg["profiles"][self.cfg["active_profile"]]

    def editing(self):
        """The crosshair being edited: the profile's default one, or the resolution variant picked in Games."""
        p = self.profile()
        return p["variants"].get(self.variant) or p["crosshair"] if self.variant else p["crosshair"]

    def set_cross(self, cross):
        p = self.profile()
        if self.variant in p["variants"]:
            p["variants"][self.variant] = cross
        else:
            p["crosshair"] = cross

    def target(self, sec):
        p = self.profile()
        if sec == "profile":
            return p
        if sec == "stretch":
            return p["stretch"]
        if sec == "cross":
            return self.editing()
        return self.editing()[sec]

    # ---------- undo / redo (whole active profile snapshots) ----------
    def record(self, key=None):
        """Snapshot before a change. Rapid changes to the same control (a slider drag, typing) = one step."""
        now = time.monotonic()
        last_key, last_t = self._last_record
        self._last_record = (key, now)
        if key is not None and key == last_key and now - last_t < 0.8:
            return
        self.undo_stack.append((self.cfg["active_profile"], copy.deepcopy(self.profile())))
        del self.undo_stack[:-50]
        self.redo_stack.clear()

    def undo_redo(self, back):
        if self.tabs.currentWidget() is self.editor:  # the editor keeps its own per-stroke history
            self.editor.canvas.step(back)
            return
        src, dst = (self.undo_stack, self.redo_stack) if back else (self.redo_stack, self.undo_stack)
        if not src:
            return
        name, prof = src.pop()
        if name in self.cfg["profiles"]:
            dst.append((name, copy.deepcopy(self.cfg["profiles"][name])))
            self.cfg["profiles"][name] = prof
            self.cfg["active_profile"] = name
            self._last_record = (None, 0.0)
            self.on_change("profile")
            self.refresh()

    def update_visibility(self):
        """Show only what the current Mode uses: Lines -> shape/lines/dot/ring, Text -> text, Image -> Image tab."""
        mode = self.target("cross")["mode"]
        for m, groups in self.mode_groups.items():
            for g in groups:
                g.setVisible(m == mode)
        for rule in self.rules:
            rule()
        cur = self.tabs.currentWidget()
        self.tabs.setTabVisible(self.tabs.indexOf(self.crosshair_page), mode != "png")
        self.tabs.setTabVisible(self.tabs.indexOf(self.image_page), mode == "png")
        if cur in (self.crosshair_page, self.image_page):  # stay on the mode's own tab instead of jumping away
            self.tabs.setCurrentWidget(self.image_page if mode == "png" else self.crosshair_page)

    def set_value(self, sec, key, val):
        if self.loading or self.target(sec)[key] == val:
            return
        self.record((sec, key))
        self.target(sec)[key] = val
        self.on_change("crosshair")
        self.preview.update()
        if sec in ("style", "rainbow", "gradient", "shadow", "arms", "expand", "cross"):
            self.update_visibility()
        if sec in ("stretch", "profile"):
            self.update_display_info()

    def say(self, text, error=False):
        self.status.setStyleSheet(f"color: {theme.tokens['danger' if error else 'ok']};")
        self.status.setText(text)

    # ---------- widgets bound to settings ----------
    def add_slider(self, form, label, sec, key, lo=None, hi=None, dec=0):
        if lo is None:
            lo, hi = field_range(sec, key)
        scale = 10 ** dec
        s = QSlider(Qt.Horizontal)
        s.setAccessibleName(tr(label))
        s.setRange(round(lo * scale), round(hi * scale))
        n = QDoubleSpinBox() if dec else QSpinBox()
        n.setRange(lo, hi)
        if dec:
            n.setDecimals(dec)
            n.setSingleStep(1 / scale)
        n.setObjectName("num")  # QSS hides its arrows (see ui/theme.py)
        n.setAccessibleName(tr(label))
        n.setAlignment(Qt.AlignRight)
        n.setFixedWidth(60)

        def from_spin(v):
            s.blockSignals(True)
            s.setValue(round(v * scale))
            s.blockSignals(False)
            self.set_value(sec, key, round(v, dec) if dec else int(v))

        s.valueChanged.connect(lambda v: n.setValue(v / scale if dec else v))
        n.valueChanged.connect(from_spin)
        self.loaders.append(lambda: n.setValue(self.target(sec)[key]))
        row = QHBoxLayout()
        row.addWidget(s, 1)
        row.addWidget(n)
        form.addRow(tr(label), row)
        return row

    def add_check(self, form, label, sec, key):
        c = QCheckBox()
        c.setAccessibleName(tr(label))
        c.toggled.connect(lambda v: self.set_value(sec, key, v))
        self.loaders.append(lambda: c.setChecked(self.target(sec)[key]))
        form.addRow(tr(label), c)
        return c

    def add_combo(self, form, label, sec, key, items):
        """items: [(stored value, English label)]."""
        box = QComboBox()
        box.setAccessibleName(tr(label))
        for val, text in items:
            box.addItem(tr(text), val)
        box.currentIndexChanged.connect(lambda i: self.set_value(sec, key, box.itemData(i)))
        self.loaders.append(lambda: box.setCurrentIndex(max(0, box.findData(self.target(sec)[key]))))
        form.addRow(tr(label), box)
        return box

    def add_hex(self, form, label, sec, key, allow_empty=False):
        ed = QLineEdit()
        ed.setMaxLength(7)
        ed.setFixedWidth(80)
        ed.setAccessibleName(tr(label))
        if allow_empty:
            ed.setPlaceholderText(tr("Lines color"))

        def changed(text):
            h = text.strip().lstrip("#").upper()
            if re.fullmatch(r"[0-9A-F]{6}", h) or (allow_empty and not h):
                self.set_value(sec, key, h)

        ed.textEdited.connect(changed)
        self.loaders.append(lambda: ed.setText("#" + self.target(sec)[key] if self.target(sec)[key] else ""))
        form.addRow(tr(label), ed)
        return ed

    def _set_color_mode(self, mode):
        if self.loading:
            return
        self.record()
        self.target("rainbow")["on"] = mode == "rainbow"
        self.target("gradient")["on"] = mode == "gradient"
        self.on_change("crosshair")
        self.preview.update()
        self.update_visibility()

    def _colorblind(self, main, outline):
        self.record()
        cross = self.target("cross")
        cross["color"] = main
        cross["colors"].update(lines=main, dot=main, ring=main, outline=outline)
        self.on_change("crosshair")
        self.refresh()

    def _unlink_arms(self, link):
        """Unlinking starts every arm from the current inner line lengths."""
        if not link and not self.loading:
            inner = self.target("inner")
            v = inner["vlen"] if inner["vsep"] else inner["len"]
            self.target("arms").update(t=v, b=v, r=inner["len"], l=inner["len"])
            self.on_change("crosshair")
            self.refresh()

    def _split_colors(self, same):
        """Turning 'same color' off starts every part from the current main color."""
        if not same and not self.loading:
            self.record()
            cols = self.target("colors")
            cols.update(lines=self.target("cross")["color"], dot=self.target("cross")["color"],
                        ring=self.target("cross")["color"])
            self.on_change("crosshair")
            self.refresh()

    def group(self, layout, title, sections, icon_name=None, hint=None):
        """Group box with a per-section 'Reset to default' button (+ optional feature icon and hint line)."""
        g = QGroupBox(tr(title))
        form = QFormLayout(g)
        layout.addWidget(g)
        if icon_name:
            pic = QLabel()
            pic.setPixmap(icon(icon_name).pixmap(18, 18))
            note = QLabel(tr(hint) if hint else "")
            note.setObjectName("muted")
            note.setWordWrap(True)
            form.addRow(pic, note)

        def reset():
            self.record()
            for sec in sections:
                if sec == "color":
                    self.target("cross")["color"] = config.DEFAULT_CROSSHAIR["color"]
                elif sec == "offset":
                    self.target("profile").update(offset_x=0, offset_y=0)
                elif sec == "display":
                    self.target("profile").update(monitor=0, stretch=copy.deepcopy(config.DEFAULT_PROFILE["stretch"]))
                else:
                    self.target("cross")[sec] = copy.deepcopy(config.DEFAULT_CROSSHAIR[sec])
            self.on_change("crosshair")
            self.refresh()

        btn = QPushButton(tr("Reset to default"))
        btn.clicked.connect(reset)
        return g, form, btn

    def _crosshair_tab(self):
        self.mode_groups = {"lines": [], "text": []}  # groups shown only in that Mode
        self.rules = []  # small show/hide rules re-run after every change
        page = QWidget()
        grid = QGridLayout(page)
        lay, lay2 = QVBoxLayout(), QVBoxLayout()
        grid.addLayout(lay, 0, 0, Qt.AlignTop)
        grid.addLayout(lay2, 1, 0, Qt.AlignTop)  # one column: two don't fit next to the preview

        g, f, reset = self.group(lay, "Shape", ["shape", "rot", "style"], "shapes",
                                 "Shape presets and solid / dashed / dotted lines.")
        self.add_combo(f, "Shape", "cross", "shape", SHAPES)
        self.add_slider(f, "Line rotation", "cross", "rot", 0, 90)
        self.add_combo(f, "Line style", "style", "kind", LINE_STYLES)
        dash = self.add_slider(f, "Dash length", "style", "dash", 1, 10)
        gap = self.add_slider(f, "Dash gap", "style", "gap", 1, 10)
        f.addRow(reset)
        kind = lambda: self.target("style")["kind"]
        self.rules += [lambda f=f: f.setRowVisible(dash, kind() == "dashed"),
                       lambda f=f: f.setRowVisible(gap, kind() != "solid")]
        self.mode_groups["lines"].append(g)

        g, f, reset = self.group(lay, "Color", ["color", "colors", "rainbow", "gradient"])
        swatches = QHBoxLayout()
        for hexc in PRESETS:
            b = QPushButton()
            b.setFixedSize(22, 22)
            b.setStyleSheet(f"background:#{hexc}; border:1px solid #555;")
            b.clicked.connect(lambda _=False, h=hexc: self._set_color(h))
            swatches.addWidget(b)
        self.hex_edit = QLineEdit()
        self.hex_edit.setMaxLength(7)
        self.hex_edit.setFixedWidth(80)
        self.hex_edit.setPlaceholderText("#RRGGBB")
        self.hex_edit.textEdited.connect(lambda t: self._set_color(t, quiet=True))  # live while typing
        self.hex_edit.editingFinished.connect(lambda: self._set_color(self.hex_edit.text()))
        swatches.addWidget(self.hex_edit)
        swatches.addStretch()
        f.addRow(tr("Color"), swatches)
        self.loaders.append(lambda: self.hex_edit.setText("#" + self.target("cross")["color"]))
        same = self.add_check(f, "Use same color for all", "colors", "same")
        part_rows = [self.add_hex(f, label, "colors", key) for key, label in (
            ("lines", "Lines color"), ("dot", "Center dot color"), ("ring", "Ring color"), ("outline", "Outline color"))]
        same.toggled.connect(lambda on, f=f: [f.setRowVisible(w, not on) for w in part_rows])
        same.toggled.connect(self._split_colors)
        self.loaders.append(lambda f=f: [f.setRowVisible(w, not self.target("colors")["same"]) for w in part_rows])
        mode = QComboBox()
        for val, text in (("static", "Static"), ("gradient", "Gradient"), ("rainbow", "Rainbow")):
            mode.addItem(icon("gradient") if val == "gradient" else QIcon(), tr(text), val)
        mode.currentIndexChanged.connect(lambda i: self._set_color_mode(mode.itemData(i)))
        self.loaders.append(lambda: mode.setCurrentIndex(
            2 if self.target("rainbow")["on"] else 1 if self.target("gradient")["on"] else 0))
        f.addRow(tr("Color mode"), mode)
        tip = self.add_hex(f, "Gradient tip color", "gradient", "c2")
        speed = self.add_slider(f, "Rainbow speed", "rainbow", "speed")
        sat = self.add_slider(f, "Rainbow saturation", "rainbow", "sat", dec=2)
        rainbow = lambda: self.target("rainbow")["on"]
        self.rules += [lambda f=f: f.setRowVisible(tip, self.target("gradient")["on"] and not rainbow()),
                       lambda f=f: f.setRowVisible(speed, rainbow()), lambda f=f: f.setRowVisible(sat, rainbow())]
        cb = QGridLayout()
        for i, (name, main, outline) in enumerate(COLORBLIND):
            b = QPushButton(icon("colorblind"), tr(name))
            b.setToolTip(tr("Sets colors only"))
            b.clicked.connect(lambda _=False, m=main, o=outline: self._colorblind(m, o))
            cb.addWidget(b, i // 2, i % 2)
        f.addRow(tr("Colorblind presets"), cb)
        f.addRow(reset)

        g, f, reset = self.group(lay, "Outline", ["outline"])
        self.add_check(f, "Outline", "outline", "on")
        self.add_slider(f, "Outline thickness", "outline", "thick")
        self.add_slider(f, "Outline opacity", "outline", "alpha", dec=2)
        f.addRow(reset)

        g, f, reset = self.group(lay, "Shadow", ["shadow"], "shadow",
                                 "Soft dark halo under the outline, for bright backgrounds.")
        self.add_check(f, "Show shadow", "shadow", "on")
        self.add_combo(f, "Halo type", "shadow", "mode", HALO_MODES)
        glow = self.add_hex(f, "Glow color", "shadow", "color")
        self.add_slider(f, "Shadow size", "shadow", "size")
        self.add_slider(f, "Shadow opacity", "shadow", "alpha", dec=2)
        self.rules.append(lambda f=f: f.setRowVisible(glow, self.target("shadow")["mode"] == "glow"))
        f.addRow(reset)

        g, f, reset = self.group(lay, "Text crosshair", ["text"], "text_crosshair",
                                 "Used when Mode is set to Text: 1-3 characters, e.g. + • × ◆")
        self.mode_groups["text"].append(g)
        chars = QLineEdit()
        chars.setMaxLength(3)
        chars.setAccessibleName(tr("Characters"))
        chars.textEdited.connect(lambda t: self.set_value("text", "chars", t))
        self.loaders.append(lambda: chars.setText(self.target("text")["chars"]))
        f.addRow(tr("Characters"), chars)
        font_row = QHBoxLayout()
        font = QFontComboBox()
        font.currentFontChanged.connect(lambda fo: self.set_value("text", "font", fo.family()))
        self.loaders.append(lambda: font.setCurrentFont(QFont(self.target("text")["font"] or self.font().family())))
        default_font = QPushButton(tr("Default"))
        default_font.clicked.connect(lambda: (self.set_value("text", "font", ""), self.refresh()))
        font_row.addWidget(font, 1)
        font_row.addWidget(default_font)
        f.addRow(tr("Font"), font_row)
        self.add_slider(f, "Text size", "text", "size", 8, 96)
        self.add_check(f, "Bold", "text", "bold")
        self.add_slider(f, "Opacity", "text", "alpha", 0, 1, dec=2)
        f.addRow(reset)

        g, f, reset = self.group(lay2, "Center Dot", ["dot"])
        self.mode_groups["lines"].append(g)
        self.add_check(f, "Show", "dot", "on")
        self.add_combo(f, "Dot shape", "dot", "shape", DOT_SHAPES)
        self.add_slider(f, "Size", "dot", "size")
        self.add_slider(f, "Opacity", "dot", "alpha", dec=2)
        f.addRow(reset)

        for sec, title in (("inner", "Inner Lines"), ("outer", "Outer Lines")):
            g, f, reset = self.group(lay2, title, [sec])
            self.mode_groups["lines"].append(g)
            self.add_check(f, "Show", sec, "on")
            self.add_slider(f, "Length", sec, "len")
            self.add_slider(f, "Thickness", sec, "thick")
            self.add_slider(f, "Gap", sec, "gap")
            self.add_slider(f, "Opacity", sec, "alpha", dec=2)
            self.add_check(f, "Separate vertical length", sec, "vsep")
            self.add_slider(f, "Vertical length", sec, "vlen")
            f.addRow(reset)

        g, f, reset = self.group(lay2, "Per-arm", ["arms"], "line_style",
                                 "Off = give each arm (inner lines) its own length and color.")
        self.mode_groups["lines"].append(g)
        link = self.add_check(f, "Link all arms", "arms", "link")
        link.toggled.connect(self._unlink_arms)
        arm_rows = [self.add_slider(f, f"{name} length", "arms", a) for a, name in ARMS]
        arm_rows += [self.add_hex(f, f"{name} color", "arms", "c" + a, allow_empty=True) for a, name in ARMS]
        self.rules.append(lambda f=f: [f.setRowVisible(w, not self.target("arms")["link"]) for w in arm_rows])
        self.rules.append(lambda g=g: g.setVisible(self.target("cross")["mode"] == "lines"
                                                   and self.target("cross")["shape"] in ("cross", "t", "x")))
        f.addRow(reset)

        g, f, reset = self.group(lay2, "Fire expand", ["expand"], "quick_switch",
                                 "While you hold left mouse in a game, the lines move outward. Visual only.")
        self.mode_groups["lines"].append(g)
        self.add_check(f, "Expand while firing", "expand", "on")
        rows = [self.add_slider(f, "Expand by (px)", "expand", "px"), self.add_slider(f, "Expand time (ms)", "expand", "ms")]
        self.rules.append(lambda f=f: [f.setRowVisible(w, self.target("expand")["on"]) for w in rows])
        f.addRow(reset)

        g, f, reset = self.group(lay2, "Ring", ["ring"])
        self.mode_groups["lines"].append(g)
        self.add_check(f, "Show ring", "ring", "on")
        self.add_slider(f, "Radius", "ring", "radius")
        self.add_slider(f, "Thickness", "ring", "thick")
        self.add_slider(f, "Opacity", "ring", "alpha", dec=2)
        self.add_slider(f, "Number of gaps", "ring", "gaps")
        self.add_slider(f, "Gap size", "ring", "gapsize")
        self.add_slider(f, "Gap rotation", "ring", "gaprot")
        f.addRow(reset)
    
        return page

    def _image_tab(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.addWidget(QLabel(tr("Used when Mode is set to Image.")))
        g, f, reset = self.group(lay, "Image", ["png"])
        row = QHBoxLayout()
        self.png_label = QLabel()
        self.png_label.setWordWrap(True)
        b = QPushButton(tr("Browse..."))
        b.clicked.connect(self._browse_png)
        row.addWidget(self.png_label, 1)
        row.addWidget(b)
        f.addRow(tr("File"), row)
        self.loaders.append(lambda: self.png_label.setText(
            os.path.basename(self.profile()["png_path"]) or tr("(none)")))
        self.add_slider(f, "Scale %", "png", "scale")
        self.add_slider(f, "Opacity", "png", "alpha", dec=2)
        rot = QComboBox()
        rot.addItems(["0", "90", "180", "270"])
        rot.currentTextChanged.connect(lambda t: self.set_value("png", "rot", int(t)))
        self.loaders.append(lambda: rot.setCurrentText(str(self.target("png")["rot"])))
        f.addRow(tr("Rotation"), rot)
        self.add_check(f, "Pause animation (GIF)", "profile", "anim_paused")
        f.addRow(reset)

        lay.addStretch()
        return page

    def _games_tab(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.addWidget(QLabel(tr("When one of these programs is focused, its profile is used. "
                                "Anything else uses the Default profile.")))
        self.games_table = QTableWidget(0, 2)
        self.games_table.setHorizontalHeaderLabels([tr("Process"), tr("Profile")])
        self.games_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.games_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.games_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.games_table.setMinimumHeight(180)
        lay.addWidget(self.games_table)
        row = QHBoxLayout()
        for text, fn in (("Browse .exe...", self._add_game_browse), ("Type name...", self._add_game_name),
                         ("Remove", self._remove_game), ("Rename profile...", self._rename_profile),
                         ("Copy to...", self._copy_to)):
            b = QPushButton(tr(text))
            b.clicked.connect(fn)
            row.addWidget(b)
        lay.addLayout(row)
        b = QPushButton(icon("search"), tr("Detect installed games..."))
        b.clicked.connect(self._detect_games)
        lay.addWidget(b, 0, Qt.AlignLeft)

        g, f, reset = self.group(lay, "Profile rules", [], "tags",
                                 "Match by program and/or window title. Tested top to bottom, before the list above.")
        reset.hide()
        self.rules_list = QListWidget()
        self.rules_list.setMaximumHeight(110)
        f.addRow(self.rules_list)
        row = QHBoxLayout()
        for text, fn in (("Add rule...", lambda: self._edit_rule(None)), ("Edit...", lambda: self._edit_rule(
                self.rules_list.currentRow())), ("Remove", self._remove_rule), ("Up", lambda: self._move_rule(-1)),
                         ("Down", lambda: self._move_rule(1))):
            b = QPushButton(tr(text))
            b.clicked.connect(fn)
            row.addWidget(b)
        f.addRow(row)
        self.loaders.append(self._load_rules)

        g, f, reset = self.group(lay, "Resolution variants (this profile)", [], "compare",
                                 "A different crosshair for a game window size, e.g. 1440x1080 stretched. "
                                 "No match = the profile's default crosshair.")
        reset.hide()
        self.variant_box = QComboBox()
        self.variant_box.currentIndexChanged.connect(self._pick_variant)
        f.addRow(tr("Editing"), self.variant_box)
        self.res_label = QLabel()
        self.res_label.setObjectName("muted")
        f.addRow(self.res_label)
        row = QHBoxLayout()
        for text, fn in (("Add for current game size", lambda: self._add_variant(self.app.game_res)),
                         ("Add size...", lambda: self._add_variant(None)), ("Remove", self._remove_variant)):
            b = QPushButton(tr(text))
            b.clicked.connect(fn)
            row.addWidget(b)
        f.addRow(row)
        self.loaders.append(self._load_variants)

        g, f, reset = self.group(lay, "HDR", [], "gradient",
                                 "Brightens the crosshair when Windows HDR makes it look dim. Never reads the game image.")
        reset.hide()
        hb = QComboBox()
        for val, text in (("Off", "Off"), ("Manual", "Manual"), ("Auto", "Auto (when HDR is on)")):
            hb.addItem(tr(text), val)
        hb.setCurrentIndex(max(0, hb.findData(self.cfg["hdr"]["mode"])))
        hb.currentIndexChanged.connect(lambda i: (self.cfg["hdr"].update(mode=hb.itemData(i)), self.on_change("hdr")))
        f.addRow(tr("HDR compensation"), hb)
        mult = QDoubleSpinBox()
        mult.setRange(1.0, 3.0)
        mult.setSingleStep(0.1)
        mult.setValue(self.cfg["hdr"]["mult"])
        mult.valueChanged.connect(lambda v: (self.cfg["hdr"].update(mult=round(v, 2)), self.on_change("hdr")))
        f.addRow(tr("Brightness multiplier"), mult)

        g, f, reset = self.group(lay, "Display (this profile)", ["offset", "display"])
        self.monitor_box = QComboBox()
        self.monitor_box.currentIndexChanged.connect(
            lambda i: None if self.loading or i < 0 else self.set_value("profile", "monitor", i))
        self.loaders.append(self._load_monitors)
        f.addRow(tr("Monitor"), self.monitor_box)
        offs = [self.add_slider(f, "Offset X px", "profile", "offset_x", -200, 200),
                self.add_slider(f, "Offset Y px", "profile", "offset_y", -200, 200)]
        self.offset_spins = [r.itemAt(1).widget() for r in offs]
        for sp in self.offset_spins:
            sp.installEventFilter(self)
            sp.setToolTip(tr("Arrow keys move the crosshair 1 px (Shift: 5 px)."))
        self.add_check(f, "Stretched resolution", "stretch", "on")
        self.add_slider(f, "In-game width", "stretch", "w", 640, 7680)
        self.add_slider(f, "In-game height", "stretch", "h", 480, 4320)
        self.add_slider(f, "Native width (0 = auto)", "stretch", "native_w", 0, 7680)
        self.display_info = QLabel()
        self.display_info.setObjectName("muted")
        f.addRow(self.display_info)
        f.addRow(reset)
        lay.addStretch()
        return page

    def _load_monitors(self):
        self.monitor_box.clear()
        self.monitor_box.addItem(tr("Follow game window"))
        for i, sc in enumerate(screens(), 1):
            g = sc.geometry()
            self.monitor_box.addItem(f"{tr('Monitor')} {i} ({g.width()}x{g.height()})")
        self.monitor_box.setCurrentIndex(min(self.profile()["monitor"], self.monitor_box.count() - 1))

    def update_display_info(self):
        nw, nh = self.app.native
        text = f"{tr('Native resolution')}: {nw}x{nh}"
        if self.profile()["stretch"]["on"]:
            text += f"  |  {tr('Horizontal scale')}: {self.app.stretch_factor():.3f}x"
        self.display_info.setText(text)

    def _share_tab(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        g, f, reset = self.group(lay, "Share code", [])
        reset.hide()
        self.code_edit = QLineEdit()
        self.code_edit.setReadOnly(True)
        f.addRow(self.code_edit)
        self.loaders.append(lambda: self.code_edit.setText(export_code(self.target("cross"))))
        self.share_row = QHBoxLayout()
        for text, fn in (("Copy Code", self._copy_code), ("Paste Code", self._paste_code)):
            b = QPushButton(tr(text))
            b.clicked.connect(fn)
            self.share_row.addWidget(b)
        b = QPushButton(tr("Show QR"))
        b.clicked.connect(self._show_qr)
        self.share_row.addWidget(b)
        f.addRow(self.share_row)
        row = QHBoxLayout()
        for text, ic, fn in (("Save share card...", "share_card", self._save_card),
                             ("Copy share card", "share_card", self._copy_card),
                             ("Import from image...", "qr_import", self._import_image),
                             ("Paste image", "qr_import", self._paste_image),
                             ("Export SVG...", "shapes", self._export_svg)):
            b = QPushButton(icon(ic), tr(text))
            b.clicked.connect(fn)
            row.addWidget(b)
        f.addRow(row)
        hint = QLabel(tr("You can also drop a QR image onto this window."))
        hint.setObjectName("muted")
        f.addRow(hint)

        g, f, reset = self.group(lay, "Import VALORANT / CS2 code", [], "link",
                                 "Paste a VALORANT code (0;P;...) e.g. from vcrdb.net, or a CS2 / CS:GO code (CSGO-...).")
        reset.hide()
        self.val_edit = QPlainTextEdit()
        self.val_edit.setPlaceholderText("0;P;c;5;h;0;0l;4;0o;2;0a;1;0f;0;1b;0")
        self.val_edit.setFixedHeight(64)
        self.val_edit.setAccessibleName(tr("Import VALORANT / CS2 code"))
        self.val_edit.textChanged.connect(self._val_preview)
        f.addRow(self.val_edit)
        self.val_cross = None
        self.val_view = PixelView(lambda: self._val_image(), zoom=4, bg="Dark", size=160)
        self.val_view.setFixedHeight(160)
        self.val_note = QLabel()
        self.val_note.setWordWrap(True)
        row = QHBoxLayout()
        row.addWidget(self.val_view, 1)
        col = QVBoxLayout()
        for text, fn in (("Paste from clipboard", lambda: self.val_edit.setPlainText(QGuiApplication.clipboard().text())),
                         ("Apply", self._val_apply), ("Save to library", self._val_save),
                         ("Browse VCRDB", lambda: QDesktopServices.openUrl(QUrl("https://www.vcrdb.net/")))):
            b = QPushButton(tr(text))
            b.clicked.connect(fn)
            col.addWidget(b)
        acc = QCheckBox(tr("Keep 1080p size"))
        acc.setChecked(self.cfg["valorant_scale_1080"])
        acc.setToolTip(tr("Off (default): exact VALORANT pixels, the same as in game at any resolution. "
                          "On: scale by screen height / 1080, e.g. to match a crosshair you used at 1080p."))
        acc.toggled.connect(lambda v: (self._set_cfg("valorant_scale_1080", v), self._val_preview()))
        col.addWidget(acc)
        col.addStretch()
        row.addLayout(col)
        f.addRow(row)
        f.addRow(self.val_note)

        g, f, reset = self.group(lay, "Backup", [])
        reset.hide()
        f.addRow(QLabel(tr("One .json file with every profile, the library and all settings. "
                           "Custom images are embedded, so the file works on another PC.")))
        row = QHBoxLayout()
        for text, fn in (("Export all...", self._export_all), ("Import...", self._import_all)):
            b = QPushButton(tr(text))
            b.clicked.connect(fn)
            row.addWidget(b)
        f.addRow(row)
        lay.addStretch()
        return page

    # ---------- library ----------
    def _library_tab(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.addWidget(QLabel(tr("Click a crosshair to apply it to the current profile.")))
        top = QHBoxLayout()
        self.lib_search = QLineEdit()
        self.lib_search.setPlaceholderText(tr("Search name or tag"))
        self.lib_search.setAccessibleName(tr("Search library"))
        self.lib_search.addAction(icon("search"), QLineEdit.LeadingPosition)
        self.lib_search.textChanged.connect(lambda _: self.load_library())
        top.addWidget(self.lib_search, 1)
        self.chip_row = QHBoxLayout()
        top.addLayout(self.chip_row)
        lay.addLayout(top)
        self.active_tags = set()
        self.lib_list = QListWidget()
        self.lib_list.setViewMode(QListWidget.IconMode)
        self.lib_list.setIconSize(QSize(64, 64))
        self.lib_list.setGridSize(QSize(110, 100))
        self.lib_list.setResizeMode(QListWidget.Adjust)
        self.lib_list.setMovement(QListWidget.Static)
        self.lib_list.itemClicked.connect(lambda it: self._lib_apply())
        lay.addWidget(self.lib_list, 1)
        row = QHBoxLayout()
        for text, fn in (("Save current to library", self._lib_save), ("Apply", self._lib_apply),
                         ("Rename", self._lib_rename), ("Duplicate", self._lib_duplicate), ("Delete", self._lib_delete),
                         ("Favorite", self._lib_fav), ("Tags...", self._lib_tags), ("Compare...", self._compare)):
            b = QPushButton(tr(text))
            b.clicked.connect(fn)
            row.addWidget(b)
        lay.addLayout(row)
        return page

    @staticmethod
    def thumbnail(cross, image=""):
        """Same renderer as the overlay, scaled into a 64x64 icon with sharp pixels."""
        pm = overlay.png_pixmap(image, cross["png"]) if cross["mode"] == "png" else None
        c = overlay.extent(cross, pm)
        img = render_image(lambda p, cc: overlay.render(p, cross, cc, pm), c)
        icon = QImage(64, 64, QImage.Format_ARGB32_Premultiplied)
        icon.fill(QColor("#111111"))
        z = max(1, 64 // img.width()) if img.width() <= 64 else 0
        p = QPainter(icon)
        if z:
            p.drawImage((64 - img.width() * z) // 2, (64 - img.height() * z) // 2,
                        img.scaled(img.width() * z, img.height() * z))
        else:
            p.setRenderHint(QPainter.SmoothPixmapTransform)
            p.drawImage(icon.rect(), img)
        p.end()
        return QIcon(QPixmap.fromImage(icon))

    def load_library(self):
        """Favorites first, filtered by the search text (name or tag) and the selected tag chips."""
        self.lib_entries = library.load()
        q = self.lib_search.text().strip().lower()
        tags = sorted({t for e in self.lib_entries for t in e["tags"]}, key=str.lower)
        self.active_tags &= set(tags)
        while self.chip_row.count():
            self.chip_row.takeAt(0).widget().deleteLater()
        for t in tags:
            b = QPushButton(icon("tags"), t)
            b.setCheckable(True)
            b.setChecked(t in self.active_tags)
            b.toggled.connect(lambda on, t=t: (self.active_tags.add(t) if on else self.active_tags.discard(t),
                                               self.load_library()))
            self.chip_row.addWidget(b)
        self.lib_list.clear()
        order = sorted(range(len(self.lib_entries)), key=lambda i: not self.lib_entries[i]["fav"])
        for i in order:
            e = self.lib_entries[i]
            text = " ".join([e["name"]] + e["tags"]).lower()
            if (q and q not in text) or not self.active_tags <= set(e["tags"]):
                continue
            item = QListWidgetItem(self.thumbnail(e["crosshair"], e["image"]), ("★ " if e["fav"] else "") + e["name"])
            item.setData(Qt.UserRole, i)
            item.setToolTip(", ".join(e["tags"]))
            self.lib_list.addItem(item)

    def _lib_fav(self):
        row = self._lib_selected()
        if row is not None:
            self.lib_entries[row]["fav"] = not self.lib_entries[row]["fav"]
            library.save(self.lib_entries)
            self.load_library()

    def _lib_tags(self):
        row = self._lib_selected()
        if row is None:
            return
        text, ok = QInputDialog.getText(self, tr("Tags"), tr("Tags (comma separated):"),
                                        text=", ".join(self.lib_entries[row]["tags"]))
        if ok:
            self.lib_entries[row]["tags"] = [t.strip()[:24] for t in text.split(",") if t.strip()][:12]
            library.save(self.lib_entries)
            self.load_library()

    def _compare(self):
        """Side by side: the current crosshair vs a library item or a pasted share code. Shared zoom/background."""
        entries = library.load()
        dlg = QDialog(self)
        dlg.setWindowTitle(tr("Compare"))
        dlg.setWindowIcon(icon("compare"))
        v = QVBoxLayout(dlg)
        row = QHBoxLayout()
        pick = QComboBox()
        for e in entries:
            pick.addItem(e["name"])
        pick.addItem(tr("Pasted share code"))
        code = QLineEdit()
        code.setPlaceholderText("XH3;...")
        row.addWidget(QLabel(tr("Compare with")))
        row.addWidget(pick, 1)
        row.addWidget(code, 2)
        v.addLayout(row)
        sel = self._lib_selected() if hasattr(self, "lib_entries") else None
        sel = -1 if sel is None else sel
        pick.setCurrentIndex(sel if 0 <= sel < len(entries) else len(entries))

        def other():
            i = pick.currentIndex()
            try:
                cr, img = (entries[i]["crosshair"], entries[i]["image"]) if i < len(entries) \
                    else (import_code(code.text()), "")
            except ShareCodeError:
                return None
            pm = overlay.png_pixmap(img, cr["png"]) if cr["mode"] == "png" else None
            c = overlay.extent(cr, pm)
            return render_image(lambda p, cc: overlay.render(p, cr, cc, pm), c), c

        mine = PreviewPanel(lambda: (render_image(self.ov.draw, self.ov.c), self.ov.c), tr)
        theirs = PixelView(other)
        mine.link(theirs)
        pick.currentIndexChanged.connect(theirs.update)
        code.textChanged.connect(theirs.update)
        views = QHBoxLayout()
        for title, w in ((tr("Current"), mine), (tr("Other"), theirs)):
            col = QVBoxLayout()
            col.addWidget(QLabel(title))
            col.addWidget(w, 1, Qt.AlignTop)
            views.addLayout(col)
        v.addLayout(views)
        dlg.resize(720, 460)
        dlg.exec()

    def _lib_selected(self):
        item = self.lib_list.currentItem()
        row = item.data(Qt.UserRole) if item else None
        return row if row is not None and 0 <= row < len(self.lib_entries) else None

    def _lib_save(self):
        name, ok = QInputDialog.getText(self, tr("Save to library"), tr("Name:"), text=self.cfg["active_profile"])
        if ok and name.strip():
            library.add(name.strip(), copy.deepcopy(self.target("cross")), self.profile()["png_path"])
            self.load_library()

    def _lib_apply(self):
        row = self._lib_selected()
        if row is None:
            return
        e = self.lib_entries[row]
        self.record()
        self.set_cross(copy.deepcopy(e["crosshair"]))
        if e["image"]:
            self.profile()["png_path"] = e["image"]
        self.on_change("crosshair")
        self.refresh()
        self.say(f"{tr('Applied')}: {e['name']} ({self.cfg['active_profile']})")

    def _lib_rename(self):
        row = self._lib_selected()
        if row is None:
            return
        name, ok = QInputDialog.getText(self, tr("Rename"), tr("Name:"), text=self.lib_entries[row]["name"])
        if ok and name.strip():
            self.lib_entries[row]["name"] = name.strip()
            library.save(self.lib_entries)
            self.load_library()

    def _lib_duplicate(self):
        row = self._lib_selected()
        if row is not None:
            e = copy.deepcopy(self.lib_entries[row])
            e["name"] += " " + tr("(copy)")
            self.lib_entries.insert(row + 1, e)
            library.save(self.lib_entries)
            self.load_library()

    def _lib_delete(self):
        row = self._lib_selected()
        if row is not None and QMessageBox.question(
                self, tr("Delete"), f"{tr('Delete from library')}: {self.lib_entries[row]['name']}?") == QMessageBox.Yes:
            del self.lib_entries[row]
            library.save(self.lib_entries)
            self.load_library()

    # ---------- VALORANT codes ----------
    def screen_h(self):
        return self.app.native[1] or 1080

    def val_scale(self):
        h = self.app.native[1]
        return h / 1080 if self.cfg["valorant_scale_1080"] and h else 1.0

    def _val_preview(self):
        text = self.val_edit.toPlainText().strip()
        self.val_cross = None
        if not text:
            self.val_note.setText("")
        else:
            try:
                self.val_cross, kind = valorant.import_any(text, self.val_scale(), self.screen_h())
                if kind == "cs2":
                    note = tr("Converted from CS2") + f" ({tr('sized for')} {self.screen_h()}p)"
                elif kind == "valorant":
                    scale = self.val_scale()
                    note = tr("Converted from VALORANT") + (f" ({tr('size scale')} {scale:.2f}x)" if scale != 1
                                                           else f" ({tr('exact pixels')})")
                else:
                    note = tr("Nullpoint code")
                self.val_note.setText(note)
                self.val_note.setStyleSheet(f"color: {theme.tokens['ok']};")
            except ShareCodeError as e:
                self.val_note.setText(f"{tr('Invalid code')}: {e}")
                self.val_note.setStyleSheet(f"color: {theme.tokens['danger']};")
        self.val_view.update()

    def _val_image(self):
        if not self.val_cross:
            return None
        cr = self.val_cross
        c = overlay.extent(cr)
        return render_image(lambda p, cc: overlay.render(p, cr, cc), c), c

    def _val_apply(self):
        if not self.val_cross:
            self.say(tr("Paste a VALORANT or CS2 code first."), True)
            return
        self.record()
        self.set_cross(copy.deepcopy(self.val_cross))
        self.on_change("crosshair")
        self.refresh()
        self.say(f"{tr('Code applied to profile')}: {self.cfg['active_profile']}")

    def _val_save(self):
        if not self.val_cross:
            self.say(tr("Paste a VALORANT or CS2 code first."), True)
            return
        name, ok = QInputDialog.getText(self, tr("Save to library"), tr("Name:"),
                                        text="CS2" if cs2.is_cs2(self.val_edit.toPlainText()) else "VALORANT")
        if ok and name.strip():
            library.add(name.strip(), copy.deepcopy(self.val_cross),
                        tags=["cs2"] if cs2.is_cs2(self.val_edit.toPlainText()) else ["valorant"])
            self.say(tr("Added to library"))

    # ---------- share card / QR import / confirm ----------
    def _card(self):
        cross = self.target("cross")
        return sharing.share_card(cross, export_code(cross), self.ov.pixmap if cross["mode"] == "png" else None)

    def _export_svg(self):
        cross = self.target("cross")
        svg = svg_export.to_svg(cross, self.ov.pixmap if cross["mode"] == "png" else None)
        if not svg:
            self.say(tr("Pick an image first."), True)
            return
        path, _ = QFileDialog.getSaveFileName(self, tr("Export SVG..."), "crosshair.svg", tr("SVG files (*.svg)"))
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(svg)
            self.say(tr("SVG saved"))
        except OSError as e:
            self.say(str(e), True)

    def _save_card(self):
        path, _ = QFileDialog.getSaveFileName(self, tr("Save share card"), "nullpoint_crosshair.png", "PNG (*.png)")
        if path:
            ok = self._card().save(path, "PNG")
            self.say(tr("Saved") + f": {os.path.basename(path)}" if ok else tr("Could not save the file."), not ok)

    def _copy_card(self):
        QGuiApplication.clipboard().setImage(self._card())
        self.say(tr("Share card copied to clipboard."))

    def import_qr_image(self, img):
        try:
            code = sharing.decode_qr(img)
        except ShareCodeError as e:
            self.say(f"{tr('Import failed')}: {e}", True)
            return
        self.confirm_import(code, tr("From a QR image"))

    def _import_image(self):
        path, _ = QFileDialog.getOpenFileName(self, tr("Import from image"), "", "Images (*.png *.jpg *.jpeg *.bmp *.webp)")
        if path:
            self.import_qr_image(QImage(path))

    def _paste_image(self):
        img = QGuiApplication.clipboard().image()
        if img.isNull():
            self.say(tr("The clipboard has no image."), True)
        else:
            self.import_qr_image(img)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls() or e.mimeData().hasImage():
            e.acceptProposedAction()

    def dropEvent(self, e):
        md = e.mimeData()
        if md.hasImage():
            self.import_qr_image(QImage(md.imageData()))
        elif md.hasUrls() and md.urls()[0].isLocalFile():
            self.import_qr_image(QImage(md.urls()[0].toLocalFile()))

    def confirm_import(self, code, source=""):
        """Preview + 'Import this crosshair?'. Nothing changes unless the user picks an action."""
        try:
            cross, kind = valorant.import_any(code, self.val_scale(), self.screen_h())
        except ShareCodeError as e:
            self.say(f"{tr('Invalid code')}: {e}", True)
            return
        if kind in ("valorant", "cs2"):
            source = (source + "  -  " if source else "") + tr(
                "Converted from VALORANT" if kind == "valorant" else "Converted from CS2")
        self.show()
        self.raise_()
        dlg = QDialog(self)
        dlg.setWindowTitle(tr("Import this crosshair?"))
        dlg.setWindowIcon(icon("link"))
        v = QVBoxLayout(dlg)
        if source:
            v.addWidget(QLabel(source))
        c = overlay.extent(cross)
        img = render_image(lambda p, cc: overlay.render(p, cross, cc), c)
        view = PixelView(lambda: (img, c), zoom=4, bg="Dark", size=220)
        v.addWidget(view, 0, Qt.AlignCenter)
        text = QLabel(code)
        text.setWordWrap(True)
        text.setTextInteractionFlags(Qt.TextSelectableByMouse)
        v.addWidget(text)
        bb = QDialogButtonBox()
        apply_btn = bb.addButton(tr("Apply to current profile"), QDialogButtonBox.AcceptRole)
        lib_btn = bb.addButton(tr("Save to library"), QDialogButtonBox.ActionRole)
        bb.addButton(QDialogButtonBox.Cancel)
        choice = {}
        bb.clicked.connect(lambda b: (choice.setdefault("b", b), dlg.accept()))
        v.addWidget(bb)
        dlg.exec()
        b = choice.get("b")
        if b is apply_btn:
            self.record()
            self.set_cross(cross)
            self.on_change("crosshair")
            self.refresh()
            self.say(f"{tr('Code applied to profile')}: {self.cfg['active_profile']}")
        elif b is lib_btn:
            library.add(tr("Imported"), cross)
            self.say(tr("Added to library"))

    # ---------- gallery ----------
    def _gallery_tab(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.addWidget(QLabel(tr("Community crosshairs from github.com/yensobased1/nullpoint (gallery folder). "
                                "Loaded only when you open this tab.")))
        self.gallery_list = QListWidget()
        self.gallery_list.setViewMode(QListWidget.IconMode)
        self.gallery_list.setIconSize(QSize(64, 64))
        self.gallery_list.setGridSize(QSize(120, 110))
        self.gallery_list.setResizeMode(QListWidget.Adjust)
        self.gallery_list.setMovement(QListWidget.Static)
        self.gallery_list.itemDoubleClicked.connect(lambda _: self._gallery_import())
        lay.addWidget(self.gallery_list, 1)
        self.gallery_status = QLabel()
        self.gallery_status.setObjectName("muted")
        lay.addWidget(self.gallery_status)
        row = QHBoxLayout()
        b = QPushButton(icon("gallery"), tr("Import"))
        b.clicked.connect(self._gallery_import)
        row.addWidget(b)
        b = QPushButton(tr("Refresh"))
        b.clicked.connect(self._gallery_refresh)
        row.addWidget(b)
        row.addStretch()
        lay.addLayout(row)
        self.gallery = sharing.Gallery(os.path.join(config.CONFIG_DIR, "gallery_cache.json"))
        self.gallery.loaded.connect(self._gallery_loaded)
        self.gallery_entries = []
        return page

    def _gallery_refresh(self):
        try:
            os.remove(self.gallery.cache_path)
        except OSError:
            pass
        self.gallery_status.setText(tr("Loading..."))
        self.gallery.fetch()

    def _gallery_loaded(self, entries, error):
        self.gallery_entries = entries
        self.gallery_list.clear()
        for e in entries:
            it = QListWidgetItem(self.thumbnail(import_code(e["code"])), e["name"])
            it.setToolTip(f"{e['name']}  -  {e['author']}\n{', '.join(e['tags'])}")
            self.gallery_list.addItem(it)
        self.gallery_status.setText(error or f"{len(entries)} {tr('crosshairs')}")

    def _gallery_import(self):
        row = self.gallery_list.currentRow()
        if 0 <= row < len(self.gallery_entries):
            e = self.gallery_entries[row]
            self.confirm_import(e["code"], f"{e['name']}  -  {e['author']}")

    # ---------- QR ----------
    def _show_qr(self):
        code = export_code(self.target("cross"))
        img = sharing.qr_image(code)
        dlg = QDialog(self)
        dlg.setWindowTitle(tr("Share code QR"))
        v = QVBoxLayout(dlg)
        pic = QLabel()
        pic.setPixmap(QPixmap.fromImage(img))
        v.addWidget(pic, 0, Qt.AlignCenter)
        text = QLabel(code)
        text.setWordWrap(True)
        text.setTextInteractionFlags(Qt.TextSelectableByMouse)
        v.addWidget(text)
        save = QPushButton(tr("Save QR as PNG"))

        def do_save():
            path, _ = QFileDialog.getSaveFileName(dlg, tr("Save QR as PNG"), "crosshair_qr.png", "PNG (*.png)")
            if path and not img.save(path, "PNG"):
                QMessageBox.warning(dlg, tr("Save QR as PNG"), tr("Could not save the file."))

        save.clicked.connect(do_save)
        v.addWidget(save)
        dlg.exec()

    # ---------- export / import ----------
    def _export_all(self):
        path, _ = QFileDialog.getSaveFileName(self, tr("Export all"), "crosshair_backup.json", "JSON (*.json)")
        if not path:
            return
        lib = library.load()
        images = {}
        for img_path in [p["png_path"] for p in self.cfg["profiles"].values()] + [e["image"] for e in lib]:
            if img_path and img_path not in images and os.path.isfile(img_path):
                with open(img_path, "rb") as f:
                    images[img_path] = base64.b64encode(f.read()).decode("ascii")
        data = {"format": "nullpoint-export", "version": 1, "config": self.cfg, "library": lib,
                "images": images}
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=1)
            self.say(f"{tr('Exported')}: {os.path.basename(path)}")
        except OSError as e:
            self.say(f"{tr('Export failed')}: {e}", True)

    def _import_all(self):
        path, _ = QFileDialog.getOpenFileName(self, tr("Import"), "", "JSON (*.json)")
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict) or data.get("format") not in ("nullpoint-export", "crosshair-overlay-export") \
                    or not isinstance(data.get("config"), dict):
                raise ValueError(tr("not a Nullpoint export file"))
            images = data.get("images") if isinstance(data.get("images"), dict) else {}
            lib = data.get("library") if isinstance(data.get("library"), list) else []
        except (OSError, ValueError) as e:
            self.say(f"{tr('Import failed')}: {e}", True)
            return
        box = QMessageBox(self)
        box.setWindowTitle(tr("Import"))
        box.setText(tr("Merge with your current profiles, or replace everything?"))
        merge_btn = box.addButton(tr("Merge"), QMessageBox.AcceptRole)
        replace_btn = box.addButton(tr("Replace"), QMessageBox.DestructiveRole)
        box.addButton(QMessageBox.Cancel)
        box.exec()
        if box.clickedButton() not in (merge_btn, replace_btn):
            return
        # Embedded images -> custom\imported\, then point profiles/library at the new copies.
        moved = {}
        out_dir = os.path.join(library.CUSTOM_DIR, "imported")
        for old, b64 in images.items():
            try:
                raw = base64.b64decode(b64, validate=True)
            except (ValueError, TypeError):
                continue
            name = os.path.basename(str(old)) or "image.png"
            if os.path.splitext(name)[1].lower() not in (".png", ".gif", ".svg"):
                continue  # only image files, never anything runnable
            os.makedirs(out_dir, exist_ok=True)
            new = os.path.join(out_dir, name)
            stem, ext = os.path.splitext(new)
            n = 2
            while os.path.exists(new):
                new, n = f"{stem}_{n}{ext}", n + 1
            with open(new, "wb") as f:
                f.write(raw)
            moved[old] = new
        new_cfg = config.normalize(data["config"])
        for p in new_cfg["profiles"].values():
            p["png_path"] = moved.get(p["png_path"], p["png_path"])
        entries = library.clean(lib)
        for e in entries:
            e["image"] = moved.get(e["image"], e["image"])
        self.record()
        if box.clickedButton() is replace_btn:
            self.cfg.clear()
            self.cfg.update(new_cfg)
            library.save(entries)
        else:
            self.cfg["profiles"].update(new_cfg["profiles"])
            self.cfg["games"].update(new_cfg["games"])
            library.save(library.load() + entries)
        for kind in ("profile", "hotkeys", "general"):
            self.on_change(kind)
        self.refresh()
        self.load_library()
        self.say(tr("Import done."))

    def _app_tab(self):
        page = QWidget()
        f = QFormLayout(page)
        only = QCheckBox()
        only.setChecked(self.cfg["show_only_in_games"])
        only.toggled.connect(lambda v: self._set_cfg("show_only_in_games", v))
        f.addRow(tr("Hide when game isn't focused"), only)
        fs = QComboBox()
        fs.addItems(["Auto", "Borderless", "Exclusive"])
        fs.setCurrentText(self.cfg["fullscreen_mode"])
        fs.currentTextChanged.connect(lambda t: self._set_cfg("fullscreen_mode", t))
        f.addRow(tr("Fullscreen mode"), fs)
        f.addRow(QLabel(tr("Exclusive fullscreen can't be drawn over by any normal window. "
                           "Use Windowed Fullscreen / Borderless in the game.")))
        for key, label in (("toggle", "Toggle overlay hotkey"), ("settings", "Open settings hotkey"),
                           ("switcher", "Quick switcher hotkey"), ("nudge", "Nudge mode hotkey")):
            ed = QKeySequenceEdit(QKeySequence(self.cfg["hotkeys"][key]))
            ed.setMaximumSequenceLength(1)
            if key == "nudge":
                ed.setClearButtonEnabled(True)
                ed.setToolTip(tr("In game: arrow keys move the crosshair 1 px (Shift: 5 px), Esc to finish. Empty = off."))
            ed.editingFinished.connect(lambda k=key, e=ed: self._set_hotkey(k, e))
            f.addRow(tr(label), ed)
        for key, label, ic in (("hold_hide", "Hide while held", "hide"), ("cheat", "Hotkey cheat sheet (hold)", "keyboard")):
            box = QComboBox()
            box.setEditable(True)
            box.addItems(HOLD_CHOICES)
            box.setCurrentText(self.cfg["hotkeys"].get(key, ""))
            box.setAccessibleName(tr(label))
            box.lineEdit().editingFinished.connect(lambda k=key, b=box: self._set_hold_key(k, b.currentText()))
            box.activated.connect(lambda _i, k=key, b=box: self._set_hold_key(k, b.currentText()))
            pic = QLabel()
            pic.setPixmap(icon(ic).pixmap(16, 16))
            row = QHBoxLayout()
            row.addWidget(pic)
            row.addWidget(box, 1)
            f.addRow(tr(label), row)
        f.addRow(QLabel(tr("Held keys: empty = off. Mouse2-5, Shift, Ctrl, Alt, F1-F24, A-Z, 0-9. "
                           "The game still gets the key.")))
        start = QCheckBox()
        start.setChecked(startup_enabled())
        start.toggled.connect(self._set_startup)
        f.addRow(tr("Start with Windows"), start)
        delay = QSpinBox()
        delay.setRange(0, 120)
        delay.setSuffix(" s")
        delay.setValue(self.cfg["startup_delay"])
        delay.setToolTip(tr("When started with Windows, wait this long before showing the crosshair."))
        delay.valueChanged.connect(lambda v: self._set_cfg("startup_delay", v))
        f.addRow(tr("Startup delay"), delay)
        for key, label, ic, kind in (("register_links", "Handle nullpoint:// links", "link", "links"),
                                     ("discord_rpc", "Discord Rich Presence", "presence", "sharing")):
            cb = QCheckBox()
            cb.setChecked(self.cfg[key])
            cb.setAccessibleName(tr(label))
            cb.toggled.connect(lambda v, k=key, kd=kind: self._set_cfg(k, v, kd))
            pic = QLabel()
            pic.setPixmap(icon(ic).pixmap(16, 16))
            row = QHBoxLayout()
            row.addWidget(pic)
            row.addWidget(cb, 1)
            f.addRow(tr(label), row)
        did = QLineEdit(self.cfg["discord_client_id"])
        did.setPlaceholderText(tr("Discord application ID (numbers)"))
        did.editingFinished.connect(lambda: self._set_cfg("discord_client_id", did.text().strip(), "sharing"))
        f.addRow(tr("Discord client ID"), did)
        sp = self.cfg["stream_page"]
        on = QCheckBox()
        on.setChecked(sp["on"])
        port = QSpinBox()
        port.setRange(1024, 65535)
        port.setValue(int(sp["port"]))
        url = QLabel()
        url.setTextInteractionFlags(Qt.TextSelectableByMouse)
        url.setText(f"http://127.0.0.1:{sp['port']}/")

        def stream_changed():
            self.cfg["stream_page"] = {"on": on.isChecked(), "port": port.value()}
            url.setText(f"http://127.0.0.1:{port.value()}/")
            self.on_change("sharing")

        on.toggled.connect(lambda _: stream_changed())
        port.editingFinished.connect(stream_changed)
        row = QHBoxLayout()
        pic = QLabel()
        pic.setPixmap(icon("stream").pixmap(16, 16))
        for w in (pic, on, QLabel(tr("Port")), port, url):
            row.addWidget(w)
        row.addStretch()
        f.addRow(tr("Stream page (OBS browser source)"), row)
        f.addRow(QLabel(tr("Local only (127.0.0.1). Add the URL as a Browser Source in OBS / Streamlabs.")))
        lp = QComboBox()
        for val in ("Auto", "On", "Off"):
            lp.addItem(tr(val), val)
        lp.setCurrentIndex(max(0, lp.findData(self.cfg["low_power"])))
        lp.currentIndexChanged.connect(lambda i: self._set_cfg("low_power", lp.itemData(i), "power"))
        row = QHBoxLayout()
        pic = QLabel()
        pic.setPixmap(icon("battery").pixmap(16, 16))
        row.addWidget(pic)
        row.addWidget(lp, 1)
        f.addRow(tr("Low-power mode"), row)
        f.addRow(QLabel(tr("Auto = on battery: slower game detection, rainbow / GIF animation paused.")))
        rm = QCheckBox(tr("Reduce motion"))
        rm.setChecked(self.cfg["reduce_motion"])
        rm.setToolTip(tr("Turns off rainbow, GIF playback (first frame only) and the fire expand animation."))
        rm.toggled.connect(lambda v: self._set_cfg("reduce_motion", v, "motion"))
        f.addRow(rm)
        row = QHBoxLayout()
        pic = QLabel()
        pic.setPixmap(icon("cpu").pixmap(16, 16))
        self.monitor_label = QLabel("-")
        row.addWidget(pic)
        row.addWidget(self.monitor_label, 1)
        f.addRow(tr("Nullpoint resource use"), row)
        row = QHBoxLayout()
        b = QPushButton(icon("usb"), tr("Make portable copy..."))
        b.clicked.connect(self._make_portable)
        row.addWidget(b)
        if config.PORTABLE:
            row.addWidget(QLabel(tr("Running in portable mode.")))
        row.addStretch()
        f.addRow(tr("Portable mode"), row)
        scale = QComboBox()
        for v in (100, 125, 150):
            scale.addItem(f"{v} %", v)
        scale.setCurrentIndex(max(0, scale.findData(self.cfg["ui_scale"])))
        scale.setAccessibleName(tr("UI text scale"))
        scale.currentIndexChanged.connect(lambda i: self._set_cfg("ui_scale", scale.itemData(i), "theme"))
        large = QCheckBox(tr("Large text"))
        large.setChecked(self.cfg["large_text"])
        large.toggled.connect(lambda v: self._set_cfg("large_text", v, "theme"))
        row = QHBoxLayout()
        pic = QLabel()
        pic.setPixmap(icon("accessibility").pixmap(16, 16))
        for w in (pic, scale, large):
            row.addWidget(w)
        row.addStretch()
        f.addRow(tr("UI text scale"), row)
        row = QHBoxLayout()
        for text, ic, fn in (("Run setup wizard", "wizard", self.app.run_wizard),
                             ("What's new", "changelog", lambda: onboarding.show_changelog(self, VERSION)),
                             ("Send feedback", "feedback", lambda: onboarding.open_feedback(VERSION, self.cfg["active_profile"]))):
            b = QPushButton(icon(ic), tr(text))
            b.clicked.connect(fn)
            row.addWidget(b)
        row.addStretch()
        f.addRow(tr("Help"), row)
        note = QLabel(tr("Send feedback opens a pre-filled GitHub issue in your browser: app version, Windows version "
                         "and profile name only. You review it before sending."))
        note.setWordWrap(True)
        note.setObjectName("muted")
        f.addRow(note)

        stream = QCheckBox()
        stream.setChecked(self.cfg["stream_safe"])
        stream.toggled.connect(lambda v: self._set_cfg("stream_safe", v, "stream"))
        f.addRow(tr("Hide crosshair from recordings/streams"), stream)
        f.addRow(QLabel(tr("On: you see it, OBS / Streamlabs / screenshots don't. Off: viewers see it.")))
        th = QComboBox()
        for val in ("System", "Dark", "Light"):
            th.addItem(tr(val), val)
        th.setCurrentIndex(max(0, th.findData(self.cfg["theme"])))
        th.currentIndexChanged.connect(lambda i: self._set_cfg("theme", th.itemData(i), "theme"))
        f.addRow(tr("Theme"), th)
        lang = QComboBox()
        for code, name in LANGUAGES.items():
            lang.addItem(name, code)
        lang.setCurrentIndex(max(0, lang.findData(self.cfg["language"])))
        lang.currentIndexChanged.connect(lambda i: self._set_cfg("language", lang.itemData(i), "language"))
        f.addRow(tr("Language"), lang)
        repo = QLineEdit(self.cfg["update_repo"])
        repo.setPlaceholderText("owner/repo")
        repo.editingFinished.connect(lambda: self._set_cfg("update_repo", repo.text().strip()))
        f.addRow(tr("Update check (GitHub repo)"), repo)
        f.addRow(QLabel(tr("Empty = off. Checks at most once a day and only shows a notification.")))
        b = QPushButton(tr("Alignment test"))
        b.clicked.connect(self.app.alignment_test)
        f.addRow(b)
        return page

    # ---------- actions ----------
    def refresh(self):
        """Reload every control from config (after profile switch, paste, reset)."""
        self.loading = True
        if self.variant not in self.profile()["variants"]:
            self.variant = ""
        self.profile_box.blockSignals(True)
        self.profile_box.clear()
        self.profile_box.addItems(sorted(self.cfg["profiles"], key=lambda n: (n != "Default", n.lower())))
        self.profile_box.setCurrentText(self.cfg["active_profile"])
        self.profile_box.blockSignals(False)
        self.mode_box.setCurrentIndex(MODES.index(self.target("cross")["mode"]))
        self.update_visibility()
        for load in self.loaders:
            load()
        self.games_table.setRowCount(0)
        for exe, prof in sorted(self.cfg["games"].items()):
            r = self.games_table.rowCount()
            self.games_table.insertRow(r)
            self.games_table.setItem(r, 0, QTableWidgetItem(exe))
            self.games_table.setItem(r, 1, QTableWidgetItem(prof))
        self.loading = False
        self.update_display_info()
        self.preview.update()

    # ---------- offset nudge (arrow keys in the offset fields) ----------
    def eventFilter(self, obj, e):
        if e.type() == e.Type.KeyPress and obj in getattr(self, "offset_spins", ()):
            d = {Qt.Key_Left: (-1, 0), Qt.Key_Right: (1, 0), Qt.Key_Up: (0, -1), Qt.Key_Down: (0, 1)}.get(e.key())
            if d:
                step = 5 if e.modifiers() & Qt.ShiftModifier else 1
                for sp, v in zip(self.offset_spins, d):
                    if v:
                        sp.setValue(sp.value() + v * step)
                return True
        return super().eventFilter(obj, e)

    # ---------- profile rules ----------
    def _load_rules(self):
        self.rules_list.clear()
        for r in self.cfg["rules"]:
            parts = [r["exe"]] if r["exe"] else []
            if r["title"]:
                parts.append(f'{tr("title")} {tr(r["match"])} "{r["title"]}"')
            self.rules_list.addItem(f'{" + ".join(parts)}  ->  {r["profile"]}')

    def _edit_rule(self, idx):
        rules = self.cfg["rules"]
        if idx is not None and not 0 <= idx < len(rules):
            return
        r = rules[idx] if idx is not None else {"exe": "", "title": "", "match": "contains",
                                                 "profile": self.cfg["active_profile"]}
        dlg = QDialog(self)
        dlg.setWindowTitle(tr("Profile rule"))
        form = QFormLayout(dlg)
        exe, title = QLineEdit(r["exe"]), QLineEdit(r["title"])
        exe.setMaxLength(100)
        title.setMaxLength(200)
        exe.setPlaceholderText("game.exe")
        match, prof = QComboBox(), QComboBox()
        for m in config.RULE_MATCH:
            match.addItem(tr(m), m)
        match.setCurrentIndex(max(0, match.findData(r["match"])))
        prof.addItems(sorted(self.cfg["profiles"]))
        prof.setCurrentText(r["profile"])
        for label, w in (("Program (optional)", exe), ("Window title (optional)", title), ("Match", match),
                         ("Profile", prof)):
            form.addRow(tr(label), w)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        form.addRow(bb)
        if dlg.exec() != QDialog.Accepted:
            return
        new = {"exe": exe.text().strip().lower(), "title": title.text(), "match": match.currentData(),
               "profile": prof.currentText()}
        if not (new["exe"] or new["title"]):
            self.say(tr("A rule needs a program or a window title."), True)
            return
        if new["match"] == "regex" and new["title"] and game_detect.safe_regex(new["title"]) is None:
            self.say(tr("That regex is invalid or could be very slow (nested repeats, backreferences). Max 100 characters."), True)
            return
        if idx is None:
            rules.append(new)
        else:
            rules[idx] = new
        self.cfg["rules"] = config.clean_rules(rules, self.cfg["profiles"])
        self.on_change("general")
        self._load_rules()

    def _remove_rule(self):
        i = self.rules_list.currentRow()
        if 0 <= i < len(self.cfg["rules"]):
            del self.cfg["rules"][i]
            self.on_change("general")
            self._load_rules()

    def _move_rule(self, d):
        i, rules = self.rules_list.currentRow(), self.cfg["rules"]
        if 0 <= i < len(rules) and 0 <= i + d < len(rules):
            rules[i], rules[i + d] = rules[i + d], rules[i]
            self.on_change("general")
            self._load_rules()
            self.rules_list.setCurrentRow(i + d)

    # ---------- detected installs ----------
    def _detect_games(self):
        found = installs.detect(self.cfg["games"])
        if not found:
            self.say(tr("No new games found in the Epic, Riot or Battle.net install lists."))
            return
        dlg = QDialog(self)
        dlg.setWindowTitle(tr("Detected games"))
        lay = QVBoxLayout(dlg)
        lst = QListWidget()
        for g in found:
            it = QListWidgetItem(f'{g["name"]}  ({g["exe"]}, {g["source"]})')
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Checked)
            lst.addItem(it)
        lay.addWidget(lst)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText(tr("Create profiles"))
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        lay.addWidget(bb)
        if dlg.exec() != QDialog.Accepted:
            return
        made = []
        for i, g in enumerate(found):
            if lst.item(i).checkState() != Qt.Checked:
                continue
            name = g["name"]
            n = 2
            while name in self.cfg["profiles"] and self.cfg["games"].get(g["exe"]) != name:
                name, n = f'{g["name"]} {n}', n + 1
            self.cfg["profiles"].setdefault(name, copy.deepcopy(self.cfg["profiles"]["Default"]))
            self.cfg["games"][g["exe"]] = name
            made.append(name)
        self.on_change("general")
        self.refresh()
        self.say(f"{tr('Profiles created')}: {', '.join(made)}" if made else tr("Nothing selected."))

    # ---------- resolution variants ----------
    def _load_variants(self):
        self.variant_box.blockSignals(True)
        self.variant_box.clear()
        self.variant_box.addItem(tr("Default crosshair"), "")
        for k in sorted(self.profile()["variants"]):
            self.variant_box.addItem(k, k)
        self.variant_box.setCurrentIndex(max(0, self.variant_box.findData(self.variant)))
        self.variant_box.blockSignals(False)
        cur = self.app.game_res or "-"
        self.res_label.setText(f"{tr('Current game window')}: {cur}")

    def _pick_variant(self, i):
        self.variant = self.variant_box.itemData(i) or ""
        self.refresh()
        if self.variant:
            self.say(f"{tr('Editing the variant for')} {self.variant}")

    def _add_variant(self, res):
        if not res:
            res, ok = QInputDialog.getText(self, tr("Add size..."), tr("Game window size (e.g. 1440x1080):"))
            if not ok:
                return
            res = res.strip().lower().replace(" ", "")
        p = self.profile()
        if not config.RES_KEY.fullmatch(res or ""):
            self.say(tr("Use WIDTHxHEIGHT, e.g. 1920x1080 (start a game first to use its size)."), True)
            return
        if res not in p["variants"] and len(p["variants"]) >= config.MAX_VARIANTS:
            self.say(tr("A profile can have up to 8 variants."), True)
            return
        self.record()
        p["variants"].setdefault(res, copy.deepcopy(p["crosshair"]))
        self.variant = res
        self.on_change("crosshair")
        self.refresh()

    def _remove_variant(self):
        p = self.profile()
        if self.variant in p["variants"]:
            self.record()
            del p["variants"][self.variant]
            self.variant = ""
            self.on_change("crosshair")
            self.refresh()

    def _pick_profile(self, name):
        if name and name in self.cfg["profiles"] and name != self.cfg["active_profile"]:
            self.cfg["active_profile"] = name
            self.on_change("profile")
            self.refresh()

    def _pick_mode(self, idx):
        if not self.loading:
            self.record()
            self.target("cross")["mode"] = MODES[idx]
            self.on_change("crosshair")
            self.refresh()

    def _set_color(self, text, quiet=False):
        h = text.strip().lstrip("#").upper()
        if re.fullmatch(r"[0-9A-F]{6}", h):
            if h != self.target("cross")["color"]:
                self.record("color")
                self.target("cross")["color"] = h
                self.on_change("crosshair")
                self.preview.update()
            if not quiet:
                self.hex_edit.setText("#" + h)
        elif not quiet:
            self.say(tr("Color must be #RRGGBB hex, e.g. #00FFFF."), True)

    def _browse_png(self):
        path, _ = QFileDialog.getOpenFileName(self, tr("Choose crosshair image"), "", "Images (*.png *.gif *.svg)")
        if path:
            self.record()
            self.profile()["png_path"] = path
            self.on_change("crosshair")
            if self.ov.pixmap is None:
                self.say(tr("Could not load that image."), True)
            self.refresh()

    def apply_image(self, path):
        """Editor 'Save + Apply': exact pixels = 100% scale, no rotation."""
        self.record()
        p = self.profile()
        p["png_path"] = path
        self.target("cross")["mode"] = "png"
        self.target("png").update(scale=100, rot=0)
        self.on_change("crosshair")
        self.refresh()
        self.say(f"{tr('Applied')}: {os.path.basename(path)} ({self.cfg['active_profile']})")

    def _copy_code(self):
        QGuiApplication.clipboard().setText(export_code(self.target("cross")))
        self.say(tr("Code copied to clipboard."))

    def _paste_code(self):
        try:
            cross, kind = valorant.import_any(QGuiApplication.clipboard().text(), self.val_scale(), self.screen_h())
        except ShareCodeError as e:
            self.say(f"{tr('Invalid code')}: {e}", True)
            return
        self.record()
        self.set_cross(cross)
        self.on_change("crosshair")
        self.refresh()
        msg = f"{tr('Code applied to profile')}: {self.cfg['active_profile']}"
        if kind in ("valorant", "cs2"):
            msg += ". " + tr("Converted from VALORANT" if kind == "valorant" else "Converted from CS2")
        if cross["mode"] == "png":
            msg += ". " + tr("Image codes hold settings only - pick the image on the Image tab.")
        self.say(msg)

    def _add_game(self, exe):
        exe = os.path.basename(exe.strip()).lower()
        if not exe:
            return
        if not exe.endswith(".exe"):
            exe += ".exe"
        default = self.cfg["games"].get(exe) or os.path.splitext(exe)[0].split("-")[0].capitalize()
        name, ok = QInputDialog.getText(self, tr("Profile"), f"{tr('Profile name for')} {exe}\n"
                                        + tr("(existing name = share that profile):"), text=default)
        name = name.strip()
        if not ok or not name:
            return
        if name not in self.cfg["profiles"]:
            self.cfg["profiles"][name] = copy.deepcopy(config.DEFAULT_PROFILE)
        self.cfg["games"][exe] = name
        self.on_change("general")
        self.refresh()

    def _add_game_browse(self):
        path, _ = QFileDialog.getOpenFileName(self, tr("Choose game .exe"), "", "Programs (*.exe)")
        if path:
            self._add_game(path)

    def _add_game_name(self):
        name, ok = QInputDialog.getText(self, tr("Add game"), tr("Process name (e.g. cs2.exe):"))
        if ok:
            self._add_game(name)

    def _remove_game(self):
        row = self.games_table.currentRow()
        if row >= 0:
            # Profile is kept (it may hold a crosshair you want); only the game link is removed.
            self.cfg["games"].pop(self.games_table.item(row, 0).text(), None)
            self.on_change("general")
            self.refresh()

    def _copy_to(self):
        """Copy the active profile's crosshair + position settings onto other profiles."""
        src = self.cfg["active_profile"]
        dlg = QDialog(self)
        dlg.setWindowTitle(tr("Copy to..."))
        dlg.setWindowIcon(icon("copy_to"))
        v = QVBoxLayout(dlg)
        v.addWidget(QLabel(f"{tr('Copy crosshair and position from')} '{src}' {tr('to')}:"))
        lst = QListWidget()
        for name in sorted(self.cfg["profiles"]):
            if name != src:
                it = QListWidgetItem(name)
                it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
                it.setCheckState(Qt.Unchecked)
                lst.addItem(it)
        v.addWidget(lst)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        v.addWidget(bb)
        if dlg.exec() != QDialog.Accepted:
            return
        targets = [lst.item(i).text() for i in range(lst.count()) if lst.item(i).checkState() == Qt.Checked]
        self.copy_profile(src, targets)

    def copy_profile(self, src, targets):
        p = self.cfg["profiles"][src]
        for name in targets:
            for k in ("crosshair", "png_path", "offset_x", "offset_y", "monitor", "stretch", "anim_paused"):
                self.cfg["profiles"][name][k] = copy.deepcopy(p[k])
        self.on_change("general")
        self.say(f"{tr('Copied to')}: {', '.join(targets) or '-'}")

    def _rename_profile(self):
        old = self.cfg["active_profile"]
        if old == "Default":
            self.say(tr("The Default profile can't be renamed."), True)
            return
        new, ok = QInputDialog.getText(self, tr("Rename profile"), tr("New name:"), text=old)
        new = new.strip()
        if not ok or not new or new == old:
            return
        if new in self.cfg["profiles"]:
            self.say(tr("A profile with that name already exists."), True)
            return
        self.cfg["profiles"][new] = self.cfg["profiles"].pop(old)
        self.cfg["games"] = {exe: (new if p == old else p) for exe, p in self.cfg["games"].items()}
        self.cfg["active_profile"] = new
        self.on_change("general")
        self.refresh()

    def _set_cfg(self, key, val, kind="general"):
        self.cfg[key] = val
        self.on_change(kind)

    def _set_hotkey(self, key, edit):
        seq = edit.keySequence().toString()
        if (seq or key == "nudge") and seq != self.cfg["hotkeys"][key]:
            self.cfg["hotkeys"][key] = seq
            self.on_change("hotkeys")

    def update_monitor(self):
        import psutil
        proc = getattr(self, "_proc", None) or psutil.Process()
        self._proc = proc
        cpu = proc.cpu_percent(None) / (psutil.cpu_count() or 1)  # first call returns 0, then since last call
        self.monitor_label.setText(f"CPU {cpu:.1f} %   RAM {proc.memory_info().rss / 1048576:.0f} MB")

    def _make_portable(self):
        exe = tools.current_exe()
        if not exe:
            self.say(tr("Build Nullpoint.exe first (build.bat), then make a portable copy."), True)
            return
        dest = QFileDialog.getExistingDirectory(self, tr("Choose an empty folder or USB drive"))
        if not dest:
            return
        dest = os.path.join(dest, "Nullpoint")
        try:
            config.save(self.cfg)
            tools.make_portable(dest, exe, config.CONFIG_DIR)
            self.say(f"{tr('Portable copy created')}: {dest}")
        except OSError as e:
            self.say(f"{tr('Could not create the portable copy')}: {e}", True)

    def _set_hold_key(self, key, text):
        text = text.strip()
        if text and hold_vk(text) is None:
            self.say(f"{tr('Unknown key')}: {text}", True)
            return
        self.cfg["hotkeys"][key] = text
        self.on_change("general")

    def _set_startup(self, on):
        try:
            set_startup(on)
        except OSError as e:
            self.say(f"{tr('Could not change startup setting')}: {e}", True)

    def closeEvent(self, e):
        e.ignore()
        self.hide()  # app keeps running in the tray
