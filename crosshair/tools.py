"""Tools tab: eDPI calculator. Battery check for low-power mode. Portable copy helper."""
import ctypes
import os
import shutil
import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QComboBox, QDoubleSpinBox, QFormLayout, QGroupBox, QHBoxLayout, QInputDialog,
                               QLabel, QListWidget, QPushButton, QSpinBox, QVBoxLayout, QWidget)

from ui.i18n import tr
from ui.icons import icon

# Typical pro eDPI ranges (DPI x in-game sensitivity) and the game's sensitivity scale vs VALORANT.
GAMES = {"VALORANT": (200, 400, 1.0), "CS2": (600, 1200, 3.181818), "Fortnite": (30, 70, None)}


class SYSTEM_POWER_STATUS(ctypes.Structure):
    _fields_ = [("ACLineStatus", ctypes.c_ubyte), ("BatteryFlag", ctypes.c_ubyte),
                ("BatteryLifePercent", ctypes.c_ubyte), ("SystemStatusFlag", ctypes.c_ubyte),
                ("BatteryLifeTime", ctypes.c_ulong), ("BatteryFullLifeTime", ctypes.c_ulong)]


def on_battery():
    st = SYSTEM_POWER_STATUS()
    return bool(ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(st))) and st.ACLineStatus == 0


def edpi(dpi, sens):
    return round(dpi * sens, 2)


# Hip-fire yaw: degrees turned per mouse count at sensitivity 1.
# CS2 / Apex: Source-engine m_yaw default 0.022 (Valve Developer Community, "m_yaw"); Apex keeps Source's value.
# VALORANT 0.07 and Overwatch 2 0.0066: the values every major converter uses (CS2 -> VALORANT = / 3.18,
# CS2 -> OW2 = x 3.33), e.g. mouse-sensitivity.com, aimlabs.com, recharge.com converter articles (checked 2026-11).
# Fortnite and Roblox are left out: their sensitivity scales couldn't be verified from a reliable source.
YAW = {"CS2": 0.022, "Apex Legends": 0.022, "VALORANT": 0.07, "Overwatch 2": 0.0066}


def convert_sens(sens, src, dst):
    """Same hip-fire turn speed in another game."""
    return sens * YAW[src] / YAW[dst]


def cm_per_360(dpi, sens, game):
    """Mouse travel in cm for a full turn: 360 / (counts per inch x sens x yaw) x 2.54."""
    return 360 / (dpi * sens * YAW[game]) * 2.54


def make_portable(dest, exe, data_dir):
    """dest/Nullpoint.exe + dest/portable.txt + dest/data (copy of the current settings)."""
    os.makedirs(dest, exist_ok=True)
    shutil.copy2(exe, os.path.join(dest, "Nullpoint.exe"))
    with open(os.path.join(dest, "portable.txt"), "w", encoding="utf-8") as f:
        f.write("Nullpoint portable mode: settings live in the 'data' folder next to Nullpoint.exe.\n")
    if os.path.isdir(data_dir):
        shutil.copytree(data_dir, os.path.join(dest, "data"), dirs_exist_ok=True)


def current_exe():
    """The .exe to copy for a portable folder, or None when running from source without a build."""
    if getattr(sys, "frozen", False):
        return sys.executable
    built = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dist", "Nullpoint.exe")
    return built if os.path.exists(built) else None


class ToolsTab(QWidget):
    def __init__(self, cfg, on_change):
        super().__init__()
        self.cfg, self.on_change = cfg, on_change
        lay = QVBoxLayout(self)
        g = QGroupBox(tr("eDPI calculator"))
        f = QFormLayout(g)
        pic = QLabel()
        pic.setPixmap(icon("calculator").pixmap(18, 18))
        note = QLabel(tr("eDPI = mouse DPI x in-game sensitivity. Same eDPI = same aim speed."))
        note.setObjectName("muted")
        f.addRow(pic, note)
        self.game = QComboBox()
        self.game.addItems(list(GAMES))
        self.dpi = QSpinBox()
        self.dpi.setRange(100, 32000)
        self.dpi.setValue(800)
        self.sens = QDoubleSpinBox()
        self.sens.setDecimals(3)
        self.sens.setRange(0.001, 100)
        self.sens.setValue(0.35)
        self.result = QLabel()
        self.result.setTextInteractionFlags(Qt.TextSelectableByMouse)
        for label, w in (("Game", self.game), ("Mouse DPI", self.dpi), ("In-game sensitivity", self.sens),
                         ("Result", self.result)):
            w.setAccessibleName(tr(label))
            f.addRow(tr(label), w)
        for w in (self.game, self.dpi, self.sens):
            (w.currentIndexChanged if w is self.game else w.valueChanged).connect(self.update_result)
        row = QHBoxLayout()
        b = QPushButton(tr("Save result..."))
        b.clicked.connect(self.save_result)
        row.addWidget(b)
        b = QPushButton(tr("Delete"))
        b.clicked.connect(self.delete_result)
        row.addWidget(b)
        row.addStretch()
        f.addRow(row)
        self.saved = QListWidget()
        self.saved.setAccessibleName(tr("Saved results"))
        self.saved.itemDoubleClicked.connect(self.load_result)
        f.addRow(tr("Saved results"), self.saved)
        lay.addWidget(g)

        g = QGroupBox(tr("Sensitivity converter"))
        f = QFormLayout(g)
        self.src, self.dst = QComboBox(), QComboBox()
        for box in (self.src, self.dst):
            box.addItems(list(YAW))
        self.dst.setCurrentText("VALORANT")
        self.csens = QDoubleSpinBox()
        self.csens.setDecimals(4)
        self.csens.setRange(0.0001, 1000)
        self.csens.setValue(1.0)
        self.cdpi = QSpinBox()
        self.cdpi.setRange(100, 32000)
        self.cdpi.setValue(800)
        self.cresult = QLabel()
        self.cresult.setTextInteractionFlags(Qt.TextSelectableByMouse)
        for label, w in (("From game", self.src), ("Sensitivity", self.csens), ("To game", self.dst),
                         ("Mouse DPI", self.cdpi), ("Result", self.cresult)):
            w.setAccessibleName(tr(label))
            f.addRow(tr(label), w)
        for w in (self.src, self.dst):
            w.currentIndexChanged.connect(self.update_convert)
        for w in (self.csens, self.cdpi):
            w.valueChanged.connect(self.update_convert)
        note = QLabel(tr("Hip-fire only (scoped / ADS sensitivity differs). Fortnite and Roblox aren't included."))
        note.setObjectName("muted")
        note.setWordWrap(True)
        f.addRow(note)
        lay.addWidget(g)
        lay.addStretch()
        self.update_convert()
        self.refresh_saved()
        self.update_result()

    def update_result(self, *_):
        game = self.game.currentText()
        lo, hi, scale = GAMES[game]
        value = edpi(self.dpi.value(), self.sens.value())
        text = f"eDPI {value:g}   ({tr('typical pro range')} {lo}-{hi})"
        if scale:  # VALORANT <-> CS2 sensitivities differ by a fixed factor
            other, factor = ("CS2", 3.181818) if game == "VALORANT" else ("VALORANT", 1 / 3.181818)
            text += f"\n{tr('Same speed in')} {other}: {self.sens.value() * factor:.3f}"
        self.result.setText(text)

    def update_convert(self, *_):
        src, dst, sens, dpi = self.src.currentText(), self.dst.currentText(), self.csens.value(), self.cdpi.value()
        out = convert_sens(sens, src, dst)
        self.cresult.setText(f"{dst}: {out:.4f}\n{tr('cm per 360')}: {cm_per_360(dpi, sens, src):.1f} cm")

    def refresh_saved(self):
        self.saved.clear()
        for r in self.cfg["edpi_saved"]:
            self.saved.addItem(f"{r['name']}  -  {r['game']}  {r['dpi']} DPI x {r['sens']:g} = {edpi(r['dpi'], r['sens']):g}")

    def save_result(self):
        name, ok = QInputDialog.getText(self, tr("Save result..."), tr("Name:"), text=self.game.currentText())
        if ok and name.strip():
            self.cfg["edpi_saved"] = (self.cfg["edpi_saved"] + [{"name": name.strip()[:30], "game": self.game.currentText(),
                                                                 "dpi": self.dpi.value(), "sens": self.sens.value()}])[-10:]
            self.on_change("general")
            self.refresh_saved()

    def delete_result(self):
        row = self.saved.currentRow()
        if 0 <= row < len(self.cfg["edpi_saved"]):
            del self.cfg["edpi_saved"][row]
            self.on_change("general")
            self.refresh_saved()

    def load_result(self, _item):
        r = self.cfg["edpi_saved"][self.saved.currentRow()]
        self.game.setCurrentText(r["game"])
        self.dpi.setValue(r["dpi"])
        self.sens.setValue(r["sens"])
